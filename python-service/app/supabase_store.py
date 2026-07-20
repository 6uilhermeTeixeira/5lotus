import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings
from .results_store import build_results_snapshot
from .schemas import BotCatalogItem, CandleSnapshot, MarketChartResponse, ResultsResponse, TradeResult


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
        self._request(
            "market_candles?on_conflict=bot_id,symbol,timeframe,timestamp_utc",
            method="POST",
            payload=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def load_chart(self, bot: BotCatalogItem, limit: int = 180) -> MarketChartResponse:
        candles_query = urlencode(
            {
                "bot_id": f"eq.{bot.id}",
                "symbol": f"eq.{bot.symbol}",
                "timeframe": f"eq.{bot.timeframe}",
                "select": "timestamp_utc,open,high,low,close,volume",
                "order": "timestamp_utc.desc",
                "limit": str(limit),
            }
        )
        candle_rows = self._request(f"market_candles?{candles_query}")
        candles = [CandleSnapshot.model_validate(row) for row in reversed(candle_rows if isinstance(candle_rows, list) else [])]
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
