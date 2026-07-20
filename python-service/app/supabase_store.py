import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings
from .results_store import build_results_snapshot
from .schemas import BotCatalogItem, CandleSnapshot, DecisionRequest, DecisionResponse, MarketChartResponse, ResultsResponse, TradeResult


class SupabaseStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_results_configured:
            raise RuntimeError("Supabase results store is not configured")
        self.base_url = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or ""

    def _request(self, path: str, *, method: str = "GET", payload: object | None = None, prefer: str | None = None) -> object:
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, default=str).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer
        request = Request(f"{self.base_url}/rest/v1/{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as error:
            raise RuntimeError(f"Supabase request failed with status {error.code}") from error
        except URLError as error:
            raise RuntimeError("Supabase request could not be completed") from error
        return json.loads(response_body) if response_body else None

    def list_bots(self) -> list[BotCatalogItem]:
        rows = self._request("bots?select=id,name,description,strategy_profile,strategy_description,symbol,timeframe&order=id")
        return [BotCatalogItem.model_validate(row) for row in rows if isinstance(row, dict)]

    def load_results(self, bot_id: str) -> ResultsResponse:
        query = urlencode({"bot_id": f"eq.{bot_id}", "select": "*", "order": "closed_at_utc.desc.nullslast"})
        rows = self._request(f"trade_results?{query}")
        return build_results_snapshot(rows if isinstance(rows, list) else [], f"supabase:trade_results:{bot_id}")

    def upsert_trade(self, bot_id: str, trade: TradeResult) -> None:
        payload = trade.model_dump(mode="json")
        payload["bot_id"] = bot_id
        payload["raw_payload"] = trade.model_dump(mode="json")
        self._request(
            "trade_results?on_conflict=bot_id,trade_id",
            method="POST",
            payload=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def upsert_candles(self, bot_id: str, symbol: str, timeframe: str, candles: list[CandleSnapshot]) -> None:
        if not candles:
            return
        payload = [
            {
                "bot_id": bot_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp_utc": candle.timestamp_utc.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]
        for start in range(0, len(payload), 1000):
            self._request("market_candles?on_conflict=bot_id,symbol,timeframe,timestamp_utc", method="POST", payload=payload[start:start + 1000], prefer="resolution=merge-duplicates,return=minimal")

    def advance_paper_trades(self, bot_id: str, candles: list[CandleSnapshot]) -> None:
        if not candles:
            return
        candle = candles[-1]
        rows = self._request(f"paper_trades?bot_id=eq.{bot_id}&status=eq.open&select=*")
        for trade in rows if isinstance(rows, list) else []:
            buy = trade["side"] == "buy"
            stop = float(trade["stop_price"])
            entry = float(trade["entry_price"])
            partial = float(trade["partial_price"])
            target = float(trade["target_price"])
            patch: dict[str, object] = {}
            # Conservative intrabar rule: a stop has precedence over all targets.
            stopped = candle.low <= stop if buy else candle.high >= stop
            if stopped:
                patch = {"status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": 0.5 if trade["partial_hit"] else -1}
            elif not trade["partial_hit"] and (candle.high >= partial if buy else candle.low <= partial):
                patch = {"partial_hit": True, "stop_price": entry}
            elif trade["partial_hit"] and (candle.high >= target if buy else candle.low <= target):
                patch = {"status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": 1.5}
            if patch:
                self._request(f"paper_trades?signal_key=eq.{trade['signal_key']}", method="PATCH", payload=patch, prefer="return=minimal")

    def record_shadow_signal(self, payload: DecisionRequest, response: DecisionResponse) -> None:
        if not payload.bot_id or not payload.candles or response.entry_price is None or response.stop_loss_price is None:
            return
        setup = str(response.metadata.get("setup_type", "fimath"))
        signal_key = f"{payload.bot_id}:{payload.timeframe}:{payload.candles[-1].timestamp_utc.isoformat()}:{response.action.value}:{setup}"
        self._request("strategy_signals?on_conflict=signal_key", method="POST", payload={"signal_key": signal_key, "bot_id": payload.bot_id, "payload": payload.model_dump(mode="json"), "response": response.model_dump(mode="json")}, prefer="resolution=merge-duplicates,return=minimal")
        self._request("paper_trades?on_conflict=signal_key", method="POST", payload={
            "signal_key": signal_key, "bot_id": payload.bot_id, "side": str(response.metadata.get("suggested_action", "buy")),
            "entry_price": response.entry_price, "initial_stop_price": response.stop_loss_price, "stop_price": response.stop_loss_price,
            "partial_price": response.partial_take_profit_price, "target_price": response.final_take_profit_price,
            "opened_at_utc": payload.timestamp_utc.isoformat(),
        }, prefer="resolution=ignore-duplicates,return=minimal")

    def closed_paper_trade_count(self, bot_id: str) -> int:
        rows = self._request(f"paper_trades?bot_id=eq.{bot_id}&status=eq.closed&select=signal_key")
        return len(rows) if isinstance(rows, list) else 0

    def load_chart(self, bot: BotCatalogItem, limit: int = 50000) -> MarketChartResponse:
        candle_rows: list[object] = []
        for offset in range(0, limit, 1000):
            query = urlencode({"bot_id": f"eq.{bot.id}", "symbol": f"eq.{bot.symbol}", "timeframe": f"eq.{bot.timeframe}", "select": "timestamp_utc,open,high,low,close,volume", "order": "timestamp_utc.desc", "limit": "1000", "offset": str(offset)})
            page = self._request(f"market_candles?{query}")
            if not isinstance(page, list) or not page:
                break
            candle_rows.extend(page)
            if len(page) < 1000:
                break
        candles = [CandleSnapshot.model_validate(row) for row in reversed(candle_rows)]
        trades_query = urlencode(
            {
                "bot_id": f"eq.{bot.id}",
                "symbol": f"eq.{bot.symbol}",
                "select": "*",
                "order": "opened_at_utc.desc",
                "limit": "100",
            }
        )
        trade_rows = self._request(f"trade_results?{trades_query}")
        trades = [TradeResult.model_validate(row) for row in trade_rows if isinstance(row, dict)] if isinstance(trade_rows, list) else []
        return MarketChartResponse(bot_id=bot.id, symbol=bot.symbol, timeframe=bot.timeframe, candles=candles, trades=trades)
