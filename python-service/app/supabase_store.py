import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adaptive import ADAPTIVE_COMPONENTS, ADAPTIVE_WINDOW_DAYS, summarize_outcomes, utc_day_start
from .config import Settings
from .results_store import build_results_snapshot
from .schemas import BotCatalogItem, CandleSnapshot, DecisionRequest, DecisionResponse, HistoricalReplayResponse, MarketChartResponse, ResultsResponse, TradeResult


class SupabaseStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_results_configured:
            raise RuntimeError("Supabase results store is not configured")
        self.base_url = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or ""
        self.settings = settings

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

    def list_bots(self, active: bool | None = True) -> list[BotCatalogItem]:
        active_filter = "" if active is None else f"active=eq.{str(active).lower()}&"
        rows = self._request(f"bots?{active_filter}select=id,name,description,strategy_profile,strategy_description,symbol,timeframe,active&order=id")
        return [BotCatalogItem.model_validate(row) for row in rows if isinstance(row, dict)]

    def load_results(self, bot_id: str) -> ResultsResponse:
        query = urlencode({"bot_id": f"eq.{bot_id}", "select": "*", "order": "closed_at_utc.desc.nullslast"})
        rows = self._request(f"trade_results?{query}")
        real_trades = rows if isinstance(rows, list) else []
        return build_results_snapshot(real_trades + self._load_paper_results(bot_id), f"supabase:trades:{bot_id}")

    def save_backtest_snapshot(self, replay: HistoricalReplayResponse, period_days: int) -> None:
        compact_payload = replay.model_dump(mode="json")
        compact_payload["candles"] = []
        self._request(
            "backtest_snapshots?on_conflict=bot_id,period_days",
            method="POST",
            payload={
                "bot_id": replay.bot_id,
                "period_days": period_days,
                "period_start_utc": replay.period_start_utc.isoformat(),
                "period_end_utc": replay.period_end_utc.isoformat(),
                "payload": compact_payload,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def load_backtest_snapshot(self, bot_id: str, period_days: int) -> HistoricalReplayResponse | None:
        query = urlencode({"bot_id": f"eq.{bot_id}", "period_days": f"eq.{period_days}", "select": "payload", "limit": "1"})
        rows = self._request(f"backtest_snapshots?{query}")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        payload = rows[0].get("payload")
        return HistoricalReplayResponse.model_validate(payload) if isinstance(payload, dict) else None

    def _load_paper_results(self, bot_id: str) -> list[dict[str, object]]:
        paper_query = urlencode(
            {
                "bot_id": f"eq.{bot_id}",
                "variant": "eq.technical",
                "select": "*",
                "order": "opened_at_utc.desc",
                "limit": "1000",
            }
        )
        signal_query = urlencode(
            {
                "bot_id": f"eq.{bot_id}",
                "select": "signal_key,response",
                "limit": "1000",
            }
        )
        paper_rows = self._request(f"paper_trades?{paper_query}")
        signal_rows = self._request(f"strategy_signals?{signal_query}")
        responses = {
            str(row["signal_key"]): row.get("response", {})
            for row in signal_rows if isinstance(row, dict) and row.get("signal_key")
        } if isinstance(signal_rows, list) else {}
        results: list[dict[str, object]] = []
        for row in paper_rows if isinstance(paper_rows, list) else []:
            if not isinstance(row, dict):
                continue
            signal_key = str(row.get("signal_key", ""))
            response = responses.get(signal_key, {})
            response = response if isinstance(response, dict) else {}
            metadata = response.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            risk_amount = float(response.get("risk_amount") or 0)
            outcome = float(row["outcome_r"]) if row.get("outcome_r") is not None else None
            entry = float(row["entry_price"])
            if outcome is None:
                exit_price = None
            elif outcome < 0:
                exit_price = float(row["initial_stop_price"])
            elif outcome >= 1:
                exit_price = float(row["target_price"])
            else:
                exit_price = entry
            setup_type = str(metadata.get("setup_type", "strategy"))
            results.append(
                {
                    "trade_id": f"paper:{signal_key}",
                    "symbol": str(response.get("symbol") or "XAUUSD"),
                    "timeframe": str(response.get("timeframe") or "M5"),
                    "setup": f"{setup_type}_paper_trade",
                    "side": row["side"],
                    "opened_at_utc": row["opened_at_utc"],
                    "closed_at_utc": row.get("closed_at_utc"),
                    "volume_lots": float(metadata.get("suggested_size") or 0),
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "stop_loss_price": float(row["initial_stop_price"]),
                    "take_profit_price": float(row["target_price"]),
                    "risk_amount": risk_amount,
                    "gross_pnl": (outcome or 0) * risk_amount,
                    "fees": 0,
                    "net_pnl": (outcome or 0) * risk_amount,
                    "rr_realized": outcome,
                    "note": "Paper trade técnico; não foi enviado ao mercado.",
                }
            )
        return results

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

    def advance_paper_trades(
        self,
        bot_id: str,
        candles: list[CandleSnapshot],
        *,
        bid: float | None = None,
        ask: float | None = None,
        timestamp_utc: datetime | None = None,
    ) -> None:
        if not candles:
            return
        candle = candles[-1]
        rows = self._request(f"paper_trades?bot_id=eq.{bot_id}&status=eq.open&select=*")
        for trade in rows if isinstance(rows, list) else []:
            opened_at = datetime.fromisoformat(str(trade["opened_at_utc"]))
            if bot_id == "bot-14" and bid is not None and ask is not None and timestamp_utc is not None and timestamp_utc > opened_at:
                buy = trade["side"] == "buy"
                entry = float(trade["entry_price"])
                stop = float(trade["stop_price"])
                target = float(trade["target_price"])
                initial_stop = float(trade["initial_stop_price"])
                risk = abs(entry - initial_stop)
                direction = 1 if buy else -1
                point_size = risk / 240 if risk else self.settings.backtest_point_size
                exit_quote = bid if buy else ask
                outcome_r = direction * (exit_quote - entry) / risk if risk else 0
                favorable_points = direction * (exit_quote - entry) / point_size if point_size else 0
                elapsed_seconds = (timestamp_utc - opened_at).total_seconds()
                soft_stop_points = float(getattr(self.settings, "happy_gold_micro_soft_stop_points", 40))
                max_holding_seconds = int(getattr(self.settings, "happy_gold_micro_max_holding_seconds", 60))
                tick_patch: dict[str, object] = {}
                stop_hit = exit_quote <= stop if buy else exit_quote >= stop
                target_hit = exit_quote >= target if buy else exit_quote <= target
                if stop_hit or favorable_points <= -soft_stop_points or target_hit or elapsed_seconds >= max_holding_seconds:
                    tick_patch = {
                        "status": "closed",
                        "closed_at_utc": timestamp_utc.isoformat(),
                        "outcome_r": outcome_r,
                    }
                else:
                    next_stop = stop
                    break_even_trigger = float(getattr(self.settings, "happy_gold_micro_break_even_trigger_points", 30))
                    break_even_offset = float(getattr(self.settings, "happy_gold_micro_break_even_offset_points", 5))
                    trailing_activation = float(getattr(self.settings, "happy_gold_micro_trailing_activation_points", 60))
                    trailing_distance = float(getattr(self.settings, "happy_gold_micro_trailing_distance_points", 30))
                    if favorable_points >= break_even_trigger:
                        break_even_stop = entry + direction * break_even_offset * point_size
                        next_stop = max(next_stop, break_even_stop) if buy else min(next_stop, break_even_stop)
                    if favorable_points >= trailing_activation:
                        trailing_stop = exit_quote - direction * trailing_distance * point_size
                        next_stop = max(next_stop, trailing_stop) if buy else min(next_stop, trailing_stop)
                    if next_stop != stop:
                        tick_patch = {"stop_price": next_stop}
                if tick_patch:
                    filters = urlencode({"signal_key": f"eq.{trade['signal_key']}", "variant": f"eq.{trade['variant']}"})
                    self._request(f"paper_trades?{filters}", method="PATCH", payload=tick_patch, prefer="return=minimal")
                    if tick_patch.get("status") == "closed":
                        continue
            if candle.timestamp_utc <= opened_at:
                continue
            buy = trade["side"] == "buy"
            stop = float(trade["stop_price"])
            entry = float(trade["entry_price"])
            partial = float(trade["partial_price"])
            target = float(trade["target_price"])
            initial_stop = float(trade["initial_stop_price"])
            risk = abs(entry - initial_stop)
            partial_fraction = float(trade.get("partial_close_pct", 50)) / 100
            direction = 1 if buy else -1
            partial_r = direction * (partial - entry) / risk if risk else 0
            target_r = direction * (target - entry) / risk if risk else 0
            patch: dict[str, object] = {}
            # Conservative intrabar rule: a stop has precedence over all targets.
            stopped = candle.low <= stop if buy else candle.high >= stop
            if stopped:
                outcome_r = partial_fraction * partial_r if trade["partial_hit"] else -1
                patch = {"status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": outcome_r}
            elif not trade["partial_hit"] and (candle.high >= partial if buy else candle.low <= partial):
                if partial_fraction >= 1:
                    patch = {"partial_hit": True, "status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": partial_r}
                else:
                    patch = {"partial_hit": True, "stop_price": entry}
            elif trade["partial_hit"] and (candle.high >= target if buy else candle.low <= target):
                outcome_r = partial_fraction * partial_r + (1 - partial_fraction) * target_r
                patch = {"status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": outcome_r}
            elif trade.get("expires_at_utc") and candle.timestamp_utc + timedelta(minutes=5) >= datetime.fromisoformat(str(trade["expires_at_utc"])):
                outcome_r = direction * (candle.close - entry) / risk if risk else 0
                patch = {"status": "closed", "closed_at_utc": candle.timestamp_utc.isoformat(), "outcome_r": outcome_r}
            elif bot_id in {"bot-12", "bot-13"} and risk:
                point_size = risk / 240
                favorable_price = candle.high if buy else candle.low
                favorable_points = direction * (favorable_price - entry) / point_size
                next_stop = stop
                if favorable_points >= self.settings.happy_gold_break_even_trigger_points:
                    break_even_stop = entry + direction * self.settings.happy_gold_break_even_offset_points * point_size
                    next_stop = max(next_stop, break_even_stop) if buy else min(next_stop, break_even_stop)
                if favorable_points >= self.settings.happy_gold_trailing_activation_points:
                    trailing_stop = favorable_price - direction * self.settings.happy_gold_trailing_distance_points * point_size
                    next_stop = max(next_stop, trailing_stop) if buy else min(next_stop, trailing_stop)
                if next_stop != stop:
                    patch = {"stop_price": next_stop}
            if patch:
                filters = urlencode({"signal_key": f"eq.{trade['signal_key']}", "variant": f"eq.{trade['variant']}"})
                self._request(f"paper_trades?{filters}", method="PATCH", payload=patch, prefer="return=minimal")

    def record_strategy_candidate(self, payload: DecisionRequest, response: DecisionResponse) -> str | None:
        if not payload.bot_id or not payload.candles or response.entry_price is None or response.stop_loss_price is None:
            return None
        setup = str(response.metadata.get("setup_type", "fimath"))
        suggested_action = str(response.metadata.get("suggested_action", ""))
        candle_timestamp = payload.candles[-1].timestamp_utc
        event_id = response.metadata.get("candidate_event_id")
        event_suffix = f":{event_id}" if event_id else ""
        signal_key = f"{payload.bot_id}:{payload.timeframe}:{candle_timestamp.isoformat()}:{suggested_action}:{setup}{event_suffix}"
        candidate = {
            "signal_key": signal_key,
            "bot_id": payload.bot_id,
            "candle_timestamp_utc": candle_timestamp.isoformat(),
            "last_evaluated_at_utc": payload.timestamp_utc.isoformat(),
            "suggested_action": suggested_action,
            "setup_type": setup,
            "flow_status": str(response.metadata.get("flow_status", "flow_unavailable")),
            "flow_confirmed": bool(response.metadata.get("flow_confirmed", False)),
            "flow_contradicted": bool(response.metadata.get("flow_contradicted", False)),
            "book_z": response.metadata.get("book_z"),
            "tick_z": response.metadata.get("tick_z"),
            "flow_score": response.metadata.get("flow_score"),
            "spread_points": payload.spread_points,
            "payload": payload.model_dump(mode="json"),
            "response": response.model_dump(mode="json"),
        }
        self._request(
            "strategy_signals?on_conflict=signal_key",
            method="POST",
            payload=candidate,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        return signal_key

    def record_paper_trade(self, signal_key: str, payload: DecisionRequest, response: DecisionResponse, variant: str) -> bool:
        if not payload.bot_id or response.entry_price is None or response.stop_loss_price is None:
            return False
        open_query = urlencode(
            {
                "bot_id": f"eq.{payload.bot_id}",
                "variant": f"eq.{variant}",
                "status": "eq.open",
                "select": "signal_key",
                "limit": "1",
            }
        )
        open_rows = self._request(f"paper_trades?{open_query}")
        if isinstance(open_rows, list) and open_rows:
            return False
        self._request("paper_trades?on_conflict=signal_key,variant", method="POST", payload={
            "signal_key": signal_key, "variant": variant, "bot_id": payload.bot_id, "side": str(response.metadata.get("suggested_action", "buy")),
            "entry_price": response.entry_price, "initial_stop_price": response.stop_loss_price, "stop_price": response.stop_loss_price,
            "partial_price": response.partial_take_profit_price, "target_price": response.final_take_profit_price,
            "partial_close_pct": response.partial_close_pct,
            "expires_at_utc": (
                payload.timestamp_utc + timedelta(seconds=int(response.metadata["max_holding_seconds"]))
            ).isoformat() if "max_holding_seconds" in response.metadata else (
                payload.timestamp_utc + timedelta(minutes=5 * int(response.metadata["max_holding_bars"]))
            ).isoformat() if "max_holding_bars" in response.metadata else None,
            "opened_at_utc": payload.timestamp_utc.isoformat(),
        }, prefer="resolution=ignore-duplicates,return=minimal")
        return True

    def closed_paper_trade_count(self, bot_id: str, variant: str) -> int:
        query = urlencode({"bot_id": f"eq.{bot_id}", "variant": f"eq.{variant}", "status": "eq.closed", "select": "signal_key"})
        rows = self._request(f"paper_trades?{query}")
        return len(rows) if isinstance(rows, list) else 0

    def load_adaptive_component_health(self, timestamp_utc: datetime) -> dict[str, dict[str, object]]:
        """Return the frozen UTC-day health snapshot used by Bot 9."""
        day_start = utc_day_start(timestamp_utc)
        window_start = day_start - timedelta(days=ADAPTIVE_WINDOW_DAYS)
        health: dict[str, dict[str, object]] = {}
        for component in ADAPTIVE_COMPONENTS:
            query = urlencode(
                [
                    ("bot_id", f"eq.{component}"),
                    ("variant", "eq.technical"),
                    ("status", "eq.closed"),
                    ("closed_at_utc", f"gte.{window_start.isoformat()}"),
                    ("closed_at_utc", f"lt.{day_start.isoformat()}"),
                    ("select", "outcome_r"),
                ]
            )
            rows = self._request(f"paper_trades?{query}")
            outcomes = [
                float(row["outcome_r"])
                for row in rows if isinstance(row, dict) and row.get("outcome_r") is not None
            ] if isinstance(rows, list) else []
            health[component] = summarize_outcomes(outcomes)
        return health

    def load_portfolio_risk_state(self, bot_id: str, timestamp_utc: datetime) -> dict[str, object]:
        """Load the Bot 10/11 risk state frozen to the current UTC day."""
        day_start = utc_day_start(timestamp_utc)
        next_day = day_start + timedelta(days=1)
        query = urlencode(
            [
                ("bot_id", f"eq.{bot_id}"),
                ("variant", "eq.technical"),
                ("opened_at_utc", f"gte.{day_start.isoformat()}"),
                ("opened_at_utc", f"lt.{next_day.isoformat()}"),
                ("select", "status,outcome_r,closed_at_utc"),
            ]
        )
        rows = self._request(f"paper_trades?{query}")
        trades = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        closed = [row for row in trades if row.get("status") == "closed" and row.get("outcome_r") is not None]
        losses = [
            datetime.fromisoformat(str(row["closed_at_utc"]))
            for row in closed
            if float(row["outcome_r"]) < 0 and row.get("closed_at_utc")
        ]
        cooldown_until = max(losses) + timedelta(minutes=15) if losses else None
        return {
            "trades_started": len(trades),
            "daily_outcome_r": round(sum(float(row["outcome_r"]) for row in closed), 6),
            "cooldown_until_utc": cooldown_until.isoformat() if cooldown_until else None,
            "as_of_utc": timestamp_utc.isoformat(),
        }

    def load_chart(self, bot: BotCatalogItem, limit: int = 5000, source_bot_id: str | None = None) -> MarketChartResponse:
        candles = self.load_candles(bot, limit, source_bot_id=source_bot_id)
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
        combined_rows = (trade_rows if isinstance(trade_rows, list) else []) + self._load_paper_results(bot.id)
        trades = [TradeResult.model_validate(row) for row in combined_rows if isinstance(row, dict)]
        return MarketChartResponse(bot_id=bot.id, symbol=bot.symbol, timeframe=bot.timeframe, candles=candles, trades=trades)

    def load_candles(self, bot: BotCatalogItem, limit: int = 5000, source_bot_id: str | None = None) -> list[CandleSnapshot]:
        candle_rows: list[object] = []
        market_data_bot_id = source_bot_id or bot.id
        for offset in range(0, limit, 1000):
            query = urlencode({"bot_id": f"eq.{market_data_bot_id}", "symbol": f"eq.{bot.symbol}", "timeframe": f"eq.{bot.timeframe}", "select": "timestamp_utc,open,high,low,close,volume", "order": "timestamp_utc.desc", "limit": "1000", "offset": str(offset)})
            page = self._request(f"market_candles?{query}")
            if not isinstance(page, list) or not page:
                break
            candle_rows.extend(page)
            if len(page) < 1000:
                break
        return [CandleSnapshot.model_validate(row) for row in reversed(candle_rows)]
