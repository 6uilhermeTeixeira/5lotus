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
        self.max_spread_points = float(getenv("DAYTRADE_MAX_SPREAD_POINTS", "3.0"))
        self.risk_per_trade_pct = float(getenv("DAYTRADE_RISK_PER_TRADE_PCT", "1.0"))
        self.min_risk_reward = float(getenv("DAYTRADE_MIN_RISK_REWARD", "2.0"))
        self.enable_live_decisions = getenv("DAYTRADE_ENABLE_LIVE_DECISIONS", "false").lower() == "true"
        self.fimath_mode = getenv("DAYTRADE_FIMATH_MODE", "shadow").lower()
        self.fimath_flow_window_seconds = int(getenv("DAYTRADE_FIMATH_FLOW_WINDOW_SECONDS", "300"))
        self.fimath_partial_pct = float(getenv("DAYTRADE_FIMATH_PARTIAL_PCT", "50"))
        self.chart_cache_limit = int(getenv("DAYTRADE_CHART_CACHE_LIMIT", "50000"))
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
