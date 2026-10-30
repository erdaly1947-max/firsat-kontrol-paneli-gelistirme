"""Windows Tkinter runtime smoke test for the actual desktop UI.

The test creates the real window and page widgets, visits every workspace,
changes every chart timeframe, and dispatches the shared toolbar events.
Network refresh and trading-engine starts are deliberately stubbed.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("This runtime smoke test must run on a Windows GitHub runner.")

    panel_path = ROOT / "tek_motor_paneli.pyw"
    loader = importlib.machinery.SourceFileLoader("fkp_panel_runtime_smoke", str(panel_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("Tkinter panel module spec could not be created.")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    original_price_loop = module.ControlPanel._btcturk_price_loop
    module.ControlPanel._btcturk_price_loop = lambda self: None

    app = None
    try:
        app = module.ControlPanel()
        app.withdraw()
        app._btcturk_pro_load_pair = lambda _symbol: None
        app._open_btcturk_pro_from_radar = lambda: app._show_workspace_page("btcturk")

        expected_pages = {
            "overview", "radar", "tracking", "analysis", "market",
            "plans", "reports", "btcturk", "settings",
        }
        if set(app.workspace_page_frames) != expected_pages:
            raise AssertionError(
                f"Unexpected workspace pages: {sorted(app.workspace_page_frames)}"
            )
        if set(app.workspace_nav_buttons) != expected_pages:
            raise AssertionError(
                f"Navigation buttons do not match page frames: {sorted(app.workspace_nav_buttons)}"
            )

        for page in (
            "overview", "radar", "tracking", "analysis", "market",
            "plans", "reports", "btcturk", "settings",
        ):
            app.workspace_nav_buttons[page].invoke()
            app.update_idletasks()
            if app.workspace_current_page != page:
                raise AssertionError(f"Navigation did not select page: {page}")
            if app.workspace_page_frames[page].winfo_manager() != "pack":
                raise AssertionError(f"Page frame is not packed: {page}")
            if not app.workspace_nav_buttons[page].instate(["disabled"]):
                raise AssertionError(f"Selected navigation button is not disabled: {page}")

        app.workspace_nav_buttons["analysis"].invoke()
        expected_timeframes = ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
        if set(app.analysis_timeframe_buttons) != set(expected_timeframes):
            raise AssertionError("Chart timeframe controls are incomplete.")
        for timeframe in expected_timeframes:
            app.analysis_timeframe_buttons[timeframe].invoke()
            app.update_idletasks()
            if app.analysis_timeframe_var.get() != timeframe:
                raise AssertionError(f"Chart timeframe action failed: {timeframe}")

        if not app.analysis_canvas.winfo_exists():
            raise AssertionError("Analysis chart canvas was not created.")

        # Exercise the real Canvas event bindings without starting the engine.
        callback_errors = []
        app.report_callback_exception = lambda exc_type, exc, _tb: callback_errors.append(
            f"{exc_type.__name__}: {exc}"
        )
        app.deiconify()
        app.update()

        # Resize across the orientation threshold. The initial ttk orientation is
        # immutable, so this must never raise a Tk callback error.
        original_orientation = app._pane_orientation
        app.geometry("1320x820+0+0")
        app.update()
        app.geometry("1000x820+0+0")
        app.update()
        if app._pane_orientation != original_orientation:
            raise AssertionError("Pane orientation changed after construction.")
        if callback_errors:
            raise AssertionError("Tk callback errors during resize: " + "; ".join(callback_errors))

        dispatched = []
        app.start_button.configure(command=lambda: dispatched.append("start"), state="normal")
        app.stop_button.configure(
            state="normal", command=lambda: dispatched.append("stop")
        )
        app.update()
        for name, button in (("start", app.start_button), ("stop", app.stop_button)):
            if button.winfo_ismapped() != 1:
                raise AssertionError(f"{name} toolbar button is not mapped.")
            if not button.bind("<Button-1>"):
                raise AssertionError(f"{name} toolbar button has no click binding.")
            button.event_generate(
                "<Button-1>",
                x=max(1, button.winfo_width() // 2),
                y=max(1, button.winfo_height() // 2),
                when="tail",
            )
        app.update()
        if dispatched != ["start", "stop"]:
            raise AssertionError(f"Shared toolbar events failed: {dispatched}")
        if callback_errors:
            raise AssertionError("Tk callback errors: " + "; ".join(callback_errors))

        print("WINDOWS_TK_WINDOW_CREATE_OK")
        print("WINDOWS_ALL_9_WORKSPACE_NAVIGATION_OK")
        print("WINDOWS_ALL_8_CHART_TIMEFRAMES_OK")
        print("WINDOWS_SHARED_START_STOP_EVENT_BINDINGS_OK")
        return 0
    finally:
        if app is not None:
            try:
                app.destroy()
            except module.tk.TclError:
                pass
        module.ControlPanel._btcturk_price_loop = original_price_loop


if __name__ == "__main__":
    raise SystemExit(main())
