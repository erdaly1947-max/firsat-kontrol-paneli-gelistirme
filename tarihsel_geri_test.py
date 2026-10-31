"""Historical replay (tarihsel yeniden oynatma) over the verified closed-candle archive.

This module reuses the live technical evaluator but never reads a future candle at
an as-of timestamp. Historical order-book/liquidity and narrative history are not
fabricated when those observations were not archived.
"""
from __future__ import annotations

import bisect
import csv
import gzip
import json
import math
import os
import statistics
import threading
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from binance_mum_arsivi import CandleArchive, current_candle_open_ms, next_candle_open_ms
from radar_core import (
    DATA_DIR,
    ENTRY_COMMISSION_RATE,
    EXIT_COMMISSION_RATE,
    REPORT_DIR,
    build_trade_plan,
    evaluate_binance_candidate,
    score_btc_market_context,
    score_opportunity,
    timeframe_bar_end_ms,
    valid_bars,
)

TIMEFRAMES = ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
HORIZONS = (("1h", 3600), ("4h", 4 * 3600), ("24h", 24 * 3600))
FIVE_MINUTES_MS = 5 * 60 * 1000
DEFAULT_ARCHIVE_PATH = DATA_DIR / "binance_ohlcv_history.sqlite3"
OBSERVATION_FIELDS = (
    "as_of_utc", "symbol", "phase", "phase_timeframe", "latest_price",
    "opportunity_score", "score_basis", "final_decision", "decision_reason",
    "findings_json", "score_components_json", "risk_plan_json",
    "missing_inputs_json", "strong_opportunity_qualification_status",
    "narrative_history_status",
)


class BacktestCancelled(RuntimeError):
    """Raised when the user cancels a historical replay."""


def date_start_ms(value: str) -> int:
    """Convert an ISO calendar date to its UTC start, for the report date filters."""
    parsed = date.fromisoformat(str(value).strip())
    return int(datetime.combine(parsed, datetime_time.min, tzinfo=timezone.utc).timestamp() * 1000)


def date_end_exclusive_ms(value: str) -> int:
    """Convert an ISO calendar date to the next UTC midnight (exclusive end)."""
    parsed = date.fromisoformat(str(value).strip()) + timedelta(days=1)
    return int(datetime.combine(parsed, datetime_time.min, tzinfo=timezone.utc).timestamp() * 1000)


def _safe_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _timeframe_previous_open(timeframe: str, as_of_ms: int) -> int:
    """Expected open time of the last candle closed at the as-of timestamp."""
    current_open = current_candle_open_ms(timeframe, now_ms=as_of_ms)
    if timeframe == "1M":
        current = datetime.fromtimestamp(current_open / 1000, timezone.utc)
        if current.month == 1:
            previous = datetime(current.year - 1, 12, 1, tzinfo=timezone.utc)
        else:
            previous = datetime(current.year, current.month - 1, 1, tzinfo=timezone.utc)
        return int(previous.timestamp() * 1000)
    if timeframe == "1w":
        return current_open - 7 * 24 * 60 * 60 * 1000
    intervals = {
        "5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000, "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000, "1d": 24 * 60 * 60 * 1000,
    }
    if timeframe not in intervals:
        raise ValueError(f"Desteklenmeyen zaman dilimi: {timeframe}")
    return current_open - intervals[timeframe]


