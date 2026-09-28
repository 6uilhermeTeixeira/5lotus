import json
import unittest
from pathlib import Path

from app.pages import _strategy_family, render_account_page, render_catalog_page, render_comparison_page, render_growth_simulator_page, render_history_page, render_login_page, render_operations_page, render_results_page
from app.schemas import BotCatalogItem


class ComparisonPageTests(unittest.TestCase):
    def test_specialized_buy_and_sell_profiles_keep_their_chart_families(self) -> None:
        sell = BotCatalogItem(id="core-mean-reversion-sell-v1", name="Mean Reversion Sell", description="", strategy_profile="mean_reversion_sell_v1_shadow", symbol="XAUUSD", timeframe="M5")
        buy = BotCatalogItem(id="core-buy-trend-dip-stochastic-v1", name="Buy Trend Dip", description="", strategy_profile="buy_trend_dip_stochastic_v1_shadow", symbol="XAUUSD", timeframe="M5")

        self.assertEqual(_strategy_family(sell), "stochastic")
        self.assertEqual(_strategy_family(buy), "multitimeframe")

        html = render_catalog_page([sell, buy]).body.decode("utf-8")
        self.assertIn("value.includes('mean_reversion_sell')", html)
        self.assertIn("value.includes('buy_trend_dip')", html)
        self.assertLess(html.index("value.includes('buy_trend_dip')"), html.index("value.includes('mean_reversion_sell')"))
        self.assertIn('/static/equity-chart.js?v=6', html)

        chart_script = (Path(__file__).parents[1] / "app" / "static" / "equity-chart.js").read_text(encoding="utf-8")
        self.assertLess(chart_script.index("value.includes('buy_trend_dip')"), chart_script.index("value.includes('mean_reversion_sell')"))

    def test_live_core_catalog_contains_all_three_family_versions_and_combination(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(item) for item in json.loads(catalog_path.read_text(encoding="utf-8"))]

        self.assertEqual(
            {bot.id for bot in bots if bot.active},
            {
                "core-zigzag", "core-zigzag-v12", "core-zigzag-v13", "core-zigzag-v2", "core-zigzag-v3", "core-zigzag-v4", "core-zigzag-v5", "core-zigzag-v6", "core-zigzag-v7", "core-zigzag-v9", "core-zigzag-v10", "core-zigzag-v72", "core-zigzag-v8",
                "core-zigzag-v11", "core-stochastic", "core-stochastic-v2", "core-stochastic-v3", "core-stochastic-v4", "core-breakout-short-v1", "core-mean-reversion-sell-v1",
                "core-multitimeframe", "core-multitimeframe-v2", "core-multitimeframe-v3", "core-buy-trend-pullback-breakout-v1", "core-buy-trend-dip-stochastic-v1",
                "core-combined-v3", "core-combined-v4",
            },
        )

    def test_catalog_uses_versioned_family_names_and_separate_subtitles(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(item) for item in json.loads(catalog_path.read_text(encoding="utf-8"))]
        by_id = {bot.id: bot for bot in bots}

        self.assertEqual(by_id["core-zigzag"].name, "ZigZag Scalper V1.0")
        self.assertEqual(by_id["core-zigzag"].subtitle, "Rompimento estrutural")
        self.assertEqual(by_id["core-zigzag-v12"].name, "ZigZag Scalper V1.1.0")
        self.assertEqual(by_id["core-zigzag-v12"].subtitle, "Microreteste estrutural")
        self.assertEqual(by_id["core-zigzag-v13"].name, "ZigZag Scalper V1.2.0")
        self.assertEqual(by_id["core-zigzag-v13"].subtitle, "Fechamento M30")
        self.assertEqual(by_id["core-zigzag-v2"].name, "ZigZag Scalper V1.3.0")
        self.assertEqual(by_id["core-zigzag-v2"].subtitle, "Gatilho · Tick estrutural")
        self.assertEqual(by_id["core-zigzag-v3"].name, "ZigZag Scalper V2.0")
        self.assertEqual(by_id["core-zigzag-v5"].name, "ZigZag Scalper V2.1")
        self.assertEqual(by_id["core-zigzag-v4"].name, "ZigZag Scalper V5.0")
        self.assertEqual(by_id["core-zigzag-v8"].name, "ZigZag Scalper V5.1")
        self.assertEqual(by_id["core-zigzag-v72"].name, "ZigZag Scalper V6.0")
        self.assertEqual(by_id["core-zigzag-v6"].name, "ZigZag Scalper V3.0")
        self.assertEqual(by_id["core-zigzag-v7"].name, "ZigZag Scalper V3.1")
        self.assertEqual(by_id["core-zigzag-v9"].name, "ZigZag Scalper V3.2")
        self.assertEqual(by_id["core-zigzag-v10"].name, "ZigZag Scalper V4.0")
        self.assertEqual(by_id["core-stochastic"].name, "Stochastic Sell V1")
        self.assertEqual(by_id["core-multitimeframe"].name, "Tendência Multitemporal V1")
        self.assertEqual(by_id["core-combined-v3"].name, "Portfólio Combinado V3")

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        self.assertIn("<h3>ZigZag Scalper V1.3.0</h3><p class=\"strategy-subtitle\">Gatilho · Tick estrutural</p>", html)
        self.assertNotIn("<h3>ZigZag Scalper V1.3.0 · Gatilho · Tick estrutural</h3>", html)
        self.assertIn('class="strategy-title-block"', html)
        self.assertIn('class="results-link">Ver resultados →', html)
        self.assertIn("height:286px", html)
        self.assertIn("margin:3px 0 0", html)

    def test_catalog_orders_zigzag_by_taxonomy_layers(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(item) for item in json.loads(catalog_path.read_text(encoding="utf-8"))]
        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        names = [
            "ZigZag Scalper V1.0", "ZigZag Scalper V1.1.0", "ZigZag Scalper V1.2.0", "ZigZag Scalper V1.3.0",
            "ZigZag Scalper V2.0", "ZigZag Scalper V2.1", "ZigZag Scalper V3.0", "ZigZag Scalper V3.1", "ZigZag Scalper V3.2",
            "ZigZag Scalper V4.0", "ZigZag Scalper V5.0", "ZigZag Scalper V5.1", "ZigZag Scalper V6.0", "ZigZag Scalper V7.0",
        ]
        positions = [html.index(f"<h3>{name}</h3>") for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_comparison_marks_bots_without_replay_as_pending(self) -> None:
        bots = [
            BotCatalogItem(
                id="core-zigzag-v12", name="ZigZag Scalper V1.2", subtitle="Microreteste estrutural",
                description="Nova geometria", strategy_profile="zigzag_scalper_v12_micro_retest_shadow",
                symbol="XAUUSD", timeframe="M5",
            )
        ]
        html = bytes(render_comparison_page(bots).body).decode("utf-8")

        self.assertIn("Replay causal pendente", html)
        self.assertIn("missing_bot_ids", html)

    def test_comparison_orders_zigzag_rows_by_taxonomy(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(item) for item in json.loads(catalog_path.read_text(encoding="utf-8"))]
        html = bytes(render_comparison_page(bots).body).decode("utf-8")
        names = [
            "ZigZag Scalper V1.0", "ZigZag Scalper V1.1.0", "ZigZag Scalper V1.2.0", "ZigZag Scalper V1.3.0",
            "ZigZag Scalper V2.0", "ZigZag Scalper V2.1", "ZigZag Scalper V3.0", "ZigZag Scalper V3.1", "ZigZag Scalper V3.2",
            "ZigZag Scalper V4.0", "ZigZag Scalper V5.0", "ZigZag Scalper V5.1", "ZigZag Scalper V6.0", "ZigZag Scalper V7.0",
        ]
        positions = [html.index(f">{name}</a>") for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_catalog_stacks_stochastic_v2_after_baseline(self) -> None:
        bots = [
            BotCatalogItem(id="core-stochastic-v2", name="Stochastic Sell V2", description="Extremo", strategy_profile="stochastic_sell_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic", name="Stochastic Sell", description="Base", strategy_profile="stochastic_sell_session", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        start = html.index('data-family="stochastic"')
        end = html.index('data-family="multitimeframe"')
        column = html[start:end]
        self.assertIn("2 variantes", column)
        self.assertLess(column.index(">Stochastic Sell</h3>"), column.index(">Stochastic Sell V2</h3>"))

    def test_catalog_stacks_stochastic_v3_after_v2(self) -> None:
        bots = [
            BotCatalogItem(id="core-stochastic-v3", name="Stochastic Sell V3", description="Adaptativa", strategy_profile="stochastic_sell_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic-v2", name="Stochastic Sell V2", description="Extremo", strategy_profile="stochastic_sell_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic", name="Stochastic Sell", description="Base", strategy_profile="stochastic_sell_session", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        start = html.index('data-family="stochastic"')
        end = html.index('data-family="multitimeframe"')
        column = html[start:end]
        self.assertIn("3 variantes", column)
        self.assertLess(column.index(">Stochastic Sell V2</h3>"), column.index(">Stochastic Sell V3</h3>"))

    def test_catalog_stacks_stochastic_v4_after_v3(self) -> None:
        bots = [
            BotCatalogItem(id="core-stochastic-v4", name="Stochastic Sell V4", description="Reteste", strategy_profile="stochastic_sell_v4_retest_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic-v3", name="Stochastic Sell V3", description="Adaptativa", strategy_profile="stochastic_sell_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic-v2", name="Stochastic Sell V2", description="Extremo", strategy_profile="stochastic_sell_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-stochastic", name="Stochastic Sell", description="Base", strategy_profile="stochastic_sell_session", symbol="XAUUSD", timeframe="M5"),
        ]
        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        start = html.index('data-family="stochastic"')
        end = html.index('data-family="multitimeframe"')
        column = html[start:end]
        self.assertIn("4 variantes", column)
        self.assertLess(column.index(">Stochastic Sell V3</h3>"), column.index(">Stochastic Sell V4</h3>"))

    def test_catalog_stacks_multitimeframe_v2_after_baseline(self) -> None:
        bots = [
            BotCatalogItem(id="core-multitimeframe-v2", name="Tendência Multitemporal V2", description="Impulso", strategy_profile="multitimeframe_trend_pullback_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-multitimeframe", name="Tendência Multitemporal", description="Base", strategy_profile="multitimeframe_trend_pullback", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        start = html.index('data-family="multitimeframe"')
        end = html.index('data-family="combined"')
        column = html[start:end]
        self.assertIn("2 variantes", column)
        self.assertLess(column.index(">Tendência Multitemporal</h3>"), column.index(">Tendência Multitemporal V2</h3>"))

    def test_catalog_stacks_multitimeframe_v3_after_v2(self) -> None:
        bots = [
            BotCatalogItem(id="core-multitimeframe-v3", name="Tendência Multitemporal V3", description="Adaptativa", strategy_profile="multitimeframe_trend_pullback_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-multitimeframe-v2", name="Tendência Multitemporal V2", description="Impulso", strategy_profile="multitimeframe_trend_pullback_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-multitimeframe", name="Tendência Multitemporal", description="Base", strategy_profile="multitimeframe_trend_pullback", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        column = html[html.index('data-family="multitimeframe"'):html.index('data-family="combined"')]
        self.assertIn("3 variantes", column)
        self.assertLess(column.index(">Tendência Multitemporal V2</h3>"), column.index(">Tendência Multitemporal V3</h3>"))

    def test_catalog_keeps_only_combined_v3(self) -> None:
        bots = [
            BotCatalogItem(id="core-combined-v3", name="Portfólio Combinado V3", description="Adaptativa", strategy_profile="portfolio_v3_adaptive_union_shadow", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")
        column = html[html.index('data-family="combined"'):]
        self.assertIn("1 variante", column)
        self.assertIn(">Portfólio Combinado V3</h3>", column)

    def test_catalog_stacks_second_zigzag_variant_in_same_family(self) -> None:
        bots = [
            BotCatalogItem(id="core-zigzag-v3", name="ZigZag Scalper V3", description="Adaptativo", strategy_profile="zigzag_scalper_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-zigzag-v2", name="ZigZag Scalper V2", description="Tick estrutural", strategy_profile="zigzag_scalper_v2_shadow", symbol="XAUUSD", timeframe="M5"),
            BotCatalogItem(id="core-zigzag", name="ZigZag Scalper", description="Base", strategy_profile="happy_gold_zigzag_scalper", symbol="XAUUSD", timeframe="M5"),
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")

        zigzag_start = html.index('data-family="zigzag"')
        stochastic_start = html.index('data-family="stochastic"')
        zigzag_column = html[zigzag_start:stochastic_start]
        self.assertIn("3 variantes", zigzag_column)
        self.assertIn("Estratégia-base", zigzag_column)
        self.assertIn("Variação 1", zigzag_column)
        self.assertIn("ZigZag Scalper V2", zigzag_column)
        self.assertLess(zigzag_column.index(">ZigZag Scalper</h3>"), zigzag_column.index(">ZigZag Scalper V2</h3>"))
        self.assertLess(zigzag_column.index(">ZigZag Scalper V2</h3>"), zigzag_column.index(">ZigZag Scalper V3</h3>"))
        self.assertIn("display:flex; flex-direction:column", html)

    def test_catalog_renders_only_selected_strategies(self) -> None:
        active_bots = [
            BotCatalogItem(id=f"bot-{index}", name=name, description="Teste", strategy_profile=profile, symbol="XAUUSD", timeframe="M5")
            for index, name, profile in [
                (6, "Stochastic Sell 18 UTC", "stochastic_sell_session"),
                (7, "Tendência Multitemporal", "multitimeframe_trend_pullback"),
                (11, "Portfólio 7/6 · 100/100", "portfolio_6_7_100_100"),
                (12, "ZigZag Scalper", "happy_gold_zigzag_scalper"),
                (13, "ZigZag Scalper · Confirmação de Regime", "happy_gold_zigzag_regime_confirmed"),
                (16, "ZigZag Scalper + Portfólio 7/6 · 100/100", "happy_gold_portfolio_100_100"),
            ]
        ]

        html = bytes(render_catalog_page(active_bots).body).decode("utf-8")

        self.assertNotIn("Arquivadas", html)
        self.assertIn('id="equity-chart"', html)
        self.assertIn("/api/backtest-market-chart?symbol=XAUUSD", html)
        self.assertIn('data-resolution="1m"', html)
        self.assertIn('data-resolution="1h"', html)
        self.assertIn('data-resolution="1d" class="selected"', html)
        self.assertIn('data-days="7"', html)
        self.assertIn('data-days="365" class="selected"', html)
        self.assertIn('data-days="1095">3A', html)
        self.assertIn('data-risk-mode="normalized" class="selected">1% Risk/Trade', html)
        self.assertNotIn('data-risk-mode="operational"', html)
        self.assertIn("chartResolution='1d',chartDays=365", html)
        self.assertIn("&mode=normalized", html)
        self.assertIn('id="chart-fit"', html)
        self.assertIn('id="refresh-history"', html)
        self.assertIn("/api/history/refresh?symbol=XAUUSD&days='+chartDays", html)
        self.assertIn("/static/vendor/lightweight-charts/lightweight-charts.standalone.production.js", html)
        self.assertIn("LotusEquityChart.create", html)
        self.assertIn("ZigZag Scalper", html)
        self.assertNotIn("Happy Gold", html)
        self.assertIn('/growth-simulator', html)
        self.assertIn('/operations', html)
        self.assertEqual(html.count('class="strategy-family"'), 4)
        self.assertNotIn('data-family="original"', html)
        self.assertIn('data-family="zigzag"', html)
        self.assertIn('data-family="stochastic"', html)
        self.assertIn('data-family="multitimeframe"', html)
        self.assertIn('data-family="combined"', html)
        self.assertIn(">Combined</h2>", html)
        self.assertIn(">Scalp</h2>", html)
        self.assertIn(">Sell</h2>", html)
        self.assertIn(">Buy</h2>", html)
        self.assertEqual(html.count('class="strategy-card-row card"'), 6)

    def test_catalog_has_card_and_family_chart_controls(self) -> None:
        bots = [
            BotCatalogItem(
                id="core-stochastic",
                name="Stochastic Sell",
                description="Base",
                strategy_profile="stochastic_sell_session",
                symbol="XAUUSD",
                timeframe="M5",
            )
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")

        self.assertIn('data-chart-bot="core-stochastic"', html)
        self.assertIn('data-chart-family-toggle="stochastic"', html)
        self.assertIn('data-chart-family-only="stochastic"', html)
        self.assertIn("2lotus:equity-visible-strategies:v2", html)
        self.assertIn('/static/equity-chart.js?v=6', html)
        self.assertIn("aria-pressed", html)
        self.assertIn("Somente esta", html)
        self.assertIn("strategyFamily(item.strategy_profile)==='combined'", html)
        self.assertIn("setVisibleBotIds", html)
        self.assertIn("Pelo menos uma estratégia deve permanecer visível", html)

    def test_authenticated_pages_use_shared_admin_sidebar(self) -> None:
        html = bytes(render_catalog_page([]).body).decode("utf-8")

        self.assertIn('class="has-app-shell"', html)
        self.assertIn('class="app-sidebar"', html)
        self.assertIn('class="app-nav-link active" href="/bots" aria-current="page"', html)
        self.assertIn('href="/operations"', html)
        self.assertIn('href="/history"', html)
        self.assertIn('href="/growth-simulator"', html)
        self.assertIn('href="/compare"', html)
        self.assertIn('/static/admin-shell.css?v=2', html)
        self.assertIn('/static/admin-shell.js?v=1', html)
        self.assertIn('data-sidebar-open', html)
        self.assertIn('data-sidebar-close', html)
        self.assertLess(html.index('href="/bots"'), html.index('href="/growth-simulator"'))
        self.assertLess(html.index('href="/growth-simulator"'), html.index('href="/compare"'))
        self.assertLess(html.index('href="/compare"'), html.index('href="/operations"'))
        self.assertLess(html.index('href="/operations"'), html.index('href="/history"'))

    def test_history_page_renders_live_year_progress(self) -> None:
        html = bytes(render_history_page().body).decode("utf-8")

        self.assertIn('class="app-nav-link active" href="/history"', html)
        self.assertIn("Fontes de ticks", html)
        self.assertIn("Dukascopy", html)
        self.assertIn("Fusion Markets · MT5", html)
        self.assertIn("Histórico baixado", html)
        self.assertIn('href="/history?source=dukascopy"', html)
        self.assertIn('href="/history?source=fusion"', html)
        self.assertIn("preço e spread não são intercambiáveis entre corretoras", html)
        self.assertIn("/api/history/progress?source=dukascopy", html)
        self.assertIn('id="overall-bar"', html)
        self.assertIn('id="year-list"', html)
        self.assertIn("Anos equivalentes baixados", html)
        self.assertIn("setInterval", html)

        fusion_html = bytes(render_history_page("fusion").body).decode("utf-8")
        self.assertIn("Aguardando exportação", fusion_html)
        self.assertIn("/api/history/progress?source=fusion", fusion_html)

    def test_strategy_cards_follow_shared_admin_visual_system(self) -> None:
        css_path = Path(__file__).parents[1] / "app" / "static" / "admin-shell.css"
        css = css_path.read_text(encoding="utf-8")

        self.assertIn(".app-content .strategy-card-row.card", css)
        self.assertIn("height: 330px", css)
        self.assertIn("background: var(--shell-surface-raised)", css)
        self.assertIn("-webkit-line-clamp: 3", css)

    def test_login_remains_outside_authenticated_shell(self) -> None:
        html = bytes(render_login_page().body).decode("utf-8")

        self.assertNotIn('class="app-sidebar"', html)
        self.assertNotIn('/static/admin-shell.css', html)

    def test_growth_simulator_has_custom_balance_and_risk_controls(self) -> None:
        html = bytes(render_growth_simulator_page().body).decode("utf-8")

        self.assertIn('id="capital"', html)
        self.assertIn('id="risk"', html)
        self.assertNotIn('data-mode="normalized"', html)
        self.assertNotIn('data-mode="operational"', html)
        self.assertIn("/api/growth-comparison", html)
        self.assertIn('id="chart"', html)
        self.assertIn('value="10000"', html)
        self.assertIn('value="1"', html)
        self.assertIn("Replay histórico por estratégia", html)
        self.assertNotIn("Cinza: referência", html)
        self.assertNotIn("data.reference,color:'#777'", html)

    def test_comparison_page_renders_six_active_bots(self) -> None:
        bots = [
            BotCatalogItem(
                id=f"bot-{index}",
                name=name,
                description="Teste",
                strategy_profile=profile,
                symbol="XAUUSD",
                timeframe="M5",
            )
            for index, name, profile in [
                (6, "Stochastic Sell 18 UTC", "stochastic_sell_session"),
                (7, "Tendência Multitemporal", "multitimeframe_trend_pullback"),
                (11, "Portfólio 7/6 · 100/100", "portfolio_6_7_100_100"),
                (12, "ZigZag Scalper", "happy_gold_zigzag_scalper"),
                (13, "ZigZag Scalper · Confirmação de Regime", "happy_gold_zigzag_regime_confirmed"),
                (16, "ZigZag Scalper + Portfólio 7/6 · 100/100", "happy_gold_portfolio_100_100"),
            ]
        ]

        response = render_comparison_page(bots)
        html = bytes(response.body).decode("utf-8")

        self.assertIn("Estratégias ativas", html)
        self.assertIn("Stochastic Sell 18 UTC", html)
        self.assertIn("Tendência Multitemporal", html)
        self.assertIn("Portfólio 7/6 · 100/100", html)
        self.assertIn("ZigZag Scalper", html)
        self.assertIn("ZigZag Scalper · Confirmação de Regime", html)
        self.assertNotIn("ZigZag Scalper · Reteste ATR", html)
        self.assertIn("Expectativa (R)", html)
        self.assertIn("Drawdown (R)", html)
        self.assertIn('data-field="expectancy-r"', html)
        self.assertIn('data-field="drawdown-r"', html)
        self.assertIn("ZigZag Scalper + Portfólio 7/6 · 100/100", html)
        self.assertNotIn("Happy Gold", html)
        self.assertIn("<strong>6</strong>", html)
        self.assertIn("/api/equity-comparison", html)
        self.assertIn('data-days="90"', html)
        self.assertIn('data-days="365" class="selected"', html)
        self.assertIn('data-days="1095"', html)
        self.assertIn("1% Risk/Trade", html)

    def test_results_page_defaults_to_long_historical_validation(self) -> None:
        bot = BotCatalogItem(
            id="bot-16",
            name="ZigZag Scalper + Portfólio",
            description="Teste",
            strategy_profile="happy_gold_portfolio_100_100",
            symbol="XAUUSD",
            timeframe="M5",
        )

        html = bytes(render_results_page(bot).body).decode("utf-8")

        self.assertIn("Validação histórica", html)
        self.assertIn('<option value="120">120 dias</option>', html)
        self.assertIn('<option value="365" selected>365 dias</option>', html)
        self.assertIn("/api/bots/bot-16/historical-replay?days=", html)
        self.assertIn("Preço e eventos simulados", html)
        self.assertIn("Premissas do replay", html)

    def test_operations_page_loads_authenticated_health_api(self) -> None:
        html = bytes(render_operations_page().body).decode("utf-8")
        self.assertIn("/api/operations", html)
        self.assertIn("Saúde operacional", html)
        self.assertIn('class="app-nav-link active" href="/operations" aria-current="page"', html)

    def test_account_page_shows_live_financial_fields_and_refreshes(self) -> None:
        bots = [BotCatalogItem(id="core-zigzag-v3", name="ZigZag Scalper V3", description="Teste", strategy_profile="zigzag_scalper_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5")]
        html = bytes(render_account_page(bots).body).decode("utf-8")

        self.assertIn("Saldo atual", html)
        self.assertIn("Saldo inicial", html)
        self.assertIn("Lucro flutuante", html)
        self.assertIn("Realizado hoje", html)
        self.assertIn("ID da conta", html)
        self.assertIn("Corretora", html)
        self.assertIn("Estratégias ativas", html)
        self.assertIn("ZigZag Scalper V3", html)
        self.assertIn("/api/account", html)
        self.assertIn("setInterval(refresh,10000)", html)
        self.assertIn('class="app-nav-link active" href="/account" aria-current="page"', html)


if __name__ == "__main__":
    unittest.main()
