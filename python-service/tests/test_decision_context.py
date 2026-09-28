from types import SimpleNamespace

from app.services.decision_context import enforce_shadow_minimum, prepare_strategy_settings
from app.schemas import DecisionAction, DecisionResponse


def _request(bot_id: str | None = "bot-1") -> SimpleNamespace:
    return SimpleNamespace(
        bot_id=bot_id,
        symbol="XAUUSD",
        timeframe="M5",
    )


def test_prepare_strategy_settings_scopes_bot_context_and_preserves_base() -> None:
    base = SimpleNamespace(default_symbol="EURUSD", default_timeframe="H1", portfolio_risk_state={})
    scoped = prepare_strategy_settings(
        base,
        _request(),
        "portfolio_6_7",
        portfolio_risk_state={"trades_started": 2},
    )
    assert scoped is not base
    assert scoped.default_symbol == "XAUUSD"
    assert scoped.default_timeframe == "M5"
    assert scoped.portfolio_risk_state == {"trades_started": 2}
    assert base.default_symbol == "EURUSD"


def test_prepare_strategy_settings_without_bot_returns_base() -> None:
    base = SimpleNamespace(default_symbol="EURUSD")
    assert prepare_strategy_settings(base, _request(None), "stochastic_sell_session") is base


def test_enforce_shadow_minimum_holds_direction_until_sample_exists() -> None:
    response = DecisionResponse(action=DecisionAction.BUY, reason="candidate", size=0.2)
    result = enforce_shadow_minimum(
        response,
        validation_variant="technical",
        closed_paper_trades=4,
        minimum_closed_trades=5,
    )
    assert result.action == DecisionAction.HOLD
    assert result.reason == "shadow_minimum_not_reached"
    assert result.size == 0
    assert result.metadata["closed_paper_trades"] == 4
