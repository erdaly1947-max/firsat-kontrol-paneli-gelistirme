"""Regression checks for the Sürüm 1 desktop-panel contracts."""
import ast
import json
import math
from pathlib import Path
import unittest
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "tek_motor_paneli.pyw"
RADAR_PATH = ROOT / "binance_erken_firsat_radari.py"
PANEL_SOURCE = PANEL_PATH.read_text(encoding="utf-8")
RADAR_SOURCE = RADAR_PATH.read_text(encoding="utf-8")
PANEL_TREE = ast.parse(PANEL_SOURCE, filename=str(PANEL_PATH))


def _method(name):
    panel_class = next(
        node for node in PANEL_TREE.body
        if isinstance(node, ast.ClassDef) and node.name == "ControlPanel"
    )
    return next(
        node for node in panel_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


class PanelUIContractTests(unittest.TestCase):
    def test_candidate_table_keeps_both_usdt_prices_btc_relative_strength_and_decision(self):
        method = _method("_build_ui")
        columns = next(
            node.value for node in ast.walk(method)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "columns" for target in node.targets)
        )
        values = tuple(ast.literal_eval(item) for item in columns.elts)
        self.assertEqual(
            values,
            ("symbol", "price", "btcturk_price", "score", "timeframe", "phase", "freshness", "btc_relative", "decision", "narrative"),
        )
        self.assertFalse(any("diff" in value.lower() for value in values))

    def test_stale_candidate_cannot_get_strong_opportunity_style(self):
        method = _method("_render_state")
        strong_assignment = next(
            node for node in ast.walk(method)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "strong" for target in node.targets)
        )
        expression = ast.unparse(strong_assignment.value)
        self.assertIn("CANLI AKIŞ GÜNCEL", expression)

    def test_opportunity_and_stop_alert_patterns_are_distinct(self):
        source = ast.unparse(_method("_write_alarm_wave"))
        self.assertIn("for _ in range(3)", source)
        self.assertIn("for _ in range(4)", source)
        self.assertIn("880.0", source)
        self.assertIn("1175.0", source)
        self.assertIn("1568.0", source)

    def test_stop_loss_crossing_selects_distinct_stop_alert(self):
        source = ast.unparse(_method("_check_level_watch"))
        self.assertIn("stop_triggered", source)
        self.assertIn("_play_alert", source)
        self.assertIn("stop", source)
        self.assertIn("opportunity", source)

    def test_selected_coin_details_include_conditional_trade_levels(self):
        source = ast.unparse(_method("_selection_changed"))
        for field in ("entry_zone_low", "entry_zone_high", "breakout_level", "stop_loss", "targets"):
            self.assertIn(field, source)
        self.assertIn("targets[:3]", source)
        self.assertIn("risk_reward", source)
        self.assertIn("geçersizleşme", source.lower())

    def test_engine_exit_disables_level_tracking(self):
        source = ast.unparse(_method("_poll"))
        self.assertIn("Seviye Takibi: Kapalı", source)
        self.assertIn("motor durdu", source)

    def test_live_stream_and_historical_candle_readiness_are_separate(self):
        source = PANEL_SOURCE
        self.assertIn("CANLI AKIŞ  ·  GÜNCEL", source)
        self.assertIn("CANLI AKIŞ  ·  UYARI", source)
        self.assertIn("GEÇMİŞ MUMLAR  ·  HAZIR", source)
        self.assertIn("GEÇMİŞ MUMLAR  ·  BEKLİYOR", source)
        self.assertIn("history_ready = engine_running and", source)

    def test_black_background_white_text_and_nonduplicated_inner_title(self):
        source = PANEL_SOURCE
        self.assertIn('black, white = "#000000", "#FFFFFF"', source)
        self.assertIn('self.configure(background=black)', source)
        self.assertIn('background="#000000", cursor="hand2"', source)
        self.assertIn("DwmSetWindowAttribute", source)
        self.assertNotIn("self.title_label =", source)
        self.assertIn("Başlat", source)
        self.assertIn("Durdur", source)
        self.assertNotIn('text="Kayıtlar"', source)

    def test_toolbar_order_and_text_size_replaces_brightness(self):
        source = PANEL_SOURCE
        labels = [
            'text="Başlat"', 'text="Durdur"', 'text="Pariteleri Güncelle"',
            'text="Günlük Rapor"', 'text="Analiz Raporu"', 'text="Sorun Giderme ZIP"',
            'text="Seviye Takibi: Kapalı"', 'text="Sesli Bildirim: Açık" if self.alarm_enabled else "Sesli Bildirim: Kapalı"',
            'text="Ses Testi"', 'text="Yazı boyutu"',
        ]
        positions = [source.index(label) for label in labels]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('base, hover = "#c62828", "#ff7f8b"', source)
        self.assertIn('style.map("Slim.Horizontal.TScale", background=[("active", white), ("pressed", white)])', source)
        self.assertIn("from_=8, to=15", source)
        self.assertIn('orient="horizontal"', source)
        self.assertIn('self.font_size_scale.bind("<ButtonRelease-1>", self._save_font_size)', source)
        self.assertIn('self.font_size_scale.bind("<KeyRelease>", self._save_font_size)', source)
        self.assertIn('self.font_size_label.configure(text=f"{size} punto")', source)
        self.assertNotIn("self.panel_brightness", source)
        self.assertNotIn("self._brightness_moved", source)

    def test_resizable_diagnostics_and_technical_details_exist(self):
        source = PANEL_SOURCE
        self.assertIn("ttk.Panedwindow(self.radar_page, orient=", source)
        self.assertIn("Teknik ayrıntılar ▸", source)
        self.assertIn("Tanılama ve son kayıtlar ▸", source)
        self.assertIn("Kayıt klasörünü aç", source)
        self.assertIn('orient="horizontal", style="Slim.Horizontal.TScrollbar"', source)
        self.assertIn("_toggle_diagnostics", source)
        self.assertIn("_toggle_technical_details", source)

    def test_motor_fields_used_by_panel_are_present_in_engine_contract(self):
        core = (ROOT / "radar_core.py").read_text(encoding="utf-8")
        for field in (
            "risk_plan", "relative_strength_vs_btc_pct_points", "btc_return_correlation",
            "strong_alarm_eligible", "strong_opportunity_qualified", "data_freshness",
            "data_completeness", "critical_level_loss_timeframes", "latest_confirmed_support_zone",
            "nearest_relevant_resistance_zone", "relative_volatility_ratio",
        ):
            self.assertIn(field, core)
        self.assertIn('"timeframes"', core)
        self.assertIn('"targets"', core)

    def test_panel_settings_use_saved_font_size_and_remove_brightness_keys(self):
        settings = json.loads((ROOT / "ayarlar.json").read_text(encoding="utf-8-sig"))
        ui = settings.get("panel_ui", {})
        self.assertEqual(ui.get("font_size"), 8)
        source = PANEL_SOURCE
        self.assertIn('font_size = panel.get("font_size", 8)', source)
        self.assertIn("self.font_size = _normalize_font_size(font_size)", source)
        self.assertIn('"font_size": int(self.font_size)', source)
        self.assertIn('ui.pop("screen_brightness", None)', source)
        self.assertIn('ui.pop("panel_brightness", None)', source)

    def test_font_size_normalization_defaults_clamps_and_preserves_saved_values(self):
        function = next(
            node for node in PANEL_TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == '_normalize_font_size'
        )
        namespace = {"math": __import__("math"), "Any": __import__("typing").Any}
        module = ast.Module(body=[function], type_ignores=[])
        exec(compile(module, str(PANEL_PATH), 'exec'), namespace)
        normalize = namespace['_normalize_font_size']
        self.assertEqual(normalize(None), 8)
        self.assertEqual(normalize('12'), 12)
        self.assertEqual(normalize(12.6), 13)
        self.assertEqual(normalize(7), 8)
        self.assertEqual(normalize(16), 15)
        self.assertEqual(normalize('not-a-number'), 8)
        self.assertEqual(normalize(float('nan')), 8)

    def test_price_rendering_is_shared_with_risk_plan_levels(self):
        source = PANEL_SOURCE
        self.assertIn("from arayuz_bicim import format_price as _format_market_price", source)
        self.assertIn("return _format_market_price(value)", source)
        core = (ROOT / "radar_core.py").read_text(encoding="utf-8")
        self.assertIn("def _display_price(value: float)", core)
        self.assertIn('"invalid_if": f"{_display_price(stop)}', core)
        self.assertNotRegex(core, r'round\([^\n]*,\s*10\)')

    def test_screenshot_picker_uses_single_file_dialog_and_supports_three_images(self):
        function = next(
            node for node in PANEL_TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == "_choose_screenshot_paths"
        )
        opened_options = []
        file_results = iter([
            "/screenshots/first screen.png",
            "/screenshots/second chart.jpg",
            "",
        ])
        confirm_results = iter([True, False])
        parent = object()

        def open_dialog(**options):
            opened_options.append(options)
            return next(file_results)

        def ask_more(*args, **kwargs):
            return next(confirm_results)

        namespace = {
            "tk": SimpleNamespace(Misc=object),
            "Path": Path,
            "Any": object,
        }
        extracted = ast.Module(body=[function], type_ignores=[])
        exec(compile(extracted, str(PANEL_PATH), "exec"), namespace)
        chosen = namespace["_choose_screenshot_paths"](
            parent, Path("/screenshots"),
            open_dialog=open_dialog, ask_more=ask_more,
        )

        self.assertEqual(len(chosen), 2)
        self.assertEqual(Path(chosen[0]).name, "first screen.png")
        self.assertEqual(Path(chosen[1]).name, "second chart.jpg")
        self.assertEqual(len(opened_options), 2)
        self.assertEqual(opened_options[0]["parent"], parent)
        self.assertEqual(
            [item[1] for item in opened_options[0]["filetypes"]],
            ["*.png", "*.jpg", "*.jpeg", "*.*"],
        )
        self.assertEqual(
            opened_options[1]["initialdir"],
            str(Path(chosen[0]).parent),
        )
        self.assertIn("filedialog.askopenfilename", ast.unparse(function))
        self.assertNotIn("askopenfilenames", ast.unparse(_method("open_screenshot_upload")))



    def test_new_workspace_pages_and_common_controls_are_wired(self):
        source = PANEL_SOURCE
        for key, label in (
            ("overview", "Genel Bakış"),
            ("radar", "Fırsat Radarı"),
            ("tracking", "Aktif Takip"),
            ("analysis", "Parite Analizi"),
            ("narrative", "Naratif Avcısı"),
            ("market", "BTC ve Piyasa"),
            ("plans", "Planlar ve Uyarılar"),
            ("reports", "Raporlar"),
            ("btcturk", "BtcTurk PRO"),
            ("settings", "Sistem ve Ayarlar"),
        ):
            self.assertIn(f'("{key}", "{label}")', source)
        self.assertIn('controls.pack(fill="x", before=self.workspace)', source)
        self.assertIn('status_row.pack(fill="x", before=self.workspace)', source)
        for method_name in (
            "start_engine", "stop_engine", "update_universe", "create_report",
            "create_analysis_report", "create_handoff_zip", "toggle_level_watch",
            "toggle_alarm", "_test_sound", "open_screenshot_upload",
        ):
            self.assertIn(f"command=self.{method_name}", source)

    def test_shared_start_stop_controls_both_live_engines_but_not_historical_backtest(self):
        start = ast.unparse(_method("start_engine"))
        stop = ast.unparse(_method("stop_engine"))
        poll = ast.unparse(_method("_poll"))
        self.assertIn("NARRATIVE_ENGINE_PATH", start)
        self.assertIn("ENGINE_PATH", start)
        self.assertIn("NARRATIVE_STOP_FILE", stop)
        self.assertIn("STOP_FILE", stop)
        self.assertIn("narrative_engine", poll)
        self.assertIn("engine", poll)
        historical_start = ast.unparse(_method("_start_historical_backtest"))
        historical_stop = ast.unparse(_method("_cancel_historical_backtest"))
        self.assertIn("_historical_backtest_thread", historical_start)
        self.assertIn("_historical_backtest_cancel", historical_stop)
        self.assertNotIn("start_engine", historical_start)
        self.assertNotIn("stop_engine", historical_stop)

    def test_narrative_is_not_in_technical_opportunity_score(self):
        self.assertIn('candidate["narrative_support"]', RADAR_SOURCE)
        self.assertIn("strong_alarm_eligible", RADAR_SOURCE)
        self.assertIn('"narrative_early_watch"', RADAR_SOURCE)
        self.assertIn("narrative puanı teknik puandan ayrıdır", PANEL_SOURCE.casefold())

    def test_narrative_first_early_watch_is_visible_in_radar_without_technical_signal(self):
        refresh = ast.unparse(_method("_refresh_radar_narrative_watch"))
        open_watch = ast.unparse(_method("_open_narrative_watch_from_radar"))
        self.assertIn("early_watch", refresh)
        self.assertIn("radar_narrative_tree", refresh)
        self.assertIn("_show_workspace_page", open_watch)
        self.assertIn("narrative_watch_tree", open_watch)
        self.assertNotIn("_select_candidate_by_symbol", open_watch)
        builder = ast.unparse(_method("_build_ui"))
        self.assertIn("Naratif erken izleme", builder)

    def test_narrative_list_shows_related_coin_symbols_and_missing_data_state(self):
        builder = ast.unparse(_method("_build_additional_workspace_pages"))
        refresh = ast.unparse(_method("_refresh_narrative_page"))
        detail = ast.unparse(_method("_narrative_show_selected"))
        self.assertIn('"data"', builder)
        self.assertIn("İlişkili coinler", builder)
        self.assertIn("coin_label", refresh)
        self.assertIn("EKSİK", refresh)
        self.assertIn("data_freshness_seconds", detail)
        self.assertIn("average_volume_change_24h", detail)
        self.assertIn("discovery_sources", detail)

    def test_narrative_source_selection_explains_real_connection_and_configuration_state(self):
        builder = ast.unparse(_method("_build_additional_workspace_pages"))
        refresh = ast.unparse(_method("_refresh_narrative_page"))
        detail = ast.unparse(_method("_narrative_show_source_status"))
        self.assertIn("narrative_source_tree", builder)
        self.assertIn("<<TreeviewSelect>>", builder)
        self.assertIn("last_success_utc", detail)
        for required in (
            "COINGECKO_DEMO_API_KEY",
            "narrative_rss_feeds",
            "narrative_rss_interval_seconds",
            "aixbt_topics",
            "cmc_market_activity",
            "dex_profiles",
            "aixbt_project_mapping",
            "bağımsız",
        ):
            self.assertIn(required, detail)
        self.assertIn("error", detail)
        self.assertIn("last_attempt_utc", detail)

    def test_analysis_chart_uses_only_motor_closed_candles_and_eight_timeframes(self):
        refresh = ast.unparse(_method("_refresh_analysis_view"))
        drawing = ast.unparse(_method("_draw_analysis_chart"))
        builder = ast.unparse(_method("_build_additional_workspace_pages"))
        self.assertIn("recent_closed_candles", refresh)
        self.assertIn("recent_closed_candles", drawing)
        self.assertIn("Gerçek veri gelene kadar örnek mum çizilmez", drawing)
        for timeframe in ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"):
            self.assertIn(f"'{timeframe}'", builder)
        self.assertIn("recent_closed_candles", PANEL_SOURCE)
        self.assertNotIn("makeBars", PANEL_SOURCE)

    def test_panedwindow_orientation_is_selected_before_creation_and_never_mutated(self):
        source = PANEL_SOURCE
        self.assertIn('self._pane_orientation = "vertical" if self.window_width < 1220 else "horizontal"', source)
        self.assertIn('ttk.Panedwindow(self.radar_page, orient=self._pane_orientation)', source)
        adapt = ast.unparse(_method("_adapt_panes"))
        self.assertNotIn(".configure(orient=", adapt)

    def test_chart_drawing_tools_persist_by_symbol_and_timeframe(self):
        source = PANEL_SOURCE
        for method_name in (
            "_analysis_drawing_key", "_save_analysis_drawings",
            "_analysis_chart_click", "_analysis_delete_last",
            "_analysis_undo_delete",
        ):
            _method(method_name)
        self.assertIn("chart_drawings", source)
        self.assertIn("self.panel_settings[\"chart_drawings\"]", source)
        self.assertIn("after(5000, lambda: self._analysis_expire_undo(token))", source)
        self.assertIn('("İmleç", "Trend çizgisi", "Paralel kanal")', source)

    def test_active_tracking_is_limited_to_five_and_saved_in_panel_settings(self):
        add_method = ast.unparse(_method("_tracking_add_selected"))
        save_method = ast.unparse(_method("_save_panel_settings"))
        self.assertIn("len(self.tracked_symbols) >= 5", add_method)
        self.assertIn("tracked_symbols", add_method)
        self.assertIn("tracked_symbols", save_method)

    def test_chart_shows_conditional_levels_without_mislabeling_them_active(self):
        helper_node = next(
            node for node in PANEL_TREE.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_analysis_plan_overlay_levels"
        )

        def safe_float(value):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            number = float(value)
            return number if math.isfinite(number) else None

        namespace = {"Any": Any, "_safe_float": safe_float}
        exec(compile(ast.Module(body=[helper_node], type_ignores=[]), str(PANEL_PATH), "exec"), namespace)
        present = namespace["_analysis_plan_overlay_levels"]
        plan = {
            "status": "FİYAT GİRİŞ BÖLGESİNDE — KOŞULLU",
            "entry_zone_low": 100.0,
            "entry_zone_high": 102.0,
            "stop_loss": 95.0,
            "targets": [{"price": 110.0}, {"price": 99.0}, {"price": "bad"}],
        }

        label, levels = present(plan)
        self.assertEqual(label, "KOŞULLU PLAN · ETKİN DEĞİL")
        self.assertEqual(
            [(level[0], level[1]) for level in levels],
            [
                (100.0, "GİRİŞ ALT"),
                (102.0, "GİRİŞ ÜST"),
                (95.0, "ZARAR-KES / GEÇERSİZLİK"),
                (110.0, "HEDEF 1"),
            ],
        )

        active_plan = dict(plan, active=True)
        active_label, active_levels = present(active_plan)
        self.assertEqual(active_label, "AKTİF PLAN")
        self.assertEqual(active_levels, levels)

        invalid_label, invalid_levels = present(dict(plan, stop_loss=101.0))
        self.assertEqual(invalid_label, "PLAN SEVİYELERİ GEÇERSİZ")
        self.assertEqual(invalid_levels, [])

        range_node = next(
            node for node in PANEL_TREE.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_analysis_chart_price_range"
        )
        range_namespace = {"Any": Any, "_safe_float": safe_float}
        exec(compile(ast.Module(body=[range_node], type_ignores=[]), str(PANEL_PATH), "exec"), range_namespace)
        scale = range_namespace["_analysis_chart_price_range"]
        layers = {
            "entry": SimpleNamespace(get=lambda: True),
            "stop": SimpleNamespace(get=lambda: True),
            "targets": SimpleNamespace(get=lambda: True),
        }
        expanded = scale([98.0, 100.0, 105.0], levels, layers)
        self.assertIsNotNone(expanded)
        self.assertGreater(expanded[1], 110.0)
        targets_hidden = dict(layers, targets=SimpleNamespace(get=lambda: False))
        reduced = scale([98.0, 100.0, 105.0], levels, targets_hidden)
        self.assertLess(reduced[1], expanded[1])

        drawing = ast.unparse(_method("_draw_analysis_chart"))
        self.assertIn("_analysis_plan_overlay_levels(plan)", drawing)
        self.assertIn("_analysis_chart_price_range(candle_prices, plan_levels, layers)", drawing)
        self.assertIn("KOŞULLU", drawing)
        self.assertIn("EMİR GÖNDERİLMEZ", drawing)

    def test_package_workflow_is_for_s1_and_package_is_explicit(self):
        workflow = (ROOT / ".github" / "workflows" / "validate-and-package.yml").read_text(encoding="utf-8")
        self.assertIn("Validate and package Sürüm 01", workflow)
        self.assertIn("Firsat-Kontrol-Paneli-Surum-01.zip", workflow)
        self.assertIn('tag = "surum-01"', workflow)
        self.assertNotIn("Firsat-Kontrol-Paneli-Surum-00.zip", workflow)
        self.assertIn("publish_package:", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("Main pushes and pull requests run validation only.", workflow)
        self.assertEqual(workflow.count("inputs.publish_package == true"), 3)
        self.assertNotIn("contains(github.event.head_commit.message, '[package]')", workflow)
        self.assertIn("checksum_path.write_text", workflow)
        self.assertIn("uses: actions/upload-artifact@v7", workflow)


    def test_selected_coin_details_distinguish_alarm_permission_from_strong_opportunity(self):
        source = ast.unparse(_method("_selection_changed"))
        self.assertIn("strong_opportunity_gate_reasons", source)
        self.assertIn("Güçlü alarm uygunluk filtresi (izin):", source)
        self.assertIn("Gerçek güçlü fırsat koşulları:", source)
        self.assertIn("Engel gerekçesi raporda bulunmuyor.", source)
        self.assertNotIn("Güçlü alarm koşulu:", source)


if __name__ == "__main__":
    unittest.main()
