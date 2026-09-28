from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        service_root = Path(__file__).resolve().parent.parent
        self.lotus_data_root = Path(getenv("LOTUS_DATA_ROOT", "/home/codexops/lotus-data"))
        self.fusion_tick_spool_root = Path(getenv(
            "DAYTRADE_FUSION_TICK_SPOOL_ROOT",
            "/home/codexops/.local/share/mt5-wine/drive_c/users/codexops/AppData/Roaming/MetaQuotes/Terminal/Common/Files",
        ))
        self.fusion_history_collector_id = getenv("DAYTRADE_FUSION_HISTORY_COLLECTOR_ID", "2lotus-fusion-demo-history-v1")
        self.lotus_dataset_version = getenv("LOTUS_DATASET_VERSION", "CURRENT")
        self.lotus_publisher_python = Path(
            getenv("LOTUS_PUBLISHER_PYTHON", "/home/codexops/projects/2Lotus/market-data-pipeline/.venv/bin/python")
        )
        self.lotus_publisher_script = Path(
            getenv("LOTUS_PUBLISHER_SCRIPT", "/home/codexops/projects/2Lotus/market-data-pipeline/scripts/publish-dataset.py")
        )
        self.lotus_publish_timeout_seconds = int(getenv("LOTUS_PUBLISH_TIMEOUT_SECONDS", "900"))
        self.app_name = getenv("DAYTRADE_APP_NAME", "2lotus-strategy-service")
        self.host = getenv("DAYTRADE_HOST", "127.0.0.1")
        self.port = int(getenv("DAYTRADE_PORT", "1112"))
        self.strategy_profile = getenv("DAYTRADE_STRATEGY_PROFILE", "stochastic_sell_session")
        self.default_symbol = getenv("DAYTRADE_DEFAULT_SYMBOL", "XAUUSD")
        self.default_timeframe = getenv("DAYTRADE_DEFAULT_TIMEFRAME", "M5")
        self.max_spread_points = float(getenv("DAYTRADE_MAX_SPREAD_POINTS", "50.0"))
        self.risk_per_trade_pct = float(getenv("DAYTRADE_RISK_PER_TRADE_PCT", "1.0"))
        self.min_execution_lot = float(getenv("DAYTRADE_MIN_EXECUTION_LOT", "0.01"))
        self.execution_lot_step = float(getenv("DAYTRADE_EXECUTION_LOT_STEP", "0.01"))
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
        self.backtest_spread_points = float(getenv("DAYTRADE_BACKTEST_SPREAD_POINTS", "0"))
        self.backtest_point_size = float(getenv("DAYTRADE_BACKTEST_POINT_SIZE", "0.01"))
        self.backtest_value_per_point_per_lot = float(getenv("DAYTRADE_BACKTEST_VALUE_PER_POINT_PER_LOT", "1"))
        self.backtest_candle_limit = int(getenv("DAYTRADE_BACKTEST_CANDLE_LIMIT", "100000"))
        self.backtest_risk_per_trade_pct = float(getenv("DAYTRADE_BACKTEST_RISK_PER_TRADE_PCT", "0.25"))
        self.backtest_slippage_points = float(getenv("DAYTRADE_BACKTEST_SLIPPAGE_POINTS", "2"))
        self.backtest_commission_per_lot = float(getenv("DAYTRADE_BACKTEST_COMMISSION_PER_LOT", "4.50"))
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
        self.happy_gold_combined_session_start_utc = getenv("DAYTRADE_HAPPY_GOLD_COMBINED_SESSION_START_UTC", "06:00")
        self.happy_gold_combined_session_end_utc = getenv("DAYTRADE_HAPPY_GOLD_COMBINED_SESSION_END_UTC", "19:00")
        self.happy_gold_impulse_30s_threshold_pips = float(getenv("DAYTRADE_HAPPY_GOLD_IMPULSE_30S_THRESHOLD_PIPS", "95.5"))
        self.happy_gold_zigzag_tick_context_900s_threshold_pips = float(
            getenv("DAYTRADE_HAPPY_GOLD_ZIGZAG_TICK_CONTEXT_900S_THRESHOLD_PIPS", "800")
        )
        self.happy_gold_structural_context_900s_threshold_pips = float(
            getenv("DAYTRADE_HAPPY_GOLD_STRUCTURAL_CONTEXT_900S_THRESHOLD_PIPS", "1000")
        )
        self.happy_gold_structural_ema20_gap_pips = float(
            getenv("DAYTRADE_HAPPY_GOLD_STRUCTURAL_EMA20_GAP_PIPS", "900")
        )
        self.happy_gold_structural_max_pivot_extension_pips = float(
            getenv("DAYTRADE_HAPPY_GOLD_STRUCTURAL_MAX_PIVOT_EXTENSION_PIPS", "50")
        )
        self.happy_gold_normalized_range_max = float(
            getenv("DAYTRADE_HAPPY_GOLD_NORMALIZED_RANGE_MAX", "1.876955192")
        )
        self.happy_gold_normalized_range_max_spread_points = float(
            getenv("DAYTRADE_HAPPY_GOLD_NORMALIZED_RANGE_MAX_SPREAD_POINTS", "15")
        )
        self.zigzag_scalper_v3_expansion_threshold = float(
            getenv("DAYTRADE_ZIGZAG_SCALPER_V3_EXPANSION_THRESHOLD", "6.0")
        )
        self.zigzag_scalper_v5_calendar_range_floor = float(
            getenv("DAYTRADE_ZIGZAG_SCALPER_V5_CALENDAR_RANGE_FLOOR", "4.5")
        )
        self.zigzag_scalper_v52_buy_ema50_distance_atr = float(
            getenv("DAYTRADE_ZIGZAG_SCALPER_V52_BUY_EMA50_DISTANCE_ATR", "1.0")
        )
        self.zigzag_scalper_v4_min_5s_move_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MIN_5S_MOVE_PIPS", "20"))
        self.zigzag_scalper_v4_min_30s_move_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MIN_30S_MOVE_PIPS", "75"))
        self.zigzag_scalper_v4_min_60s_move_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MIN_60S_MOVE_PIPS", "120"))
        self.zigzag_scalper_v4_min_efficiency = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MIN_EFFICIENCY", "0.18"))
        self.zigzag_scalper_v4_min_tick_acceleration = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MIN_TICK_ACCELERATION", "0.85"))
        self.zigzag_scalper_v4_max_spread_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V4_MAX_SPREAD_PIPS", "100"))
        self.zigzag_scalper_v12_retest_max_age_seconds = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V12_RETEST_MAX_AGE_SECONDS", "90"))
        self.zigzag_scalper_v12_retest_max_depth_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V12_RETEST_MAX_DEPTH_PIPS", "50"))
        self.zigzag_scalper_v12_min_rejection_move_pips = float(getenv("DAYTRADE_ZIGZAG_SCALPER_V12_MIN_REJECTION_MOVE_PIPS", "5"))
        self.stochastic_sell_v2_threshold = float(getenv("DAYTRADE_STOCHASTIC_SELL_V2_THRESHOLD", "85"))
        self.stochastic_sell_v2_target_rr = float(getenv("DAYTRADE_STOCHASTIC_SELL_V2_TARGET_RR", "1.25"))
        self.stochastic_sell_v2_partial_pct = float(getenv("DAYTRADE_STOCHASTIC_SELL_V2_PARTIAL_PCT", "50"))
        self.stochastic_sell_v2_cutoff_hour = int(getenv("DAYTRADE_STOCHASTIC_SELL_V2_CUTOFF_HOUR", "15"))
        self.stochastic_sell_v3_cutoff_hour = int(getenv("DAYTRADE_STOCHASTIC_SELL_V3_CUTOFF_HOUR", "13"))
        self.multitimeframe_v2_strength_min = float(getenv("DAYTRADE_MULTITIMEFRAME_V2_STRENGTH_MIN", "0.5"))
        self.multitimeframe_v2_session_start_hour = int(getenv("DAYTRADE_MULTITIMEFRAME_V2_SESSION_START_HOUR", "13"))
        self.multitimeframe_v2_session_end_hour = int(getenv("DAYTRADE_MULTITIMEFRAME_V2_SESSION_END_HOUR", "16"))
        self.multitimeframe_v2_stop_atr = float(getenv("DAYTRADE_MULTITIMEFRAME_V2_STOP_ATR", "1.2"))
        self.multitimeframe_v2_target_rr = float(getenv("DAYTRADE_MULTITIMEFRAME_V2_TARGET_RR", "1.25"))
        self.multitimeframe_v2_max_holding_bars = int(getenv("DAYTRADE_MULTITIMEFRAME_V2_MAX_HOLDING_BARS", "6"))
        self.happy_gold_impulse_session_start_utc = getenv("DAYTRADE_HAPPY_GOLD_IMPULSE_SESSION_START_UTC", "00:00")
        self.happy_gold_impulse_session_end_utc = getenv("DAYTRADE_HAPPY_GOLD_IMPULSE_SESSION_END_UTC", "17:00")
        self.happy_gold_multiwindow_shadow_enabled = getenv("DAYTRADE_HAPPY_GOLD_MULTIWINDOW_SHADOW_ENABLED", "false").lower() == "true"
        self.results_store_path = Path(
            getenv("DAYTRADE_RESULTS_STORE_PATH", str(service_root / "data" / "trade-results.json"))
        )
        self.backtest_cache_path = Path(
            getenv("DAYTRADE_BACKTEST_CACHE_PATH", str(service_root / "data" / "backtests"))
        )
        self.legacy_backtest_cache_path = Path(
            getenv("DAYTRADE_LEGACY_BACKTEST_PATH", str(service_root / "data" / "backtests-legacy"))
        )
        self.bots_catalog_path = Path(getenv("DAYTRADE_BOTS_CATALOG_PATH", str(service_root / "data" / "bots.json")))
        self.legacy_bots_catalog_path = Path(
            getenv("DAYTRADE_LEGACY_BOTS_CATALOG_PATH", str(service_root / "data" / "legacy-bots.json"))
        )
        self.dashboard_password = getenv("DAYTRADE_DASHBOARD_PASSWORD")
        self.session_secret = getenv("DAYTRADE_SESSION_SECRET")
        self.session_max_age_seconds = int(getenv("DAYTRADE_SESSION_MAX_AGE_SECONDS", "43200"))
        self.results_store = getenv("DAYTRADE_RESULTS_STORE", "JSON").upper()
        self.supabase_url = getenv("DAYTRADE_SUPABASE_URL")
        self.supabase_service_role_key = getenv("DAYTRADE_SUPABASE_SERVICE_ROLE_KEY")
        self.ingest_api_key = getenv("DAYTRADE_INGEST_API_KEY")
        self.mt5_login = getenv("DAYTRADE_MT5_LOGIN", "")
        self.mt5_server = getenv("DAYTRADE_MT5_SERVER", "")
        self.mt5_initial_balance = float(getenv("DAYTRADE_MT5_INITIAL_BALANCE", "100"))
        self.supabase_timeout_seconds = float(getenv("DAYTRADE_SUPABASE_TIMEOUT_SECONDS", "2.0"))
        self.supabase_retry_attempts = int(getenv("DAYTRADE_SUPABASE_RETRY_ATTEMPTS", "2"))
        self.login_rate_limit_attempts = int(getenv("DAYTRADE_LOGIN_RATE_LIMIT_ATTEMPTS", "5"))
        self.ingest_rate_limit_per_minute = int(getenv("DAYTRADE_INGEST_RATE_LIMIT_PER_MINUTE", "180"))
        self.tick_ingest_rate_limit_per_minute = int(getenv("DAYTRADE_TICK_INGEST_RATE_LIMIT_PER_MINUTE", "120"))
        self._validate()

    def _validate(self) -> None:
        if self.results_store not in {"JSON", "SUPABASE"}:
            raise ValueError("DAYTRADE_RESULTS_STORE must be JSON or SUPABASE")
        if self.fimath_mode not in {"shadow", "live"}:
            raise ValueError("DAYTRADE_FIMATH_MODE must be shadow or live")
        if not 0 < self.risk_per_trade_pct <= 10:
            raise ValueError("DAYTRADE_RISK_PER_TRADE_PCT must be between 0 and 10")
        if self.min_execution_lot <= 0 or self.execution_lot_step <= 0:
            raise ValueError("execution lot minimum and step must be positive")
        if not 0 < self.backtest_risk_per_trade_pct <= 10:
            raise ValueError("DAYTRADE_BACKTEST_RISK_PER_TRADE_PCT must be between 0 and 10")
        if self.session_max_age_seconds <= 0:
            raise ValueError("DAYTRADE_SESSION_MAX_AGE_SECONDS must be positive")
        if self.supabase_timeout_seconds <= 0 or not 1 <= self.supabase_retry_attempts <= 5:
            raise ValueError("Supabase timeout/retry settings are invalid")
        if self.tick_ingest_rate_limit_per_minute <= 0:
            raise ValueError("DAYTRADE_TICK_INGEST_RATE_LIMIT_PER_MINUTE must be positive")
        if self.mt5_initial_balance <= 0:
            raise ValueError("DAYTRADE_MT5_INITIAL_BALANCE must be positive")
        if self.lotus_publish_timeout_seconds <= 0:
            raise ValueError("LOTUS_PUBLISH_TIMEOUT_SECONDS must be positive")
        if not 1 <= self.stochastic_sell_v3_cutoff_hour <= 23:
            raise ValueError("DAYTRADE_STOCHASTIC_SELL_V3_CUTOFF_HOUR must be between 1 and 23")
        if self.session_secret and len(self.session_secret) < 32:
            raise ValueError("DAYTRADE_SESSION_SECRET must contain at least 32 characters")

    @property
    def dashboard_auth_configured(self) -> bool:
        return bool(self.dashboard_password and self.session_secret)

    @property
    def supabase_results_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
