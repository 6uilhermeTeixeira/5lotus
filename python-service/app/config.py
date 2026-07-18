from functools import lru_cache
from os import getenv


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("DAYTRADE_APP_NAME", "mt5-daytrade-strategy-service")
        self.host = getenv("DAYTRADE_HOST", "127.0.0.1")
        self.port = int(getenv("DAYTRADE_PORT", "8000"))
        self.strategy_profile = getenv("DAYTRADE_STRATEGY_PROFILE", "price_action_breakout_pullback")
        self.default_symbol = getenv("DAYTRADE_DEFAULT_SYMBOL", "XAUUSD")
        self.default_timeframe = getenv("DAYTRADE_DEFAULT_TIMEFRAME", "M5")
        self.max_spread_points = float(getenv("DAYTRADE_MAX_SPREAD_POINTS", "3.0"))
        self.risk_per_trade_pct = float(getenv("DAYTRADE_RISK_PER_TRADE_PCT", "5.0"))
        self.min_risk_reward = float(getenv("DAYTRADE_MIN_RISK_REWARD", "1.5"))
        self.enable_live_decisions = getenv("DAYTRADE_ENABLE_LIVE_DECISIONS", "false").lower() == "true"


@lru_cache
def get_settings() -> Settings:
    return Settings()
