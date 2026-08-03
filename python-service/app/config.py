from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        service_root = Path(__file__).resolve().parent.parent
        self.app_name = getenv("DAYTRADE_APP_NAME", "2lotus-strategy-service")
        self.host = getenv("DAYTRADE_HOST", "127.0.0.1")
        self.port = int(getenv("DAYTRADE_PORT", "8000"))
        self.strategy_profile = getenv("DAYTRADE_STRATEGY_PROFILE", "fimath_ema20_flow")
        self.default_symbol = getenv("DAYTRADE_DEFAULT_SYMBOL", "XAUUSD")
        self.default_timeframe = getenv("DAYTRADE_DEFAULT_TIMEFRAME", "M5")
        self.max_spread_points = float(getenv("DAYTRADE_MAX_SPREAD_POINTS", "50.0"))
        self.risk_per_trade_pct = float(getenv("DAYTRADE_RISK_PER_TRADE_PCT", "1.0"))
        self.min_risk_reward = float(getenv("DAYTRADE_MIN_RISK_REWARD", "2.0"))
        self.enable_live_decisions = getenv("DAYTRADE_ENABLE_LIVE_DECISIONS", "false").lower() == "true"
        self.fimath_mode = getenv("DAYTRADE_FIMATH_MODE", "shadow").lower()
        self.fimath_flow_window_seconds = int(getenv("DAYTRADE_FIMATH_FLOW_WINDOW_SECONDS", "300"))
        self.fimath_flow_min_samples = int(getenv("DAYTRADE_FIMATH_FLOW_MIN_SAMPLES", "30"))
        self.fimath_flow_z_threshold = float(getenv("DAYTRADE_FIMATH_FLOW_Z_THRESHOLD", "1.0"))
        self.fimath_flow_policy = getenv("DAYTRADE_FIMATH_FLOW_POLICY", "veto").lower()
        if self.fimath_flow_policy not in {"required", "veto"}:
            raise ValueError("DAYTRADE_FIMATH_FLOW_POLICY must be 'required' or 'veto'")
        self.fimath_partial_pct = float(getenv("DAYTRADE_FIMATH_PARTIAL_PCT", "50"))
        self.fimath_min_closed_paper_trades = int(getenv("DAYTRADE_FIMATH_MIN_CLOSED_PAPER_TRADES", "30"))
        self.chart_cache_limit = int(getenv("DAYTRADE_CHART_CACHE_LIMIT", "5000"))
        self.backtest_balance = float(getenv("DAYTRADE_BACKTEST_BALANCE", "10000"))
        self.backtest_spread_points = float(getenv("DAYTRADE_BACKTEST_SPREAD_POINTS", "10"))
        self.backtest_point_size = float(getenv("DAYTRADE_BACKTEST_POINT_SIZE", "0.01"))
        self.backtest_value_per_point_per_lot = float(getenv("DAYTRADE_BACKTEST_VALUE_PER_POINT_PER_LOT", "1"))
        self.backtest_candle_limit = int(getenv("DAYTRADE_BACKTEST_CANDLE_LIMIT", "120000"))
        self.backtest_market_data_bot_id = getenv("DAYTRADE_BACKTEST_MARKET_DATA_BOT_ID", "bot-1")
        self.backtest_risk_per_trade_pct = float(getenv("DAYTRADE_BACKTEST_RISK_PER_TRADE_PCT", "0.25"))
        self.backtest_slippage_points = float(getenv("DAYTRADE_BACKTEST_SLIPPAGE_POINTS", "2"))
        self.backtest_commission_per_lot = float(getenv("DAYTRADE_BACKTEST_COMMISSION_PER_LOT", "0"))
        self.backtest_session_start_utc = getenv("DAYTRADE_BACKTEST_SESSION_START_UTC", "06:00")
        self.backtest_session_end_utc = getenv("DAYTRADE_BACKTEST_SESSION_END_UTC", "21:00")
        self.backtest_max_trades_per_day = int(getenv("DAYTRADE_BACKTEST_MAX_TRADES_PER_DAY", "4"))
        self.backtest_daily_loss_limit_r = float(getenv("DAYTRADE_BACKTEST_DAILY_LOSS_LIMIT_R", "2"))
        self.backtest_cooldown_bars_after_loss = int(getenv("DAYTRADE_BACKTEST_COOLDOWN_BARS_AFTER_LOSS", "3"))
        self.backtest_regime_enabled = getenv("DAYTRADE_BACKTEST_REGIME_ENABLED", "true").lower() == "true"
        self.backtest_regime_trend_adx = float(getenv("DAYTRADE_BACKTEST_REGIME_TREND_ADX", "25"))
        self.backtest_regime_range_adx = float(getenv("DAYTRADE_BACKTEST_REGIME_RANGE_ADX", "20"))
        self.backtest_regime_high_volatility_percentile = float(getenv("DAYTRADE_BACKTEST_REGIME_HIGH_VOLATILITY_PERCENTILE", "90"))
        self.backtest_validation_fold_days = int(getenv("DAYTRADE_BACKTEST_VALIDATION_FOLD_DAYS", "30"))
        self.happy_gold_break_even_trigger_points = float(getenv("DAYTRADE_HAPPY_GOLD_BREAK_EVEN_TRIGGER_POINTS", "40"))
        self.happy_gold_break_even_offset_points = float(getenv("DAYTRADE_HAPPY_GOLD_BREAK_EVEN_OFFSET_POINTS", "0"))
        self.happy_gold_trailing_activation_points = float(getenv("DAYTRADE_HAPPY_GOLD_TRAILING_ACTIVATION_POINTS", "120"))
        self.happy_gold_trailing_distance_points = float(getenv("DAYTRADE_HAPPY_GOLD_TRAILING_DISTANCE_POINTS", "60"))
        self.happy_gold_max_holding_bars = int(getenv("DAYTRADE_HAPPY_GOLD_MAX_HOLDING_BARS", "2"))
        self.happy_gold_market_calibrations: dict[str, dict[str, float | int | str | bool]] = {
            "EURUSD": {
                "use_atr_geometry": True,
                "atr_stop_multiplier": 1.5,
                "target_r": 2.5,
                "break_even_r": 1.0,
                "trailing_activation_r": 1.2,
                "trailing_distance_atr": 1.0,
                "max_holding_bars": 12,
                "pivot_span": 2,
                "session_start_utc": "07:00",
                "session_end_utc": "17:00",
            },
            "BTCUSD": {
                "use_atr_geometry": True,
                "atr_stop_multiplier": 1.5,
                "target_r": 2.5,
                "break_even_r": 1.0,
                "trailing_activation_r": 1.2,
                "trailing_distance_atr": 1.0,
                "max_holding_bars": 8,
                "pivot_span": 3,
                "session_start_utc": "12:00",
                "session_end_utc": "23:59",
            },
        }
        self.happy_gold_micro_min_directional_ticks = int(getenv("DAYTRADE_HAPPY_GOLD_MICRO_MIN_DIRECTIONAL_TICKS", "4"))
        self.happy_gold_micro_min_tick_imbalance = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_MIN_TICK_IMBALANCE", "0.25"))
        self.happy_gold_micro_min_m1_body_ratio = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_MIN_M1_BODY_RATIO", "0.55"))
        self.happy_gold_micro_max_extension_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_MAX_EXTENSION_POINTS", "80"))
        self.happy_gold_micro_soft_stop_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_SOFT_STOP_POINTS", "40"))
        self.happy_gold_micro_break_even_trigger_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_BREAK_EVEN_TRIGGER_POINTS", "30"))
        self.happy_gold_micro_break_even_offset_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_BREAK_EVEN_OFFSET_POINTS", "5"))
        self.happy_gold_micro_trailing_activation_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_TRAILING_ACTIVATION_POINTS", "60"))
        self.happy_gold_micro_trailing_distance_points = float(getenv("DAYTRADE_HAPPY_GOLD_MICRO_TRAILING_DISTANCE_POINTS", "30"))
        self.happy_gold_micro_max_holding_seconds = int(getenv("DAYTRADE_HAPPY_GOLD_MICRO_MAX_HOLDING_SECONDS", "60"))
        self.happy_gold_micro_reentry_bucket_seconds = int(getenv("DAYTRADE_HAPPY_GOLD_MICRO_REENTRY_BUCKET_SECONDS", "15"))
        self.results_store_path = Path(
            getenv("DAYTRADE_RESULTS_STORE_PATH", str(service_root / "data" / "trade-results.json"))
        )
        self.bots_catalog_path = Path(getenv("DAYTRADE_BOTS_CATALOG_PATH", str(service_root / "data" / "bots.json")))
        self.dashboard_password = getenv("DAYTRADE_DASHBOARD_PASSWORD")
        self.session_secret = getenv("DAYTRADE_SESSION_SECRET")
        self.session_max_age_seconds = int(getenv("DAYTRADE_SESSION_MAX_AGE_SECONDS", "43200"))
        self.results_store = getenv("DAYTRADE_RESULTS_STORE", "JSON").upper()
        self.supabase_url = getenv("DAYTRADE_SUPABASE_URL")
        self.supabase_service_role_key = getenv("DAYTRADE_SUPABASE_SERVICE_ROLE_KEY")
        self.ingest_api_key = getenv("DAYTRADE_INGEST_API_KEY")

    @property
    def dashboard_auth_configured(self) -> bool:
        return bool(self.dashboard_password and self.session_secret)

    @property
    def supabase_results_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