def _continuous_suffix(
    bars: list[dict[str, Any]], timeframe: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Use only the latest uninterrupted run; older gaps cannot feed indicators."""
    if len(bars) < 2:
        return list(bars), False
    start = 0
    had_gap = False
    for index in range(1, len(bars)):
        try:
            expected = next_candle_open_ms(int(bars[index - 1]["t"]), timeframe)
            actual = int(bars[index]["t"])
        except (KeyError, TypeError, ValueError, OverflowError):
            start = index
            had_gap = True
            continue
        if actual != expected:
            start = index
            had_gap = True
    return list(bars[start:]), had_gap


def _bars_as_of(
    rows: list[dict[str, Any]], timeframe: str, as_of_ms: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return only candles whose full close time is at/before the replay instant."""
    closed_rows = valid_bars(rows, closed_only=True, exclude_synthetic=True)
    usable = [
        row for row in closed_rows
        if (end_ms := timeframe_bar_end_ms(timeframe, int(row["t"]))) is not None
        and end_ms <= as_of_ms
    ]
    suffix, had_gap = _continuous_suffix(usable, timeframe)
    notes: list[str] = []
    if had_gap:
        notes.append(f"{timeframe}: geçmiş mumlarda boşluk; yalnızca son kesintisiz bölüm kullanıldı.")
    expected_open = _timeframe_previous_open(timeframe, as_of_ms)
    if not suffix or int(suffix[-1]["t"]) != expected_open:
        notes.append(f"{timeframe}: test anında beklenen son kapanmış mum arşivde yok.")
        return [], notes
    return suffix[-140:], notes


def _series_close_times(bars: list[dict[str, Any]], timeframe: str) -> list[int]:
    result = []
    for row in bars:
        end_ms = timeframe_bar_end_ms(timeframe, int(row["t"]))
        if end_ms is not None:
            result.append(end_ms)
    return result


def _window_bars(
    bars: list[dict[str, Any]], close_times: list[int],
    signal_ms: int, horizon_seconds: int,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Get future 5m bars through a horizon, rejecting gaps and incomplete coverage."""
    start = bisect.bisect_right(close_times, signal_ms)
    deadline = signal_ms + horizon_seconds * 1000
    end = bisect.bisect_left(close_times, deadline)
    if end >= len(bars):
        return None, "İleri dönem mumları arşivde henüz yok."
    selected = bars[start:end + 1]
    if not selected or int(selected[0]["t"]) != signal_ms:
        return None, "Sinyal sonrasındaki ilk 5 dakikalık mum eksik."
    for previous, current in zip(selected, selected[1:]):
        if next_candle_open_ms(int(previous["t"]), "5m") != int(current["t"]):
            return None, "İleri dönem içinde 5 dakikalık mum boşluğu var."
    if close_times[end] < deadline:
        return None, "İstenen ölçüm ufkuna ulaşılmadı."
    return selected, None


def _forward_return(
    bars: list[dict[str, Any]], close_times: list[int],
    signal_ms: int, signal_price: float, horizon_seconds: int,
) -> dict[str, Any]:
    selected, issue = _window_bars(bars, close_times, signal_ms, horizon_seconds)
    label = f"{horizon_seconds // 3600}h" if horizon_seconds % 3600 == 0 else f"{horizon_seconds}s"
    if issue or not selected:
        return {"status": "DEĞERLENDİRİLEMEDİ", "reason": issue, "return_pct": None}
    last = selected[-1]
    close = _safe_number(last.get("c"))
    if close is None or signal_price <= 0:
        return {"status": "DEĞERLENDİRİLEMEDİ", "reason": "Geçerli kapanış fiyatı yok.", "return_pct": None}
    actual_seconds = (close_times[bisect.bisect_left(close_times, signal_ms + horizon_seconds * 1000)] - signal_ms) / 1000
    return {
        "status": "HESAPLANDI",
        "target_horizon": label,
        "actual_elapsed_seconds": actual_seconds,
        "as_of_utc": datetime.fromtimestamp(close_times[bisect.bisect_left(close_times, signal_ms + horizon_seconds * 1000)] / 1000, timezone.utc).isoformat(),
        "close_price": close,
        "return_pct": round((close / signal_price - 1.0) * 100.0, 5),
        "bars_observed": len(selected),
    }


def _excursion_24h(
    bars: list[dict[str, Any]], close_times: list[int],
    signal_ms: int, signal_price: float,
) -> dict[str, Any]:
    selected, issue = _window_bars(bars, close_times, signal_ms, 24 * 3600)
    if issue or not selected:
        return {"status": "DEĞERLENDİRİLEMEDİ", "reason": issue, "mfe_pct": None, "mae_pct": None}
    highs = [_safe_number(row.get("h")) for row in selected]
    lows = [_safe_number(row.get("l")) for row in selected]
    if any(value is None for value in highs + lows) or signal_price <= 0:
        return {"status": "DEĞERLENDİRİLEMEDİ", "reason": "Yüksek/düşük mum verisi geçersiz.", "mfe_pct": None, "mae_pct": None}
    return {
        "status": "HESAPLANDI",
        "mfe_pct": round((max(float(value) for value in highs) / signal_price - 1.0) * 100.0, 5),
        "mae_pct": round((min(float(value) for value in lows) / signal_price - 1.0) * 100.0, 5),
        "bars_observed": len(selected),
        "note": "MFE (en yüksek olumlu hareket) ve MAE (en yüksek olumsuz hareket), sinyal sonrası 24 saatin mum tepe/diplerinden hesaplanır.",
    }


def _evaluate_technical_plan(
    plan: Any, bars: list[dict[str, Any]], close_times: list[int],
    signal_ms: int,
) -> dict[str, Any]:
    """Replay entry/stop/target from future OHLC; ambiguous intrabar order is not guessed."""
    if not isinstance(plan, dict):
        return {"status": "PLAN YOK — TEKNİK PLAN ÜRETİLMEDİ"}
    low = _safe_number(plan.get("entry_zone_low"))
    high = _safe_number(plan.get("entry_zone_high"))
    reference = _safe_number(plan.get("entry_reference"))
    stop = _safe_number(plan.get("stop_loss"))
    targets = plan.get("targets") if isinstance(plan.get("targets"), list) else []
    valid_targets = [
        _safe_number(item.get("price")) for item in targets if isinstance(item, dict)
    ]
    target = min((value for value in valid_targets if value is not None and high is not None and value > high), default=None)
    if any(value is None for value in (low, high, reference, stop, target)):
        return {"status": "PLAN YOK — GİRİŞ/STOP/TEKNİK HEDEF EKSİK"}
    if float(high) < float(low) or not float(low) <= float(reference) <= float(high) or float(stop) >= float(low):
        return {"status": "DEĞERLENDİRİLEMEDİ — PLAN SEVİYELERİ TUTARSIZ"}

    future_start = bisect.bisect_right(close_times, signal_ms)
    future_bars = bars[future_start:]
    future_closes = close_times[future_start:]
    if not future_bars or int(future_bars[0]["t"]) != signal_ms:
        return {"status": "DEĞERLENDİRİLEMEDİ — İLK İLERİ MUM EKSİK"}

    entry_deadline = signal_ms + 24 * 3600 * 1000
    entry_index: int | None = None
    for index, (bar, close_ms) in enumerate(zip(future_bars, future_closes)):
        if close_ms > entry_deadline:
            break
        if index and next_candle_open_ms(int(future_bars[index - 1]["t"]), "5m") != int(bar["t"]):
            return {"status": "DEĞERLENDİRİLEMEDİ — GİRİŞ ÖNCESİ MUM BOŞLUĞU"}
        bar_high = _safe_number(bar.get("h"))
        bar_low = _safe_number(bar.get("l"))
        if bar_high is None or bar_low is None:
            return {"status": "DEĞERLENDİRİLEMEDİ — GEÇERSİZ OHLC"}
        entry_touched = bar_high >= float(low) and bar_low <= float(high)
        stop_touched = bar_low <= float(stop)
        if stop_touched:
            if entry_touched:
                return {
                    "status": "OLAY SIRASI BELİRSİZ — AYNI MUMDA GİRİŞ/STOP",
                    "entry_observed": None,
                    "note": "5 dakikalık mum içinde giriş ve stop sırası OHLC verisinden belirlenemez.",
                }
            return {
                "status": "KURULUM GEÇERSİZLEŞTİ — GİRİŞ ÖNCESİ",
                "outcome_time_utc": datetime.fromtimestamp(close_ms / 1000, timezone.utc).isoformat(),
                "observed_low": bar_low,
            }
        if entry_touched:
            target_touched = bar_high >= float(target)
            if target_touched:
                return {
                    "status": "OLAY SIRASI BELİRSİZ — AYNI MUMDA GİRİŞ/HEDEF",
                    "entry_observed": None,
                    "note": "Giriş ve hedef aynı 5 dakikalık mumda görüldü; sıra bilinmiyor.",
                }
            entry_index = index
            break

    if entry_index is None:
        if not future_closes or future_closes[-1] < entry_deadline:
            return {"status": "DEĞERLENDİRİLEMEDİ — GİRİŞ İÇİN 24 SAATLİK KAPSAM YOK"}
        return {"status": "GİRİŞ GÖZLENMEDİ (24 SAAT)", "entry_observed": False}

    entry_bar = future_bars[entry_index]
    entry_time_ms = future_closes[entry_index]
    outcome_deadline = entry_time_ms + 24 * 3600 * 1000
    outcome_found: tuple[str, float, int, float | None, float | None] | None = None
    for index in range(entry_index + 1, len(future_bars)):
        bar = future_bars[index]
        close_ms = future_closes[index]
        if close_ms > outcome_deadline:
            break
        previous = future_bars[index - 1]
        if next_candle_open_ms(int(previous["t"]), "5m") != int(bar["t"]):
            return {"status": "DEĞERLENDİRİLEMEDİ — GİRİŞ SONRASI MUM BOŞLUĞU"}
        bar_high = _safe_number(bar.get("h"))
        bar_low = _safe_number(bar.get("l"))
        if bar_high is None or bar_low is None:
            return {"status": "DEĞERLENDİRİLEMEDİ — GEÇERSİZ OHLC"}
        stop_touched = bar_low <= float(stop)
        target_touched = bar_high >= float(target)
        if stop_touched and target_touched:
            return {
                "status": "OLAY SIRASI BELİRSİZ — AYNI MUMDA HEDEF/STOP",
                "entry_observed": True,
                "entry_observed_at_utc": datetime.fromtimestamp(entry_time_ms / 1000, timezone.utc).isoformat(),
                "entry_price_basis": "Giriş bölgesi orta noktası; gerçek dolum fiyatı bilinmiyor.",
            }
        if stop_touched:
            outcome_found = ("STOP SEVİYESİ GÖZLENDİ", float(stop), close_ms, bar_low, bar_high)
            break
        if target_touched:
            outcome_found = ("HEDEF 1 GÖZLENDİ", float(target), close_ms, bar_low, bar_high)
            break

    if outcome_found is None:
        if not future_closes or future_closes[-1] < outcome_deadline:
            return {
                "status": "DEĞERLENDİRİLEMEDİ — GİRİŞ SONRASI 24 SAATLİK KAPSAM YOK",
                "entry_observed": True,
                "entry_observed_at_utc": datetime.fromtimestamp(entry_time_ms / 1000, timezone.utc).isoformat(),
                "entry_price_reference": float(reference),
            }
        return {
            "status": "24 SAATTE HEDEF/STOP GÖZLENMEDİ",
            "entry_observed": True,
            "entry_observed_at_utc": datetime.fromtimestamp(entry_time_ms / 1000, timezone.utc).isoformat(),
            "entry_price_reference": float(reference),
        }

    status, exit_price, exit_ms, observed_low, observed_high = outcome_found
    gross_pct = (exit_price / float(reference) - 1.0) * 100.0
    net_pct = (
        exit_price * (1.0 - EXIT_COMMISSION_RATE)
        / (float(reference) * (1.0 + ENTRY_COMMISSION_RATE)) - 1.0
    ) * 100.0
    return {
        "status": status,
        "entry_observed": True,
        "entry_observed_at_utc": datetime.fromtimestamp(entry_time_ms / 1000, timezone.utc).isoformat(),
        "entry_price_reference": float(reference),
        "entry_price_basis": "Giriş bölgesi orta noktası; gerçek mum içi dolum fiyatı bilinmiyor.",
        "exit_observed_at_utc": datetime.fromtimestamp(exit_ms / 1000, timezone.utc).isoformat(),
        "planned_exit_price": exit_price,
        "observed_exit_candle_low": observed_low,
        "observed_exit_candle_high": observed_high,
        "gross_return_pct": round(gross_pct, 5),
        "estimated_net_return_pct": round(net_pct, 5),
        "commission_assumption": {
            "entry_pct": ENTRY_COMMISSION_RATE * 100,
            "exit_pct": EXIT_COMMISSION_RATE * 100,
            "note": "Tahmini sabit komisyon; kayma (slippage) dahil değil.",
        },
        "execution_note": "Seviyenin mum içinde görülmesi gerçek emir dolumu değildir; fiyat boşlukları ve emir sırası modellenmez.",
    }


def _aggregate_outcomes(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for horizon, _seconds in HORIZONS:
        values = [
            float(item["forward_returns"][horizon]["return_pct"])
            for item in episodes
            if isinstance(item.get("forward_returns"), dict)
            and isinstance(item["forward_returns"].get(horizon), dict)
            and item["forward_returns"][horizon].get("status") == "HESAPLANDI"
            and isinstance(item["forward_returns"][horizon].get("return_pct"), (int, float))
        ]
        output[horizon] = {
            "observations": len(values),
            "mean_return_pct": round(statistics.fmean(values), 5) if values else None,
            "median_return_pct": round(statistics.median(values), 5) if values else None,
            "positive_return_count": sum(value > 0 for value in values),
            "negative_return_count": sum(value < 0 for value in values),
        }
    return output


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"JSON'a çevrilemeyen tür: {type(value).__name__}")


def run_historical_backtest(
    *,
    archive_path: str | Path = DEFAULT_ARCHIVE_PATH,
    report_dir: str | Path = REPORT_DIR,
    symbols: list[str] | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    settings: dict[str, Any] | None = None,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Replay every archived 5m close for selected symbols; store a report and snapshot CSV.

    start_ms is inclusive and end_ms is exclusive. The replay uses the entire archive
    before start_ms to establish the state at the requested start, and future candles
    after end_ms only to complete the 1h/4h/24h and trade-plan outcome windows.
    """
    archive_path = Path(archive_path)
    report_dir = Path(report_dir)
    if start_ms is not None and (isinstance(start_ms, bool) or not isinstance(start_ms, int) or start_ms < 0):
        raise ValueError("start_ms negatif olmayan UTC milisaniye tamsayısı olmalı.")
    if end_ms is not None and (isinstance(end_ms, bool) or not isinstance(end_ms, int) or end_ms < 0):
        raise ValueError("end_ms negatif olmayan UTC milisaniye tamsayısı olmalı.")
    if start_ms is not None and end_ms is not None and end_ms <= start_ms:
        raise ValueError("end_ms, start_ms değerinden büyük olmalı.")

    cancel_event = cancel_event or threading.Event()
    settings = settings if isinstance(settings, dict) else {}
    archive = CandleArchive(archive_path)
    available_symbols = archive.list_symbols("5m")
    requested_symbols = (
        sorted({str(item).strip().upper() for item in symbols if str(item).strip()})
        if symbols else available_symbols
    )
    requested_symbols = [symbol for symbol in requested_symbols if symbol.endswith("USDT")]
    missing_symbols = [symbol for symbol in requested_symbols if symbol not in available_symbols]
    selected_symbols = [symbol for symbol in requested_symbols if symbol in available_symbols]

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_stamp}-{time.time_ns() % 1_000_000_000:09d}"
    report_dir.mkdir(parents=True, exist_ok=True)
    observations_path = report_dir / f"tarihsel_geri_test_gozlemler_{run_id}.csv.gz"
    summary_path = report_dir / f"tarihsel_geri_test_ozet_{run_id}.json"
    observations_tmp = observations_path.with_name(f".{observations_path.name}.{os.getpid()}.tmp")
    summary_tmp = summary_path.with_name(f".{summary_path.name}.{os.getpid()}.tmp")

    episodes: list[dict[str, Any]] = []
    warnings: list[str] = []
    observation_count = 0
    evaluated_points = 0
    skipped_points = 0
    total_symbols = len(selected_symbols)
    run_started = datetime.now(timezone.utc).isoformat()
    btc_series_raw = {
        timeframe: archive.load_bars("BTCUSDT", timeframe)
        for timeframe in TIMEFRAMES
    } if "BTCUSDT" in available_symbols else {timeframe: [] for timeframe in TIMEFRAMES}
    btc_close_times = {
        timeframe: _series_close_times(rows, timeframe)
        for timeframe, rows in btc_series_raw.items()
    }

    try:
        with gzip.open(observations_tmp, "wt", encoding="utf-8", newline="") as compressed:
            writer = csv.DictWriter(compressed, fieldnames=OBSERVATION_FIELDS)
            writer.writeheader()

            for symbol_index, symbol in enumerate(selected_symbols, start=1):
                if cancel_event.is_set():
                    raise BacktestCancelled("Tarihsel geri test kullanıcı tarafından durduruldu.")
                raw_by_tf = {
                    timeframe: archive.load_bars(symbol, timeframe)
                    for timeframe in TIMEFRAMES
                }
                master_bars = raw_by_tf["5m"]
                if not master_bars:
                    warnings.append(f"{symbol}: 5m mum arşivi boş.")
                    continue
                master_close_times = _series_close_times(master_bars, "5m")
                series = {
                    timeframe: _series_close_times(rows, timeframe)
                    for timeframe, rows in raw_by_tf.items()
                }
                active_episode: dict[str, Any] | None = None
                last_coverage_stamp: int | None = None

                def finish_episode(reason: str, ended_ms: int | None) -> None:
                    nonlocal active_episode
                    if active_episode is None:
                        return
                    active_episode["ended_at_utc"] = (
                        datetime.fromtimestamp(ended_ms / 1000, timezone.utc).isoformat()
                        if ended_ms is not None else None
                    )
                    active_episode["end_reason"] = reason
                    if active_episode.get("in_requested_period"):
                        episodes.append(active_episode)
                    active_episode = None

                for bar_index, master_bar in enumerate(master_bars):
                    if bar_index % 32 == 0 and cancel_event.is_set():
                        raise BacktestCancelled("Tarihsel geri test kullanıcı tarafından durduruldu.")
                    as_of_ms = master_close_times[bar_index]
                    if as_of_ms is None:
                        skipped_points += 1
                        continue
                    if end_ms is not None and as_of_ms >= end_ms:
                        break

                    symbol_bars: dict[str, list[dict[str, Any]]] = {}
                    missing_inputs: list[str] = []
                    for timeframe in TIMEFRAMES:
                        sliced, notes = _bars_as_of(raw_by_tf[timeframe], timeframe, as_of_ms)
                        symbol_bars[timeframe] = sliced
                        missing_inputs.extend(notes)
                    latest_5m = symbol_bars["5m"][-1] if symbol_bars["5m"] else None
                    if latest_5m is None or int(latest_5m["t"]) != int(master_bar["t"]):
                        skipped_points += 1
                        if active_episode is not None:
                            active_episode["coverage_gaps_count"] = int(active_episode.get("coverage_gaps_count", 0)) + 1
                        continue
                    if len(symbol_bars["5m"]) < 30:
                        # A short post-gap tail is not evidence that a previous signal ended.
                        skipped_points += 1
                        if active_episode is not None:
                            active_episode["coverage_gaps_count"] = int(active_episode.get("coverage_gaps_count", 0)) + 1
                        continue

                    btc_bars: dict[str, list[dict[str, Any]]] = {}
                    btc_notes: list[str] = []
                    for timeframe in TIMEFRAMES:
                        sliced, notes = _bars_as_of(btc_series_raw[timeframe], timeframe, as_of_ms)
                        btc_bars[timeframe] = sliced
                        btc_notes.extend(notes)
                    btc_context = score_btc_market_context(btc_bars)
                    btc_complete = isinstance(btc_context, dict) and btc_context.get("data_completeness") == "TAM"

                    base_asset = symbol[:-4]
                    pair = {
                        "base_asset": base_asset,
                        "binance_symbol": symbol,
                        "strong_alarm_eligible": False,
                        "strong_alarm_block_reason": "Geçmiş parite/izin durumu bu test anı için arşivlenmedi.",
                    }
                    candidate = evaluate_binance_candidate(
                        symbol, symbol_bars, btc_bars, pair, settings,
                    )
                    evaluated_points += 1
                    if not isinstance(candidate, dict):
                        skipped_points += 1
                        if active_episode is not None:
                            active_episode["coverage_gaps_count"] = int(active_episode.get("coverage_gaps_count", 0)) + 1
                        continue

                    phase = candidate.get("phase")
                    in_period = (start_ms is None or as_of_ms >= start_ms)
                    if phase not in {"A", "B", "C"}:
                        if in_period:
                            finish_episode("A/B/C aday aşaması sona erdi.", as_of_ms)
                        elif active_episode is not None:
                            # Before the requested start, the state is replayed only to warm up.
                            finish_episode("İstenen tarih aralığından önce sona erdi.", as_of_ms)
                        if progress_callback and bar_index % 96 == 0:
                            progress_callback({
                                "symbol": symbol, "symbol_index": symbol_index,
                                "symbol_total": total_symbols, "evaluated_points": evaluated_points,
                                "observations": observation_count, "message": f"{symbol} geçmişi inceleniyor",
                            })
                        continue

                    latest_price = _safe_number(latest_5m.get("c"))
                    if latest_price is None:
                        skipped_points += 1
                        continue
                    candidate["latest_price"] = latest_price
                    # This internal marker allows the existing scorer to evaluate a
                    # historical as-of snapshot. It is overwritten before any report output.
                    candidate["data_freshness"] = "CANLI AKIŞ GÜNCEL"
                    candidate["btc_market_context"] = btc_context
                    candidate["btc_market_context_freshness"] = (
                        "CANLI AKIŞ GÜNCEL" if btc_complete else "TARİHSEL BTC VERİSİ EKSİK"
                    )
                    candidate["strong_alarm_eligible"] = False
                    candidate["strong_alarm_block_reason"] = (
                        "Geçmiş parite uygunluğu ve kaynak izinleri arşivlenmedi."
                    )
                    candidate["risk_plan"] = build_trade_plan(candidate, settings=settings)
                    candidate.update(score_opportunity(candidate, btc_context=btc_context, historical=True))
                    candidate["data_freshness"] = "TARİHSEL KAPANIŞ MUMU"
                    candidate["strong_opportunity_qualified"] = None
                    candidate["strong_opportunity_qualification_status"] = (
                        "DEĞERLENDİRİLEMEDİ — geçmiş likidite, emir defteri ve parite izin geçmişi yok"
                    )
                    candidate["historical_data_status"] = "TARİHSEL KAPANIŞ VERİSİ"
                    candidate["historical_missing_inputs"] = list(dict.fromkeys(missing_inputs + btc_notes))
                    candidate["narrative_history_status"] = (
                        "DEĞERLENDİRİLEMEDİ — tarihsel naratif gözlemleri mevcut mum arşivinde yok"
                    )

                    if active_episode is None:
                        active_episode = {
                            "signal_id": f"{symbol}-{as_of_ms}",
                            "symbol": symbol,
                            "first_detected_at_utc": datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat(),
                            "first_detected_epoch_ms": as_of_ms,
                            "initial_phase": phase,
                            "initial_phase_timeframe": candidate.get("phase_timeframe"),
                            "initial_price": latest_price,
                            "initial_score": candidate.get("opportunity_score"),
                            "initial_decision": candidate.get("final_decision"),
                            "initial_findings": candidate.get("findings", []),
                            "initial_risk_plan": candidate.get("risk_plan"),
                            "technical_plan_start_ms": (
                                as_of_ms if (
                                    isinstance(candidate.get("risk_plan"), dict)
                                    and candidate["risk_plan"].get("technical_targets_available") is True
                                ) else None
                            ),
                            "technical_plan_start_price": (
                                latest_price if (
                                    isinstance(candidate.get("risk_plan"), dict)
                                    and candidate["risk_plan"].get("technical_targets_available") is True
                                ) else None
                            ),
                            "latest_phase": phase,
                            "latest_score": candidate.get("opportunity_score"),
                            "latest_decision": candidate.get("final_decision"),
                            "maximum_phase": phase,
                            "maximum_score": candidate.get("opportunity_score"),
                            "snapshot_count": 0,
                            "coverage_gaps_count": 0,
                            "events": [],
                            "in_requested_period": False,
                            "first_missing_inputs": candidate.get("historical_missing_inputs", []),
                        }
                    else:
                        if active_episode.get("latest_phase") != phase:
                            active_episode["events"].append({
                                "type": "AŞAMA DEĞİŞTİ",
                                "at_utc": datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat(),
                                "from": active_episode.get("latest_phase"), "to": phase,
                            })
                        if active_episode.get("latest_decision") != candidate.get("final_decision"):
                            active_episode["events"].append({
                                "type": "NİHAİ KARAR DEĞİŞTİ",
                                "at_utc": datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat(),
                                "from": active_episode.get("latest_decision"), "to": candidate.get("final_decision"),
                            })
                        active_episode["latest_phase"] = phase
                        if (
                            active_episode.get("technical_plan_start_ms") is None
                            and isinstance(candidate.get("risk_plan"), dict)
                            and candidate["risk_plan"].get("technical_targets_available") is True
                        ):
                            # Freeze the first valid plan when one appears; an A-stage
                            # detection may precede the later B/C technical plan.
                            active_episode["initial_risk_plan"] = candidate.get("risk_plan")
                            active_episode["technical_plan_start_ms"] = as_of_ms
                            active_episode["technical_plan_start_price"] = latest_price
                        active_episode["latest_score"] = candidate.get("opportunity_score")
                        active_episode["latest_decision"] = candidate.get("final_decision")
                        old_max_score = _safe_number(active_episode.get("maximum_score"))
                        new_score = _safe_number(candidate.get("opportunity_score"))
                        if new_score is not None and (old_max_score is None or new_score > old_max_score):
                            active_episode["maximum_score"] = new_score
                        if {"A": 1, "B": 2, "C": 3}.get(phase, 0) > {"A": 1, "B": 2, "C": 3}.get(active_episode.get("maximum_phase"), 0):
                            active_episode["maximum_phase"] = phase

                    active_episode["snapshot_count"] = int(active_episode.get("snapshot_count", 0)) + 1
                    if missing_inputs:
                        active_episode["coverage_gaps_count"] = int(active_episode.get("coverage_gaps_count", 0)) + len(missing_inputs)
                    if in_period:
                        active_episode["in_requested_period"] = True
                        writer.writerow({
                            "as_of_utc": datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat(),
                            "symbol": symbol,
                            "phase": phase,
                            "phase_timeframe": candidate.get("phase_timeframe"),
                            "latest_price": latest_price,
                            "opportunity_score": candidate.get("opportunity_score"),
                            "score_basis": candidate.get("opportunity_score_basis"),
                            "final_decision": candidate.get("final_decision"),
                            "decision_reason": candidate.get("decision_reason"),
                            "findings_json": json.dumps(candidate.get("findings", []), ensure_ascii=False, allow_nan=False),
                            "score_components_json": json.dumps(candidate.get("score_components", {}), ensure_ascii=False, allow_nan=False),
                            "risk_plan_json": json.dumps(candidate.get("risk_plan", {}), ensure_ascii=False, allow_nan=False),
                            "missing_inputs_json": json.dumps(candidate.get("historical_missing_inputs", []), ensure_ascii=False, allow_nan=False),
                            "strong_opportunity_qualification_status": candidate.get("strong_opportunity_qualification_status"),
                            "narrative_history_status": candidate.get("narrative_history_status"),
                        })
                        observation_count += 1
                    if progress_callback and bar_index % 96 == 0:
                        progress_callback({
                            "symbol": symbol, "symbol_index": symbol_index,
                            "symbol_total": total_symbols, "evaluated_points": evaluated_points,
                            "observations": observation_count, "message": f"{symbol} geçmişi inceleniyor",
                        })

                if active_episode is not None:
                    finish_episode("Arşiv/test aralığının sonuna ulaşıldı; adaylığın sona erdiği varsayılmadı.", None)

                full_5m = raw_by_tf["5m"]
                all_close_times = _series_close_times(full_5m, "5m")
                for episode in [item for item in episodes if item["symbol"] == symbol and "forward_returns" not in item]:
                    signal_ms = int(episode["first_detected_epoch_ms"])
                    signal_price = float(episode["initial_price"])
                    episode["forward_returns"] = {
                        label: _forward_return(full_5m, all_close_times, signal_ms, signal_price, seconds)
                        for label, seconds in HORIZONS
                    }
                    episode["mfe_mae_24h"] = _excursion_24h(
                        full_5m, all_close_times, signal_ms, signal_price,
                    )
                    plan_start_ms = episode.get("technical_plan_start_ms")
                    if plan_start_ms is None:
                        episode["technical_plan_evaluation"] = {
                            "status": "PLAN OLUŞMADI — TEKNİK İŞLEM PLANI YOK"
                        }
                    else:
                        episode["technical_plan_evaluation"] = _evaluate_technical_plan(
                            episode.get("initial_risk_plan"), full_5m, all_close_times,
                            int(plan_start_ms),
                        )
                    episode["technical_plan_created_at_utc"] = (
                        datetime.fromtimestamp(int(plan_start_ms) / 1000, timezone.utc).isoformat()
                        if plan_start_ms is not None else None
                    )
                    episode.pop("technical_plan_start_ms", None)
                    episode["historical_liquidity_status"] = (
                        "DEĞERLENDİRİLEMEDİ — emir defteri, spread ve derinlik geçmişi arşivde yok"
                    )
                    episode["historical_narrative_status"] = (
                        "DEĞERLENDİRİLEMEDİ — geçmiş tarihli naratif kayıtları henüz mevcut değil"
                    )
                    episode["initial_risk_plan"] = episode.get("initial_risk_plan") or {}
                    episode.pop("in_requested_period", None)
                if progress_callback:
                    progress_callback({
                        "symbol": symbol, "symbol_index": symbol_index,
                        "symbol_total": total_symbols, "evaluated_points": evaluated_points,
                        "observations": observation_count, "message": f"{symbol} tamamlandı",
                    })

        os.replace(observations_tmp, observations_path)

        phase_counts: dict[str, int] = {}
        decision_counts: dict[str, int] = {}
        plan_counts: dict[str, int] = {}
        for episode in episodes:
            phase = str(episode.get("initial_phase") or "BİLİNMİYOR")
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            decision = str(episode.get("initial_decision") or "BİLİNMİYOR")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            plan_status = str((episode.get("technical_plan_evaluation") or {}).get("status") or "BİLİNMİYOR")
            plan_counts[plan_status] = plan_counts.get(plan_status, 0) + 1

        first_signal_dates = [
            episode["first_detected_at_utc"] for episode in episodes
        ]
        result = {
            "schema_version": 1,
            "run_id": run_id,
            "started_at_utc": run_started,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "archive_path": str(archive_path),
            "requested_symbols": requested_symbols,
            "tested_symbols": selected_symbols,
            "missing_symbols": missing_symbols,
            "requested_start_ms": start_ms,
            "requested_end_exclusive_ms": end_ms,
            "signal_episode_count": len(episodes),
            "candidate_observation_count": observation_count,
            "evaluated_5m_points": evaluated_points,
            "skipped_5m_points": skipped_points,
            "phase_counts": phase_counts,
            "initial_decision_counts": decision_counts,
            "technical_plan_status_counts": plan_counts,
            "forward_return_summary": _aggregate_outcomes(episodes),
            "signals": episodes,
            "warnings": warnings,
            "measurements_not_implemented_or_not_archived": {
                "strong_opportunity": "Geçmiş likidite, emir defteri, spread, derinlik ve parite izin geçmişi olmadığı için kesin doğrulanamaz.",
                "narrative": "Naratif Avcısı henüz geliştirilmedi; geçmiş tarihli naratif gözlemi yok.",
                "missed_rises": "Sayısal yükseliş eşiği tasarım kararlarında tanımlı olmadığı için kaçırılmış yükseliş sayısı uydurulmaz.",
                "real_execution": "Mum içi sıra, gerçek emir dolumu, fiyat kayması ve emir defteri etkisi modellenmez.",
            },
            "method": {
                "replay_resolution": "5m kapanış anı",
                "timeframes": list(TIMEFRAMES),
                "no_lookahead": "Yalnızca tam kapanışı as_of_ms değerine eşit veya daha eski olan mumlar teknik değerlendirmeye alınır.",
                "history_gaps": "Bir zaman dilimindeki boşluktan önceki mumlar o test anında gösterge hesabına dahil edilmez; son kesintisiz bölüm kullanılır.",
                "radar_outcomes": "İlk sinyal anından sonraki 1h/4h/24h kapanış getirileri, 24h MFE/MAE; eksik ufuklar değerlendirilemedi olarak kalır.",
                "technical_plan": "Giriş, stop ve ilk teknik hedef yalnızca gelecekteki 5m mum aralıklarından izlenir; aynı mumda çakışan olaylar belirsiz olarak bırakılır.",
                "fees": f"Tahmini giriş %{ENTRY_COMMISSION_RATE * 100:.2f} + çıkış %{EXIT_COMMISSION_RATE * 100:.2f}; fiyat kayması hariç.",
                "score": "Tarihsel puan, arşivde ölçülemeyen 5 likidite puanı çıkarılıp ölçülebilen 95 puan üzerinden 100'e ölçeklenir.",
            },
            "observations_csv_gz": str(observations_path),
            "summary_json": str(summary_path),
        }
        with summary_tmp.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False, default=_json_default)
            handle.write("\n")
        os.replace(summary_tmp, summary_path)
        return result
    except Exception:
        for path in (observations_tmp, summary_tmp):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
