"""Build strategy comparisons independently from the HTTP layer."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from ..schemas import BotCatalogItem, EquityComparisonResponse, EquityPoint, EquitySeries, HistoricalReplayResponse
from ..strategies.registry import strategy_presentation_order


ReplayLoader = Callable[[BotCatalogItem], HistoricalReplayResponse | None]


def build_equity_comparison(
    bots: Iterable[BotCatalogItem],
    *,
    symbol: str,
    timeframe: str,
    period_days: int,
    load_replay: ReplayLoader,
) -> EquityComparisonResponse:
    series: list[EquitySeries] = []
    missing: list[str] = []
    for bot in sorted(bots, key=lambda item: (strategy_presentation_order(item.strategy_profile), item.name.casefold())):
        replay = load_replay(bot)
        if replay is None:
            missing.append(bot.id)
            continue
        cumulative = 0.0
        points: list[EquityPoint] = []
        for point in sorted(replay.daily_pnl, key=lambda item: item.day):
            cumulative += point.net_pnl
            points.append(EquityPoint(day=point.day, cumulative_pnl=round(cumulative, 2)))
        if not points:
            points.append(EquityPoint(day=replay.period_start_utc.date(), cumulative_pnl=0.0))
            if replay.period_end_utc.date() != replay.period_start_utc.date():
                points.append(EquityPoint(day=replay.period_end_utc.date(), cumulative_pnl=0.0))
        series.append(EquitySeries(
            bot_id=bot.id,
            name=bot.name,
            strategy_profile=bot.strategy_profile,
            summary=replay.summary,
            expectancy_r=replay.expectancy_r,
            max_drawdown_r=replay.max_drawdown_r,
            points=points,
        ))
    return EquityComparisonResponse(
        symbol=symbol,
        timeframe=timeframe,
        period_days=period_days,
        updated_at_utc=datetime.now(timezone.utc),
        series=series,
        missing_bot_ids=missing,
    )
