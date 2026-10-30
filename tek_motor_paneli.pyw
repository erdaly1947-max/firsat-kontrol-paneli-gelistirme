"""FIRSAT-KONTROL PANELİ — yerel Tkinter arayüzü, tek Binance analiz motoru.

Bu uygulama yalnızca halka açık piyasa verilerini kullanır. Hesap/bakiye/pozisyon
verilerine erişmez ve emir göndermez. A/B/C değerleri araştırma aşamalarıdır.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any
import platform

from arayuz_bicim import format_price as _format_market_price
import wave
import struct
import zipfile

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from analysis_report import (
    build_analysis_report,
    build_image_replacement_plan,
    download_active_image,
    fetch_image_manifest,
    make_image_thumbnail,
    upload_image_batch,
    validate_image_bytes,
    validate_image_file,
    compress_analysis_report,
    gzip_compress_bytes,
    load_connection_config,
    upload_analysis_report,
    upload_json_report,
    upload_troubleshooting_zip,
)

from ortak_piyasa import fetch_btcturk_usdt_last_prices
from btcturk_pro import (
    TIMEFRAMES as BTCTURK_PRO_TIMEFRAMES,
    analyze_btcturk_pro,
    estimate_orderbook_execution,
    fetch_binance_comparison,
    fetch_btcturk_pro_candles,
    fetch_btcturk_pro_markets,
    fetch_btcturk_pro_orderbook,
    fetch_btcturk_pro_ticker,
    format_exchange_price,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
REPORT_DIR = ROOT / "reports"
RUN_DIR = ROOT / "run"
STATE_PATH = DATA_DIR / "binance_state.json"
SETTINGS_PATH = ROOT / "ayarlar.json"
ENGINE_PATH = ROOT / "binance_erken_firsat_radari.py"
STOP_FILE = RUN_DIR / "stop_radar.flag"
PANEL_LOG_PATH = LOG_DIR / "tek_motor_paneli.log"
ENGINE_LOG_PATH = LOG_DIR / "binance_radar.log"
APP_TITLE = "FIRSAT-KONTROL PANELİ"
SCREENSHOTS_DIR = Path(r"C:\Users\erdal\OneDrive\Resimler\Screenshots")

for _directory in (DATA_DIR, LOG_DIR, REPORT_DIR, RUN_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


def _make_logger() -> logging.Logger:
    logger = logging.getLogger("firsat_kontrol_paneli")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            PANEL_LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    return logger


LOGGER = _make_logger()


def _choose_screenshot_paths(
    parent: tk.Misc,
    initialdir: str | Path,
    *,
    open_dialog: Any = None,
    ask_more: Any = None,
) -> tuple[str, ...]:
    """Choose screenshots one at a time to avoid Windows multi-select dialog issues."""
    if open_dialog is None:
        open_dialog = filedialog.askopenfilename
    if ask_more is None:
        ask_more = messagebox.askyesno

    selected_paths: list[str] = []
    current_directory = str(initialdir)
    image_filetypes = [
        ("PNG görüntüleri", "*.png"),
        ("JPG görüntüleri", "*.jpg"),
        ("JPEG görüntüleri", "*.jpeg"),
        ("Tüm dosyalar", "*.*"),
    ]

    while len(selected_paths) < 3:
        selected = open_dialog(
            parent=parent,
            title="Ekran görüntüsünü seç",
            initialdir=current_directory,
            filetypes=image_filetypes,
        )
        if not selected:
            break

        selected_path = str(selected)
        if selected_path not in selected_paths:
            selected_paths.append(selected_path)
        current_directory = str(Path(selected_path).parent)

        if len(selected_paths) >= 3:
            break
        if not ask_more(
            "Başka görüntü seçilsin mi?",
            f"{Path(selected_path).name} seçildi.\n\nBir görüntü daha eklemek ister misiniz? (En fazla 3 görüntü.)",
            parent=parent,
        ):
            break

    return tuple(selected_paths)


def _normalize_font_size(value: Any, default: int = 8) -> int:
    """Round and clamp a saved/UI font size to the supported 8–15 point range."""
    fallback = max(8, min(15, int(default)))
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if not math.isfinite(numeric):
        return fallback
    return max(8, min(15, int(round(numeric))))


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def _write_gzip_atomic(path: Path, raw: bytes) -> None:
    """Atomically save a gzip-compressed report without leaving partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temp.write_bytes(gzip_compress_bytes(raw))
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _remove_legacy_report_versions(pattern: str, keep_path: Path) -> int:
    """Remove only old timestamped report files generated by this application."""
    removed = 0
    try:
        entries = list(REPORT_DIR.iterdir())
    except OSError:
        return 0
    matcher = re.compile(pattern)
    for candidate in entries:
        if candidate == keep_path or not candidate.is_file():
            continue
        if not matcher.fullmatch(candidate.name):
            continue
        try:
            candidate.unlink()
            removed += 1
        except OSError as exc:
            LOGGER.warning("Eski tarihli rapor kaldırılamadı (%s): %s", candidate.name, exc)
    return removed


def _parse_utc_epoch(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _format_price(value: Any) -> str:
    """Render market prices as ordinary decimal text, not scientific notation."""
    return _format_market_price(value)


def _display_timeframe(value: Any) -> str:
    raw = str(value or "").strip()
    return {
        "5m": "5 dk", "15m": "15 dk", "30m": "30 dk",
        "1h": "1 sa", "4h": "4 sa", "1d": "1 gün",
        "1w": "1 hafta", "1M": "1 ay",
    }.get(raw, raw or "—")


def _format_metric(value: Any, digits: int = 2) -> str:
    number = _safe_float(value)
    return f"{number:.{digits}f}" if number is not None else "—"


def _format_btcturk_price(prices: dict[str, float], symbol: str, updated_at: float | None) -> str:
    if updated_at is None:
        return "veri yok"
    if time.time() - updated_at > 90:
        return "veri eski"
    value = _safe_float(prices.get(symbol.upper()))
    return _format_price(value) if value is not None and value > 0 else "veri yok"


def _format_age(seconds: Any) -> str:
    value = _safe_float(seconds)
    if value is None or value < 0:
        return "bilinmiyor"
    if value < 60:
        return f"{value:.0f} sn"
    if value < 3600:
        return f"{value / 60:.1f} dk"
    if value < 86400:
        return f"{value / 3600:.1f} sa"
    return f"{value / 86400:.1f} gün"


def _short(value: Any, limit: int = 500) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    else:
        text = str(value)
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(128 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def _get_engine_interpreter() -> str:
    executable = Path(sys.executable)
    if executable.name.casefold() == "pythonw.exe":
        sibling = executable.with_name("python.exe")
        if sibling.is_file():
            return str(sibling)
    return str(executable)


def _tail_text(paths: list[Path], *, max_lines: int = 300, max_bytes: int = 128 * 1024) -> str:
    """Return a bounded combined log tail for diagnostics, keeping recent lines first."""
    lines: list[str] = []
    used = 0
    for path in paths:
        try:
            raw = path.read_bytes()
            raw = raw[-max_bytes:]
            text = raw.decode("utf-8", errors="replace")
            group = [f"===== {path.name} =====", *text.splitlines()[-max_lines:]]
        except OSError:
            continue
        for line in reversed(group):
            encoded_size = len(line.encode("utf-8", errors="replace")) + 1
            if len(lines) >= max_lines or used + encoded_size > max_bytes:
                break
            lines.append(line)
            used += encoded_size
        if len(lines) >= max_lines or used >= max_bytes:
            break
    return "\n".join(reversed(lines)) + ("\n" if lines else "")


def _format_btc_context_summary(state: dict[str, Any]) -> str:
    context = state.get("btc_market_context")
    context = context if isinstance(context, dict) else {}
    gate = state.get("btc_strong_alert_gate")
    gate = gate if isinstance(gate, dict) else {}
    if state.get("btc_market_context_freshness") != "CANLI AKIŞ GÜNCEL" or context.get("data_completeness") != "TAM":
        return "Veri: UYARI  |  BTC bağlamı eski veya eksik; güçlü fırsat filtresi kapalı."
    tfs = context.get("timeframes")
    tfs = tfs if isinstance(tfs, dict) else {}
    def direction(tf: str) -> str:
        row = tfs.get(tf)
        if not isinstance(row, dict) or row.get("available") is not True:
            return "veri yetersiz"
        return "pozitif" if row.get("bullish") is True else "zayıf" if row.get("price_above_slow_ema") is False else "karışık"
    ref = tfs.get("4h") if isinstance(tfs.get("4h"), dict) else tfs.get("1h", {})
    ref = ref if isinstance(ref, dict) else {}
    def zone_text(zone: Any) -> str:
        if not isinstance(zone, dict):
            return "—"
        low, high, center = (_safe_float(zone.get(k)) for k in ("lower", "upper", "center"))
        if low is not None and high is not None:
            return f"{_format_price(low)}–{_format_price(high)}"
        return _format_price(center) if center is not None else "—"
    losses = context.get("critical_level_loss_timeframes")
    warnings = context.get("risk_warnings")
    losses = losses if isinstance(losses, list) else []
    warnings = warnings if isinstance(warnings, list) else []
    risk = "kritik seviye kaybı uyarısı" if losses or any("SEVİYE KAYBI" in str(x).upper() for x in warnings) else "kayıtlı kritik seviye kaybı yok"
    gate_text = "güçlü fırsat filtresi açık" if gate.get("eligible") is True else "güçlü fırsat filtresi kapalı"
    return (
        f"Ana yön: 1 sa {direction('1h')} / 4 sa {direction('4h')}  |  "
        f"Risk: {risk}  |  Destek: {zone_text(ref.get('latest_confirmed_support_zone'))}  |  "
        f"Direnç: {zone_text(ref.get('nearest_relevant_resistance_zone'))}  |  {gate_text}"
    )


def _format_btc_context_details(state: dict[str, Any]) -> str:
    context = state.get("btc_market_context")
    context = context if isinstance(context, dict) else {}
    gate = state.get("btc_strong_alert_gate")
    gate = gate if isinstance(gate, dict) else {}
    if state.get("btc_market_context_freshness") != "CANLI AKIŞ GÜNCEL" or context.get("data_completeness") != "TAM":
        return "BTC piyasa verisi eksik veya eski. Güçlü fırsat filtresi kapalı.\n" + str(state.get("btc_market_context_warning") or "")
    tfs = context.get("timeframes")
    tfs = tfs if isinstance(tfs, dict) else {}
    lines = ["BTC piyasa teknik ayrıntıları"]
    for tf in ("1h", "4h"):
        row = tfs.get(tf)
        if not isinstance(row, dict) or row.get("available") is not True:
            lines.append(f"{_display_timeframe(tf)}: veri yetersiz")
            continue
        def zone_text(zone: Any) -> str:
            if not isinstance(zone, dict):
                return "teyitli bölge yok"
            low, high, center = (_safe_float(zone.get(k)) for k in ("lower", "upper", "center"))
            if low is not None and high is not None:
                return f"{_format_price(low)}–{_format_price(high)}"
            return _format_price(center) if center is not None else "teyitli bölge yok"
        direction = "pozitif" if row.get("bullish") is True else "zayıf" if row.get("price_above_slow_ema") is False else "karışık"
        lines.append(f"{_display_timeframe(tf)} yön: {direction}")
        lines.append("  Destek: " + zone_text(row.get("latest_confirmed_support_zone")))
        lines.append("  Direnç: " + zone_text(row.get("nearest_relevant_resistance_zone")))
        lines.append("  Kanal: " + str(row.get("channel_status") or "teyitli kanal yok"))
    volatility = _safe_float(context.get("relative_volatility_ratio"))
    lines.append(f"Göreceli oynaklık: {volatility:.2f} kat" if volatility is not None else "Göreceli oynaklık: ölçülemedi")
    lines.append("Güçlü fırsat filtresi: açık" if gate.get("eligible") is True else "Güçlü fırsat filtresi: kapalı")
    losses = context.get("critical_level_loss_timeframes")
    if isinstance(losses, list) and losses:
        lines.append("Kritik seviye kaybı görülen zamanlar: " + ", ".join(_display_timeframe(x) for x in losses))
    warnings = context.get("risk_warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("Risk uyarıları: " + "; ".join(str(x) for x in warnings[:6] if x))
    return "\n".join(lines)


def _format_btc_relative(row: dict[str, Any]) -> str:
    if row.get("btc_market_context_freshness") not in (None, "CANLI AKIŞ GÜNCEL"):
        return "VERİ ESKİ"
    relative = row.get("relative_strength_vs_btc_pct_points")
    relative = relative if isinstance(relative, dict) else {}
    value = _safe_float(relative.get("1h"))
    if value is None:
        return "YETERSİZ"
    label = "GÜÇLÜ" if value >= 0.25 else "ZAYIF" if value <= -0.25 else "NÖTR"
    return f"{label} {value:+.2f}"


def _format_btc_correlation(row: dict[str, Any]) -> str:
    if row.get("btc_market_context_freshness") not in (None, "CANLI AKIŞ GÜNCEL"):
        return "veri eski"
    correlation = row.get("btc_return_correlation")
    correlation = correlation if isinstance(correlation, dict) else {}
    hourly = correlation.get("1h")
    if not isinstance(hourly, dict):
        return "—"
    value = _safe_float(hourly.get("value"))
    observations, minimum = hourly.get("observations"), hourly.get("minimum_required")
    if value is None or not isinstance(observations, int) or not isinstance(minimum, int) or observations < minimum:
        return "yetersiz veri"
    return f"{value:+.2f}"


def _format_candidate_decision_summary(candidate: dict[str, Any]) -> str:
    """Prioritize decision, BTC relationship, technical levels, and blockers."""
    decision = candidate.get("final_decision") or candidate.get("decision_class") or "—"
    phase = candidate.get("phase") or candidate.get("last_known_phase") or "—"
    reason = str(candidate.get("decision_reason") or "Karar gerekçesi henüz yok.")
    relative = candidate.get("relative_strength_vs_btc_pct_points")
    relative = relative if isinstance(relative, dict) else {}
    rel_text = ", ".join(
        f"{_display_timeframe(tf)}: {_safe_float(relative.get(tf)):+.2f} yüzde puanı"
        for tf in ("15m", "1h", "4h") if _safe_float(relative.get(tf)) is not None
    ) or "göreceli güç hesaplanamadı"
    correlations = candidate.get("btc_return_correlation")
    correlations = correlations if isinstance(correlations, dict) else {}
    corr_text = []
    for tf in ("1h", "4h"):
        item = correlations.get(tf)
        if not isinstance(item, dict):
            continue
        value = _safe_float(item.get("value"))
        count, minimum = item.get("observations"), item.get("minimum_required")
        if value is not None and isinstance(count, int) and isinstance(minimum, int) and count >= minimum:
            corr_text.append(f"{_display_timeframe(tf)}: {value:+.2f}")
    corr_text_value = ", ".join(corr_text) or "yeterli eşzamanlı mum yok"
    assessment = candidate.get("btc_correlation_assessment")
    assessment = assessment if isinstance(assessment, dict) else {}
    assessment_text = str(assessment.get("summary") or "Korelasyon risk yorumu yok.")
    timeframe = str(candidate.get("phase_timeframe") or candidate.get("timeframe") or "")
    timeframes = candidate.get("timeframes")
    timeframes = timeframes if isinstance(timeframes, dict) else {}
    selected = timeframes.get(timeframe)
    metrics = selected.get("metrics") if isinstance(selected, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    channel = metrics.get("confirmed_channel")
    channel_text = f"{channel.get('direction', 'kanal')} / {channel.get('status', 'teyitli')}" if isinstance(channel, dict) and channel.get("available") is True else "teyitli kanal yok"
    close = _safe_float(metrics.get("close"))
    zones = metrics.get("support_resistance_zones")
    zones = zones if isinstance(zones, list) else []
    valid_zones = [
        zone for zone in zones
        if isinstance(zone, dict) and _safe_float(zone.get("center")) is not None
    ]
    supports = [
        zone for zone in valid_zones if zone.get("kind") == "support"
        and (close is None or float(zone["center"]) <= close)
    ]
    resistances = [
        zone for zone in valid_zones if zone.get("kind") == "resistance"
        and (close is None or float(zone["center"]) >= close)
    ]
    support = max(supports, key=lambda zone: float(zone["center"]), default=None)
    resistance = min(resistances, key=lambda zone: float(zone["center"]), default=None)
    support_text = _format_price(support.get("center")) if support else "—"
    resistance_text = _format_price(resistance.get("center")) if resistance else "—"
    plan = candidate.get("risk_plan")
    plan = plan if isinstance(plan, dict) else {}
    low, high = _safe_float(plan.get("entry_zone_low")), _safe_float(plan.get("entry_zone_high"))
    stop = _safe_float(plan.get("stop_loss"))
    targets = plan.get("targets")
    target = _safe_float(targets[0].get("price")) if isinstance(targets, list) and targets and isinstance(targets[0], dict) else None
    entry_text = f"{_format_price(low)}–{_format_price(high)} USDT" if low is not None and high is not None else "mevcut değil"
    stop_text = f"{_format_price(stop)} USDT" if stop is not None else "mevcut değil"
    target_text = f"{_format_price(target)} USDT" if target is not None else "teknik hedef yok"
    components = candidate.get("score_components")
    components = components if isinstance(components, dict) else {}
    try:
        adjustment = int(components.get("btc_correlation_risk_adjustment", 0))
    except (TypeError, ValueError, OverflowError):
        adjustment = 0
    missing = candidate.get("missing_checks")
    missing = [str(item) for item in missing if item] if isinstance(missing, list) else []
    blockers = "; ".join(missing[:2]) if missing else "kayıtlı eksik kontrol yok"
    return "\n".join([
        f"{decision} | Aşama {phase} | Puan {candidate.get('opportunity_score', '—')}",
        f"Gerekçe: {reason}",
        f"BTC'ye göre getiri farkı: {rel_text}",
        f"BTC korelasyonu: {corr_text_value}. {assessment_text}",
        f"Fiyat yapısı: {channel_text} | Yakın destek: {support_text} | Yakın direnç: {resistance_text}",
        f"Koşullu giriş: {entry_text} | Zarar durdurma: {stop_text} | İlk teknik hedef: {target_text}",
        f"Eksik teyit/engel: {blockers}",
        f"Korelasyon puan etkisi: {adjustment:+d}; riskli BTC bağlamında yüksek pozitif korelasyona ceza uygulanır.",
    ])


class PillButton(tk.Canvas):
    """Small rounded pill button with explicit semantic color roles."""

    def __init__(
        self, master: tk.Misc, *, text: str, command: Any, role: str = "action",
        state: str = "normal", width: int | None = None,
    ) -> None:
        self._text = text
        self._command = command
        self._role = role
        self._state = state
        self._hover = False
        self._font = ("Segoe UI", 9, "bold")
        measured = tkfont.Font(family=self._font[0], size=self._font[1], weight=self._font[2]).measure(text)
        requested_width = max(measured + 28, int(width or 0) * 8)
        super().__init__(
            master, width=requested_width, height=27, bd=0, highlightthickness=0,
            relief="flat", background="#000000", cursor="hand2",
        )
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
            cnf = None
        redraw = False
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
            redraw = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "role" in kwargs:
            self._role = str(kwargs.pop("role"))
            redraw = True
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            self.configure(cursor="hand2" if self._state != "disabled" else "arrow")
            redraw = True
        if "font" in kwargs:
            requested_font = kwargs.pop("font")
            self._font = tuple(requested_font) if isinstance(requested_font, (tuple, list)) else requested_font
            redraw = True
        result = super().configure(cnf, **kwargs)
        if redraw:
            self._draw()
        return result

    config = configure

    def instate(self, states: list[str] | tuple[str, ...]) -> bool:
        for state in states:
            if state == "disabled" and self._state != "disabled":
                return False
            if state == "!disabled" and self._state == "disabled":
                return False
        return True

    def _on_enter(self, _event: Any = None) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _event: Any = None) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, _event: Any = None) -> None:
        if self._state != "disabled" and callable(self._command):
            self._command()

    def _draw(self) -> None:
        self.delete("all")
        width = max(20, self.winfo_width())
        height = max(20, self.winfo_height())
        if self._role == "accent":
            base, hover = "#008f95", "#00767b"
        else:
            base, hover = "#c62828", "#ff7f8b"
        if self._state == "disabled":
            fill, foreground = "#6a5555", "#d8d8d8"
        else:
            fill, foreground = (hover if self._hover else base), "#ffffff"
        cap = height
        self.create_oval(0, 0, cap, height, fill=fill, outline=fill)
        self.create_rectangle(cap / 2, 0, width - cap / 2, height, fill=fill, outline=fill)
        self.create_oval(width - cap, 0, width, height, fill=fill, outline=fill)
        self.create_text(width / 2, height / 2, text=self._text, fill=foreground, font=self._font)


class ControlPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        screen_width = max(800, self.winfo_screenwidth())
        screen_height = max(600, self.winfo_screenheight())
        # Start near half-screen width; resizable panes reflow when widened.
        window_width = min(int(screen_width * 0.80), max(min(1000, int(screen_width * 0.80)), int(screen_width * 0.52)))
        window_height = min(int(screen_height * 0.90), int(screen_height * 0.93))
        window_height = max(min(620, int(screen_height * 0.93)), window_height)
        self.window_width = window_width
        self.geometry(
            f"{window_width}x{window_height}+"
            f"{max(0, (screen_width - window_width) // 2)}+"
            f"{max(0, (screen_height - window_height) // 2)}"
        )
        self.minsize(min(820, window_width), min(600, window_height))
        icon_path = ROOT / "firsat_kontrol.ico"
        if icon_path.is_file():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

        self.settings = _read_json(SETTINGS_PATH, {})
        if not isinstance(self.settings, dict):
            self.settings = {}
        panel = self.settings.get("panel_ui")
        if not isinstance(panel, dict):
            panel = {}
            self.settings["panel_ui"] = panel
        self.panel_settings = panel
        self.alarm_enabled = panel.get("alarm_sound_enabled", True) is True
        volume = _safe_float(panel.get("alarm_volume", 55))
        self.alarm_volume = int(max(0, min(100, volume if volume is not None else 55)))
        font_size = panel.get("font_size", 8)
        self.font_size = _normalize_font_size(font_size)

        self.engine: subprocess.Popen[str] | None = None
        self.engine_started_epoch: float | None = None
        self.stop_requested_epoch: float | None = None
        self.close_after_stop = False
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.current_state: dict[str, Any] = {}
        self.current_state_epoch: float | None = None
        self.current_candidates: dict[str, dict[str, Any]] = {}
        self.current_candidate_key: str | None = None
        self._last_rendered_stamp: str | None = None
        self._previous_strong_keys: set[str] = set()
        self._alarm_primed = False
        self._level_watch_key: str | None = None
        self._level_previous_price: float | None = None
        self._level_crossed: set[str] = set()
        self._log_read_thread: threading.Thread | None = None
        self._last_error_state_stamp: str | None = None
        self.btcturk_prices: dict[str, float] = {}
        self.btcturk_prices_updated_at: float | None = None
        self.btcturk_price_error: str | None = None
        self._btcturk_price_stop = threading.Event()

        self.status_var = tk.StringVar(value="Motor durduruldu")
        self.live_status_var = tk.StringVar(value="CANLI AKIŞ  ·  UYARI")
        self.history_status_var = tk.StringVar(value="GEÇMİŞ MUMLAR  ·  BEKLİYOR")
        self.start_time_var = tk.StringVar(value="Başlangıç: —")
        self.stop_time_var = tk.StringVar(value="Bitiş: —")
        self.level_var = tk.StringVar(value="Seviye takibi: kapalı")
        self.diagnostics_summary_var = tk.StringVar(value="Motor ayrıntıları henüz alınmadı.")
        self.candidates_heading_var = tk.StringVar(value="ÖNCELİKLİ ADAYLAR · VERİ BEKLENİYOR")
        self.details_heading_var = tk.StringVar(value="SEÇİLEN COIN · VERİ BEKLENİYOR")
        self.volume_var = tk.IntVar(value=self.alarm_volume)
        self.btc_context_var = tk.StringVar(value="BTC piyasa özeti: veri bekleniyor")
        self.btc_details_open = False
        self.technical_details_open = False
        self.diagnostics_open = False
        self._pane_orientation = "horizontal"
        saved_btcturk_pro = _read_json(DATA_DIR / "btcturk_pro_state.json", {})
        self.btcturk_pro_symbol = str(
            saved_btcturk_pro.get("last_symbol", "BTCUSDT")
            if isinstance(saved_btcturk_pro, dict) else "BTCUSDT"
        ).upper()
        self.btcturk_pro_markets: dict[str, dict[str, Any]] = {}
        self.btcturk_pro_data: dict[str, Any] | None = None
        self.btcturk_pro_request_id = 0
        self.btcturk_pro_load_busy = False
        self.btcturk_pro_quote_refresh_busy = False
        self.workspace_current_page = "radar"
        self.btcturk_pro_timeframe_var = tk.StringVar(value="15m")
        self.btcturk_pro_show_plan = tk.BooleanVar(value=True)
        self.btcturk_pro_show_support_resistance = tk.BooleanVar(value=True)
        self.btcturk_pro_show_fibonacci = tk.BooleanVar(value=True)
        self.btcturk_pro_show_channel = tk.BooleanVar(value=True)
        self.btcturk_pro_entry_var = tk.StringVar(value=self.btcturk_pro_symbol)
        self.btcturk_pro_amount_var = tk.StringVar(value="")
        self.btcturk_pro_status_var = tk.StringVar(value="BtcTurk PRO verisi bekleniyor")
        self.btcturk_pro_quote_var = tk.StringVar(value="BtcTurk fiyatı bekleniyor")
        self.btcturk_pro_binance_var = tk.StringVar(value="Binance karşılaştırması: henüz alınmadı")
        self.btcturk_pro_market_rules_var = tk.StringVar(value="Parite işlem kuralları bekleniyor")
        self.btcturk_pro_cost_var = tk.StringVar(value="İşlem tutarı girildiğinde emir defteri maliyet tahmini gösterilir.")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._poll)
        self.after(350, self._apply_windows_titlebar)
        threading.Thread(target=self._btcturk_price_loop, name="btcturk-price-refresh", daemon=True).start()
        LOGGER.info("Panel açıldı. Başlangıç kodu: %s", ENGINE_PATH.name)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        black, white = "#000000", "#FFFFFF"
        style.configure("TFrame", background=black)
        style.configure("TLabel", background=black, foreground=white, font=("Segoe UI", self.font_size))
        style.configure("TLabelframe", background=black, foreground=white, bordercolor=white, relief="solid")
        style.configure("TLabelframe.Label", background=black, foreground=white, font=("Segoe UI", self.font_size, "bold"))
        style.configure("TButton", background=black, foreground=white, bordercolor=white, padding=(7, 4), font=("Segoe UI", self.font_size - 1))
        style.map("TButton", background=[("active", "#292929"), ("pressed", "#444444")], foreground=[("disabled", "#888888"), ("active", white)])
        style.configure("Status.TLabel", background=black, foreground=white, font=("Segoe UI", self.font_size, "bold"))
        style.configure("Section.TLabel", background=black, foreground=white, font=("Segoe UI", self.font_size, "bold"))
        style.configure("SectionGood.TLabel", background=black, foreground="#39FF88", font=("Segoe UI", self.font_size, "bold"))
        style.configure("SectionPending.TLabel", background=black, foreground="#FFD166", font=("Segoe UI", self.font_size, "bold"))
        style.configure("SectionBad.TLabel", background=black, foreground="#FF4545", font=("Segoe UI", self.font_size, "bold"))
        style.configure("LiveGood.TLabel", background=black, foreground="#39FF88", font=("Segoe UI", self.font_size, "bold"), padding=(5, 3))
        style.configure("LiveBad.TLabel", background=black, foreground="#FF4545", font=("Segoe UI", self.font_size, "bold"), padding=(5, 3))
        style.configure("HistoryGood.TLabel", background=black, foreground="#39FF88", font=("Segoe UI", self.font_size, "bold"), padding=(5, 3))
        style.configure("HistoryPending.TLabel", background=black, foreground="#FFD166", font=("Segoe UI", self.font_size, "bold"), padding=(5, 3))
        style.configure("BTC.TLabel", background=black, foreground=white, font=("Segoe UI", self.font_size, "bold"))
        style.configure("Time.TLabel", background=black, foreground=white, font=("Segoe UI", max(9, self.font_size - 2)))
        style.configure("Treeview", background=black, fieldbackground=black, foreground=white, rowheight=27, font=("Segoe UI", self.font_size - 1), borderwidth=0)
        style.configure("Treeview.Heading", background="#151515", foreground=white, font=("Segoe UI", self.font_size - 1, "bold"), padding=(4, 6), relief="solid")
        style.map("Treeview", background=[("selected", "#243447")], foreground=[("selected", white)])
        style.configure("Slim.Vertical.TScrollbar", arrowsize=8, width=8, background="#5A5A5A", troughcolor=black, bordercolor=black, arrowcolor=white)
        style.configure("Slim.Horizontal.TScrollbar", arrowsize=8, width=8, background="#5A5A5A", troughcolor=black, bordercolor=black, arrowcolor=white)
        style.configure("Slim.Horizontal.TScale", sliderlength=13, troughcolor="#3A3A3A", background="#777777", borderwidth=0, relief="flat")
        style.map("Slim.Horizontal.TScale", background=[("active", white), ("pressed", white)])
        style.configure("TSeparator", background=white)
        self.configure(background=black)

        self.workspace = ttk.Frame(self)
        self.workspace.pack(fill="both", expand=True)
        self.workspace_navigation = ttk.Frame(self.workspace, padding=(8, 10), width=154)
        self.workspace_navigation.pack(side="left", fill="y")
        self.workspace_navigation.pack_propagate(False)
        ttk.Label(
            self.workspace_navigation, text="ÇALIŞMA ALANI",
            style="Section.TLabel", wraplength=132,
        ).pack(fill="x", anchor="w", pady=(0, 12))
        self.workspace_nav_buttons: dict[str, ttk.Button] = {}
        navigation_items = (
            ("overview", "Genel Bakış"),
            ("radar", "Fırsat Radarı"),
            ("tracking", "Aktif Takip"),
            ("analysis", "Parite Analizi"),
            ("market", "BTC ve Piyasa"),
            ("plans", "Planlar ve Uyarılar"),
            ("reports", "Raporlar"),
            ("btcturk", "BtcTurk PRO"),
            ("settings", "Sistem ve Ayarlar"),
        )
        for page_key, page_label in navigation_items:
            button = ttk.Button(
                self.workspace_navigation,
                text=page_label,
                command=lambda selected=page_key: (
                    self._open_btcturk_pro_from_radar()
                    if selected == "btcturk"
                    else self._show_workspace_page(selected)
                ),
            )
            button.pack(fill="x", pady=(0, 5))
            self.workspace_nav_buttons[page_key] = button
        self.nav_radar_button = self.workspace_nav_buttons["radar"]
        self.nav_btcturk_button = self.workspace_nav_buttons["btcturk"]
        ttk.Label(
            self.workspace_navigation,
            text="Binance: fırsat keşfi\nBtcTurk PRO: işlem analizi",
            justify="left", wraplength=132,
        ).pack(fill="x", anchor="w", pady=(12, 0))
        self.workspace_pages = ttk.Frame(self.workspace)
        self.workspace_pages.pack(side="left", fill="both", expand=True)
        self.radar_page = ttk.Frame(self.workspace_pages)
        self.radar_page.pack(fill="both", expand=True)
        self.btcturk_page = ttk.Frame(self.workspace_pages)

        status_row = ttk.Frame(self, padding=(12, 5, 12, 5))
        status_row.pack(fill="x", before=self.workspace)
        self.live_status_label = ttk.Label(status_row, textvariable=self.live_status_var, style="LiveBad.TLabel")
        self.live_status_label.pack(side="left", padx=(0, 12))
        self.history_status_label = ttk.Label(status_row, textvariable=self.history_status_var, style="HistoryPending.TLabel")
        self.history_status_label.pack(side="left", padx=(0, 12))
        self.operation_status_label = ttk.Label(status_row, textvariable=self.status_var, style="TLabel", anchor="e")
        self.operation_status_label.pack(side="right", fill="x", expand=True)
        ttk.Separator(self.radar_page, orient="horizontal").pack(fill="x", padx=12, pady=(0, 7))

        btc_row = ttk.Frame(self.radar_page, padding=(12, 0, 12, 4))
        btc_row.pack(fill="x")
        ttk.Label(btc_row, text="BTC PİYASA ÖZETİ", style="BTC.TLabel").pack(side="left", anchor="n")
        self.btc_summary_label = ttk.Label(btc_row, textvariable=self.btc_context_var, justify="left", wraplength=max(360, self.window_width - 280), anchor="w")
        self.btc_summary_label.pack(side="left", fill="x", expand=True, padx=(10, 8))
        self.btc_details_button = ttk.Button(btc_row, text="BTC ayrıntıları ▸", command=self._toggle_btc_details)
        self.btc_details_button.pack(side="right")
        self.btc_details_frame = ttk.Frame(self.radar_page, padding=(12, 2, 12, 6))
        btc_detail_inner = ttk.Frame(self.btc_details_frame)
        btc_detail_inner.pack(fill="both", expand=True)
        self.btc_details_text = tk.Text(btc_detail_inner, height=4, wrap="word", font=("Segoe UI", self.font_size - 1), background=black, foreground=white, insertbackground=white, selectbackground="#243447", relief="flat", state="disabled")
        btc_details_scroll = ttk.Scrollbar(btc_detail_inner, orient="vertical", style="Slim.Vertical.TScrollbar", command=self.btc_details_text.yview)
        self.btc_details_text.configure(yscrollcommand=btc_details_scroll.set)
        self.btc_details_text.grid(row=0, column=0, sticky="nsew")
        btc_details_scroll.grid(row=0, column=1, sticky="ns")
        btc_detail_inner.rowconfigure(0, weight=1)
        btc_detail_inner.columnconfigure(0, weight=1)
        ttk.Separator(self.radar_page, orient="horizontal").pack(fill="x", padx=12, pady=(0, 7))

        controls = ttk.Frame(self, padding=(12, 3, 12, 5))
        controls.pack(fill="x")
        self.controls_inner = ttk.Frame(controls)
        self.controls_inner.pack(fill="x")
        self.toolbar_items: list[tk.Widget] = []
        start_group = ttk.Frame(self.controls_inner)
        self.start_button = PillButton(start_group, text="Başlat", command=self.start_engine, role="action", width=8)
        self.start_button.pack(fill="x")
        ttk.Label(start_group, textvariable=self.start_time_var, style="Time.TLabel", anchor="center").pack(fill="x")
        self.toolbar_items.append(start_group)
        stop_group = ttk.Frame(self.controls_inner)
        self.stop_button = PillButton(stop_group, text="Durdur", command=self.stop_engine, role="action", state="disabled", width=8)
        self.stop_button.pack(fill="x")
        ttk.Label(stop_group, textvariable=self.stop_time_var, style="Time.TLabel", anchor="center").pack(fill="x")
        self.toolbar_items.append(stop_group)
        update_group = ttk.Frame(self.controls_inner)
        self.update_list_button = PillButton(update_group, text="Pariteleri Güncelle", command=self.update_universe, role="action")
        self.update_list_button.pack(fill="x")
        self.toolbar_items.append(update_group)
        daily_group = ttk.Frame(self.controls_inner)
        PillButton(daily_group, text="Günlük Rapor", command=self.create_report, role="action").pack(fill="x")
        self.toolbar_items.append(daily_group)
        analysis_group = ttk.Frame(self.controls_inner)
        PillButton(analysis_group, text="Analiz Raporu", command=self.create_analysis_report, role="action").pack(fill="x")
        self.toolbar_items.append(analysis_group)
        zip_group = ttk.Frame(self.controls_inner)
        PillButton(zip_group, text="Sorun Giderme ZIP", command=self.create_handoff_zip, role="action").pack(fill="x")
        self.toolbar_items.append(zip_group)
        level_group = ttk.Frame(self.controls_inner)
        self.level_button = PillButton(level_group, text="Seviye Takibi: Kapalı", command=self.toggle_level_watch, role="accent")
        self.level_button.pack(fill="x")
        self.toolbar_items.append(level_group)
        alarm_group = ttk.Frame(self.controls_inner)
        self.alarm_button = PillButton(alarm_group, text="Sesli Bildirim: Açık" if self.alarm_enabled else "Sesli Bildirim: Kapalı", command=self.toggle_alarm, role="accent")
        self.alarm_button.pack(fill="x")
        self.toolbar_items.append(alarm_group)
        sound_test_group = ttk.Frame(self.controls_inner)
        PillButton(sound_test_group, text="Ses Testi", command=self._test_sound, role="accent").pack(fill="x")
        self.toolbar_items.append(sound_test_group)
        volume_group = ttk.Frame(self.controls_inner)
        ttk.Label(volume_group, text="Ses", anchor="center").pack(fill="x")
        self.volume_scale = ttk.Scale(volume_group, from_=0, to=100, orient="horizontal", length=92, variable=self.volume_var, command=self._volume_moved, style="Slim.Horizontal.TScale")
        self.volume_scale.pack(fill="x", padx=2)
        self.volume_scale.bind("<ButtonRelease-1>", self._save_volume)
        self.volume_scale.bind("<KeyRelease>", self._save_volume)
        self.volume_label = ttk.Label(volume_group, text=f"{self.alarm_volume}%", anchor="center")
        self.volume_label.pack(fill="x")
        self.toolbar_items.append(volume_group)
        font_group = ttk.Frame(self.controls_inner)
        ttk.Label(font_group, text="Yazı boyutu", anchor="center").pack(fill="x")
        self.font_size_var = tk.DoubleVar(value=self.font_size)
        self.font_size_scale = ttk.Scale(
            font_group, from_=8, to=15, orient="horizontal", length=92,
            variable=self.font_size_var, command=self._font_size_moved,
            style="Slim.Horizontal.TScale",
        )
        self.font_size_scale.pack(fill="x", padx=2)
        self.font_size_scale.bind("<ButtonRelease-1>", self._save_font_size)
        self.font_size_scale.bind("<KeyRelease>", self._save_font_size)
        self.font_size_label = ttk.Label(font_group, text=f"{self.font_size} punto", anchor="center")
        self.font_size_label.pack(fill="x", pady=(0, 13))
        self.toolbar_items.append(font_group)
        camera_group = ttk.Frame(self.controls_inner)
        PillButton(camera_group, text="📷", command=self.open_screenshot_upload, role="accent", width=5).pack(fill="x")
        self.toolbar_items.append(camera_group)
        self.controls_inner.bind("<Configure>", self._layout_toolbar, add="+")
        self.after(120, self._layout_toolbar)
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=(0, 5), before=self.workspace)

        self.pane = ttk.Panedwindow(self.radar_page, orient="horizontal")
        self.pane.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.left_pane = ttk.Frame(self.pane, padding=(0, 0, 5, 0))
        self.right_pane = ttk.Frame(self.pane, padding=(5, 0, 0, 0))
        self.pane.add(self.left_pane, weight=5)
        self.pane.add(self.right_pane, weight=4)
        self.left_heading = ttk.Label(self.left_pane, textvariable=self.candidates_heading_var, style="SectionPending.TLabel")
        self.left_heading.pack(anchor="w", pady=(0, 5))
        radar_filter_row = ttk.Frame(self.left_pane)
        radar_filter_row.pack(fill="x", pady=(0, 5))
        self.radar_search_var = tk.StringVar(value="")
        self.radar_search_entry = ttk.Entry(radar_filter_row, textvariable=self.radar_search_var)
        self.radar_search_entry.pack(side="left", fill="x", expand=True)
        self.radar_search_entry.insert(0, "")
        self.radar_search_entry.bind("<KeyRelease>", lambda _event: self._apply_radar_filters())
        ttk.Button(
            radar_filter_row, text="Temizle",
            command=lambda: (self.radar_search_var.set(""), self._apply_radar_filters()),
        ).pack(side="left", padx=(5, 0))
        tree_frame = ttk.Frame(self.left_pane)
        tree_frame.pack(fill="both", expand=True)
        columns = ("symbol", "price", "btcturk_price", "score", "timeframe", "phase", "freshness", "btc_relative", "decision")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        headers = {
            "symbol": "Coin", "price": "Binance USDT", "btcturk_price": "BtcTurk USDT",
            "score": "Puan", "timeframe": "Zaman", "phase": "A/B/C", "freshness": "Veri",
            "btc_relative": "BTC'ye göre", "decision": "Son karar",
        }
        widths = {"symbol": 88, "price": 94, "btcturk_price": 94, "score": 48,
                  "timeframe": 55, "phase": 46, "freshness": 68, "btc_relative": 88, "decision": 112}
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], minwidth=34,
                             anchor="center" if col != "symbol" else "w",
                             stretch=col in ("symbol", "decision"))
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", style="Slim.Vertical.TScrollbar", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", style="Slim.Horizontal.TScrollbar", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.tag_configure("strong", background="#102A19", foreground="#39FF88")
        self.tree.tag_configure("stale", background="#301010", foreground="#FF7777")
        self.tree.tag_configure("phase_a", foreground="#8AB4F8")
        self.tree.tag_configure("phase_b", foreground="#FFD166")
        self.tree.tag_configure("phase_c", foreground="#FFFFFF")
        self.tree.tag_configure("decision_strong", foreground="#39FF88")
        self.tree.tag_configure("decision_no_trade", foreground="#FF4545")
        self.tree.tag_configure("decision_wait", foreground="#FFD166")
        self.tree.tag_configure("decision_watch", foreground="#8AB4F8")
        self.tree.tag_configure("decision_early", foreground="#8AB4F8")
        self.tree.tag_configure("decision_breakout", foreground="#FFD166")

        right_header = ttk.Frame(self.right_pane)
        right_header.pack(fill="x", pady=(0, 5))
        self.right_heading = ttk.Label(right_header, textvariable=self.details_heading_var, style="SectionPending.TLabel")
        self.right_heading.pack(side="left", anchor="w")
        self.technical_toggle_button = ttk.Button(right_header, text="Teknik ayrıntılar ▸", command=self._toggle_technical_details)
        self.technical_toggle_button.pack(side="right")
        self.right_content = ttk.Panedwindow(self.right_pane, orient="vertical")
        self.right_content.pack(fill="both", expand=True)
        self.quick_panel = ttk.Frame(self.right_content)
        self.right_content.add(self.quick_panel, weight=3)
        detail_frame = ttk.Frame(self.quick_panel)
        detail_frame.pack(fill="both", expand=True)
        self.details = tk.Text(detail_frame, wrap="word", font=("Segoe UI", self.font_size), background=black, foreground=white, insertbackground=white, selectbackground="#243447", state="disabled", height=14, relief="flat", padx=6, pady=5)
        self.details.tag_configure("scenario", foreground="#FFFFFF", font=("Segoe UI", self.font_size, "bold"))
        self.details.tag_configure("entry", foreground="#FFFFFF")
        self.details.tag_configure("breakout", foreground="#FFD166")
        self.details.tag_configure("stop", foreground="#FF4545")
        self.details.tag_configure("target", foreground="#D8B4FE")
        self.details.tag_configure("stale", foreground="#FF4545")
        self.details.tag_configure("current", foreground="#39FF88")
        self.details.tag_configure("decision_good", foreground="#39FF88", font=("Segoe UI", self.font_size, "bold"))
        self.details.tag_configure("decision_wait", foreground="#FFD166")
        self.details.tag_configure("decision_bad", foreground="#FF4545")
        self.details.tag_configure("decision_early", foreground="#8AB4F8")
        self.details.tag_configure("decision_watch", foreground="#8AB4F8")
        self.details.tag_configure("section", foreground="#FFFFFF", font=("Segoe UI", self.font_size, "bold"))
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", style="Slim.Vertical.TScrollbar", command=self.details.yview)
        detail_scroll_bottom = ttk.Scrollbar(detail_frame, orient="horizontal", style="Slim.Horizontal.TScrollbar", command=self.details.xview)
        self.details.configure(yscrollcommand=detail_scroll.set, xscrollcommand=detail_scroll_bottom.set)
        self.details.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")
        detail_scroll_bottom.grid(row=1, column=0, sticky="ew")
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)

        self.technical_panel = ttk.Frame(self.right_content, padding=(4, 4, 4, 4))
        ttk.Label(self.technical_panel, text="Göstergeler · sekiz zaman dilimi · fiyat yapısı · eksik kanıtlar", style="Section.TLabel").pack(anchor="w", pady=(0, 4))
        tech_text_frame = ttk.Frame(self.technical_panel)
        tech_text_frame.pack(fill="both", expand=True)
        self.technical_details = tk.Text(tech_text_frame, wrap="none", font=("Consolas", max(9, self.font_size - 1)), background=black, foreground=white, insertbackground=white, selectbackground="#243447", state="disabled", height=9, relief="flat", padx=6, pady=5)
        tech_y = ttk.Scrollbar(tech_text_frame, orient="vertical", style="Slim.Vertical.TScrollbar", command=self.technical_details.yview)
        tech_x = ttk.Scrollbar(tech_text_frame, orient="horizontal", style="Slim.Horizontal.TScrollbar", command=self.technical_details.xview)
        self.technical_details.configure(yscrollcommand=tech_y.set, xscrollcommand=tech_x.set)
        self.technical_details.grid(row=0, column=0, sticky="nsew")
        tech_y.grid(row=0, column=1, sticky="ns")
        tech_x.grid(row=1, column=0, sticky="ew")
        tech_text_frame.rowconfigure(0, weight=1)
        tech_text_frame.columnconfigure(0, weight=1)

        diagnostics_controls = ttk.Frame(self.radar_page, padding=(12, 2, 12, 3))
        diagnostics_controls.pack(fill="x")
        self.diagnostics_toggle_button = ttk.Button(diagnostics_controls, text="Tanılama ve son kayıtlar ▸", command=self._toggle_diagnostics)
        self.diagnostics_toggle_button.pack(side="left")
        ttk.Label(diagnostics_controls, text="A/B/C araştırma aşamalarıdır; teknik senaryolar garanti değildir.", style="TLabel").pack(side="right")
        self.diagnostics_frame = ttk.LabelFrame(self.radar_page, text="Tanılama ayrıntıları", padding=5)
        ttk.Label(self.diagnostics_frame, textvariable=self.diagnostics_summary_var, wraplength=max(400, self.window_width - 50), justify="left").pack(fill="x", anchor="w", pady=(0, 4))
        log_controls = ttk.Frame(self.diagnostics_frame)
        log_controls.pack(fill="x", pady=(0, 4))
        ttk.Label(log_controls, text="Son kayıtlar", style="Section.TLabel").pack(side="left")
        ttk.Button(log_controls, text="Kayıt klasörünü aç", command=self.open_logs).pack(side="right")
        log_frame = ttk.Frame(self.diagnostics_frame)
        log_frame.pack(fill="both", expand=True)
        self.log_view = tk.Text(log_frame, height=10, wrap="none", font=("Consolas", max(9, self.font_size - 1)), background=black, foreground=white, insertbackground=white, selectbackground="#243447", state="disabled", relief="flat", padx=5, pady=4)
        log_y = ttk.Scrollbar(log_frame, orient="vertical", style="Slim.Vertical.TScrollbar", command=self.log_view.yview)
        log_x = ttk.Scrollbar(log_frame, orient="horizontal", style="Slim.Horizontal.TScrollbar", command=self.log_view.xview)
        self.log_view.configure(yscrollcommand=log_y.set, xscrollcommand=log_x.set)
        self.log_view.grid(row=0, column=0, sticky="nsew")
        log_y.grid(row=0, column=1, sticky="ns")
        log_x.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.bind("<Configure>", self._adapt_panes, add="+")
        self.bind("<Configure>", self._resize_wraplengths, add="+")
        self._build_btcturk_pro_ui()
        self._build_additional_workspace_pages()
        self._apply_font_scale()
        self._refresh_status_indicators()
        self._show_workspace_page("overview")
        self.after(15000, self._schedule_btcturk_pro_quote_refresh)

    def _build_additional_workspace_pages(self) -> None:
        """Create the remaining workspaces and connect them to existing engine state."""
        self.workspace_page_frames: dict[str, ttk.Frame] = {
            "radar": self.radar_page,
            "btcturk": self.btcturk_page,
        }

        self.overview_page = ttk.Frame(self.workspace_pages)
        self.tracking_page = ttk.Frame(self.workspace_pages)
        self.analysis_page = ttk.Frame(self.workspace_pages)
        self.market_page = ttk.Frame(self.workspace_pages)
        self.plans_page = ttk.Frame(self.workspace_pages)
        self.reports_page = ttk.Frame(self.workspace_pages)
        self.settings_page = ttk.Frame(self.workspace_pages)

        for key, frame in (
            ("overview", self.overview_page),
            ("tracking", self.tracking_page),
            ("analysis", self.analysis_page),
            ("market", self.market_page),
            ("plans", self.plans_page),
            ("reports", self.reports_page),
            ("settings", self.settings_page),
        ):
            self.workspace_page_frames[key] = frame

        def heading(parent: ttk.Frame, title: str, subtitle: str) -> None:
            band = ttk.Frame(parent, padding=(14, 12, 14, 7))
            band.pack(fill="x")
            ttk.Label(band, text=title, style="Section.TLabel").pack(anchor="w")
            ttk.Label(band, text=subtitle, wraplength=1000).pack(anchor="w", pady=(3, 0))

        # Genel Bakış
        heading(
            self.overview_page, "Genel Bakış",
            "Piyasa bağlamı, motor/veri durumu ve öne çıkan adaylar tek ekranda.",
        )
        overview_metrics = ttk.Frame(self.overview_page, padding=(12, 4, 12, 9))
        overview_metrics.pack(fill="x")
        self.overview_metric_vars = {
            "engine": tk.StringVar(value="Motor hazır"),
            "universe": tk.StringVar(value="— parite"),
            "strong": tk.StringVar(value="— güçlü aday"),
            "freshness": tk.StringVar(value="Veri bekleniyor"),
        }
        for title, key in (
            ("MOTOR DURUMU", "engine"),
            ("TARAMA EVRENİ", "universe"),
            ("GÜÇLÜ FIRSAT", "strong"),
            ("VERİ DURUMU", "freshness"),
        ):
            card = ttk.LabelFrame(overview_metrics, text=title, padding=(9, 7))
            card.pack(side="left", fill="both", expand=True, padx=(0, 7))
            ttk.Label(card, textvariable=self.overview_metric_vars[key], style="Section.TLabel").pack(anchor="w")
        overview_split = ttk.Panedwindow(self.overview_page, orient="horizontal")
        overview_split.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        overview_list = ttk.Frame(overview_split)
        overview_detail = ttk.Frame(overview_split)
        overview_split.add(overview_list, weight=6)
        overview_split.add(overview_detail, weight=4)
        ttk.Label(overview_list, text="ÖNCELİKLİ ADAYLAR", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        overview_columns = ("symbol", "price", "score", "phase", "freshness", "decision")
        self.overview_tree = ttk.Treeview(
            overview_list, columns=overview_columns, show="headings", selectmode="browse",
        )
        for column, label, width in (
            ("symbol", "Coin", 100), ("price", "Binance USDT", 105),
            ("score", "Puan", 55), ("phase", "A/B/C", 52),
            ("freshness", "Veri", 80), ("decision", "Son karar", 155),
        ):
            self.overview_tree.heading(column, text=label)
            self.overview_tree.column(column, width=width, minwidth=48, stretch=column in ("symbol", "decision"))
        self.overview_tree.pack(fill="both", expand=True)
        self.overview_tree.bind("<<TreeviewSelect>>", self._overview_selection_changed)
        self.overview_tree.bind("<Double-1>", lambda _event: self._overview_open_selected())
        overview_actions = ttk.Frame(overview_list)
        overview_actions.pack(fill="x", pady=(6, 0))
        ttk.Button(overview_actions, text="Parite Analizi", command=lambda: self._show_workspace_page("analysis")).pack(side="left")
        ttk.Button(overview_actions, text="Fırsat Radarı", command=lambda: self._show_workspace_page("radar")).pack(side="left", padx=(6, 0))
        ttk.Label(overview_detail, text="SEÇİLİ ADAY VE PİYASA BAĞLAMI", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.overview_detail_text = tk.Text(
            overview_detail, wrap="word", height=18, state="disabled",
            background="#000000", foreground="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=8, pady=7, font=("Segoe UI", self.font_size),
        )
        self.overview_detail_text.pack(fill="both", expand=True)

        # Aktif Takip
        heading(
            self.tracking_page, "Aktif Takip",
            "En fazla beş kullanıcı seçimi kaydedilir; liste mevcut teknik aday durumundan beslenir.",
        )
        tracking_actions = ttk.Frame(self.tracking_page, padding=(12, 3, 12, 8))
        tracking_actions.pack(fill="x")
        ttk.Button(
            tracking_actions, text="Seçili adayı takibe ekle",
            command=self._tracking_add_selected,
        ).pack(side="left")
        ttk.Button(
            tracking_actions, text="Seçili kaydı çıkar",
            command=self._tracking_remove_selected,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            tracking_actions, text="Parite Analizi",
            command=self._tracking_open_selected,
        ).pack(side="left", padx=(6, 0))
        self.tracking_status_var = tk.StringVar(value="Takip listesi boş.")
        ttk.Label(self.tracking_page, textvariable=self.tracking_status_var).pack(anchor="w", padx=13, pady=(0, 5))
        tracking_frame = ttk.Frame(self.tracking_page, padding=(12, 0, 12, 12))
        tracking_frame.pack(fill="both", expand=True)
        tracking_columns = ("symbol", "price", "score", "phase", "freshness", "decision")
        self.tracking_tree = ttk.Treeview(
            tracking_frame, columns=tracking_columns, show="headings", selectmode="browse",
        )
        for column, label, width in (
            ("symbol", "Coin", 120), ("price", "Binance USDT", 120),
            ("score", "Puan", 65), ("phase", "A/B/C", 65),
            ("freshness", "Veri", 110), ("decision", "Son karar", 220),
        ):
            self.tracking_tree.heading(column, text=label)
            self.tracking_tree.column(column, width=width, minwidth=50, stretch=column in ("symbol", "decision"))
        self.tracking_tree.pack(fill="both", expand=True)
        self.tracking_tree.bind("<Double-1>", lambda _event: self._tracking_open_selected())

        # Parite Analizi: Binance technical engine's actual last closed candles.
        heading(
            self.analysis_page, "Parite Analizi",
            "Grafik, motorun aday anlık görüntüsünde sunduğu kapanmış mumlardan oluşturulur; eksik mum uydurulmaz.",
        )
        analysis_header = ttk.Frame(self.analysis_page, padding=(12, 2, 12, 8))
        analysis_header.pack(fill="x")
        self.analysis_symbol_var = tk.StringVar(value="Coin seçilmedi")
        self.analysis_price_var = tk.StringVar(value="Fiyat: —")
        ttk.Label(analysis_header, textvariable=self.analysis_symbol_var, style="Section.TLabel").pack(side="left")
        ttk.Label(analysis_header, textvariable=self.analysis_price_var).pack(side="left", padx=(14, 0))
        ttk.Button(
            analysis_header, text="BtcTurk PRO'ya aktar",
            command=self._open_btcturk_pro_from_radar,
        ).pack(side="right")
        timeframe_row = ttk.Frame(self.analysis_page, padding=(12, 0, 12, 5))
        timeframe_row.pack(fill="x")
        self.analysis_timeframe_var = tk.StringVar(value="15m")
        self.analysis_timeframe_buttons: dict[str, ttk.Button] = {}
        for timeframe in ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"):
            button = ttk.Button(
                timeframe_row, text=timeframe,
                command=lambda selected=timeframe: self._analysis_set_timeframe(selected),
                width=5,
            )
            button.pack(side="left", padx=(0, 4))
            self.analysis_timeframe_buttons[timeframe] = button
        self.analysis_layer_vars = {
            "entry": tk.BooleanVar(value=True),
            "targets": tk.BooleanVar(value=True),
            "stop": tk.BooleanVar(value=True),
            "sr": tk.BooleanVar(value=True),
            "fib": tk.BooleanVar(value=False),
            "channel": tk.BooleanVar(value=False),
            "ema": tk.BooleanVar(value=True),
            "volume": tk.BooleanVar(value=True),
        }
        layer_row = ttk.Frame(self.analysis_page, padding=(12, 0, 12, 6))
        layer_row.pack(fill="x")
        for key, label in (
            ("entry", "Giriş bölgesi"), ("targets", "Hedefler"),
            ("stop", "Zarar-kes / geçersizlik"), ("sr", "Destek / direnç"),
            ("fib", "Fibonacci"), ("channel", "Kanal"),
            ("ema", "EMA"), ("volume", "Hacim"),
        ):
            ttk.Checkbutton(
                layer_row, text=label, variable=self.analysis_layer_vars[key],
                command=self._draw_analysis_chart,
            ).pack(side="left", padx=(0, 8))
        drawing_row = ttk.Frame(self.analysis_page, padding=(12, 0, 12, 7))
        drawing_row.pack(fill="x")
        ttk.Label(drawing_row, text="Çizim aracı:").pack(side="left", padx=(0, 5))
        self.analysis_tool_var = tk.StringVar(value="İmleç")
        self.analysis_tool_combo = ttk.Combobox(
            drawing_row, textvariable=self.analysis_tool_var,
            values=("İmleç", "Trend çizgisi", "Paralel kanal"),
            state="readonly", width=17,
        )
        self.analysis_tool_combo.pack(side="left")
        self.analysis_tool_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: setattr(self, "_analysis_pending_points", []),
        )
        ttk.Button(drawing_row, text="Son çizimi sil", command=self._analysis_delete_last).pack(side="left", padx=(8, 0))
        self.analysis_undo_button = ttk.Button(
            drawing_row, text="Geri al (5 sn)", command=self._analysis_undo_delete, state="disabled",
        )
        self.analysis_undo_button.pack(side="left", padx=(5, 0))
        self.analysis_hover_var = tk.StringVar(value="İmleç: —")
        ttk.Label(drawing_row, textvariable=self.analysis_hover_var).pack(side="right")
        self.analysis_status_var = tk.StringVar(value="Bir coin seçin.")
        ttk.Label(self.analysis_page, textvariable=self.analysis_status_var, wraplength=1100).pack(anchor="w", padx=13, pady=(0, 5))
        self.analysis_canvas = tk.Canvas(
            self.analysis_page, background="#05090e", highlightbackground="#485766",
            highlightthickness=1, height=390,
        )
        self.analysis_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.analysis_canvas.bind("<Configure>", self._draw_analysis_chart, add="+")
        self.analysis_canvas.bind("<Motion>", self._analysis_chart_motion, add="+")
        self.analysis_canvas.bind("<Button-1>", self._analysis_chart_click, add="+")
        indicators_row = ttk.Frame(self.analysis_page, padding=(12, 0, 12, 8))
        indicators_row.pack(fill="x")
        self.analysis_indicator_vars = {
            "rsi": tk.StringVar(value="RSI: veri bekleniyor"),
            "macd": tk.StringVar(value="MACD: veri bekleniyor"),
            "momentum": tk.StringVar(value="Momentum bileşeni: veri bekleniyor"),
        }
        self.analysis_indicator_frames: dict[str, ttk.LabelFrame] = {}
        self.analysis_indicator_checks: dict[str, tk.BooleanVar] = {}
        for key, title in (
            ("rsi", "RSI · Göreceli Güç Endeksi"),
            ("macd", "MACD · Ortalama Yakınsaması"),
            ("momentum", "Momentum · Motor puan bileşeni"),
        ):
            card = ttk.LabelFrame(indicators_row, text=title, padding=(8, 5))
            card.pack(side="left", fill="both", expand=True, padx=(0, 7))
            show_var = tk.BooleanVar(value=True)
            self.analysis_indicator_checks[key] = show_var
            ttk.Checkbutton(
                card, text="Göster", variable=show_var,
                command=self._refresh_analysis_indicators,
            ).pack(anchor="e")
            ttk.Label(card, textvariable=self.analysis_indicator_vars[key], wraplength=280).pack(anchor="w")
            self.analysis_indicator_frames[key] = card
        analysis_plan_frame = ttk.LabelFrame(self.analysis_page, text="Aktif teknik plan ve değerlendirme", padding=5)
        analysis_plan_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.analysis_plan_text = tk.Text(
            analysis_plan_frame, height=5, wrap="word", state="disabled",
            background="#000000", foreground="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=6, pady=4, font=("Segoe UI", max(8, self.font_size - 1)),
        )
        self.analysis_plan_text.pack(fill="x")

        # BTC ve Piyasa
        heading(
            self.market_page, "BTC ve Piyasa",
            "BTC ana yönü, seviye durumu, oynaklık ve piyasa verisinin eksiksizliği.",
        )
        market_actions = ttk.Frame(self.market_page, padding=(12, 2, 12, 5))
        market_actions.pack(fill="x")
        ttk.Button(
            market_actions, text="BTC ayrıntılarını yenile",
            command=self._refresh_market_page,
        ).pack(side="left")
        self.market_context_text = tk.Text(
            self.market_page, wrap="word", state="disabled",
            background="#000000", foreground="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=10, pady=8, font=("Consolas", max(8, self.font_size - 1)),
        )
        self.market_context_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Planlar ve Uyarılar
        heading(
            self.plans_page, "Planlar ve Uyarılar",
            "Motorun ürettiği aday planları, koşullu girişleri ve geçersizlik durumlarını takip et.",
        )
        plans_actions = ttk.Frame(self.plans_page, padding=(12, 2, 12, 7))
        plans_actions.pack(fill="x")
        ttk.Button(
            plans_actions, text="Seçili planı Parite Analizi'nde aç",
            command=lambda: self._show_workspace_page("analysis"),
        ).pack(side="left")
        self.plans_status_var = tk.StringVar(value="Plan verisi bekleniyor.")
        ttk.Label(self.plans_page, textvariable=self.plans_status_var).pack(anchor="w", padx=13, pady=(0, 5))
        plans_frame = ttk.Frame(self.plans_page, padding=(12, 0, 12, 12))
        plans_frame.pack(fill="both", expand=True)
        plan_columns = ("symbol", "status", "timeframe", "entry", "stop", "targets", "decision")
        self.plans_tree = ttk.Treeview(
            plans_frame, columns=plan_columns, show="headings", selectmode="browse",
        )
        for column, label, width in (
            ("symbol", "Coin", 110), ("status", "Plan durumu", 190),
            ("timeframe", "Zaman", 75), ("entry", "Koşullu giriş", 145),
            ("stop", "Zarar-kes", 100), ("targets", "Teknik hedefler", 180),
            ("decision", "Son karar", 170),
        ):
            self.plans_tree.heading(column, text=label)
            self.plans_tree.column(column, width=width, minwidth=60, stretch=column in ("status", "decision"))
        self.plans_tree.pack(fill="both", expand=True)
        self.plans_tree.bind("<Double-1>", lambda _event: self._plans_open_selected())

        # Raporlar
        heading(
            self.reports_page, "Raporlar",
            "Radarın erken tespit başarısı ile teknik işlem planının olay sonuçları ayrı raporlanır.",
        )
        report_actions = ttk.Frame(self.reports_page, padding=(12, 5, 12, 8))
        report_actions.pack(fill="x")
        ttk.Button(report_actions, text="Günlük Rapor Oluştur", command=self.create_report).pack(side="left")
        ttk.Button(report_actions, text="Analiz Raporu Oluştur", command=self.create_analysis_report).pack(side="left", padx=(6, 0))
        ttk.Button(report_actions, text="Sorun Giderme ZIP", command=self.create_handoff_zip).pack(side="left", padx=(6, 0))
        reports_split = ttk.Panedwindow(self.reports_page, orient="horizontal")
        reports_split.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        radar_report = ttk.LabelFrame(reports_split, text="Radarın erken tespit performansı", padding=10)
        plan_report = ttk.LabelFrame(reports_split, text="Teknik işlem planı sonuçları", padding=10)
        reports_split.add(radar_report, weight=1)
        reports_split.add(plan_report, weight=1)
        ttk.Label(
            radar_report,
            text="Erken tespit, geç tespit ve kaçırılan yükselişler; 1 saat, 4 saat ve 24 saat ölçümleri.\n\n"
                 "Ölçüm verileri oluşmadıkça başarı oranı gösterilmez.",
            wraplength=420, justify="left",
        ).pack(anchor="w")
        ttk.Label(
            plan_report,
            text="Giriş gerçekleşmesi, hedefler, zarar durdurma, geçersizleşme, süre dolumu ve belirsiz olay sırası.\n\n"
                 "Gerçek kullanıcı işlemleri değil, motorun önerdiği planların fiyat davranışı ölçülür.",
            wraplength=420, justify="left",
        ).pack(anchor="w")

        # Sistem ve Ayarlar
        heading(
            self.settings_page, "Sistem ve Ayarlar",
            "Ortak üst çubukta motor işlemleri ve hızlı kontroller; burada bağlantı ve tanılama özeti.",
        )
        setting_actions = ttk.Frame(self.settings_page, padding=(12, 3, 12, 8))
        setting_actions.pack(fill="x")
        ttk.Button(setting_actions, text="Pariteleri Güncelle", command=self.update_universe).pack(side="left")
        ttk.Button(setting_actions, text="Kayıt klasörünü aç", command=self.open_logs).pack(side="left", padx=(6, 0))
        ttk.Button(setting_actions, text="Ses Testi", command=self._test_sound).pack(side="left", padx=(6, 0))
        self.settings_status_var = tk.StringVar(value="Sistem durumu bekleniyor.")
        ttk.Label(self.settings_page, textvariable=self.settings_status_var, wraplength=1100).pack(anchor="w", padx=13, pady=(0, 7))
        self.settings_diagnostics_text = tk.Text(
            self.settings_page, wrap="word", state="disabled", height=18,
            background="#000000", foreground="#FFFFFF", insertbackground="#FFFFFF",
            relief="flat", padx=9, pady=7, font=("Consolas", max(8, self.font_size - 1)),
        )
        self.settings_diagnostics_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        drawings = self.panel_settings.get("chart_drawings", {})
        self.chart_drawings: dict[str, list[dict[str, Any]]] = drawings if isinstance(drawings, dict) else {}
        tracked = self.panel_settings.get("tracked_symbols", [])
        self.tracked_symbols: list[str] = [
            str(value).upper() for value in tracked if isinstance(value, str)
        ][:5] if isinstance(tracked, list) else []
        self._analysis_pending_points: list[dict[str, float]] = []
        self._analysis_chart_geometry: dict[str, float] = {}
        self._analysis_hover_xy: tuple[float, float] | None = None
        self._analysis_undo_state: tuple[str, dict[str, Any]] | None = None
        self._analysis_undo_token = 0
        self._radar_all_keys: list[str] = []
        self._refresh_workspace_views()

    def _show_workspace_page(self, page: str) -> None:
        frames = getattr(self, "workspace_page_frames", {})
        if page not in frames:
            page = "radar"
        for frame in frames.values():
            try:
                frame.pack_forget()
            except tk.TclError:
                pass
        frames[page].pack(fill="both", expand=True)
        self.workspace_current_page = page
        for page_key, button in getattr(self, "workspace_nav_buttons", {}).items():
            button.configure(state="disabled" if page_key == page else "normal")
        if page == "btcturk":
            if self.btcturk_pro_data is None and not self.btcturk_pro_load_busy:
                self._btcturk_pro_load_pair(self.btcturk_pro_symbol)
        elif page == "analysis":
            self._refresh_analysis_view()
        elif page == "market":
            self._refresh_market_page()
        elif page == "overview":
            self._refresh_overview_page()
        elif page == "tracking":
            self._refresh_tracking_page()
        elif page == "plans":
            self._refresh_plans_page()
        elif page == "settings":
            self._refresh_settings_page()

    def _refresh_workspace_views(self) -> None:
        if not hasattr(self, "workspace_page_frames"):
            return
        self._refresh_overview_page()
        self._refresh_tracking_page()
        self._refresh_plans_page()
        self._refresh_market_page()
        self._refresh_settings_page()
        if self.workspace_current_page == "analysis":
            self._refresh_analysis_view()

    def _candidate_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        wanted = str(symbol or "").upper()
        for candidate in self.current_candidates.values():
            name = str(candidate.get("symbol") or candidate.get("base_asset") or "").upper()
            if name == wanted or (name and wanted == name + "USDT"):
                return candidate
        return None

    def _select_candidate_by_symbol(self, symbol: str) -> bool:
        candidate = self._candidate_for_symbol(symbol)
        if not candidate:
            messagebox.showinfo(
                "Aday bulunamadı",
                f"{symbol} için güncel teknik aday kaydı bulunmuyor. Fırsat Radarı güncellendiğinde tekrar deneyin.",
            )
            return False
        key = self._candidate_key(candidate)
        if not self.tree.exists(key):
            self._show_workspace_page("radar")
            messagebox.showinfo(
                "Aday görünür değil",
                "Aday mevcut listede görünmüyor; arama filtresini temizleyip tekrar seçin.",
            )
            return False
        self.tree.selection_set(key)
        self.tree.focus(key)
        self.current_candidate_key = key
        self._selection_changed()
        return True

    def _overview_selection_changed(self, _event: Any = None) -> None:
        selection = self.overview_tree.selection()
        if selection:
            self._select_candidate_by_symbol(selection[0])

    def _overview_open_selected(self) -> None:
        selection = self.overview_tree.selection()
        if selection and self._select_candidate_by_symbol(selection[0]):
            self._show_workspace_page("analysis")

    def _refresh_overview_page(self) -> None:
        if not hasattr(self, "overview_tree"):
            return
        state = self.current_state if isinstance(self.current_state, dict) else {}
        count = state.get("scan_symbol_count", state.get("common_pair_count", "—"))
        strong = sum(
            1 for item in self.current_candidates.values()
            if item.get("strong_opportunity_qualified") is True
            and item.get("strong_alarm_eligible") is True
            and item.get("data_freshness") == "CANLI AKIŞ GÜNCEL"
        )
        self.overview_metric_vars["engine"].set(self.status_var.get())
        self.overview_metric_vars["universe"].set(f"{count} parite")
        self.overview_metric_vars["strong"].set(f"{strong} güçlü aday")
        self.overview_metric_vars["freshness"].set(
            "Canlı veri güncel" if self.engine and self.engine.poll() is None
            and state.get("live_stream_status") == "CANLI AKIŞ GÜNCEL"
            else "Güncellik teyidi yok"
        )
        old_selection = self.overview_tree.selection()
        selected_symbol = old_selection[0] if old_selection else None
        self.overview_tree.delete(*self.overview_tree.get_children())
        for key in getattr(self, "_radar_all_keys", []):
            item = self.current_candidates.get(key)
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or item.get("base_asset") or "")
            phase = item.get("phase") or item.get("last_known_phase") or "—"
            freshness = "GÜNCEL" if item.get("data_freshness") == "CANLI AKIŞ GÜNCEL" else "UYARI"
            decision = str(item.get("final_decision") or item.get("decision_class") or item.get("state") or "—")
            self.overview_tree.insert(
                "", "end", iid=symbol,
                values=(
                    symbol, _format_price(item.get("latest_price", item.get("price"))),
                    item.get("opportunity_score", item.get("score_0_100", "—")),
                    phase, freshness, decision,
                ),
            )
        if selected_symbol and self.overview_tree.exists(selected_symbol):
            self.overview_tree.selection_set(selected_symbol)
        candidate = self._selected_candidate()
        if candidate:
            plan = candidate.get("risk_plan") if isinstance(candidate.get("risk_plan"), dict) else {}
            detail = "\n".join((
                f"Seçili coin: {candidate.get('symbol') or candidate.get('base_asset') or '—'}",
                f"Fiyat: {_format_price(candidate.get('latest_price'))} USDT",
                f"Teknik puan: {candidate.get('opportunity_score', candidate.get('score_0_100', '—'))}",
                f"Aşama: {candidate.get('phase') or candidate.get('last_known_phase') or '—'}",
                f"Karar: {candidate.get('final_decision') or candidate.get('decision_class') or '—'}",
                f"Neden öne çıkıyor: {candidate.get('decision_reason') or 'Gerekçe mevcut değil'}",
                f"Plan durumu: {plan.get('status') or 'Plan yok'}",
                "",
                _format_candidate_decision_summary(candidate),
                "",
                "BTC piyasa özeti:",
                _format_btc_context_summary(state),
            ))
        else:
            detail = "Henüz seçilmiş teknik aday yok.\n\nFırsat Radarı ekranından bir coin seçin."
        self._set_text(self.overview_detail_text, detail)

    def _tracking_add_selected(self) -> None:
        candidate = self._selected_candidate()
        if not candidate:
            messagebox.showinfo("Aktif Takip", "Önce Fırsat Radarı ekranında bir coin seçin.")
            return
        symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "").upper()
        if not symbol:
            return
        if symbol in self.tracked_symbols:
            messagebox.showinfo("Aktif Takip", f"{symbol} zaten takip listesinde.")
            return
        if len(self.tracked_symbols) >= 5:
            messagebox.showinfo("Aktif Takip", "Aktif Takip listesinde en fazla beş parite tutulabilir.")
            return
        self.tracked_symbols.append(symbol)
        self.panel_settings["tracked_symbols"] = list(self.tracked_symbols)
        self._save_panel_settings()
        self._refresh_tracking_page()

    def _tracking_remove_selected(self) -> None:
        selection = self.tracking_tree.selection()
        if not selection:
            messagebox.showinfo("Aktif Takip", "Listeden çıkarılacak pariteyi seçin.")
            return
        symbol = selection[0]
        self.tracked_symbols = [value for value in self.tracked_symbols if value != symbol]
        self.panel_settings["tracked_symbols"] = list(self.tracked_symbols)
        self._save_panel_settings()
        self._refresh_tracking_page()

    def _tracking_open_selected(self) -> None:
        selection = self.tracking_tree.selection()
        if not selection:
            messagebox.showinfo("Aktif Takip", "İncelenecek pariteyi seçin.")
            return
        if self._select_candidate_by_symbol(selection[0]):
            self._show_workspace_page("analysis")

    def _refresh_tracking_page(self) -> None:
        if not hasattr(self, "tracking_tree"):
            return
        self.tracking_tree.delete(*self.tracking_tree.get_children())
        present = 0
        for symbol in self.tracked_symbols:
            candidate = self._candidate_for_symbol(symbol)
            if not candidate:
                self.tracking_tree.insert(
                    "", "end", iid=symbol,
                    values=(symbol, "—", "—", "—", "EVRENDE BEKLENİYOR", "Güncel aday kaydı yok"),
                )
                continue
            present += 1
            plan = candidate.get("risk_plan") if isinstance(candidate.get("risk_plan"), dict) else {}
            self.tracking_tree.insert(
                "", "end", iid=symbol,
                values=(
                    symbol, _format_price(candidate.get("latest_price")),
                    candidate.get("opportunity_score", candidate.get("score_0_100", "—")),
                    candidate.get("phase") or candidate.get("last_known_phase") or "—",
                    "GÜNCEL" if candidate.get("data_freshness") == "CANLI AKIŞ GÜNCEL" else "UYARI",
                    plan.get("status") or candidate.get("final_decision") or "Plan yok",
                ),
            )
        self.tracking_status_var.set(
            f"{len(self.tracked_symbols)}/5 parite takipte · {present} tanesi güncel aday verisiyle eşleşti."
            if self.tracked_symbols else "Takip listeniz boş. Fırsat Radarı'ndan coin seçip ekleyebilirsiniz."
        )

    def _analysis_set_timeframe(self, timeframe: str) -> None:
        if timeframe not in ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"):
            return
        self.analysis_timeframe_var.set(timeframe)
        self._analysis_pending_points = []
        for key, button in self.analysis_timeframe_buttons.items():
            button.configure(state="disabled" if key == timeframe else "normal")
        self._refresh_analysis_view()

    def _analysis_current_metrics(self, candidate: dict[str, Any]) -> dict[str, Any]:
        rows = candidate.get("timeframes")
        rows = rows if isinstance(rows, dict) else {}
        row = rows.get(self.analysis_timeframe_var.get())
        metrics = row.get("metrics") if isinstance(row, dict) else None
        return metrics if isinstance(metrics, dict) else {}

    def _refresh_analysis_indicators(self) -> None:
        candidate = self._selected_candidate()
        metrics = self._analysis_current_metrics(candidate) if candidate else {}
        components = candidate.get("components") if candidate and isinstance(candidate.get("components"), dict) else {}
        values = {
            "rsi": (
                f"RSI({metrics.get('rsi_period', 14)}): {_format_metric(metrics.get('rsi_14'))} · "
                f"{metrics.get('rsi_zone') or 'bölge belirlenmedi'}"
            ),
            "macd": (
                f"MACD: {_format_metric(metrics.get('macd_line'))} · Sinyal: "
                f"{_format_metric(metrics.get('macd_signal'))} · Histogram: {_format_metric(metrics.get('macd_histogram'))}"
            ),
            "momentum": (
                f"Motor momentum bileşeni: {_format_metric(components.get('momentum'))} puan. "
                "Bağımsız momentum zaman serisi motor durumunda sunulmuyor."
            ),
        }
        for key, value in values.items():
            self.analysis_indicator_vars[key].set(value)
            self.analysis_indicator_frames[key].pack_forget() if not self.analysis_indicator_checks[key].get() else None
            if self.analysis_indicator_checks[key].get():
                self.analysis_indicator_frames[key].pack(side="left", fill="both", expand=True, padx=(0, 7))

    def _refresh_analysis_view(self) -> None:
        if not hasattr(self, "analysis_canvas"):
            return
        candidate = self._selected_candidate()
        if not candidate:
            self.analysis_symbol_var.set("Coin seçilmedi")
            self.analysis_price_var.set("Fiyat: —")
            self.analysis_status_var.set("Fırsat Radarı'nda bir aday seçin. Grafik yalnızca motorun sağladığı gerçek mumlarla çizilir.")
            self._set_text(self.analysis_plan_text, "Seçili aday bulunmuyor.")
            self._refresh_analysis_indicators()
            self._draw_analysis_chart()
            return
        symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "—")
        self.analysis_symbol_var.set(f"{symbol} · {self.analysis_timeframe_var.get()}")
        price = candidate.get("latest_price")
        self.analysis_price_var.set(f"Fiyat: {_format_price(price)} USDT")
        candles = candidate.get("recent_closed_candles")
        candles = candles if isinstance(candles, dict) else {}
        bars = candles.get(self.analysis_timeframe_var.get())
        count = len(bars) if isinstance(bars, list) else 0
        self.analysis_status_var.set(
            f"Kaynak: Binance Spot · {self.analysis_timeframe_var.get()} · "
            f"Motor anlık görüntüsünde {count} kapanmış mum mevcut. Daha uzun geçmiş motor durumunda sunulmadığında grafik genişletilmez."
        )
        plan = candidate.get("risk_plan") if isinstance(candidate.get("risk_plan"), dict) else {}
        target_lines = []
        for index, target in enumerate(plan.get("targets", []) if isinstance(plan.get("targets"), list) else [], start=1):
            if isinstance(target, dict) and _safe_float(target.get("price")) is not None:
                target_lines.append(
                    f"Hedef {index}: {_format_price(target.get('price'))} USDT "
                    f"({target.get('basis') or target.get('name') or 'teknik hedef'})"
                )
        details = [
            f"Plan durumu: {plan.get('status') or 'plan yok'}",
            f"Zaman dilimi: {plan.get('timeframe') or candidate.get('phase_timeframe') or '—'}",
            f"Koşullu giriş alt/üst: {_format_price(plan.get('entry_zone_low'))} / {_format_price(plan.get('entry_zone_high'))} USDT",
            f"Zarar-kes: {_format_price(plan.get('stop_loss'))} USDT",
            *(target_lines or ["Teknik hedef: mevcut değil"]),
            f"Geçersizlik koşulu: {plan.get('invalid_if') or plan.get('reason') or 'belirtilmedi'}",
            "",
            "Not: Bu bir işlem planı taslağıdır; emir gönderilmez. Yeni öneri otomatik etkinleştirilmez.",
        ]
        self._set_text(self.analysis_plan_text, "\n".join(details))
        self._refresh_analysis_indicators()
        self._draw_analysis_chart()

    def _analysis_drawing_key(self) -> str:
        candidate = self._selected_candidate()
        symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "") if candidate else ""
        return f"{symbol}|{self.analysis_timeframe_var.get()}"

    def _save_analysis_drawings(self) -> None:
        self.panel_settings["chart_drawings"] = self.chart_drawings
        self._save_panel_settings()

    def _draw_analysis_chart(self, _event: Any = None) -> None:
        canvas = getattr(self, "analysis_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(420, canvas.winfo_width())
        height = max(270, canvas.winfo_height())
        candidate = self._selected_candidate()
        timeframe = self.analysis_timeframe_var.get() if hasattr(self, "analysis_timeframe_var") else "15m"
        if not candidate:
            canvas.create_text(
                width / 2, height / 2,
                text="Grafik için Fırsat Radarı'ndan bir coin seçin.",
                fill="#FFFFFF", font=("Segoe UI", 12),
            )
            self._analysis_chart_geometry = {}
            return
        candle_map = candidate.get("recent_closed_candles")
        candle_map = candle_map if isinstance(candle_map, dict) else {}
        raw_bars = candle_map.get(timeframe)
        bars = [
            bar for bar in raw_bars
            if isinstance(bar, dict)
            and all(_safe_float(bar.get(key)) is not None for key in ("t", "o", "h", "l", "c"))
        ][-8:] if isinstance(raw_bars, list) else []
        if not bars:
            canvas.create_text(
                width / 2, height / 2,
                text=f"{timeframe}: motor durumunda kapanmış mum bulunmuyor.\nGerçek veri gelene kadar örnek mum çizilmez.",
                fill="#FFD166", justify="center", font=("Segoe UI", 11),
            )
            self._analysis_chart_geometry = {}
            return

        show_volume = self.analysis_layer_vars["volume"].get()
        left, right, top = 78.0, width - 88.0, 24.0
        price_bottom = height * (0.67 if show_volume else 0.88)
        volume_top, volume_bottom = height * 0.76, height - 27.0
        prices = [
            float(bar[key]) for bar in bars for key in ("o", "h", "l", "c")
        ]
        low, high = min(prices), max(prices)
        span = max(high - low, abs(high) * 0.001, 1e-10)
        low -= span * 0.10
        high += span * 0.10
        usable = max(1.0, price_bottom - top)
        def y_price(value: float) -> float:
            return top + (high - value) / (high - low) * usable
        first_time = float(bars[0]["t"])
        last_time = float(bars[-1]["t"])
        if last_time <= first_time:
            last_time = first_time + 1.0
        def x_time(value: float) -> float:
            return left + (value - first_time) / (last_time - first_time) * (right - left)
        step = (right - left) / max(1, len(bars))
        def x_index(index: int) -> float:
            return left + (index + 0.5) * step
        self._analysis_chart_geometry = {
            "left": left, "right": right, "top": top, "bottom": price_bottom,
            "low": low, "high": high, "first_time": first_time, "last_time": last_time,
        }

        for i in range(5):
            fraction = i / 4
            yy = top + fraction * usable
            value = high - fraction * (high - low)
            canvas.create_line(left, yy, right, yy, fill="#273642")
            canvas.create_text(left - 7, yy, text=_format_price(value), fill="#B1BEC9", anchor="e", font=("Consolas", 8))
        max_volume = max((_safe_float(bar.get("v")) or 0.0) for bar in bars) or 1.0
        body_width = max(4.0, min(18.0, step * 0.55))
        for index, bar in enumerate(bars):
            x = x_index(index)
            open_price, close_price = float(bar["o"]), float(bar["c"])
            high_price, low_price = float(bar["h"]), float(bar["l"])
            color = "#39FF88" if close_price >= open_price else "#FF6B72"
            canvas.create_line(x, y_price(high_price), x, y_price(low_price), fill=color, width=1.5)
            y_open, y_close = y_price(open_price), y_price(close_price)
            y_top, y_bottom = min(y_open, y_close), max(y_open, y_close)
            canvas.create_rectangle(
                x - body_width / 2, y_top, x + body_width / 2,
                max(y_top + 2, y_bottom), fill=color, outline=color,
            )
            if show_volume:
                volume = max(0.0, _safe_float(bar.get("v")) or 0.0)
                bar_height = volume / max_volume * max(1.0, volume_bottom - volume_top)
                canvas.create_rectangle(
                    x - body_width / 2, volume_bottom - bar_height,
                    x + body_width / 2, volume_bottom,
                    fill=color, outline="", stipple="gray50",
                )
            stamp = datetime.fromtimestamp(float(bar["t"]) / 1000, tz=timezone.utc).astimezone()
            canvas.create_text(
                x, height - 8, text=stamp.strftime("%d.%m %H:%M"),
                fill="#98A8B6", anchor="s", font=("Consolas", 7),
            )

        metrics = self._analysis_current_metrics(candidate)
        layers = self.analysis_layer_vars
        plan = candidate.get("risk_plan") if isinstance(candidate.get("risk_plan"), dict) else {}
        levels: list[tuple[float, str, str]] = []
        def add_level(raw: Any, label: str, color: str) -> None:
            value = _safe_float(raw)
            if value is not None and low <= value <= high:
                levels.append((value, label, color))
        if layers["entry"].get():
            add_level(plan.get("entry_zone_low"), "GİRİŞ ALT", "#E9B65D")
            add_level(plan.get("entry_zone_high"), "GİRİŞ ÜST", "#E9B65D")
        if layers["stop"].get():
            add_level(plan.get("stop_loss"), "ZARAR-KES / GEÇERSİZLİK", "#F06A75")
        if layers["targets"].get():
            targets = plan.get("targets")
            if isinstance(targets, list):
                for index, target in enumerate(targets[:4], start=1):
                    if isinstance(target, dict):
                        add_level(target.get("price"), f"HEDEF {index}", "#C6A4F5")
        if layers["sr"].get():
            zones = metrics.get("support_resistance_zones")
            if isinstance(zones, list):
                for zone in zones:
                    if not isinstance(zone, dict):
                        continue
                    kind = zone.get("kind")
                    label = "DESTEK" if kind == "support" else "DİRENÇ" if kind == "resistance" else str(kind or "BÖLGE")
                    add_level(zone.get("center"), label, "#42B9A1" if kind == "support" else "#D99B62")
        if layers["fib"].get():
            fib = metrics.get("fibonacci")
            if isinstance(fib, dict) and fib.get("available") is True:
                for group_name, group in (("FIB GERİ ÇEKİLME", fib.get("retracements")), ("FIB UZATMA", fib.get("extensions"))):
                    if isinstance(group, dict):
                        for name, value in group.items():
                            add_level(value, f"{group_name} {str(name).replace('retracement_', '').replace('extension_', '')}", "#69A8E8")
        if layers["ema"].get():
            add_level(metrics.get("ema_fast"), "EMA HIZLI", "#72A9ED")
            add_level(metrics.get("ema_slow"), "EMA YAVAŞ", "#B69BEA")
        if layers["channel"].get():
            channel = metrics.get("confirmed_channel")
            if isinstance(channel, dict) and channel.get("available") is True:
                add_level(channel.get("upper_now"), "KANAL ÜST", "#B69BEA")
                add_level(channel.get("lower_now"), "KANAL ALT", "#B69BEA")
        for value, label, color in levels:
            yy = y_price(value)
            canvas.create_line(left, yy, right, yy, fill=color, dash=(5, 4), width=1)
            canvas.create_text(right - 3, yy - 5, text=f"{label}  {_format_price(value)}", fill=color, anchor="e", font=("Segoe UI", 8, "bold"))

        drawings = self.chart_drawings.get(self._analysis_drawing_key(), [])
        if isinstance(drawings, list):
            for drawing in drawings:
                if not isinstance(drawing, dict):
                    continue
                points = drawing.get("points")
                if not isinstance(points, list) or len(points) < 2:
                    continue
                try:
                    x1, y1 = x_time(float(points[0]["t"])), y_price(float(points[0]["p"]))
                    x2, y2 = x_time(float(points[1]["t"])), y_price(float(points[1]["p"]))
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                canvas.create_line(x1, y1, x2, y2, fill="#E9D27B", width=2, dash=(7, 3))
                if drawing.get("kind") == "channel":
                    offset = _safe_float(drawing.get("offset")) or 0.0
                    if low <= float(points[0]["p"]) + offset <= high and low <= float(points[1]["p"]) + offset <= high:
                        canvas.create_line(
                            x1, y_price(float(points[0]["p"]) + offset),
                            x2, y_price(float(points[1]["p"]) + offset),
                            fill="#E9D27B", width=1.5, dash=(5, 4),
                        )
                canvas.create_oval(x1 - 3, y1 - 3, x1 + 3, y1 + 3, fill="#E9D27B", outline="")
                canvas.create_oval(x2 - 3, y2 - 3, x2 + 3, y2 + 3, fill="#E9D27B", outline="")

        if self._analysis_pending_points:
            pending = self._analysis_pending_points
            for point in pending:
                try:
                    px = x_time(float(point["t"]))
                    py = y_price(float(point["p"]))
                    canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#FFFFFF", outline="#E9D27B")
                except (KeyError, TypeError, ValueError):
                    pass
            if len(pending) >= 2:
                canvas.create_line(
                    x_time(float(pending[0]["t"])), y_price(float(pending[0]["p"])),
                    x_time(float(pending[1]["t"])), y_price(float(pending[1]["p"])),
                    fill="#FFFFFF", dash=(4, 3),
                )

        if self._analysis_hover_xy:
            hx, hy = self._analysis_hover_xy
            if left <= hx <= right and top <= hy <= price_bottom:
                canvas.create_line(hx, top, hx, price_bottom, fill="#8198AC", dash=(2, 3), tags=("hover",))
                canvas.create_line(left, hy, right, hy, fill="#8198AC", dash=(2, 3), tags=("hover",))
        fib = metrics.get("fibonacci")
        fib_note = ""
        if layers["fib"].get() and (not isinstance(fib, dict) or fib.get("available") is not True):
            fib_note = " · Fibonacci bu zaman diliminde teyitli değil"
        canvas.create_text(
            left, height - 25,
            text=f"Binance Spot · {timeframe} · {len(bars)} kapanmış mum · hacim{fib_note}",
            fill="#B8C5D0", anchor="w", font=("Segoe UI", 8),
        )

    def _analysis_chart_motion(self, event: Any) -> None:
        geometry = self._analysis_chart_geometry
        if not geometry:
            return
        x, y = float(event.x), float(event.y)
        left, right = geometry["left"], geometry["right"]
        top, bottom = geometry["top"], geometry["bottom"]
        if left <= x <= right and top <= y <= bottom:
            fraction = (y - top) / max(1.0, bottom - top)
            price = geometry["high"] - fraction * (geometry["high"] - geometry["low"])
            self.analysis_hover_var.set(f"Fiyat: {_format_price(price)} USDT")
            self._analysis_hover_xy = (x, y)
            self._draw_analysis_chart()
        else:
            self.analysis_hover_var.set("İmleç: —")
            self._analysis_hover_xy = None

    def _analysis_chart_point(self, event: Any) -> dict[str, float] | None:
        geometry = self._analysis_chart_geometry
        if not geometry:
            return None
        left, right = geometry["left"], geometry["right"]
        top, bottom = geometry["top"], geometry["bottom"]
        if not (left <= event.x <= right and top <= event.y <= bottom):
            return None
        x_fraction = (float(event.x) - left) / max(1.0, right - left)
        y_fraction = (float(event.y) - top) / max(1.0, bottom - top)
        stamp = geometry["first_time"] + x_fraction * (geometry["last_time"] - geometry["first_time"])
        price = geometry["high"] - y_fraction * (geometry["high"] - geometry["low"])
        return {"t": float(stamp), "p": float(price)}

    def _analysis_chart_click(self, event: Any) -> None:
        tool = self.analysis_tool_var.get()
        if tool == "İmleç":
            return
        point = self._analysis_chart_point(event)
        if point is None:
            return
        required = 3 if tool == "Paralel kanal" else 2
        self._analysis_pending_points.append(point)
        if len(self._analysis_pending_points) < required:
            self.analysis_status_var.set(
                "Çizim noktası seçildi. " +
                ("Paralel kanal için ikinci ve üçüncü noktayı seçin." if required == 3 else "Çizgiyi tamamlamak için ikinci noktayı seçin.")
            )
            self._draw_analysis_chart()
            return
        points = self._analysis_pending_points[:2]
        drawing: dict[str, Any] = {"kind": "channel" if required == 3 else "trend", "points": points}
        if required == 3:
            first, second, third = self._analysis_pending_points
            if abs(second["t"] - first["t"]) < 1:
                self._analysis_pending_points = []
                self.analysis_status_var.set("Paralel kanal için iki ana nokta farklı zamanlarda seçilmelidir.")
                self._draw_analysis_chart()
                return
            ratio = (third["t"] - first["t"]) / (second["t"] - first["t"])
            baseline = first["p"] + ratio * (second["p"] - first["p"])
            drawing["offset"] = third["p"] - baseline
        key = self._analysis_drawing_key()
        existing = self.chart_drawings.get(key, [])
        existing = existing if isinstance(existing, list) else []
        existing.append(drawing)
        self.chart_drawings[key] = existing
        self._analysis_pending_points = []
        self._save_analysis_drawings()
        self.analysis_status_var.set("Çizim kaydedildi; bu zaman dilimi ve coin için korunacak.")
        self._draw_analysis_chart()

    def _analysis_delete_last(self) -> None:
        key = self._analysis_drawing_key()
        drawings = self.chart_drawings.get(key, [])
        if not isinstance(drawings, list) or not drawings:
            messagebox.showinfo("Çizimler", "Bu coin ve zaman diliminde silinecek çizim yok.")
            return
        removed = drawings.pop()
        self.chart_drawings[key] = drawings
        self._analysis_undo_state = (key, removed)
        self._analysis_undo_token += 1
        token = self._analysis_undo_token
        self.analysis_undo_button.configure(state="normal")
        self.after(5000, lambda: self._analysis_expire_undo(token))
        self._save_analysis_drawings()
        self._draw_analysis_chart()

    def _analysis_expire_undo(self, token: int) -> None:
        if token != self._analysis_undo_token:
            return
        self._analysis_undo_state = None
        if hasattr(self, "analysis_undo_button"):
            self.analysis_undo_button.configure(state="disabled")

    def _analysis_undo_delete(self) -> None:
        if not self._analysis_undo_state:
            return
        key, drawing = self._analysis_undo_state
        drawings = self.chart_drawings.get(key, [])
        drawings = drawings if isinstance(drawings, list) else []
        drawings.append(drawing)
        self.chart_drawings[key] = drawings
        self._analysis_undo_state = None
        self._analysis_undo_token += 1
        self.analysis_undo_button.configure(state="disabled")
        self._save_analysis_drawings()
        self._draw_analysis_chart()

    def _overview_or_analysis_select(self, symbol: str, open_analysis: bool = False) -> None:
        if self._select_candidate_by_symbol(symbol) and open_analysis:
            self._show_workspace_page("analysis")

    def _plans_open_selected(self) -> None:
        selection = self.plans_tree.selection()
        if selection and self._select_candidate_by_symbol(selection[0]):
            self._show_workspace_page("analysis")

    def _refresh_plans_page(self) -> None:
        if not hasattr(self, "plans_tree"):
            return
        self.plans_tree.delete(*self.plans_tree.get_children())
        count = 0
        for key in getattr(self, "_radar_all_keys", []):
            candidate = self.current_candidates.get(key)
            if not isinstance(candidate, dict):
                continue
            plan = candidate.get("risk_plan")
            if not isinstance(plan, dict):
                continue
            targets = plan.get("targets") if isinstance(plan.get("targets"), list) else []
            target_text = ", ".join(
                _format_price(item.get("price")) for item in targets[:3]
                if isinstance(item, dict) and _safe_float(item.get("price")) is not None
            ) or "—"
            entry_low = _safe_float(plan.get("entry_zone_low"))
            entry_high = _safe_float(plan.get("entry_zone_high"))
            entry = (
                f"{_format_price(entry_low)} – {_format_price(entry_high)}"
                if entry_low is not None and entry_high is not None else "—"
            )
            symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "")
            self.plans_tree.insert(
                "", "end", iid=symbol,
                values=(
                    symbol, plan.get("status") or "Plan yok",
                    plan.get("timeframe") or candidate.get("phase_timeframe") or "—",
                    entry, _format_price(plan.get("stop_loss")), target_text,
                    candidate.get("final_decision") or candidate.get("decision_class") or "—",
                ),
            )
            count += 1
        self.plans_status_var.set(
            f"{count} aday için motor kaynaklı plan kaydı görüntüleniyor. Yeni plan, kullanıcı onayı olmadan etkinleştirilmez."
        )

    def _refresh_market_page(self) -> None:
        if hasattr(self, "market_context_text"):
            self._set_text(
                self.market_context_text,
                _format_btc_context_details(self.current_state)
                if isinstance(self.current_state, dict) and self.current_state
                else "BTC piyasa bağlamı için motor verisi bekleniyor.",
            )

    def _refresh_settings_page(self) -> None:
        if not hasattr(self, "settings_diagnostics_text"):
            return
        self.settings_status_var.set(
            f"{self.status_var.get()} · {self.live_status_var.get()} · {self.history_status_var.get()}"
        )
        payload = "\n".join((
            self.diagnostics_summary_var.get(),
            "",
            "Mevcut kontroller: Başlat, Durdur, Pariteleri Güncelle, Günlük Rapor, Analiz Raporu, "
            "Sorun Giderme ZIP, Seviye Takibi, Sesli Bildirim, Ses Testi, Ses Düzeyi, Yazı Boyutu ve Ekran Görüntüsü.",
            "",
            "Teknik motor ve BtcTurk PRO veri/işlem alanları ayrıdır. Bu sayfa motor ayarlarını değiştirmez; "
            "üst çubuktaki mevcut işlevleri ve tanılama durumunu tek noktada görünür kılar.",
        ))
        self._set_text(self.settings_diagnostics_text, payload)

    def _apply_radar_filters(self) -> None:
        if not hasattr(self, "tree"):
            return
        query = self.radar_search_var.get().strip().casefold() if hasattr(self, "radar_search_var") else ""
        for key in getattr(self, "_radar_all_keys", []):
            candidate = self.current_candidates.get(key, {})
            haystack = " ".join((
                str(candidate.get("symbol") or candidate.get("base_asset") or ""),
                str(candidate.get("decision_reason") or ""),
                str(candidate.get("final_decision") or candidate.get("decision_class") or ""),
                str(candidate.get("state") or ""),
            )).casefold()
            visible = not query or query in haystack
            if self.tree.exists(key):
                if visible:
                    self.tree.reattach(key, "", "end")
                else:
                    self.tree.detach(key)

    def _build_btcturk_pro_ui(self) -> None:
        page = self.btcturk_page
        page.columnconfigure(0, weight=1)

        header = ttk.Frame(page, padding=(12, 9, 12, 5))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="BtcTurk PRO · BAĞIMSIZ İŞLEM ANALİZİ", style="Section.TLabel").pack(side="left")
        self.btcturk_pro_status_label = ttk.Label(
            header, textvariable=self.btcturk_pro_status_var,
            style="SectionPending.TLabel", wraplength=380, justify="right",
        )
        self.btcturk_pro_status_label.pack(side="right", padx=(8, 0))
        ttk.Separator(page, orient="horizontal").grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        search_row = ttk.Frame(page, padding=(12, 0, 12, 6))
        search_row.grid(row=2, column=0, sticky="ew")
        ttk.Label(search_row, text="BtcTurk USDT paritesi:").pack(side="left", padx=(0, 6))
        self.btcturk_pro_pair_combo = ttk.Combobox(
            search_row, textvariable=self.btcturk_pro_entry_var,
            values=(), width=16,
        )
        self.btcturk_pro_pair_combo.pack(side="left", padx=(0, 6))
        self.btcturk_pro_pair_combo.bind("<Return>", lambda _event: self._btcturk_pro_open_pair())
        self.btcturk_pro_open_button = ttk.Button(
            search_row, text="Pariteyi Aç", command=self._btcturk_pro_open_pair,
        )
        self.btcturk_pro_open_button.pack(side="left", padx=(0, 6))
        self.btcturk_pro_refresh_button = ttk.Button(
            search_row, text="Veriyi Yenile", command=self._btcturk_pro_open_pair,
        )
        self.btcturk_pro_refresh_button.pack(side="left", padx=(0, 6))
        ttk.Button(
            search_row, text="Binance Seçimini Aktar",
            command=self._btcturk_pro_import_selected,
        ).pack(side="left")

        quote_frame = ttk.LabelFrame(page, text="BtcTurk piyasa verisi ve ayrı Binance karşılaştırması", padding=(8, 5))
        quote_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))
        quote_frame.columnconfigure(0, weight=1)
        quote_frame.columnconfigure(1, weight=1)
        ttk.Label(
            quote_frame, textvariable=self.btcturk_pro_quote_var,
            justify="left", wraplength=660,
        ).grid(row=0, column=0, sticky="w", padx=(3, 10))
        ttk.Label(
            quote_frame, textvariable=self.btcturk_pro_binance_var,
            justify="left", wraplength=560,
        ).grid(row=0, column=1, sticky="w", padx=(10, 3))

        cost_row = ttk.Frame(page, padding=(12, 0, 12, 7))
        cost_row.grid(row=4, column=0, sticky="ew")
        ttk.Label(cost_row, text="İşlem tutarı (USDT, isteğe bağlı):").pack(side="left", padx=(0, 5))
        self.btcturk_pro_amount_entry = ttk.Entry(
            cost_row, textvariable=self.btcturk_pro_amount_var, width=13,
        )
        self.btcturk_pro_amount_entry.pack(side="left", padx=(0, 5))
        ttk.Button(
            cost_row, text="Maliyet / kayma tahmini",
            command=self._btcturk_pro_estimate_cost,
        ).pack(side="left", padx=(0, 9))
        ttk.Label(
            cost_row, textvariable=self.btcturk_pro_market_rules_var,
            wraplength=680, justify="left",
        ).pack(side="left", fill="x", expand=True)
        ttk.Separator(page, orient="horizontal").grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 6))

        main = ttk.Panedwindow(page, orient="horizontal")
        main.grid(row=6, column=0, sticky="nsew", padx=12, pady=(0, 6))
        page.rowconfigure(6, weight=5)
        left = ttk.Frame(main, padding=(0, 0, 6, 0))
        right = ttk.Frame(main, padding=(6, 0, 0, 0))
        main.add(left, weight=6)
        main.add(right, weight=4)

        chart_header = ttk.Frame(left)
        chart_header.pack(fill="x", pady=(0, 5))
        ttk.Label(chart_header, text="BtcTurk mum ve hacim grafiği", style="Section.TLabel").pack(side="left")
        timeframe_row = ttk.Frame(left)
        timeframe_row.pack(fill="x", pady=(0, 4))
        self.btcturk_pro_timeframe_buttons: dict[str, ttk.Button] = {}
        for timeframe in BTCTURK_PRO_TIMEFRAMES:
            button = ttk.Button(
                timeframe_row, text=timeframe,
                command=lambda selected=timeframe: self._btcturk_pro_select_timeframe(selected),
                width=5,
            )
            button.pack(side="left", padx=(0, 3))
            self.btcturk_pro_timeframe_buttons[timeframe] = button
        layer_row = ttk.Frame(left)
        layer_row.pack(fill="x", pady=(0, 4))
        for label, variable in (
            ("İşlem planı", self.btcturk_pro_show_plan),
            ("Destek/direnç", self.btcturk_pro_show_support_resistance),
            ("Fibonacci", self.btcturk_pro_show_fibonacci),
            ("Kanal", self.btcturk_pro_show_channel),
        ):
            ttk.Checkbutton(
                layer_row, text=label, variable=variable,
                command=self._btcturk_pro_draw_chart,
            ).pack(side="left", padx=(0, 9))
        self.btcturk_pro_chart = tk.Canvas(
            left, background="#000000", highlightbackground="#777777",
            highlightthickness=1, height=330,
        )
        self.btcturk_pro_chart.pack(fill="both", expand=True)
        self.btcturk_pro_chart.bind(
            "<Configure>", lambda _event: self._btcturk_pro_draw_chart(),
            add="+",
        )

        ttk.Label(right, text="Emir defteri · ilk 10 kademe", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        book_frame = ttk.Frame(right)
        book_frame.pack(fill="both", expand=True)
        columns = ("side", "price", "quantity", "value")
        self.btcturk_pro_orderbook_tree = ttk.Treeview(
            book_frame, columns=columns, show="headings", height=14,
        )
        for column, heading, width in (
            ("side", "Yön", 62), ("price", "Fiyat (USDT)", 118),
            ("quantity", "Miktar", 105), ("value", "Toplam (USDT)", 120),
        ):
            self.btcturk_pro_orderbook_tree.heading(column, text=heading)
            self.btcturk_pro_orderbook_tree.column(
                column, width=width, minwidth=48, anchor="center",
                stretch=column in {"price", "value"},
            )
        book_scroll = ttk.Scrollbar(
            book_frame, orient="vertical",
            style="Slim.Vertical.TScrollbar",
            command=self.btcturk_pro_orderbook_tree.yview,
        )
        self.btcturk_pro_orderbook_tree.configure(yscrollcommand=book_scroll.set)
        self.btcturk_pro_orderbook_tree.pack(side="left", fill="both", expand=True)
        book_scroll.pack(side="right", fill="y")
        self.btcturk_pro_orderbook_tree.tag_configure("ask", foreground="#FF7777")
        self.btcturk_pro_orderbook_tree.tag_configure("bid", foreground="#39FF88")

        plan_frame = ttk.LabelFrame(page, text="BtcTurk verisine dayalı işlem planı ve maliyet", padding=5)
        plan_frame.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 6))
        self.btcturk_pro_cost_text = tk.Text(
            plan_frame, height=7, wrap="word",
            font=("Consolas", max(9, self.font_size - 1)),
            background="#000000", foreground="#FFFFFF",
            insertbackground="#FFFFFF", state="disabled",
            relief="flat", padx=5, pady=4,
        )
        self.btcturk_pro_cost_text.pack(fill="both", expand=True)
        self.btcturk_pro_cost_text.tag_configure("good", foreground="#39FF88")
        self.btcturk_pro_cost_text.tag_configure("warning", foreground="#FFD166")
        self.btcturk_pro_cost_text.tag_configure("bad", foreground="#FF7777")

        technical_frame = ttk.LabelFrame(page, text="Sekiz zaman diliminde teknik değerlendirme", padding=5)
        technical_frame.grid(row=8, column=0, sticky="nsew", padx=12, pady=(0, 10))
        page.rowconfigure(8, weight=2)
        technical_inner = ttk.Frame(technical_frame)
        technical_inner.pack(fill="both", expand=True)
        self.btcturk_pro_technical_text = tk.Text(
            technical_inner, height=8, wrap="none",
            font=("Consolas", max(9, self.font_size - 1)),
            background="#000000", foreground="#FFFFFF",
            insertbackground="#FFFFFF", state="disabled",
            relief="flat", padx=5, pady=4,
        )
        technical_y = ttk.Scrollbar(
            technical_inner, orient="vertical",
            style="Slim.Vertical.TScrollbar",
            command=self.btcturk_pro_technical_text.yview,
        )
        technical_x = ttk.Scrollbar(
            technical_inner, orient="horizontal",
            style="Slim.Horizontal.TScrollbar",
            command=self.btcturk_pro_technical_text.xview,
        )
        self.btcturk_pro_technical_text.configure(
            yscrollcommand=technical_y.set, xscrollcommand=technical_x.set,
        )
        self.btcturk_pro_technical_text.grid(row=0, column=0, sticky="nsew")
        technical_y.grid(row=0, column=1, sticky="ns")
        technical_x.grid(row=1, column=0, sticky="ew")
        technical_inner.rowconfigure(0, weight=1)
        technical_inner.columnconfigure(0, weight=1)


    def _open_btcturk_pro_from_radar(self) -> None:
        candidate = self._selected_candidate()
        symbol = None
        if isinstance(candidate, dict):
            symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "").upper().strip()
        self._show_workspace_page("btcturk")
        if symbol:
            symbol = symbol.replace("/", "").replace("_", "")
            if not symbol.endswith("USDT"):
                symbol += "USDT"
            self.btcturk_pro_entry_var.set(symbol)
            self._btcturk_pro_load_pair(symbol)
        elif self.btcturk_pro_data is None and not self.btcturk_pro_load_busy:
            self._btcturk_pro_load_pair(self.btcturk_pro_symbol)

    def _btcturk_pro_import_selected(self) -> None:
        candidate = self._selected_candidate()
        if not isinstance(candidate, dict):
            messagebox.showinfo(
                "BtcTurk PRO", "Önce Fırsat Radarı ekranında bir coin seçin.",
            )
            return
        symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "").upper().strip()
        symbol = symbol.replace("/", "").replace("_", "")
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        self._show_workspace_page("btcturk")
        self.btcturk_pro_entry_var.set(symbol)
        self._btcturk_pro_load_pair(symbol)

    def _btcturk_pro_open_pair(self) -> None:
        symbol = str(self.btcturk_pro_entry_var.get() or "").upper().replace("/", "").replace("_", "").strip()
        if symbol and not symbol.endswith("USDT"):
            symbol += "USDT"
        if not re.fullmatch(r"[A-Z0-9]{2,26}USDT", symbol):
            messagebox.showwarning(
                "BtcTurk PRO", "Geçerli bir USDT paritesi girin. Örnek: BTCUSDT.",
            )
            return
        self._btcturk_pro_load_pair(symbol)

    def _btcturk_pro_save_last_pair(self, symbol: str) -> None:
        destination = DATA_DIR / "btcturk_pro_state.json"
        temporary = destination.with_name(destination.name + ".tmp")
        payload = {
            "last_symbol": symbol,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        except OSError as exc:
            LOGGER.warning("BtcTurk PRO son parite kaydı yazılamadı: %s", exc)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _btcturk_pro_load_pair(self, symbol: str) -> None:
        symbol = str(symbol or "").upper().replace("/", "").replace("_", "").strip()
        if symbol and not symbol.endswith("USDT"):
            symbol += "USDT"
        if not re.fullmatch(r"[A-Z0-9]{2,26}USDT", symbol):
            self.btcturk_pro_status_var.set("Geçersiz USDT paritesi")
            return
        self.btcturk_pro_symbol = symbol
        self.btcturk_pro_entry_var.set(symbol)
        self._btcturk_pro_save_last_pair(symbol)
        self.btcturk_pro_status_var.set(f"{symbol} · BtcTurk verileri alınıyor…")
        self.btcturk_pro_open_button.configure(state="disabled")
        self.btcturk_pro_refresh_button.configure(state="disabled")
        self.btcturk_pro_request_id += 1
        request_id = self.btcturk_pro_request_id
        self.btcturk_pro_load_busy = True

        def worker() -> None:
            try:
                markets = fetch_btcturk_pro_markets()
                market = markets.get(symbol)
                if market is None:
                    result = {
                        "ok": True, "pair_found": False,
                        "symbol": symbol, "markets": markets,
                    }
                else:
                    quote_error = None
                    orderbook_error = None
                    try:
                        ticker = fetch_btcturk_pro_ticker(symbol)
                    except Exception as exc:
                        ticker = {
                            "symbol": symbol, "last": None, "bid": None, "ask": None,
                            "timestamp_ms": 0, "base_volume_24h": None,
                            "change_24h_pct": None, "source": "BtcTurk ticker",
                        }
                        quote_error = f"{type(exc).__name__}: {str(exc)[:220]}"
                    try:
                        book = fetch_btcturk_pro_orderbook(symbol)
                    except Exception as exc:
                        book = {
                            "symbol": symbol, "bids": [], "asks": [],
                            "timestamp_ms": 0, "source": "BtcTurk emir defteri",
                        }
                        orderbook_error = f"{type(exc).__name__}: {str(exc)[:220]}"
                    bars = fetch_btcturk_pro_candles(symbol)
                    data = analyze_btcturk_pro(
                        symbol, markets, ticker, book, bars,
                        self.settings if isinstance(self.settings, dict) else {},
                    )
                    comparison = fetch_binance_comparison(symbol)
                    data["binance_comparison"] = comparison
                    data["quote_error"] = quote_error
                    data["orderbook_error"] = orderbook_error
                    result = {
                        "ok": True, "pair_found": True,
                        "symbol": symbol, "markets": markets, "data": data,
                    }
            except Exception as exc:
                result = {
                    "ok": False,
                    "symbol": symbol,
                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                }
            try:
                self.after(0, self._btcturk_pro_apply_load, request_id, result)
            except tk.TclError:
                return

        threading.Thread(
            target=worker, daemon=True, name="btcturk-pro-load",
        ).start()

    def _btcturk_pro_apply_load(self, request_id: int, result: dict[str, Any]) -> None:
        if request_id != self.btcturk_pro_request_id:
            return
        self.btcturk_pro_load_busy = False
        self.btcturk_pro_open_button.configure(state="normal")
        self.btcturk_pro_refresh_button.configure(state="normal")
        if not result.get("ok"):
            error = str(result.get("error") or "BtcTurk verisi alınamadı.")
            self.btcturk_pro_status_var.set("BtcTurk PRO veri uyarısı")
            self.btcturk_pro_quote_var.set(error)
            self.btcturk_pro_binance_var.set("Binance karşılaştırması yapılamadı.")
            self._set_text(self.btcturk_pro_cost_text, "Piyasa verisi alınamadığı için işlem planı oluşturulmadı.\n" + error)
            self._set_text(self.btcturk_pro_technical_text, "BtcTurk mum geçmişi alınamadı; teknik değerlendirme yapılmadı.")
            self.btcturk_pro_chart.delete("all")
            self.btcturk_pro_orderbook_tree.delete(*self.btcturk_pro_orderbook_tree.get_children())
            return

        markets = result.get("markets")
        self.btcturk_pro_markets = markets if isinstance(markets, dict) else {}
        values = sorted(self.btcturk_pro_markets)
        self.btcturk_pro_pair_combo.configure(values=values)
        symbol = str(result.get("symbol") or self.btcturk_pro_symbol)
        if not result.get("pair_found"):
            self.btcturk_pro_data = None
            self.btcturk_pro_status_var.set("İŞLEM PLANI OLUŞTURULAMAZ")
            self.btcturk_pro_quote_var.set(
                f"{symbol}: BtcTurk'te etkin USDT Spot paritesi bulunamadı. Coin seçili bırakıldı."
            )
            self.btcturk_pro_binance_var.set(
                "Başka bir BtcTurk USDT paritesi arayabilir veya Binance Fırsat Radarı'na dönebilirsiniz."
            )
            self.btcturk_pro_market_rules_var.set("Bu coin için BtcTurk işlem kuralı bulunamadı.")
            self._set_text(
                self.btcturk_pro_cost_text,
                "BtcTurk'te etkin USDT paritesi yok. İşlem planı hesaplanmadı; farklı bir USDT paritesi arayın.",
            )
            self._set_text(self.btcturk_pro_technical_text, "BtcTurk USDT mum/hacim verisi bulunmadığı için teknik analiz yapılmadı.")
            self.btcturk_pro_chart.delete("all")
            self.btcturk_pro_orderbook_tree.delete(*self.btcturk_pro_orderbook_tree.get_children())
            messagebox.showwarning(
                "BtcTurk USDT paritesi bulunamadı",
                f"{symbol} BtcTurk'te etkin USDT Spot paritesi değil. Seçili coin korundu; başka parite arayabilirsiniz.",
            )
            return

        self.btcturk_pro_data = result.get("data")
        if not isinstance(self.btcturk_pro_data, dict):
            self.btcturk_pro_status_var.set("BtcTurk PRO veri hatası")
            return
        self.btcturk_pro_symbol = symbol
        self.btcturk_pro_entry_var.set(symbol)
        self._btcturk_pro_save_last_pair(symbol)
        self._btcturk_pro_render_data()

    def _btcturk_pro_render_data(self) -> None:
        data = self.btcturk_pro_data
        if not isinstance(data, dict):
            return
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        ticker = data.get("ticker") if isinstance(data.get("ticker"), dict) else {}
        metrics = data.get("market_metrics") if isinstance(data.get("market_metrics"), dict) else {}
        price = ticker.get("last")
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        spread_pct = metrics.get("spread_pct")
        volume = ticker.get("base_volume_24h")
        ticker_age = data.get("ticker_age_seconds")
        book_age = data.get("orderbook_age_seconds")
        self.btcturk_pro_status_var.set(
            f"{data.get('readiness') or 'DURUM BİLİNMİYOR'} · {data.get('readiness_reason') or ''}"
        )
        if data.get("readiness") == "İŞLEM YAPILABİLİR":
            self.btcturk_pro_status_label.configure(style="SectionGood.TLabel")
        elif data.get("readiness") == "DİKKAT":
            self.btcturk_pro_status_label.configure(style="SectionPending.TLabel")
        else:
            self.btcturk_pro_status_label.configure(style="SectionBad.TLabel")
        self.btcturk_pro_quote_var.set(
            f"BtcTurk son: {format_exchange_price(price, market)} USDT"
            f"   |   Alış: {format_exchange_price(bid, market)}"
            f"   |   Satış: {format_exchange_price(ask, market)}"
            f"   |   Fark: {spread_pct:.4f}%" if isinstance(spread_pct, (int, float))
            else f"BtcTurk son: {format_exchange_price(price, market)} USDT"
                 f"   |   Alış: {format_exchange_price(bid, market)}"
                 f"   |   Satış: {format_exchange_price(ask, market)}"
                 "   |   Fark: hesaplanamadı"
        )
        if isinstance(volume, (int, float)):
            self.btcturk_pro_quote_var.set(
                self.btcturk_pro_quote_var.get() + f"\n24 saat hacim: {volume:,.6g} {market.get('base', '')}"
            )
        self.btcturk_pro_quote_var.set(
            self.btcturk_pro_quote_var.get()
            + f"\nTicker yaşı: {_format_age(ticker_age)} · Emir defteri yaşı: {_format_age(book_age)}"
        )
        comparison = data.get("binance_comparison")
        if isinstance(comparison, dict) and comparison.get("last") is not None:
            change = comparison.get("change_24h_pct")
            change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "24 saat değişimi yok"
            self.btcturk_pro_binance_var.set(
                f"Binance karşılaştırması: {format_exchange_price(comparison.get('last'), market)} USDT"
                f"   |   24 saat: {change_text}\nBu fiyat ve değişim BtcTurk işlem hesabına girmez."
            )
        else:
            self.btcturk_pro_binance_var.set(
                "Binance karşılaştırması alınamadı. İşlem analizi yalnızca BtcTurk verisiyle sürer."
            )
        minimum = market.get("minimum_order_usdt")
        minimum_amount = market.get("minimum_amount")
        maximum_amount = market.get("maximum_amount")
        numerator_scale = market.get("numerator_scale")
        denominator_scale = market.get("denominator_scale")
        has_fraction = market.get("has_fraction")
        tick_size = market.get("tick_size")
        price_scale_text = (
            f"{denominator_scale} basamak" if has_fraction is True and denominator_scale is not None
            else "tam sayı fiyat" if has_fraction is False
            else "bilinmiyor"
        )
        methods = ", ".join(market.get("order_methods") or []) or "BtcTurk verisinde yok"
        self.btcturk_pro_market_rules_var.set(
            f"Asgari emir: {format_exchange_price(minimum, {'denominator_scale': 2, 'has_fraction': True}) if minimum is not None else 'bilinmiyor'} USDT"
            f" · Min/Max miktar: {minimum_amount if minimum_amount is not None else '—'} / {maximum_amount if maximum_amount is not None else '—'}"
            f" · Fiyat hassasiyeti: {price_scale_text}"
            f" · Miktar hassasiyeti: {numerator_scale if numerator_scale is not None else '—'} basamak"
            f" · Fiyat adımı: {tick_size if tick_size is not None else '—'}"
            f" · Emir türleri: {methods}"
        )
        self._btcturk_pro_render_orderbook(data)
        self._btcturk_pro_draw_chart()
        self._btcturk_pro_render_details(data)

    def _btcturk_pro_render_orderbook(self, data: dict[str, Any]) -> None:
        tree = self.btcturk_pro_orderbook_tree
        tree.delete(*tree.get_children())
        book = data.get("orderbook") if isinstance(data.get("orderbook"), dict) else {}
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        bids = book.get("bids") if isinstance(book.get("bids"), list) else []
        asks = book.get("asks") if isinstance(book.get("asks"), list) else []
        if not bids and not asks:
            tree.insert("", "end", values=("VERİ YOK", "—", "—", "—"))
            return
        for level in asks[:10]:
            tree.insert("", "end", values=(
                "SATIŞ",
                format_exchange_price(level.get("price"), market),
                f"{level.get('quantity', 0):,.8g}",
                f"{level.get('quote_value', 0):,.2f}",
            ), tags=("ask",))
        for level in bids[:10]:
            tree.insert("", "end", values=(
                "ALIŞ",
                format_exchange_price(level.get("price"), market),
                f"{level.get('quantity', 0):,.8g}",
                f"{level.get('quote_value', 0):,.2f}",
            ), tags=("bid",))

    def _btcturk_pro_select_timeframe(self, timeframe: str) -> None:
        if timeframe not in BTCTURK_PRO_TIMEFRAMES:
            return
        self.btcturk_pro_timeframe_var.set(timeframe)
        self._btcturk_pro_draw_chart()

    def _btcturk_pro_draw_chart(self) -> None:
        canvas = getattr(self, "btcturk_pro_chart", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(300, canvas.winfo_width())
        height = max(220, canvas.winfo_height())
        data = self.btcturk_pro_data
        if not isinstance(data, dict):
            canvas.create_text(width / 2, height / 2, text="BtcTurk mum verisi bekleniyor", fill="#FFFFFF")
            return
        timeframe = self.btcturk_pro_timeframe_var.get()
        bars_by_timeframe = data.get("bars_by_timeframe")
        bars = bars_by_timeframe.get(timeframe) if isinstance(bars_by_timeframe, dict) else None
        bars = [bar for bar in bars if isinstance(bar, dict) and bar.get("closed") is True][-80:] if isinstance(bars, list) else []
        if not bars:
            canvas.create_text(width / 2, height / 2, text=f"{timeframe}: kapanmış BtcTurk mumu yok", fill="#FFD166")
            return
        top, price_bottom = 22.0, height * 0.69
        volume_top, volume_bottom = height * 0.75, height - 30.0
        left, right = 72.0, width - 20.0
        highs = [float(bar["h"]) for bar in bars]
        lows = [float(bar["l"]) for bar in bars]
        upper, lower = max(highs), min(lows)
        spread = max(upper - lower, abs(upper) * 0.001, 1e-12)
        upper += spread * 0.06
        lower -= spread * 0.06
        usable_height = max(1.0, price_bottom - top)
        def y_price(value: float) -> float:
            return top + (upper - value) / (upper - lower) * usable_height
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            value = upper - (upper - lower) * fraction
            y = top + usable_height * fraction
            canvas.create_line(left, y, right, y, fill="#303030")
            canvas.create_text(left - 6, y, text=f"{value:.6g}", fill="#DDDDDD", anchor="e", font=("Consolas", 8))
        step = (right - left) / max(1, len(bars))
        body_width = max(2.0, min(9.0, step * 0.62))
        max_volume = max(float(bar.get("v", 0) or 0) for bar in bars) or 1.0
        for index, bar in enumerate(bars):
            x = left + step * (index + 0.5)
            open_, close = float(bar["o"]), float(bar["c"])
            high, low = float(bar["h"]), float(bar["l"])
            color = "#39FF88" if close >= open_ else "#FF6666"
            canvas.create_line(x, y_price(high), x, y_price(low), fill=color, width=1)
            y_open, y_close = y_price(open_), y_price(close)
            body_top, body_bottom = min(y_open, y_close), max(y_open, y_close)
            if body_bottom - body_top < 1.5:
                body_bottom = body_top + 1.5
            canvas.create_rectangle(
                x - body_width / 2, body_top, x + body_width / 2, body_bottom,
                fill=color, outline=color,
            )
            volume = max(0.0, float(bar.get("v", 0) or 0))
            volume_height = (volume / max_volume) * max(1.0, volume_bottom - volume_top)
            canvas.create_rectangle(
                x - body_width / 2, volume_bottom - volume_height,
                x + body_width / 2, volume_bottom,
                fill=color, outline=color,
            )
        plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        timeframe_rows = data.get("assessments") if isinstance(data.get("assessments"), dict) else {}
        selected_row = timeframe_rows.get(timeframe) if isinstance(timeframe_rows.get(timeframe), dict) else {}
        selected_metrics = selected_row.get("metrics") if isinstance(selected_row.get("metrics"), dict) else {}
        levels: list[tuple[Any, str, str]] = []

        if self.btcturk_pro_show_plan.get():
            levels.extend([
                (plan.get("entry_zone_low"), "#FFD166", "GİRİŞ ALT"),
                (plan.get("entry_zone_high"), "#FFD166", "GİRİŞ ÜST"),
                (plan.get("stop_loss"), "#FF6666", "ZARAR-KES"),
            ])
            targets = plan.get("targets")
            if isinstance(targets, list):
                for index, target in enumerate(targets[:3], start=1):
                    if isinstance(target, dict):
                        levels.append((target.get("price"), "#D8B4FE", f"HEDEF {index}"))

        if self.btcturk_pro_show_support_resistance.get():
            zones = selected_metrics.get("support_resistance_zones")
            if isinstance(zones, list):
                last_close = float(bars[-1]["c"])
                supports = sorted(
                    (zone for zone in zones if isinstance(zone, dict)
                     and zone.get("kind") == "support"
                     and _safe_float(zone.get("center")) is not None
                     and float(zone["center"]) <= last_close),
                    key=lambda zone: last_close - float(zone["center"]),
                )[:3]
                resistances = sorted(
                    (zone for zone in zones if isinstance(zone, dict)
                     and zone.get("kind") == "resistance"
                     and _safe_float(zone.get("center")) is not None
                     and float(zone["center"]) >= last_close),
                    key=lambda zone: float(zone["center"]) - last_close,
                )[:3]
                for zone in supports:
                    strength = "GÜÇLÜ DESTEK" if zone.get("strong") is True else "DESTEK"
                    levels.append((zone.get("center"), "#45B7A5", strength))
                for zone in resistances:
                    strength = "GÜÇLÜ DİRENÇ" if zone.get("strong") is True else "DİRENÇ"
                    levels.append((zone.get("center"), "#E69F5A", strength))

        if self.btcturk_pro_show_fibonacci.get():
            fibonacci = selected_metrics.get("fibonacci")
            retracements = fibonacci.get("retracements") if isinstance(fibonacci, dict) else None
            if isinstance(retracements, dict):
                for name, price in retracements.items():
                    levels.append((price, "#56B4E9", "FIB " + str(name).replace("retracement_", "")))

        if self.btcturk_pro_show_channel.get():
            channel = selected_metrics.get("confirmed_channel")
            if isinstance(channel, dict) and channel.get("available") is True:
                levels.extend([
                    (channel.get("upper_now"), "#B39DDB", "KANAL ÜST"),
                    (channel.get("lower_now"), "#B39DDB", "KANAL ALT"),
                ])

        for raw_price, color, label in levels:
            try:
                value = float(raw_price)
            except (TypeError, ValueError, OverflowError):
                continue
            if not lower <= value <= upper:
                continue
            y = y_price(value)
            canvas.create_line(left, y, right, y, fill=color, dash=(4, 3), width=1)
            canvas.create_text(
                right - 3, y - 8,
                text=f"{label} {format_exchange_price(value, market)}",
                fill=color, anchor="e", font=("Segoe UI", 8, "bold"),
            )
        canvas.create_text(
            left, height - 23,
            text=f"BtcTurk {timeframe} · {len(bars)} kapanmış mum · hacim",
            fill="#DDDDDD", anchor="w", font=("Segoe UI", 8),
        )
        for index in sorted({0, len(bars) // 2, len(bars) - 1}):
            stamp = datetime.fromtimestamp(
                int(bars[index]["t"]) / 1000, tz=timezone.utc,
            ).astimezone().strftime("%d.%m %H:%M")
            x = left + step * (index + 0.5)
            canvas.create_text(
                x, height - 9, text=stamp,
                fill="#DDDDDD", anchor="center", font=("Consolas", 7),
            )

    def _btcturk_pro_render_details(self, data: dict[str, Any]) -> None:
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
        metrics = data.get("market_metrics") if isinstance(data.get("market_metrics"), dict) else {}
        assessments = data.get("assessments") if isinstance(data.get("assessments"), dict) else {}
        lines = [
            f"PARİTE: {data.get('symbol')} · KAYNAK: BtcTurk Spot",
            str(data.get("readiness_reason") or ""),
            f"Son kapanmış mum zamanı: {datetime.fromtimestamp(data['last_candle_time_ms'] / 1000, tz=timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M:%S') if data.get('last_candle_time_ms') else 'bulunamadı'} · Yaş: {_format_age(data.get('last_candle_age_seconds'))}",
            f"Alış-satış farkı: {_format_metric(metrics.get('spread_pct'), 4)}% · "
            f"Alış derinliği (%1): {_format_metric(metrics.get('bid_depth_1pct_usdt'), 2)} USDT · "
            f"Satış derinliği (%1): {_format_metric(metrics.get('ask_depth_1pct_usdt'), 2)} USDT",
            f"Emir defteri dengesi: {_format_metric(metrics.get('imbalance_1pct_pct'), 2)}%",
            f"Asgari emir: {market.get('minimum_order_usdt') if market.get('minimum_order_usdt') is not None else 'BtcTurk verisinde yok'} USDT",
            "",
            "--- BTC TURK İŞLEM PLANI ---",
            f"Plan durumu: {plan.get('status') or 'plan yok'}",
            f"Plan fiyat kaynağı: {plan.get('price_reference') or '—'}",
            f"Plan fiyat referansı yaşı: {_format_age(plan.get('price_reference_age_seconds'))}",
            str(plan.get("draft_warning") or ""),
        ]
        for label, key in (
            ("Koşullu giriş alt", "entry_zone_low"),
            ("Koşullu giriş üst", "entry_zone_high"),
            ("Kırılım", "breakout_level"),
            ("Zarar durdurma", "stop_loss"),
        ):
            lines.append(f"{label}: {format_exchange_price(plan.get(key), market)} USDT")
        targets = plan.get("targets")
        if isinstance(targets, list) and targets:
            for index, target in enumerate(targets[:3], start=1):
                if not isinstance(target, dict):
                    continue
                lines.append(
                    f"Hedef {index}: {format_exchange_price(target.get('price'), market)} USDT"
                    f" · brüt R {target.get('gross_risk_reward', '—')}"
                    f" · komisyon sonrası tahmini net R {target.get('net_risk_reward_estimate', '—')}"
                )
        else:
            lines.append("Teknik hedef bulunmadı; işlem planı oluşturulamaz.")
        lines.extend([
            "Komisyon varsayımı: giriş %0,14 + çıkış %0,14. Fiyat kayması, girilen tutar ve anlık emir defteri yeterli değilse tahmin edilmez.",
            "Fiyat adımı / miktar hassasiyeti: BtcTurk exchangeInfo değerleri kullanılır; hesapta yuvarlanmış ekran fiyatları kullanılmaz.",
            "",
            "--- ZAMAN DİLİMİ TEKNİK DEĞERLENDİRMESİ ---",
        ])
        for timeframe in BTCTURK_PRO_TIMEFRAMES:
            row = assessments.get(timeframe)
            if not isinstance(row, dict):
                continue
            m = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
            lines.append(
                f"[{timeframe}] {row.get('state') or '—'} · kapanmış mum {row.get('closed_bars', 0)}"
                f" / gerekli {row.get('required_closed_bars', 0)}"
            )
            if m:
                lines.append(
                    f"  Kapanış {format_exchange_price(m.get('close'), market)}"
                    f" · Hacim {m.get('current_volume', '—')}"
                    f" · EMA hızlı/yavaş {m.get('ema_fast', '—')} / {m.get('ema_slow', '—')}"
                    f" · MACD {m.get('macd_line', '—')} · RSI {m.get('rsi_14', '—')}"
                    f" · ADX {m.get('adx_14', '—')} · ATR {m.get('atr_14', '—')}"
                )
                zones = m.get("support_resistance_zones")
                if isinstance(zones, list):
                    selected = [
                        f"{'Destek' if z.get('kind') == 'support' else 'Direnç'} "
                        f"{format_exchange_price(z.get('center'), market)}"
                        for z in zones[:5] if isinstance(z, dict)
                    ]
                    if selected:
                        lines.append("  Bölgeler: " + " · ".join(selected))
                channel = m.get("confirmed_channel")
                if isinstance(channel, dict) and channel.get("available") is True:
                    lines.append(
                        f"  Kanal: {channel.get('direction')} · üst {format_exchange_price(channel.get('upper_now'), market)}"
                    )
                fibonacci = m.get("fibonacci")
                if isinstance(fibonacci, dict) and fibonacci.get("available") is True:
                    lines.append(f"  Fibonacci: {fibonacci.get('direction')} · {fibonacci.get('levels') or fibonacci.get('retracements') or 'seviyeler mevcut'}")
            missing = row.get("missing_checks")
            if isinstance(missing, list) and missing:
                lines.append("  Veri uyarısı: " + "; ".join(str(item) for item in missing[:2]))
        lines.extend([
            "",
            "Veri kaynağı: BtcTurk kendi USDT mumları, hacmi, ticker ve emir defteri. Binance yalnızca ayrı fiyat karşılaştırmasıdır.",
            "Bu alan emir göndermez, hesap bakiyesi okumaz ve gerçek dolum/kârlılık iddiasında bulunmaz.",
        ])
        self._set_text(self.btcturk_pro_technical_text, "\n".join(lines))

        cost_lines = [
            f"İŞLEM DURUMU: {data.get('readiness') or '—'}",
            str(data.get("readiness_reason") or ""),
        ]
        if data.get("quote_error"):
            cost_lines.append("Ticker uyarısı: " + str(data["quote_error"]))
        if data.get("orderbook_error"):
            cost_lines.append("Emir defteri uyarısı: " + str(data["orderbook_error"]))
        plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
        if plan.get("draft_warning"):
            cost_lines.append(str(plan["draft_warning"]))
        cost_lines.extend([
            f"Plan fiyat kaynağı: {plan.get('price_reference') or '—'}",
            f"Spread: {_format_metric(metrics.get('spread_pct'), 4)}% "
            f"· %1 derinlik alış/satış: {_format_metric(metrics.get('bid_depth_1pct_usdt'), 2)} / "
            f"{_format_metric(metrics.get('ask_depth_1pct_usdt'), 2)} USDT",
            "Komisyon sonrası net risk/getiri, sabit %0,14 giriş + %0,14 çıkış varsayımıyla hesaplanır.",
            "Emir tutarı girilmediğinde fiyat kayması tahmini yapılmaz. Girilen tutar için mevcut emir defteri kademeleri üzerinden alış/satış ortalaması hesaplanır.",
        ])
        self._set_text(self.btcturk_pro_cost_text, "\n".join(cost_lines))

    def _btcturk_pro_estimate_cost(self) -> None:
        data = self.btcturk_pro_data
        if not isinstance(data, dict):
            messagebox.showinfo("Maliyet tahmini", "Önce geçerli bir BtcTurk paritesi açın.")
            return
        amount = _safe_float(self.btcturk_pro_amount_var.get())
        if amount is None or amount <= 0:
            messagebox.showwarning("Maliyet tahmini", "Pozitif bir USDT işlem tutarı girin.")
            return
        market = data.get("market") if isinstance(data.get("market"), dict) else {}
        minimum = _safe_float(market.get("minimum_order_usdt"))
        prefix = []
        if minimum is not None and amount < minimum:
            prefix.append(
                f"UYARI: Girilen {amount:.2f} USDT tutar BtcTurk asgari emir değerinin ({minimum:.2f} USDT) altında."
            )
        elif minimum is None:
            prefix.append("UYARI: BtcTurk exchangeInfo asgari emir değeri vermedi; asgari tutar doğrulanamadı.")
        try:
            estimate = estimate_orderbook_execution(
                data.get("orderbook") or {}, amount,
                (data.get("market_metrics") or {}).get("midpoint"),
            )
        except Exception as exc:
            self.btcturk_pro_cost_var.set(f"Emir defteri maliyet tahmini yapılamadı: {exc}")
            existing = self.btcturk_pro_cost_text.get("1.0", "end").strip()
            self._set_text(
                self.btcturk_pro_cost_text,
                existing + "\n" + "\n".join(prefix) + "\n" + self.btcturk_pro_cost_var.get(),
            )
            return
        buy, sell = estimate["buy"], estimate["sell"]
        if buy.get("filled"):
            buy_text = (
                f"Alış ortalaması {buy['average_price']:.8g} USDT · "
                f"en iyi satışa göre kayma {buy['slippage_pct_vs_best_ask']:.4f}% · "
                f"komisyon {buy['commission_usdt_estimate']:.4f} USDT"
            )
        else:
            buy_text = "Alış: mevcut satış kademeleri girilen tutarı karşılamıyor."
        if sell.get("filled"):
            sell_text = (
                f"Satış ortalaması {sell['average_price']:.8g} USDT · "
                f"en iyi alışa göre kayma {sell['slippage_pct_vs_best_bid']:.4f}% · "
                f"komisyon {sell['commission_usdt_estimate']:.4f} USDT"
            )
        else:
            sell_text = "Satış: mevcut alış kademeleri gereken miktarı karşılamıyor."
        lines = [
            f"İŞLEM TUTARI: {amount:,.2f} USDT",
            *prefix,
            buy_text,
            sell_text,
            "Bu hesap anlık emir defteri derinliğine dayalı tahmindir; gerçek emir, gerçekleşme fiyatı veya ücret tahsilatı değildir.",
        ]
        self.btcturk_pro_cost_var.set("\n".join(lines))
        existing = self.btcturk_pro_cost_text.get("1.0", "end").strip()
        self._set_text(
            self.btcturk_pro_cost_text,
            existing + "\n\n--- GİRİLEN TUTAR İÇİN MALİYET / KAYMA TAHMİNİ ---\n" + "\n".join(lines),
        )

    def _schedule_btcturk_pro_quote_refresh(self) -> None:
        if getattr(self, "workspace_current_page", None) == "btcturk":
            self._btcturk_pro_refresh_quote_async()
        try:
            self.after(15000, self._schedule_btcturk_pro_quote_refresh)
        except tk.TclError:
            return

    def _btcturk_pro_refresh_quote_async(self) -> None:
        data = self.btcturk_pro_data
        if not isinstance(data, dict) or self.btcturk_pro_quote_refresh_busy or self.btcturk_pro_load_busy:
            return
        symbol = str(data.get("symbol") or "")
        request_id = self.btcturk_pro_request_id
        self.btcturk_pro_quote_refresh_busy = True

        def worker() -> None:
            old_ticker = data.get("ticker") if isinstance(data.get("ticker"), dict) else {}
            old_book = data.get("orderbook") if isinstance(data.get("orderbook"), dict) else {}
            quote_error = None
            book_error = None
            try:
                ticker = fetch_btcturk_pro_ticker(symbol)
            except Exception as exc:
                ticker = old_ticker
                quote_error = f"{type(exc).__name__}: {str(exc)[:180]}"
            try:
                book = fetch_btcturk_pro_orderbook(symbol)
            except Exception as exc:
                book = old_book
                book_error = f"{type(exc).__name__}: {str(exc)[:180]}"
            try:
                refreshed = analyze_btcturk_pro(
                    symbol, self.btcturk_pro_markets, ticker, book,
                    data.get("bars_by_timeframe") or {},
                    self.settings if isinstance(self.settings, dict) else {},
                )
                refreshed["binance_comparison"] = data.get("binance_comparison")
                refreshed["quote_error"] = quote_error
                refreshed["orderbook_error"] = book_error
                result = refreshed
            except Exception as exc:
                result = None
                error = f"{type(exc).__name__}: {str(exc)[:180]}"
            else:
                error = None
            try:
                self.after(0, self._btcturk_pro_apply_quote_refresh, request_id, symbol, result, error)
            except tk.TclError:
                return

        threading.Thread(
            target=worker, daemon=True, name="btcturk-pro-quote-refresh",
        ).start()

    def _btcturk_pro_apply_quote_refresh(
        self, request_id: int, symbol: str,
        result: dict[str, Any] | None, error: str | None,
    ) -> None:
        self.btcturk_pro_quote_refresh_busy = False
        if request_id != self.btcturk_pro_request_id or symbol != self.btcturk_pro_symbol:
            return
        if isinstance(result, dict):
            self.btcturk_pro_data = result
            self._btcturk_pro_render_data()
        elif error:
            LOGGER.warning("BtcTurk PRO piyasa yenilemesi başarısız: %s", error)

    def _apply_windows_titlebar(self) -> None:
        if os.name != "nt":
            return
        try:
            build = int(platform.version().split(".")[-1])
            if build < 22000:
                LOGGER.info("Başlık şeridi renk ayarı desteklenmiyor; Windows yapı no: %s.", build)
                return
            import ctypes
            hwnd = ctypes.c_void_p(self.winfo_id())
            dwm = ctypes.windll.dwmapi
            for attribute, color, label in ((35, 0x00808080, "başlık arka planı"), (36, 0x00FFFFFF, "başlık yazısı")):
                value = ctypes.c_int(color)
                result = dwm.DwmSetWindowAttribute(hwnd, ctypes.c_uint(attribute), ctypes.byref(value), ctypes.sizeof(value))
                if result != 0:
                    raise OSError(f"DwmSetWindowAttribute({label}) başarısız: {result}")
        except Exception as exc:
            LOGGER.info("Başlık şeridi rengi uygulanamadı: %s", exc)

    def _layout_toolbar(self, _event: Any = None) -> None:
        if not getattr(self, "toolbar_items", None):
            return
        available = self.controls_inner.winfo_width()
        if available < 300:
            available = max(640, self.window_width - 24)
        for item in self.toolbar_items:
            item.grid_forget()
        row = column = used = 0
        for item in self.toolbar_items:
            requested = item.winfo_reqwidth() + 7
            if used and used + requested > max(580, available - 8):
                row += 1
                column = used = 0
            item.grid(row=row, column=column, sticky="w", padx=(0, 5), pady=(0, 3))
            used += requested
            column += 1

    def _adapt_panes(self, _event: Any = None) -> None:
        if not hasattr(self, "pane"):
            return
        wanted = "vertical" if self.winfo_width() < 1220 else "horizontal"
        if wanted != self._pane_orientation:
            self.pane.configure(orient=wanted)
            self._pane_orientation = wanted
            self.after_idle(self._set_default_pane_position)

    def _set_default_pane_position(self) -> None:
        try:
            self.pane.sashpos(0, max(400, int(self.pane.winfo_width() * 0.53)) if self._pane_orientation == "horizontal" else max(240, int(self.pane.winfo_height() * 0.48)))
        except tk.TclError:
            pass

    def _resize_wraplengths(self, _event: Any = None) -> None:
        if not hasattr(self, "btc_summary_label"):
            return
        try:
            self.btc_summary_label.configure(wraplength=max(320, self.winfo_width() - 330))
        except tk.TclError:
            pass
        if hasattr(self, "diagnostics_frame"):
            for widget in self.diagnostics_frame.winfo_children()[:1]:
                try:
                    widget.configure(wraplength=max(320, self.winfo_width() - 70))
                except (tk.TclError, AttributeError):
                    pass
        self.after_idle(self._layout_toolbar)

    def _toggle_btc_details(self) -> None:
        self.btc_details_open = not self.btc_details_open
        if self.btc_details_open:
            self.btc_details_button.configure(text="BTC ayrıntıları ▾")
            self.btc_details_frame.pack(fill="x", padx=0, pady=(0, 3), after=self.btc_summary_label.master)
            self._set_text(self.btc_details_text, _format_btc_context_details(self.current_state))
        else:
            self.btc_details_button.configure(text="BTC ayrıntıları ▸")
            self.btc_details_frame.pack_forget()

    def _toggle_technical_details(self) -> None:
        self.technical_details_open = not self.technical_details_open
        if self.technical_details_open:
            self.technical_toggle_button.configure(text="Teknik ayrıntılar ▾")
            if str(self.technical_panel) not in self.right_content.panes():
                self.right_content.add(self.technical_panel, weight=2)
            self.after_idle(self._set_right_pane_position)
        else:
            self.technical_toggle_button.configure(text="Teknik ayrıntılar ▸")
            try:
                self.right_content.forget(self.technical_panel)
            except tk.TclError:
                pass

    def _set_right_pane_position(self) -> None:
        try:
            self.right_content.sashpos(0, max(160, int(self.right_content.winfo_height() * 0.57)))
        except tk.TclError:
            pass

    def _toggle_diagnostics(self) -> None:
        self.diagnostics_open = not self.diagnostics_open
        if self.diagnostics_open:
            self.diagnostics_toggle_button.configure(text="Tanılama ve son kayıtlar ▾")
            self.diagnostics_frame.pack(fill="both", expand=False, padx=12, pady=(0, 7))
            self.after_idle(self._layout_toolbar)
        else:
            self.diagnostics_toggle_button.configure(text="Tanılama ve son kayıtlar ▸")
            self.diagnostics_frame.pack_forget()

    def _font_size_moved(self, value: str | None = None) -> None:
        raw_value = value if value is not None else self.font_size_var.get()
        size = _normalize_font_size(raw_value)
        self.font_size = size
        if getattr(self, "font_size_var", None) is not None and self.font_size_var.get() != size:
            self.font_size_var.set(size)
        if hasattr(self, "font_size_label"):
            self.font_size_label.configure(text=f"{size} punto")
        self._apply_font_scale()

    def _save_font_size(self, _event: Any = None) -> None:
        self._font_size_moved()
        self.panel_settings["font_size"] = int(self.font_size)
        self._save_panel_settings()
        self._log_line(f"Arayüz yazı boyutu: {self.font_size} punto")

    def _apply_font_scale(self) -> None:
        size = _normalize_font_size(self.font_size)
        self.font_size = size
        style = ttk.Style(self)
        style.configure("TLabel", font=("Segoe UI", size))
        style.configure("TLabelframe.Label", font=("Segoe UI", size, "bold"))
        style.configure("TButton", font=("Segoe UI", max(8, size - 1)))
        style.configure("Status.TLabel", font=("Segoe UI", size, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", size, "bold"))
        for name in ("SectionGood.TLabel", "SectionPending.TLabel", "SectionBad.TLabel", "LiveGood.TLabel", "LiveBad.TLabel", "HistoryGood.TLabel", "HistoryPending.TLabel", "BTC.TLabel"):
            style.configure(name, font=("Segoe UI", size, "bold"))
        style.configure("Time.TLabel", font=("Segoe UI", max(8, size - 2)))
        style.configure("Treeview", font=("Segoe UI", max(8, size - 1)), rowheight=max(27, int(size * 2.7)))
        style.configure("Treeview.Heading", font=("Segoe UI", max(8, size - 1), "bold"))
        for widget in getattr(self, "toolbar_items", []):
            for child in widget.winfo_children():
                if isinstance(child, PillButton):
                    child.configure(font=("Segoe UI", max(8, size - 1), "bold"))
                elif isinstance(child, ttk.Label):
                    child.configure(font=("Segoe UI", max(8, size - 2)))
        for widget_name, font in (("details", ("Segoe UI", size)), ("btc_details_text", ("Segoe UI", max(8, size - 1))), ("technical_details", ("Consolas", max(8, size - 1))), ("log_view", ("Consolas", max(8, size - 1)))):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                try:
                    widget.configure(font=font)
                except tk.TclError:
                    pass
        if hasattr(self, 'details'):
            self.details.tag_configure("scenario", font=("Segoe UI", size, "bold"))
            self.details.tag_configure("decision_good", font=("Segoe UI", size, "bold"))
        self._refresh_status_indicators()
    def _refresh_status_indicators(self) -> None:
        if not hasattr(self, "live_status_label"):
            return
        self.live_status_label.configure(style="LiveGood.TLabel" if self.live_status_var.get().endswith("GÜNCEL") else "LiveBad.TLabel")
        self.history_status_label.configure(style="HistoryGood.TLabel" if self.history_status_var.get().endswith("HAZIR") else "HistoryPending.TLabel")

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _set_section_freshness(self, state: dict[str, Any], selected: dict[str, Any] | None = None) -> None:
        live_current = self.engine is not None and self.engine.poll() is None and state.get("live_stream_status", state.get("status")) == "CANLI AKIŞ GÜNCEL"
        history_ready = live_current and (state.get("history_status") == "GEÇMİŞ MUM HAZIR" or state.get("bootstrap_ready") is True)
        if not live_current:
            self.candidates_heading_var.set("ÖNCELİKLİ ADAYLAR · CANLI VERİ UYARISI")
            self.left_heading.configure(style="SectionBad.TLabel")
        elif not history_ready:
            self.candidates_heading_var.set("ÖNCELİKLİ ADAYLAR · GEÇMİŞ VERİ BEKLENİYOR")
            self.left_heading.configure(style="SectionPending.TLabel")
        else:
            self.candidates_heading_var.set("ÖNCELİKLİ ADAYLAR · VERİLER GÜNCEL")
            self.left_heading.configure(style="SectionGood.TLabel")
        selected_fresh = isinstance(selected, dict) and selected.get("data_freshness") == "CANLI AKIŞ GÜNCEL" and live_current
        if not selected_fresh:
            self.details_heading_var.set("SEÇİLEN COIN · VERİ UYARISI")
            self.right_heading.configure(style="SectionBad.TLabel")
        elif not history_ready:
            self.details_heading_var.set("SEÇİLEN COIN · GEÇMİŞ KONTROLLER BEKLENİYOR")
            self.right_heading.configure(style="SectionPending.TLabel")
        else:
            self.details_heading_var.set("SEÇİLEN COIN · VERİLER GÜNCEL")
            self.right_heading.configure(style="SectionGood.TLabel")

    def _append_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        for line_number, line in enumerate(text.splitlines(), start=1):
            tag = None
            if line.startswith("PARİTE "):
                tag = "scenario"
            elif line.startswith("GÜÇLÜ FIRSAT") or line.startswith("Karar: GÜÇLÜ FIRSAT"):
                tag = "decision_good"
            elif line.startswith("İŞLEM YOK") or line.startswith("FIRSAT GEÇERSİZ") or line.startswith("Karar: FIRSAT GEÇERSİZ"):
                tag = "decision_bad"
            elif line.startswith("KIRILIM BEKLENİYOR") or line.startswith("Teyit bekleyen:"):
                tag = "decision_wait"
            elif line.startswith("ERKEN ADAY"):
                tag = "decision_early"
            elif line.startswith("İZLEMEDE"):
                tag = "decision_watch"
            elif line.startswith("Koşullu giriş bölgesi:"):
                tag = "entry"
            elif line.startswith("Beklenen kırılım:"):
                tag = "breakout"
            elif line.startswith("Zarar durdurma:") or line.startswith("Geçersizleşme:"):
                tag = "stop"
            elif line.startswith("Teknik hedef") or line.startswith("Kâr alma bölgesi:"):
                tag = "target"
            elif line.startswith("Fiyat:"):
                tag = "current" if "VERİ: GÜNCEL" in line else "stale"
            elif line.startswith("---"):
                tag = "section"
            if tag:
                self.details.tag_add(tag, f"{line_number}.0", f"{line_number}.end")
        self.details.configure(state="disabled")

    def _selected_candidate(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.current_candidates.get(selection[0])

    def _selection_changed(self, _event: Any = None) -> None:
        candidate = self._selected_candidate()
        if not candidate:
            self.current_candidate_key = None
            self._set_section_freshness(self.current_state, None)
            self._append_details("Bir aday seçin.\n\nA/B/C araştırma aşamalarıdır; alım emri veya kârlılık garantisi değildir.")
            self._set_text(self.technical_details, "Teknik ayrıntılar için bir aday seçin.")
            return
        key = self._candidate_key(candidate)
        if self._level_watch_key and self._level_watch_key != key:
            self._level_watch_key = None
            self._level_previous_price = None
            self._level_crossed.clear()
            self.level_var.set("Seviye takibi: kapalı (aday seçimi değişti)")
            self.level_button.configure(text="Seviye Takibi: Kapalı")
        self.current_candidate_key = key
        self._set_section_freshness(self.current_state, candidate)
        plan = candidate.get("risk_plan") if isinstance(candidate.get("risk_plan"), dict) else {}
        entry_low = _safe_float(plan.get("entry_zone_low"))
        entry_high = _safe_float(plan.get("entry_zone_high"))
        breakout = _safe_float(plan.get("breakout_level"))
        stop = _safe_float(plan.get("stop_loss"))
        targets = plan.get("targets")
        target_lines = []
        if isinstance(targets, list):
            for index, target in enumerate(targets[:3], start=1):
                if isinstance(target, dict) and _safe_float(target.get("price")) is not None:
                    label = target.get("name") or f"Hedef {index}"
                    gross_target_rr = _safe_float(target.get("gross_risk_reward", target.get("risk_reward")))
                    net_target_rr = _safe_float(target.get("net_risk_reward_estimate"))
                    rr_parts = []
                    if gross_target_rr is not None:
                        rr_parts.append(f"brüt {_format_metric(gross_target_rr, 2)}R")
                    if net_target_rr is not None:
                        rr_parts.append(f"komisyon sonrası tahmini {_format_metric(net_target_rr, 2)}R")
                    rr_text = " | " + " / ".join(rr_parts) if rr_parts else ""
                    target_lines.append(f"Teknik hedef {index}: {label} — {_format_price(target.get('price'))} USDT{rr_text}")
        entry_text = f"{_format_price(entry_low)}–{_format_price(entry_high)} USDT" if entry_low is not None and entry_high is not None else "hesaplanmadı"
        phase = candidate.get("phase") or candidate.get("last_known_phase") or "—"
        timeframe = _display_timeframe(candidate.get("phase_timeframe") or candidate.get("timeframe"))
        decision = str(candidate.get("final_decision") or candidate.get("decision_class") or "—")
        price = _format_price(candidate.get("latest_price", candidate.get("price")))
        freshness = "GÜNCEL" if candidate.get("data_freshness") == "CANLI AKIŞ GÜNCEL" else "UYARI"
        missing = candidate.get("missing_checks")
        missing = [str(item) for item in missing if item] if isinstance(missing, list) else []
        gate_reasons = candidate.get("strong_opportunity_gate_reasons")
        gate_reasons = [str(item) for item in gate_reasons if item] if isinstance(gate_reasons, list) else []
        alarm_block_reason = str(candidate.get("strong_alarm_block_reason") or "").strip()
        if gate_reasons:
            blockers = "; ".join(gate_reasons[:3])
        elif missing:
            blockers = "; ".join(missing[:3])
        elif alarm_block_reason:
            blockers = alarm_block_reason
        elif candidate.get("strong_opportunity_qualified") is True:
            blockers = "Güçlü fırsat kapıları sağlandı."
        else:
            blockers = "Engel gerekçesi raporda bulunmuyor."
        reason = str(candidate.get("decision_reason") or "Karar gerekçesi henüz yok.")
        try:
            score = float(candidate.get("opportunity_score", candidate.get("score_0_100")))
            score_text = f"{score:.0f}/100"
        except (TypeError, ValueError, OverflowError):
            score_text = "—"
        first_target = targets[0] if isinstance(targets, list) and targets and isinstance(targets[0], dict) else {}
        risk_reward = _safe_float(plan.get("gross_risk_reward", plan.get("risk_reward")))
        if risk_reward is None:
            risk_reward = _safe_float(first_target.get("gross_risk_reward", first_target.get("risk_reward")))
        if risk_reward is None:
            reference = _safe_float(plan.get("entry_reference"))
            target_price = _safe_float(first_target.get("price"))
            if reference is not None and stop is not None and target_price is not None and reference > stop:
                risk_reward = (target_price - reference) / (reference - stop)
        net_risk_reward = _safe_float(plan.get("net_risk_reward_estimate"))
        if net_risk_reward is None:
            net_risk_reward = _safe_float(first_target.get("net_risk_reward_estimate"))
        lines = [
            f"PARİTE  {candidate.get('symbol') or candidate.get('base_asset') or '—'}   |   {timeframe}   |   Aşama {phase}",
            f"Fiyat: {price} USDT   |   VERİ: {freshness}",
            f"Karar: {decision}   |   Puan: {score_text}",
            f"Neden öne çıkıyor: {reason}",
            "", "--- BTC İLİŞKİSİ VE ANA ENGEL ---",
            _format_candidate_decision_summary(candidate),
            "", "--- GİRİŞ VE RİSK KONTROLÜ ---",
            f"Plan durumu: {plan.get('status') or 'plan yok'}",
            f"Koşullu giriş bölgesi: {entry_text}",
            f"Beklenen kırılım: {_format_price(breakout) if breakout is not None else 'mevcut değil'} USDT",
            f"Zarar durdurma: {_format_price(stop) if stop is not None else 'mevcut değil'} USDT",
            *(target_lines or ["Teknik hedefler: mevcut değil"]),
            f"Risk/getiri (brüt): {_format_metric(risk_reward, 2)} kat",
            f"Risk/getiri (komisyon dahil tahmini net; fiyat kayması hariç): {_format_metric(net_risk_reward, 2)} kat" if net_risk_reward is not None else "Risk/getiri (komisyon dahil tahmini net): hedef bulunmadığı için hesaplanmadı",
            "Komisyon varsayımı: giriş %0,14 + çıkış %0,14. Fiyat kayması için yeterli BtcTurk alış-satış/emir defteri verisi bulunmadığında tahmin eklenmez.",
            f"Geçersizleşme: {_format_price(stop) + ' USDT altındaki zarar durdurma seviyesi görülürse senaryo geçersizdir' if stop is not None else plan.get('reason') or 'plan koşulları bozulduğunda senaryo geçersizdir'}",
            "", "--- KONTROL DURUMU ---",
            f"Canlı fiyat verisi: {freshness}",
            f"Güçlü fırsat kapısı: {'AÇIK' if candidate.get('strong_opportunity_qualified') is True else 'KAPALI / BEKLE'}",
            f"Güçlü alarm uygunluk filtresi (izin): {'GEÇTİ' if candidate.get('strong_alarm_eligible') is True else 'ENGELLİ'}",
            f"Gerçek güçlü fırsat koşulları: {'SAĞLANDI' if candidate.get('strong_opportunity_qualified') is True else 'SAĞLANMADI'}",
            f"Ana engel / teyit bekleyen: {blockers}",
            "", "A/B/C araştırma aşamalarıdır; emir veya kârlılık garantisi değildir. Komisyon sonrası değerler sabit ücret varsayımıdır; fiili ücret ve gerçekleşen fiyat kayması farklı olabilir. Program emir göndermez.",
        ]
        self._append_details("\n".join(map(str, lines)))
        self._set_text(self.technical_details, self._format_technical_details(candidate))
        self._refresh_workspace_views()

    def _format_technical_details(self, candidate: dict[str, Any]) -> str:
        lines = [
            f"Coin: {candidate.get('symbol') or candidate.get('base_asset') or '—'}",
            f"Keşif yolu: {candidate.get('discovery_route') or candidate.get('discovery_path') or candidate.get('discovery_method') or '—'}",
            "",
            "GÖSTERGE AÇIKLAMALARI: EMA (üssel ortalama), MACD (trend/momentum), RSI (göreceli güç), ADX/DMI (trend gücü/yönü), ATR (oynaklık aralığı).",
            "",
        ]
        timeframes = candidate.get("timeframes")
        timeframes = timeframes if isinstance(timeframes, dict) else {}
        ordered = ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
        found = False
        for timeframe in ordered:
            row = timeframes.get(timeframe)
            if not isinstance(row, dict):
                continue
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
            if not isinstance(metrics, dict):
                continue
            found = True
            close = metrics.get("close", metrics.get("latest_price"))
            lines.append(f"[{_display_timeframe(timeframe)}] Fiyat {_format_price(close)} USDT")
            lines.append(
                "  EMA: hızlı " + _format_price(metrics.get("ema_fast")) +
                " | yavaş " + _format_price(metrics.get("ema_slow")) +
                " | MACD: " + _format_metric(metrics.get("macd_line")) +
                " | sinyal " + _format_metric(metrics.get("macd_signal")) +
                " | RSI " + _format_metric(metrics.get("rsi_14")) +
                " (" + str(metrics.get("rsi_zone") or "bölge yok") + ")"
            )
            lines.append(
                "  ADX " + _format_metric(metrics.get("adx_14")) +
                " | +DI " + _format_metric(metrics.get("plus_di_14")) +
                " | -DI " + _format_metric(metrics.get("minus_di_14")) +
                " | ATR " + _format_price(metrics.get("atr_14")) +
                " | DMI " + str(metrics.get("dmi_direction") or "ölçülemedi")
            )
            channel = metrics.get("confirmed_channel")
            if isinstance(channel, dict) and channel.get("available") is True:
                lines.append("  Kanal: " + str(channel.get("direction") or "—") + " / " + str(channel.get("status") or "teyitli"))
            zones = metrics.get("support_resistance_zones")
            if isinstance(zones, list):
                chosen = []
                for zone in zones:
                    if isinstance(zone, dict) and _safe_float(zone.get("center")) is not None:
                        kind = "Destek" if zone.get("kind") == "support" else "Direnç" if zone.get("kind") == "resistance" else str(zone.get("kind") or "Bölge")
                        chosen.append(f"{kind} {_format_price(zone.get('center'))}")
                if chosen:
                    lines.append("  Fiyat yapısı: " + " · ".join(chosen[:4]))
            fibonacci = metrics.get("fibonacci")
            if isinstance(fibonacci, dict) and fibonacci:
                lines.append("  Fibonacci: " + _short(fibonacci, 480).replace("\n", " "))
            lines.append("")
        if not found:
            lines.append("Motor bu aday için zaman dilimi bazında gösterge ayrıntısı sunmadı.")
        lines.extend(["", "BULGULAR", _short(candidate.get("findings", []), 3000), "", "EKSİK KONTROLLER", _short(candidate.get("missing_checks", []), 2000)])
        relative = candidate.get("relative_strength_vs_btc_pct_points")
        if isinstance(relative, dict):
            lines.extend(["", "BTC'YE GÖRE GÖRECELİ GÜÇ"])
            for tf in ordered:
                value = _safe_float(relative.get(tf))
                if value is not None:
                    lines.append(f"  {_display_timeframe(tf)}: {value:+.2f} yüzde puanı")
        correlations = candidate.get("btc_return_correlation")
        if isinstance(correlations, dict):
            lines.extend(["", "BTC GETİRİ KORELASYONU"])
            for tf in ("1h", "4h"):
                detail = correlations.get(tf)
                if isinstance(detail, dict):
                    lines.append(f"  {_display_timeframe(tf)}: {_format_metric(detail.get('value'))} · gözlem {detail.get('observations', '—')}/{detail.get('minimum_required', '—')}")
        return "\n".join(lines)

    @staticmethod
    def _candidate_key(candidate: dict[str, Any]) -> str:
        symbol = str(candidate.get("symbol") or candidate.get("base_asset") or "").upper()
        timeframe = str(candidate.get("phase_timeframe") or candidate.get("timeframe") or "")
        return f"{symbol}|{timeframe}"

    def start_engine(self) -> None:
        if self.engine and self.engine.poll() is None:
            return
        if not ENGINE_PATH.is_file():
            messagebox.showerror("Motor dosyası bulunamadı", f"Başlatılacak kaynak dosyası yok:\n{ENGINE_PATH}")
            return
        STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            STOP_FILE.unlink(missing_ok=True)
        except OSError as exc:
            messagebox.showerror("Başlatılamadı", f"Durdurma işareti kaldırılamadı: {exc}")
            return
        self.engine_started_epoch = time.time()
        self.start_time_var.set("Başlangıç: " + datetime.fromtimestamp(self.engine_started_epoch).strftime("%H:%M:%S"))
        self.stop_requested_epoch = None
        self._last_rendered_stamp = None
        self._previous_strong_keys.clear()
        self._alarm_primed = False
        interpreter = _get_engine_interpreter()
        command = [interpreter, str(ENGINE_PATH), "--stop-file", str(STOP_FILE), "--single-engine"]
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            self.engine = subprocess.Popen(
                command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env, creationflags=creationflags,
            )
        except (OSError, ValueError) as exc:
            self.engine = None
            self.engine_started_epoch = None
            self.status_var.set("Motor başlatılamadı")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            LOGGER.exception("Motor başlatılamadı")
            messagebox.showerror("Motor başlatılamadı", f"{type(exc).__name__}: {exc}")
            return
        self._log_line(f"Motor başlatıldı (PID {self.engine.pid}); komut: {Path(interpreter).name} binance_erken_firsat_radari.py --single-engine")
        self.status_var.set("BAŞLATILIYOR — ilk güncel motor durumu bekleniyor")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._log_read_thread = threading.Thread(target=self._read_engine_output, args=(self.engine,),
                                                 daemon=True, name="engine-output-reader")
        self._log_read_thread.start()

    def _read_engine_output(self, process: subprocess.Popen[str]) -> None:
        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    self.output_queue.put(raw_line.rstrip("\r\n"))
        except (OSError, ValueError) as exc:
            self.output_queue.put(f"[stdout okuyucu uyarısı] {type(exc).__name__}: {exc}")

    def stop_engine(self) -> None:
        if not self.engine or self.engine.poll() is not None:
            self.status_var.set("Motor durduruldu")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            return
        try:
            STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
            STOP_FILE.write_text("stop requested\n", encoding="utf-8")
            self.stop_requested_epoch = time.time()
            self.status_var.set("DURDURMA İSTEĞİ GÖNDERİLDİ")
            self._log_line("Motor için kontrollü durdurma istendi.")
            self.stop_button.configure(state="disabled")
        except OSError as exc:
            messagebox.showerror("Durdurma isteği başarısız", str(exc))

    def update_universe(self) -> None:
        if not self.update_list_button.instate(["!disabled"]):
            return
        active = bool(self.engine and self.engine.poll() is None)
        if active and not messagebox.askyesno(
            "Motor çalışıyor",
            "Parite listesi yenilense bile çalışan motor belleğindeki evreni hemen değiştirmeyebilir.\n"
            "İşlem sonunda motoru yeniden başlatmanız gerekir. Listeyi şimdi yenileyeyim mi?",
        ):
            return
        self.update_list_button.configure(state="disabled")
        self.status_var.set("BtcTurk USDT Spot parite listesi güncelleniyor…")
        self._log_line("Kamuya açık BtcTurk parite listesi güncellemesi başlatıldı.")

        def worker() -> None:
            try:
                from ortak_piyasa import BTCTURK_UNIVERSE_CACHE_PATH, fetch_btcturk_usdt_spot
                symbols = fetch_btcturk_usdt_spot()
                if not isinstance(symbols, dict) or not symbols:
                    raise RuntimeError("BtcTurk doğrulanabilir USDT listesi boş döndü.")
                unverified = any(
                    isinstance(item, dict) and item.get("pair_status") == "TICKER_SNAPSHOT_FALLBACK_NOT_EXCHANGEINFO_VERIFIED"
                    for item in symbols.values()
                )
                cached = _read_json(BTCTURK_UNIVERSE_CACHE_PATH, {})
                verified_cached = isinstance(cached, dict) and cached.get("active_status_verified") is True
                result = {
                    "ok": True, "count": len(symbols), "unverified": unverified,
                    "verified_cached": verified_cached, "path": str(BTCTURK_UNIVERSE_CACHE_PATH),
                    "message": "Ticker yedeği kullanıldı; aktif işlem durumu doğrulanmadı." if unverified else "BtcTurk exchangeInfo ile liste doğrulandı.",
                }
            except Exception as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.output_queue.put("__UNIVERSE_RESULT__" + json.dumps(result, ensure_ascii=False))
        threading.Thread(target=worker, daemon=True, name="universe-refresh").start()

    def _btcturk_price_loop(self) -> None:
        while not self._btcturk_price_stop.is_set():
            try:
                prices = fetch_btcturk_usdt_last_prices(timeout=4.5)
                sampled_at = time.time()
                error = None
            except Exception as exc:
                prices = None
                sampled_at = None
                error = f"{type(exc).__name__}: {str(exc)[:240]}"
            try:
                self.after(0, self._apply_btcturk_prices, prices, sampled_at, error)
            except tk.TclError:
                return
            if self._btcturk_price_stop.wait(30):
                return

    def _apply_btcturk_prices(
        self, prices: dict[str, float] | None, sampled_at: float | None, error: str | None
    ) -> None:
        if prices is not None:
            self.btcturk_prices = prices
            self.btcturk_prices_updated_at = sampled_at
            self.btcturk_price_error = None
        else:
            self.btcturk_price_error = error or "BtcTurk fiyatı alınamadı."
        for key, row in self.current_candidates.items():
            if key not in self.tree.get_children(""):
                continue
            symbol = str(row.get("symbol") or row.get("base_asset") or "")
            self.tree.set(key, "btcturk_price", _format_btcturk_price(
                self.btcturk_prices, symbol, self.btcturk_prices_updated_at
            ))
        if error:
            LOGGER.warning("BtcTurk fiyat güncellemesi başarısız: %s", error)
        elif prices is not None:
            LOGGER.info("BtcTurk USDT fiyatları güncellendi: %d parite", len(prices))

    def _poll(self) -> None:
        self._drain_output_queue()
        if self.engine:
            return_code = self.engine.poll()
            if return_code is not None:
                self._log_line(f"Motor süreci sona erdi. Çıkış kodu: {return_code}")
                self.engine = None
                self.stop_time_var.set("Bitiş: " + datetime.now().strftime("%H:%M:%S"))
                if self._level_watch_key:
                    self._level_watch_key = None
                    self._level_previous_price = None
                    self._level_crossed.clear()
                    self.level_var.set("Seviye takibi: kapalı (motor durdu)")
                    self.level_button.configure(text="Seviye Takibi: Kapalı")
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                if not self.close_after_stop:
                    self.status_var.set("Motor durduruldu" if return_code == 0 else f"Motor kapandı (çıkış kodu {return_code})")
                if self.close_after_stop:
                    self._btcturk_price_stop.set()
                    self.destroy()
                    return
            elif self.stop_requested_epoch and time.time() - self.stop_requested_epoch > 30:
                self._log_line("Motor 30 saniye içinde kapanmadı; kontrollü kapatma başarısız olduğu için işlem sonlandırılıyor.")
                try:
                    self.engine.terminate()
                except OSError:
                    pass
                self.stop_requested_epoch = None

        state = _read_json(STATE_PATH, None)
        if isinstance(state, dict):
            stamp = str(state.get("generated_at_utc") or "")
            stamp_epoch = _parse_utc_epoch(stamp)
            launched = self.engine_started_epoch
            is_new_session_state = launched is None or (stamp_epoch is not None and stamp_epoch >= launched - 2.0)
            if is_new_session_state and stamp and stamp != self._last_rendered_stamp and (
                self.current_state_epoch is None or stamp_epoch is None or stamp_epoch >= self.current_state_epoch
            ):
                self.current_state = state
                self.current_state_epoch = stamp_epoch
                self._last_rendered_stamp = stamp
                self._render_state(state)
                self._check_strong_alerts(state)
                self._check_level_watch(state)
        self.after(1000, self._poll)

    def _drain_output_queue(self) -> None:
        rendered: list[str] = []
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if line.startswith("__UNIVERSE_RESULT__"):
                try:
                    result = json.loads(line[len("__UNIVERSE_RESULT__"):])
                except json.JSONDecodeError:
                    result = {"ok": False, "error": "Liste güncelleme sonucu okunamadı."}
                self.update_list_button.configure(state="normal")
                if result.get("ok"):
                    message = (
                        f"Parite listesi güncellendi: {result['count']} kayıt.\n"
                        f"Kayıt yolu: {result['path']}\n{result.get('message', '')}"
                    )
                    self.status_var.set(f"Parite listesi hazır: {result['count']} kayıt")
                    self._log_line(message.replace("\n", " | "))
                    if result.get("unverified") and not result.get("verified_cached"):
                        message += "\n\nUyarı: aktif işlem durumu doğrulanmayan ticker yedeği kaydedilmiş olabilir; güçlü alarmlar bu kayıttan dolayı kapalı kalmalıdır."
                    messagebox.showinfo("Parite listesi", message)
                else:
                    self._log_line("Parite listesi yenilenemedi: " + str(result.get("error")))
                    messagebox.showerror("Parite listesi yenilenemedi", str(result.get("error")))
                continue
            if line.strip():
                LOGGER.info("ENGINE | %s", line)
                rendered.append(line)
        if rendered:
            self.log_view.configure(state="normal")
            for line in rendered[-80:]:
                self.log_view.insert("end", line + "\n")
            # Bound visible text so the panel does not grow without limit.
            line_count = int(self.log_view.index("end-1c").split(".")[0])
            if line_count > 220:
                self.log_view.delete("1.0", f"{line_count - 180}.0")
            self.log_view.see("end")
            self.log_view.configure(state="disabled")

    def _log_line(self, line: str) -> None:
        LOGGER.info(line)
        self.log_view.configure(state="normal")
        self.log_view.insert("end", line + "\n")
        line_count = int(self.log_view.index("end-1c").split(".")[0])
        if line_count > 220:
            self.log_view.delete("1.0", f"{line_count - 180}.0")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def _render_state(self, state: dict[str, Any]) -> None:
        status = str(state.get("status") or "Durum bilinmiyor")
        if self.engine is None and self.engine_started_epoch is None:
            status = f"MOTOR KAPALI — son kayıt: {status}"
        elif self.engine is None and self.engine_started_epoch is not None:
            status = status if status in ("BAŞLATMA HATASI", "TARAMA EVRENİ BEKLENİYOR") else "Motor durduruldu"
        live_status = state.get("live_stream_status")
        history_status = state.get("history_status")
        engine_running = self.engine is not None and self.engine.poll() is None
        live_current = engine_running and live_status == "CANLI AKIŞ GÜNCEL"
        history_ready = engine_running and (history_status == "GEÇMİŞ MUM HAZIR" or state.get("bootstrap_ready") is True)
        self.live_status_var.set("CANLI AKIŞ  ·  GÜNCEL" if live_current else "CANLI AKIŞ  ·  UYARI")
        self.history_status_var.set("GEÇMİŞ MUMLAR  ·  HAZIR" if history_ready else "GEÇMİŞ MUMLAR  ·  BEKLİYOR")
        if self.engine is None:
            operation = "Motor durduruldu" if self.engine_started_epoch is not None else "Motor hazır"
        else:
            operation = "Motor çalışıyor" if engine_running else "Motor kapanıyor"
        if state.get("status") in ("BAŞLATMA HATASI", "TARAMA EVRENİ BEKLENİYOR"):
            operation = str(state.get("status"))
        self.status_var.set(operation)
        self._refresh_status_indicators()
        count = state.get("scan_symbol_count", state.get("common_pair_count", "—"))
        raw_mode = str(state.get("universe_mode") or "bilinmiyor")
        mode = {"single": "tek motor", "single_engine": "tek motor", "local": "yerel liste"}.get(raw_mode.casefold(), raw_mode)
        connected = state.get("websocket_connected_shards", "—")
        total = state.get("websocket_total_shards", "—")
        ws_age = state.get("websocket_last_message_age_seconds")
        alert_text = "açık" if self.alarm_enabled else "kapalı"
        level_text = "açık" if self._level_watch_key else "kapalı"
        warning = str(state.get("universe_warning") or state.get("alert_filter_warning") or "").strip()
        self.diagnostics_summary_var.set(
            f"Tarama evreni: {count} parite  |  Çalışma: {mode}  |  "
            f"Canlı veri bağlantıları: {connected}/{total}  |  Son veri: {_format_age(ws_age)}  |  "
            f"Sesli bildirim: {alert_text}  |  Seviye takibi: {level_text}" +
            (f"  |  Uyarı: {warning[:100]}" if warning else "")
        )
        self.btc_context_var.set(_format_btc_context_summary(state) if engine_running else "Motor durduruldu; BTC özeti son kayıttan.")
        if self.btc_details_open:
            self._set_text(self.btc_details_text, _format_btc_context_details(state))

        rows = state.get("candidates")
        if not isinstance(rows, list):
            rows = []
        normalized: dict[str, dict[str, Any]] = {}
        sortable = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or row.get("base_asset") or "").strip().upper()
            if not symbol:
                continue
            tf = str(row.get("phase_timeframe") or row.get("timeframe") or "")
            key = f"{symbol}|{tf}"
            normalized[key] = row
            sortable.append((row, key))
        # Strong, live C/B candidates first; no row is silently dropped by a UI cap.
        sortable.sort(key=lambda pair: (
            pair[0].get("data_freshness") == "CANLI AKIŞ GÜNCEL",
            pair[0].get("strong_alarm_eligible") is True,
            {"C": 3, "B": 2, "A": 1}.get(pair[0].get("phase") or pair[0].get("last_known_phase"), 0),
            _safe_float(pair[0].get("opportunity_score", pair[0].get("score_0_100"))) or -1,
        ), reverse=True)
        old_selection = self.tree.selection()
        selected = old_selection[0] if old_selection else self.current_candidate_key
        for old_key in getattr(self, "_radar_all_keys", []):
            if self.tree.exists(old_key):
                self.tree.delete(old_key)
        self.tree.delete(*self.tree.get_children())
        self._radar_all_keys = []
        self.current_candidates = normalized
        for row, key in sortable:
            phase = row.get("phase") or row.get("last_known_phase") or "—"
            symbol = row.get("symbol") or row.get("base_asset") or "—"
            freshness = str(row.get("data_freshness") or "—")
            if freshness == "CANLI AKIŞ GÜNCEL":
                freshness_label = "GÜNCEL"
            elif "ESKİ" in freshness.upper() or "STALE" in freshness.upper():
                freshness_label = "ESKİ"
            elif "EKSİK" in freshness.upper() or "MISSING" in freshness.upper():
                freshness_label = "EKSİK"
            else:
                freshness_label = freshness[:12]
            decision = str(row.get("final_decision") or row.get("decision_class") or row.get("state") or "—")
            decision_label = {
                "KIRILIM BEKLENİYOR": "KIRILIM BEKLE",
                "FIRSAT GEÇERSİZ": "GEÇERSİZ",
                "GÜÇLÜ FIRSAT": "GÜÇLÜ FIRSAT",
            }.get(decision.upper(), decision)
            strong = (row.get("strong_opportunity_qualified") is True
                      and row.get("strong_alarm_eligible") is True
                      and freshness == "CANLI AKIŞ GÜNCEL")
            if strong:
                tags = ("strong", "decision_strong")
            elif freshness != "CANLI AKIŞ GÜNCEL":
                tags = ("stale",)
            else:
                decision_tag = {
                    "GÜÇLÜ FIRSAT": "decision_strong",
                    "İŞLEM YOK": "decision_no_trade",
                    "FIRSAT GEÇERSİZ": "decision_no_trade",
                    "KIRILIM BEKLENİYOR": "decision_wait",
                    "İZLEMEDE": "decision_watch",
                    "ERKEN ADAY": "decision_early",
                }.get(str(decision).upper())
                phase_tag = f"phase_{str(phase).lower()}" if phase in ("A", "B", "C") else None
                tags = tuple(tag for tag in (phase_tag, decision_tag) if tag)
            self._radar_all_keys.append(key)
            self.tree.insert("", "end", iid=key, values=(
                ("★ " if strong else "") + str(symbol),
                _format_price(row.get("latest_price", row.get("price"))),
                _format_btcturk_price(self.btcturk_prices, str(row.get("symbol") or row.get("base_asset") or ""), self.btcturk_prices_updated_at),
                row.get("opportunity_score", row.get("score_0_100", "—")),
                _display_timeframe(row.get("phase_timeframe") or row.get("timeframe")),
                phase, freshness_label, _format_btc_relative(row), decision_label,
            ), tags=tags)
        self._apply_radar_filters()
        if selected and selected in normalized:
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.current_candidate_key = selected
            self._selection_changed()
        elif sortable:
            first_key = sortable[0][1]
            self.tree.selection_set(first_key)
            self.tree.focus(first_key)
            self.current_candidate_key = first_key
            self._selection_changed()
        else:
            self.current_candidate_key = None
            self._append_details(
                "Henüz aday kaydı yok.\n\n" +
                f"Motor durumu: {status}\n" +
                f"Başlangıç mum hazırlığı: {state.get('bootstrap_progress_pct', '—')}%\n\n" +
                "Tarama evreni doğrulanamıyorsa Parite listesini güncelle düğmesini kullanın."
            )
        selected_candidate = self.current_candidates.get(self.current_candidate_key) if self.current_candidate_key else None
        self._set_section_freshness(state, selected_candidate)
        self._refresh_workspace_views()
        if state.get("status") in ("BAŞLATMA HATASI", "TARAMA EVRENİ BEKLENİYOR"):
            if self._last_error_state_stamp != str(state.get("generated_at_utc")):
                self._last_error_state_stamp = str(state.get("generated_at_utc"))
                LOGGER.warning("Motor durumu: %s | %s", state.get("status"), state.get("error") or state.get("warning"))

    def _check_strong_alerts(self, state: dict[str, Any]) -> None:
        # A prior session's saved state may be displayed on panel launch, but must
        # never create a fresh alarm when the live engine is not running.
        if not self.engine or self.engine.poll() is not None:
            self._previous_strong_keys.clear()
            self._alarm_primed = False
            return
        if state.get("live_stream_status", state.get("status")) != "CANLI AKIŞ GÜNCEL":
            # Gate the alarm on live transport health. Historical completeness remains
            # strict per candidate; one unrelated unresolved archive gap must not
            # silence a different candidate whose own data and opportunity gates pass.
            self._previous_strong_keys.clear()
            self._alarm_primed = False
            return
        candidates = state.get("candidates")
        if not isinstance(candidates, list):
            return
        live: set[str] = set()
        for row in candidates:
            if not isinstance(row, dict):
                continue
            phase = row.get("phase")
            if (phase not in ("B", "C") or row.get("strong_alarm_eligible") is not True
                    or row.get("strong_opportunity_qualified") is not True
                    or row.get("data_freshness") != "CANLI AKIŞ GÜNCEL"):
                continue
            key = self._candidate_key(row)
            live.add(key)
            if self._alarm_primed and key not in self._previous_strong_keys and self.alarm_enabled and self.alarm_volume > 0:
                self._play_alert()
                LOGGER.info("Yeni güçlü fırsat alarmı: %s (%s)", key, phase)
        self._previous_strong_keys = live
        self._alarm_primed = True

    def toggle_alarm(self) -> None:
        self.alarm_enabled = not self.alarm_enabled
        self.panel_settings["alarm_sound_enabled"] = self.alarm_enabled
        self.alarm_button.configure(text="Sesli Bildirim: Açık" if self.alarm_enabled else "Sesli Bildirim: Kapalı")
        self._save_panel_settings()
        self._log_line("Sesli bildirim " + ("açıldı." if self.alarm_enabled else "kapatıldı."))

    def _volume_moved(self, _value: str | None = None) -> None:
        try:
            self.alarm_volume = max(0, min(100, int(float(self.volume_var.get()))))
        except (ValueError, tk.TclError):
            self.alarm_volume = 55
        self.volume_label.configure(text=f"{self.alarm_volume}%")

    def _save_volume(self, _event: Any = None) -> None:
        self._volume_moved()
        self.panel_settings["alarm_volume"] = self.alarm_volume
        self._save_panel_settings()


    def _save_panel_settings(self) -> None:
        # Update only panel_ui fields; preserve every engine/risk setting.
        try:
            current = _read_json(SETTINGS_PATH, {})
            if not isinstance(current, dict):
                current = {}
            ui = current.get("panel_ui")
            if not isinstance(ui, dict):
                ui = {}
            ui.pop("screen_brightness", None)
            ui.pop("panel_brightness", None)
            ui.update({
                "alarm_sound_enabled": bool(self.alarm_enabled),
                "alarm_volume": int(self.alarm_volume),
                "font_size": int(self.font_size),
            })
            for key in ("tracked_symbols", "chart_drawings"):
                if key in getattr(self, "panel_settings", {}):
                    ui[key] = self.panel_settings[key]
            current["panel_ui"] = ui
            _write_json_atomic(SETTINGS_PATH, current)
            self.settings = current
            self.panel_settings = ui
        except Exception as exc:
            LOGGER.exception("Panel ses ayarları kaydedilemedi: %s", exc)

    def _write_alarm_wave(self, kind: str = "opportunity") -> Path:
        """Create a volume-scaled, event-specific PCM alert for Windows."""
        path = RUN_DIR / ("panel_stop_alert.wav" if kind == "stop" else "panel_opportunity_alert.wav")
        sample_rate = 22050
        amplitude = int(26000 * (self.alarm_volume / 100.0))
        if kind == "stop":
            # Four short, high-pitched notes distinguish a stop-loss crossing.
            segments = []
            for _ in range(4):
                segments.extend([(1568.0, 0.085), (0.0, 0.075)])
        else:
            # Three paired chimes identify a newly confirmed strong opportunity.
            segments = []
            for _ in range(3):
                segments.extend([(880.0, 0.09), (1175.0, 0.13), (0.0, 0.10)])
        data = bytearray()
        for frequency, duration in segments:
            count = int(sample_rate * duration)
            for i in range(count):
                envelope = min(1.0, i / max(1, sample_rate * 0.01), (count - i) / max(1, sample_rate * 0.015))
                sample = 0 if frequency == 0 else int(amplitude * max(0.0, envelope) * math.sin(2.0 * math.pi * frequency * i / sample_rate))
                data.extend(struct.pack("<h", max(-32767, min(32767, sample))))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(bytes(data))
        return path

    def _play_alert(self, kind: str = "opportunity") -> None:
        if not self.alarm_enabled or self.alarm_volume <= 0:
            return
        if os.name == "nt":
            try:
                import winsound
                path = self._write_alarm_wave(kind)
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                return
            except (OSError, RuntimeError, wave.Error):
                pass
        try:
            for _ in range(4 if kind == "stop" else 3):
                self.bell()
        except tk.TclError:
            pass

    def _test_sound(self) -> None:
        if self.alarm_volume <= 0:
            messagebox.showinfo("Ses testi", "Ses seviyesi %0; test sesi kapalı.")
            return
        enabled_before = self.alarm_enabled
        self.alarm_enabled = True
        self._play_alert()
        self.alarm_enabled = enabled_before

    def toggle_level_watch(self) -> None:
        if self._level_watch_key:
            self._level_watch_key = None
            self._level_previous_price = None
            self._level_crossed.clear()
            self.level_var.set("Seviye takibi: kapalı")
            self.level_button.configure(text="Seviye Takibi: Kapalı")
            self._log_line("Seviye takibi kapatıldı.")
            return
        if not self.engine or self.engine.poll() is not None:
            messagebox.showwarning("Seviye takibi açılamadı", "Seviye takibi için motorun çalışıyor ve canlı veri üretiyor olması gerekir.")
            return
        candidate = self._selected_candidate()
        if not candidate:
            messagebox.showinfo("Seviye takibi", "Önce aday tablosundan bir coin seçin.")
            return
        plan = candidate.get("risk_plan")
        if not isinstance(plan, dict) or plan.get("status") in (None, "VERİ ESKİ — PLAN YOK", "UYGUN DEĞİL", "HESAPLANAMADI"):
            messagebox.showwarning("Seviye takibi açılamadı", str((plan or {}).get("reason") if isinstance(plan, dict) else "Geçerli koşullu risk planı yok."))
            return
        if candidate.get("data_freshness") != "CANLI AKIŞ GÜNCEL":
            messagebox.showwarning("Seviye takibi açılamadı", "Coinin güncel canlı veri durumu doğrulanmadı.")
            return
        price = _safe_float(candidate.get("latest_price"))
        if price is None or price <= 0:
            messagebox.showwarning("Seviye takibi açılamadı", "Güncel fiyat bulunamadı.")
            return
        self._level_watch_key = self._candidate_key(candidate)
        self.level_button.configure(text="Seviye Takibi: Açık")
        self._level_previous_price = price
        self._level_crossed.clear()
        self.level_var.set(f"Seviye takibi: {self._level_watch_key}")
        self._log_line(f"Seviye takibi açıldı: {self._level_watch_key}; mevcut fiyat başlangıç seviyesi kabul edildi.")

    def _check_level_watch(self, state: dict[str, Any]) -> None:
        key = self._level_watch_key
        if not key:
            return
        candidate = self.current_candidates.get(key)
        if (not candidate
                or candidate.get("data_freshness") != "CANLI AKIŞ GÜNCEL"
                or state.get("live_stream_status", state.get("status")) != "CANLI AKIŞ GÜNCEL"):
            # On stale candidate/stream data, wait and re-baseline; historical bootstrap
            # warnings elsewhere in the universe do not fabricate or suppress crossings.
            self._level_previous_price = None
            return
        plan = candidate.get("risk_plan")
        price = _safe_float(candidate.get("latest_price"))
        if not isinstance(plan, dict) or price is None or price <= 0:
            self._level_previous_price = None
            return
        if self._level_previous_price is None:
            self._level_previous_price = price
            return
        previous = self._level_previous_price
        events: list[str] = []
        low, high = _safe_float(plan.get("entry_zone_low")), _safe_float(plan.get("entry_zone_high"))
        breakout = _safe_float(plan.get("breakout_level"))
        stop = _safe_float(plan.get("stop_loss"))
        if low is not None and high is not None and min(previous, price) <= high and max(previous, price) >= low:
            if (previous < low and price >= low) or (previous > high and price <= high) or low <= price <= high and not low <= previous <= high:
                events.append("Giriş bölgesine giriş")
        if breakout is not None and previous <= breakout < price:
            events.append("Yukarı yönlü kırılım seviyesi geçildi")
        if stop is not None and previous >= stop > price:
            events.append("Zarar durdurma seviyesi aşağı geçildi")
        targets = plan.get("targets")
        if isinstance(targets, list):
            for index, target in enumerate(targets, start=1):
                if not isinstance(target, dict):
                    continue
                target_price = _safe_float(target.get("price"))
                label = str(target.get("name") or f"Teknik hedef {index}")
                event_key = f"target:{target_price}"
                if target_price is not None:
                    if price < target_price <= previous:
                        self._level_crossed.discard(event_key)
                    if previous <= target_price < price and event_key not in self._level_crossed:
                        events.append(f"{label} geçildi")
                        self._level_crossed.add(event_key)
        if events:
            for event in events:
                self._log_line(f"SEVİYE ALARMI | {key} | {event} | fiyat={_format_price(price)}")
            if self.alarm_enabled:
                stop_triggered = any("Zarar durdurma seviyesi" in event for event in events)
                self._play_alert("stop" if stop_triggered else "opportunity")
        self._level_previous_price = price

    def _diagnostic_payload(self) -> dict[str, Any]:
        config = _read_json(SETTINGS_PATH, {})
        if not isinstance(config, dict):
            config = {}
        fan = config.get("fan_token_bases_to_skip", [])
        stable = config.get("stablecoin_bases_no_strong_alarm", [])
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "application": APP_TITLE,
            "python_version": sys.version.split()[0],
            "engine_source_exists": ENGINE_PATH.is_file(),
            "state_file_exists": STATE_PATH.is_file(),
            "settings": {
                "path": str(SETTINGS_PATH),
                "exists": SETTINGS_PATH.is_file(),
                "size_bytes": SETTINGS_PATH.stat().st_size if SETTINGS_PATH.is_file() else None,
                "sha256": _sha256_file(SETTINGS_PATH),
                "fan_token_exclusion_count": len(fan) if isinstance(fan, list) else None,
                "stablecoin_exclusion_count": len(stable) if isinstance(stable, list) else None,
            },
            "engine_status": self.current_state.get("status"),
            "live_stream_status": self.current_state.get("live_stream_status"),
            "history_status": self.current_state.get("history_status"),
            "state_generated_at_utc": self.current_state.get("generated_at_utc"),
            "universe_mode": self.current_state.get("universe_mode"),
            "scan_symbol_count": self.current_state.get("scan_symbol_count"),
            "websocket_connected_shards": self.current_state.get("websocket_connected_shards"),
            "websocket_total_shards": self.current_state.get("websocket_total_shards"),
            "candidate_count": len(self.current_candidates),
            "note": "Tanı özeti ayarların tam içeriğini içermez. Komisyon ve kayma hesaplanmaz; teknik risk/getiri oranı brüt olarak değerlendirilir.",
        }

    def open_screenshot_upload(self) -> None:
        """Choose and preview up to three screenshots before any upload begins."""
        if not SCREENSHOTS_DIR.is_dir():
            messagebox.showerror(
                "Ekran görüntüsü klasörü bulunamadı",
                f"Belirtilen klasör mevcut değil:\n{SCREENSHOTS_DIR}",
                parent=self,
            )
            return
        selected_paths = _choose_screenshot_paths(self, SCREENSHOTS_DIR)
        if not selected_paths:
            return
        if len(selected_paths) > 3:
            messagebox.showwarning(
                "En fazla üç görüntü",
                "Bir seferde en fazla 3 görüntü seçebilirsiniz. Hiçbir dosya yüklenmedi.",
                parent=self,
            )
            return
        try:
            local_images = [validate_image_file(path) for path in selected_paths]
        except Exception as exc:
            messagebox.showerror(
                "Görüntü doğrulanamadı",
                str(exc),
                parent=self,
            )
            return
        config = load_connection_config(ROOT)
        if not config:
            messagebox.showerror(
                "Bulut bağlantısı yapılandırılmamış",
                "Mevcut Windows Credential Manager içinde Firsat-Kontrol-Paneli/ReportUploadToken bulunamadı.",
                parent=self,
            )
            return

        self.status_var.set("Görüntü önizlemesi hazırlanıyor…")

        def _load_preview() -> None:
            try:
                previews: list[dict[str, Any]] = []
                for item in local_images:
                    path = Path(item["path"])
                    raw = path.read_bytes()
                    validate_image_bytes(raw, path.name)
                    prepared = dict(item)
                    prepared["size_bytes"] = len(raw)
                    prepared["thumbnail_bytes"] = make_image_thumbnail(raw)
                    previews.append(prepared)

                cloud_images = fetch_image_manifest()
                for item in cloud_images:
                    raw = download_active_image(
                        item["id"], item["filename"], item["content_type"]
                    )
                    item["thumbnail_bytes"] = make_image_thumbnail(raw)

                self.after(
                    0,
                    lambda: self._show_image_upload_preview(previews, cloud_images, config),
                )
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                try:
                    self.after(0, lambda: self._screenshot_preview_failed(error_text))
                except tk.TclError:
                    pass

        threading.Thread(
            target=_load_preview,
            name="screenshot-preview-fetch",
            daemon=True,
        ).start()

    def _screenshot_preview_failed(self, error: str) -> None:
        self.status_var.set("Ekran görüntüsü önizlemesi alınamadı")
        self._log_line(f"Ekran görüntüsü önizlemesi başarısız: {error}")
        messagebox.showerror(
            "Önizleme hazırlanamadı",
            f"Bulut görüntüleri veya seçilen dosyalar doğrulanamadı.\n\n{error}",
            parent=self,
        )

    def _show_image_upload_preview(
        self,
        local_images: list[dict[str, Any]],
        cloud_images: list[dict[str, Any]],
        config: dict[str, str],
    ) -> None:
        from PIL import Image, ImageTk

        plan = build_image_replacement_plan(cloud_images, len(local_images))
        replaced_ids = {item["id"] for item in plan["replace"]}
        dialog = tk.Toplevel(self)
        dialog.title("Ekran görüntülerini buluta yükle")
        dialog.transient(self)
        dialog.geometry("900x590")
        dialog.minsize(760, 500)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        body = ttk.Frame(dialog, padding=10)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        local_frame = ttk.LabelFrame(
            body, text=f"Yeni seçilen görüntüler ({len(local_images)}/3)", padding=8
        )
        local_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        cloud_frame = ttk.LabelFrame(
            body, text=f"Buluttaki etkin görüntüler ({len(cloud_images)}/3)", padding=8
        )
        cloud_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        dialog._preview_photo_refs = []

        for index, item in enumerate(local_images):
            card = ttk.Frame(local_frame, padding=5, relief="groove")
            card.grid(row=index // 2, column=index % 2, sticky="n", padx=4, pady=4)
            with Image.open(io.BytesIO(item["thumbnail_bytes"])) as preview:
                photo = ImageTk.PhotoImage(preview.copy(), master=dialog)
            dialog._preview_photo_refs.append(photo)
            ttk.Label(card, image=photo).pack(pady=(0, 5))
            size_mib = item["size_bytes"] / (1024 * 1024)
            ttk.Label(
                card,
                text=f"{item['filename']}\n{size_mib:.2f} MiB\nYENİ",
                justify="center",
                wraplength=215,
            ).pack()

        for index, item in enumerate(cloud_images):
            card = ttk.Frame(cloud_frame, padding=5, relief="groove")
            card.grid(row=index // 2, column=index % 2, sticky="n", padx=4, pady=4)
            with Image.open(io.BytesIO(item["thumbnail_bytes"])) as preview:
                photo = ImageTk.PhotoImage(preview.copy(), master=dialog)
            dialog._preview_photo_refs.append(photo)
            ttk.Label(card, image=photo).pack(pady=(0, 5))
            state = "DEĞİŞTİRİLECEK" if item["id"] in replaced_ids else "KORUNACAK"
            size_mib = item["size_bytes"] / (1024 * 1024)
            ttk.Label(
                card,
                text=f"{item['filename']}\n{size_mib:.2f} MiB\n{state}",
                justify="center",
                wraplength=215,
            ).pack()

        status_var = tk.StringVar(
            value="Yükleme başlamadı. Dosyaları aktarmak için Buluta Yükle düğmesine basın."
        )
        status_label = ttk.Label(
            body, textvariable=status_var, wraplength=850, justify="left"
        )
        status_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 6))

        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(actions, text="Vazgeç", command=dialog.destroy).pack(side="right", padx=(6, 0))
        upload_button = ttk.Button(
            actions,
            text="Buluta Yükle",
            command=lambda: self._begin_image_upload(
                dialog, local_images, config, upload_button, status_label
            ),
        )
        upload_button.pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        self.status_var.set("Ekran görüntüsü önizlemesi hazır; aktarım için onay bekleniyor.")

    def _begin_image_upload(
        self,
        dialog: tk.Toplevel,
        local_images: list[dict[str, Any]],
        config: dict[str, str],
        upload_button: ttk.Button,
        status_label: ttk.Label,
    ) -> None:
        upload_button.configure(state="disabled")
        status_label.configure(text="Seçilen görüntüler ayrı isteklerle yükleniyor…")
        paths = [item["path"] for item in local_images]

        def _upload() -> None:
            try:
                result = upload_image_batch(config, paths)
                error_text = None
            except Exception as exc:
                result = None
                error_text = f"{type(exc).__name__}: {exc}"
            try:
                self.after(
                    0,
                    lambda: self._image_upload_finished(
                        dialog, upload_button, status_label, result, error_text
                    ),
                )
            except tk.TclError:
                pass

        threading.Thread(
            target=_upload,
            name="screenshot-image-upload",
            daemon=True,
        ).start()

    def _image_upload_finished(
        self,
        dialog: tk.Toplevel,
        upload_button: ttk.Button,
        status_label: ttk.Label,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        if error or not result:
            detail = error or "Sunucudan başarılı sonuç alınamadı."
            self.status_var.set("Ekran görüntüsü aktarımı başarısız")
            self._log_line(f"Ekran görüntüsü aktarımı başarısız: {detail}")
            try:
                status_label.configure(text=f"Yükleme başarısız: {detail}")
                upload_button.configure(state="normal")
                messagebox.showerror(
                    "Görüntüler yüklenemedi",
                    f"Mevcut etkin görüntü listesi korunmalıdır. Ayrıntı:\n\n{detail}",
                    parent=dialog,
                )
            except tk.TclError:
                pass
            return

        images = result.get("images") if isinstance(result.get("images"), list) else []
        self.status_var.set(f"Bulutta {len(images)} etkin görüntü var")
        self._log_line(f"Ekran görüntüsü grubu buluta yüklendi; etkin görüntü sayısı: {len(images)}")
        try:
            if dialog.winfo_exists():
                dialog.destroy()
        except tk.TclError:
            pass
        links = "\n".join(
            f"{item.get('filename', item.get('id', 'Görüntü'))}: {item.get('url', '')}"
            for item in images
        )
        messagebox.showinfo(
            "Görüntüler buluta yüklendi",
            f"Etkin görüntü sayısı: {len(images)}\n\n{links}",
            parent=self,
        )

    def _make_report(self) -> tuple[Path, Path, Path, str]:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        base = "firsat_kontrol_raporu"
        payload = {
            "report_generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "state": self.current_state,
            "diagnostics": self._diagnostic_payload(),
        }
        json_path = REPORT_DIR / f"{base}.json.gz"
        md_path = REPORT_DIR / f"{base}.md.gz"
        diagnostic_path = REPORT_DIR / f"{base}_tani.json.gz"
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"
        diagnostic_bytes = json.dumps(payload["diagnostics"], ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"
        _write_gzip_atomic(json_path, json_bytes)
        _write_gzip_atomic(diagnostic_path, diagnostic_bytes)
        candidates = self.current_state.get("candidates") if isinstance(self.current_state.get("candidates"), list) else []
        table_rows = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol") or row.get("base_asset") or "—"
            phase = row.get("phase") or row.get("last_known_phase") or "—"
            score = row.get("opportunity_score", row.get("score_0_100", "—"))
            table_rows.append((
                str(symbol), str(phase), _format_price(row.get("latest_price")),
                str(row.get("phase_timeframe") or "—"),
                str(row.get("final_decision") or row.get("state") or "—"), str(score),
                _format_btc_relative(row), _format_btc_correlation(row),
            ))
        markdown = [
            f"# {APP_TITLE} — Durum Raporu", "",
            f"- Rapor zamanı (UTC): {payload['report_generated_at_utc']}",
            f"- Motor durumu: {self.current_state.get('status', 'bilinmiyor')}",
            f"- Canlı akış durumu: {self.current_state.get('live_stream_status', 'bilinmiyor')}",
            f"- Geçmiş mum durumu: {self.current_state.get('history_status', 'bilinmiyor')}",
            f"- Tarama evreni: {self.current_state.get('scan_symbol_count', '—')}",
            f"- Canlı veri bağlantıları: {self.current_state.get('websocket_connected_shards', '—')}/{self.current_state.get('websocket_total_shards', '—')}",
            f"- Aday sayısı: {len(table_rows)}", "",
            "## BTC piyasa bağlamı", "",
            _format_btc_context_summary(self.current_state), "",
            "## Aday özeti", "",
            "| Coin | Aşama | Fiyat (USDT) | Zaman dilimi | Karar | Puan | BTC göreli 1h | BTC corr 1h |",
            "|---|---:|---:|---|---|---:|---:|---:|",
        ]
        for symbol, phase, price, tf, decision, score, btc_relative, btc_correlation in table_rows[:100]:
            markdown.append(
                f"| {symbol} | {phase} | {price} | {tf} | {decision.replace('|', '/')} | "
                f"{score} | {btc_relative} | {btc_correlation} |"
            )
        if len(table_rows) > 100:
            markdown.append(f"\nİlk 100 satır gösterildi; JSON dosyasında {len(table_rows)} adayın tamamı bulunur.")
        markdown.extend([
            "", "## Güvenlik ve yorum", "",
            "A/B/C araştırma aşamalarıdır; alım emri veya kârlılık garantisi değildir. Program emir göndermez.",
            "Fiyat/stop/hedef planları koşullu teknik senaryolardır. Komisyon ve kayma hesaplanmaz; spread ayrı likidite filtresinde değerlendirilir. Gerçek emir/dolum ve BtcTurk uygulanabilirliği bu programda doğrulanmaz.",
            "", "## Tanı bilgisi", "", "Ayrıntılar JSON raporundaki diagnostics alanında saklanır. Tam ayarlar.json içeriği rapora kopyalanmaz.", "",
        ])
        _write_gzip_atomic(md_path, "\n".join(markdown).encode("utf-8"))
        removed = _remove_legacy_report_versions(
            r"firsat_kontrol_raporu_\d{8}_\d{6}(?:_tani)?\.(?:json|md)\.gz",
            json_path,
        )
        LOGGER.info(
            "Sabit adlı sıkıştırılmış raporlar oluşturuldu: %s, %s, %s; eski tarihli günlük rapor dosyaları temizlendi: %d",
            json_path.name, md_path.name, diagnostic_path.name, removed,
        )
        return json_path, md_path, diagnostic_path, "\n".join(markdown)

    def create_report(self) -> None:
        try:
            json_path, md_path, diagnostic_path, markdown = self._make_report()
            self.clipboard_clear()
            self.clipboard_append(markdown)
            self.update_idletasks()
            self._open_select(json_path)

            config = load_connection_config(ROOT)
            if not config:
                messagebox.showinfo(
                    "Günlük rapor hazır",
                    f"Rapor dosyaları yerelde oluşturuldu:\n{json_path}\n{md_path}\n{diagnostic_path}\n\n"
                    "Windows Kimlik Bilgileri Yöneticisi'nde yükleme anahtarı bulunamadı. " 
                    "Eski bağlantı dosyanız varsa silmeyin; program onu yalnızca anahtar güvenli alana kaydedilip doğrulandıktan sonra kaldırır. "
                    "Markdown özeti panoya kopyalandı.",
                )
                self._log_line(f"Günlük rapor yerelde oluşturuldu; bulut bağlantısı yapılandırılmamış: {json_path.name}")
                return

            raw_payload = json.loads(gzip.decompress(json_path.read_bytes()).decode("utf-8"))
            daily_payload = {
                "report_type": "daily",
                "schema_version": 1,
                "report_generated_at_utc": raw_payload.get("report_generated_at_utc"),
                "payload": raw_payload,
                "markdown": markdown,
            }
            compressed = compress_analysis_report(daily_payload)
            self.status_var.set("Günlük rapor oluşturuldu; buluta gönderiliyor…")
            self._log_line(f"Günlük rapor gzip olarak buluta gönderiliyor: {json_path.name}")
            messagebox.showinfo(
                "Günlük rapor hazır",
                f"Rapor dosyaları yerelde oluşturuldu:\n{json_path}\n{md_path}\n{diagnostic_path}\n\n"
                "Buluta gönderim arka planda başlatıldı. Tamamlanınca okunabilir bağlantı gösterilecek. "
                "Markdown özeti panoya kopyalandı.",
            )

            def _upload() -> None:
                try:
                    result = upload_json_report(config, compressed, "daily")
                    error = None
                except Exception as exc:
                    result = None
                    error = f"{type(exc).__name__}: {exc}"
                try:
                    self.after(0, lambda: self._cloud_report_upload_finished(
                        "Günlük rapor", json_path, result, error
                    ))
                except tk.TclError:
                    pass

            threading.Thread(target=_upload, name="daily-report-upload", daemon=True).start()
        except Exception as exc:
            LOGGER.exception("Rapor oluşturulamadı veya bulut gönderimi hazırlanamadı")
            messagebox.showerror("Rapor oluşturulamadı", f"{type(exc).__name__}: {exc}")

    def _cloud_report_upload_finished(
        self, report_label: str, report_path: Path,
        result: dict[str, Any] | None, error: str | None,
    ) -> None:
        if error:
            self.status_var.set(f"{report_label} yerelde kaydedildi; bulut aktarımı başarısız")
            self._log_line(f"{report_label} buluta gönderilemedi: {error}")
            messagebox.showwarning(
                f"{report_label} yerelde kaydedildi",
                f"Buluta gönderim başarısız oldu; yerel dosya korunuyor.\n\n"
                f"Dosya: {report_path}\nHata: {error}",
            )
            return
        read_url = (result or {}).get("read_url") or "Sunucu yanıtında okuma bağlantısı yok."
        self.status_var.set(f"{report_label} buluta yüklendi")
        self._log_line(f"{report_label} buluta gönderildi: {report_path.name}")
        messagebox.showinfo(
            f"{report_label} gönderildi",
            f"Rapor buluta yüklendi.\n\nChatGPT'nin okuyabileceği bağlantı:\n{read_url}",
        )

    def create_analysis_report(self) -> None:
        """Create a compact TA-only report and upload it asynchronously when configured."""
        try:
            payload = build_analysis_report(self.current_state)
            compressed = compress_analysis_report(payload)
            report_path = REPORT_DIR / "analiz_raporu.json.gz"
            temporary = report_path.with_name(f".{report_path.name}.{os.getpid()}.tmp")
            try:
                temporary.write_bytes(compressed)
                os.replace(temporary, report_path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            removed = _remove_legacy_report_versions(r"analiz_raporu_\d{8}_\d{6}_\d+\.json\.gz", report_path)
            if removed:
                LOGGER.info("Eski tarihli analiz raporu dosyaları temizlendi: %d", removed)

            self.clipboard_clear()
            self.clipboard_append(json.dumps(payload, ensure_ascii=False, indent=2))
            self.update_idletasks()
            self._open_select(report_path)

            config = load_connection_config(ROOT)
            if not config:
                messagebox.showinfo(
                    "Analiz raporu hazır",
                    f"Analiz raporu sıkıştırılarak kaydedildi ve dosyası seçildi:\n{report_path}\n\n"
                    "Raporun JSON özeti panoya kopyalandı. Windows Kimlik Bilgileri Yöneticisi'nde yükleme anahtarı bulunamadı. "
                    "Eski bağlantı dosyanız varsa silmeyin; program doğrulama tamamlanmadan kaldırmaz.",
                )
                self._log_line(f"Analiz raporu oluşturuldu; bağlantı yapılandırılmamış: {report_path.name}")
                return

            self.status_var.set("Analiz raporu sunucuya gönderiliyor…")
            self._log_line(f"Analiz raporu gzip olarak gönderiliyor: {report_path.name}")

            def _upload() -> None:
                try:
                    result = upload_analysis_report(config, compressed)
                    error = None
                except Exception as exc:
                    result = None
                    error = f"{type(exc).__name__}: {exc}"
                try:
                    self.after(0, lambda: self._analysis_upload_finished(report_path, result, error))
                except tk.TclError:
                    pass

            threading.Thread(target=_upload, name="analysis-report-upload", daemon=True).start()
        except Exception as exc:
            LOGGER.exception("Analiz raporu oluşturulamadı")
            messagebox.showerror("Analiz raporu oluşturulamadı", f"{type(exc).__name__}: {exc}")

    def _analysis_upload_finished(
        self, report_path: Path, result: dict[str, Any] | None, error: str | None
    ) -> None:
        if error:
            self.status_var.set("Analiz raporu yerelde kaydedildi; sunucuya gönderilemedi")
            self._log_line(f"Analiz raporu gönderilemedi: {error}")
            messagebox.showwarning(
                "Analiz raporu yerel olarak kaydedildi",
                f"Sunucuya gönderim başarısız oldu. Radar çalışmaya devam ediyor.\n\n"
                f"Dosya: {report_path}\nHata: {error}",
            )
            return
        read_url = (result or {}).get("read_url") or "Sunucu yanıtında okuma bağlantısı yok."
        self.status_var.set("Analiz raporu sunucuya yüklendi")
        self._log_line(f"Analiz raporu sunucuya gönderildi: {report_path.name}")
        messagebox.showinfo(
            "Analiz raporu gönderildi",
            f"Güncel analiz raporu sunucuya yüklendi.\n\n"
            f"Yerel dosya: {report_path}\n\n"
            f"ChatGPT'nin okuyabileceği bağlantı:\n{read_url}\n\n"
            "Raporun JSON özeti panoya kopyalandı; yerel dosya Dosya Gezgini'nde seçildi.",
        )

    def create_handoff_zip(self) -> None:
        try:
            json_path, md_path, diagnostic_path, markdown = self._make_report()
            zip_path = REPORT_DIR / "firsat_kontrol_devir.zip"
            log_tail = _tail_text([PANEL_LOG_PATH, ENGINE_LOG_PATH], max_lines=300, max_bytes=128 * 1024)
            manifest: dict[str, Any] = {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": [],
                "limits": {"log_tail_max_lines": 300, "log_tail_max_bytes": 128 * 1024},
            }
            temporary = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{time.time_ns()}.tmp")
            files = [json_path, md_path, diagnostic_path]
            if log_tail:
                files.append(None)
            try:
                with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                    for path in files:
                        if path is None:
                            raw = gzip_compress_bytes(log_tail.encode("utf-8", errors="replace"))
                            name = "diagnostics/log_tail.txt.gz"
                        else:
                            raw = path.read_bytes()
                            name = f"reports/{path.name}"
                        archive.writestr(name, raw)
                        manifest["files"].append({"name": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                    state_summary = gzip_compress_bytes(json.dumps(
                        self._diagnostic_payload(), ensure_ascii=False, indent=2
                    ).encode("utf-8"))
                    archive.writestr("diagnostics/state_summary.json.gz", state_summary)
                    manifest["files"].append({
                        "name": "diagnostics/state_summary.json.gz",
                        "size_bytes": len(state_summary),
                        "sha256": hashlib.sha256(state_summary).hexdigest(),
                    })
                    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
                with zipfile.ZipFile(temporary, "r") as check:
                    bad = check.testzip()
                    if bad:
                        raise ValueError(f"ZIP bütünlük denetimi başarısız: {bad}")
                    for entry in manifest["files"]:
                        raw = check.read(entry["name"])
                        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                            raise ValueError(f"ZIP SHA-256 doğrulaması başarısız: {entry['name']}")
                os.replace(temporary, zip_path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            removed = _remove_legacy_report_versions(r"firsat_kontrol_devir_\d{8}_\d{6}\.zip", zip_path)
            if removed:
                LOGGER.info("Eski tarihli sorun giderme ZIP dosyaları temizlendi: %d", removed)
            self.clipboard_clear()
            self.clipboard_append("\n".join([
                f"Fırsat-Kontrol Paneli devir paketi: {zip_path.name}",
                f"Motor durumu: {self.current_state.get('status', 'bilinmiyor')}",
                f"Aday sayısı: {len(self.current_candidates)}",
                "Ayrıntılı rapor, tanı özeti ve sınırlı günlük eki ZIP içinde.",
            ]))
            self.update_idletasks()
            self._open_select(zip_path)
            self._log_line(f"Sorun Giderme ve Devir Paketi (ZIP) oluşturuldu ve bütünlük denetimi geçti: {zip_path.name}")

            config = load_connection_config(ROOT)
            if not config:
                messagebox.showinfo(
                    "Devir paketi hazır",
                    f"ZIP oluşturuldu ve bütünlük denetimi geçti:\n{zip_path}\n\n"
                    "Windows Kimlik Bilgileri Yöneticisi'nde yükleme anahtarı bulunamadı. "
                    "Panoya kısa devir özeti kopyalandı.",
                )
                return

            daily_raw = json.loads(gzip.decompress(json_path.read_bytes()).decode("utf-8"))
            troubleshooting_payload = {
                "report_type": "troubleshooting",
                "schema_version": 1,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "application": APP_TITLE,
                "summary": {
                    "application_version": self.current_state.get("application_version"),
                    "engine_status": self.current_state.get("status"),
                    "live_stream_status": self.current_state.get("live_stream_status"),
                    "history_status": self.current_state.get("history_status"),
                    "candidate_count": len(self.current_candidates),
                    "zip_file": zip_path.name,
                    "zip_size_bytes": zip_path.stat().st_size,
                    "zip_sha256": _sha256_file(zip_path),
                },
                "daily_report": daily_raw,
                "diagnostics": self._diagnostic_payload(),
                "manifest": manifest,
                "log_tail": log_tail,
                "markdown": markdown,
                "interpretation_limits": [
                    "Bu paket teknik tanı içindir; alım/satım emri göndermez.",
                    "Log bölümü son 300 satır ve en fazla 128 KiB kaynak metinle sınırlıdır.",
                ],
            }
            troubleshooting_compressed = compress_analysis_report(troubleshooting_payload)
            self.status_var.set("Sorun giderme raporu ve ZIP buluta gönderiliyor…")
            messagebox.showinfo(
                "Devir paketi hazır",
                f"ZIP oluşturuldu ve bütünlük denetimi geçti:\n{zip_path}\n\n"
                "Okunabilir tanı raporu ve ZIP dosyası buluta arka planda gönderiliyor. "
                "Tamamlanınca bağlantılar gösterilecek.",
            )

            def _upload() -> None:
                structured_result = None
                zip_result = None
                structured_error = None
                zip_error = None
                try:
                    structured_result = upload_json_report(config, troubleshooting_compressed, "troubleshooting")
                except Exception as exc:
                    structured_error = f"{type(exc).__name__}: {exc}"
                try:
                    zip_result = upload_troubleshooting_zip(config, zip_path.read_bytes())
                except Exception as exc:
                    zip_error = f"{type(exc).__name__}: {exc}"
                try:
                    self.after(0, lambda: self._troubleshooting_upload_finished(
                        zip_path, structured_result, zip_result, structured_error, zip_error
                    ))
                except tk.TclError:
                    pass

            threading.Thread(target=_upload, name="troubleshooting-report-upload", daemon=True).start()
        except Exception as exc:
            LOGGER.exception("Devir ZIP oluşturulamadı veya bulut aktarımı hazırlanamadı")
            messagebox.showerror("Devir paketi oluşturulamadı", f"{type(exc).__name__}: {exc}")

    def _troubleshooting_upload_finished(
        self, zip_path: Path,
        structured_result: dict[str, Any] | None, zip_result: dict[str, Any] | None,
        structured_error: str | None, zip_error: str | None,
    ) -> None:
        lines = []
        if structured_result:
            url = structured_result.get("read_url") or "Okuma bağlantısı sunucu tarafından verilmedi."
            lines.append(f"ChatGPT'nin okuyabileceği tanı raporu:\n{url}")
            self._log_line(f"Sorun giderme tanı raporu buluta gönderildi: {zip_path.name}")
        else:
            lines.append(f"Okunabilir tanı raporu gönderilemedi: {structured_error or 'bilinmeyen hata'}")
            self._log_line(f"Sorun giderme tanı raporu gönderilemedi: {structured_error or 'bilinmeyen hata'}")
        if zip_result:
            url = zip_result.get("read_url") or "ZIP indirme bağlantısı sunucu tarafından verilmedi."
            lines.append(f"ZIP indirme bağlantısı:\n{url}")
            self._log_line(f"Sorun giderme ZIP paketi buluta gönderildi: {zip_path.name}")
        else:
            lines.append(f"ZIP buluta gönderilemedi: {zip_error or 'bilinmeyen hata'}")
            self._log_line(f"Sorun giderme ZIP paketi gönderilemedi: {zip_error or 'bilinmeyen hata'}")
        if structured_result and zip_result:
            self.status_var.set("Sorun giderme raporu ve ZIP buluta yüklendi")
            messagebox.showinfo("Devir paketi gönderildi", "\n\n".join(lines))
        elif structured_result or zip_result:
            self.status_var.set("Sorun giderme paketinin bir bölümü buluta yüklendi")
            messagebox.showwarning("Devir paketi kısmen gönderildi", "\n\n".join(lines))
        else:
            self.status_var.set("Devir paketi yerelde kaydedildi; bulut aktarımı başarısız")
            messagebox.showwarning("Devir paketi yerelde kaydedildi", "\n\n".join(lines))

    def _open_select(self, path: Path) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer.exe", "/select,", str(path)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(path.parent)])
        except OSError as exc:
            LOGGER.warning("Dosya Gezgini açılamadı: %s", exc)

    def open_logs(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(LOG_DIR))  # type: ignore[attr-defined]
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(LOG_DIR)])
        except OSError as exc:
            messagebox.showerror("Klasör açılamadı", str(exc))

    def _on_close(self) -> None:
        if self.engine and self.engine.poll() is None:
            if not messagebox.askyesno("Paneli kapat", "Motor çalışıyor. Kontrollü durdurma isteği gönderip panel kapatılsın mı?"):
                return
            self.close_after_stop = True
            self.stop_engine()
            self.status_var.set("Motor kapanması bekleniyor…")
            return
        self._btcturk_price_stop.set()
        self.destroy()


def main() -> int:
    try:
        # Migrate legacy report credentials before showing the panel.
        load_connection_config(ROOT)
        app = ControlPanel()
        app.mainloop()
        return 0
    except Exception:
        LOGGER.exception("Arayüz başlatılamadı")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
