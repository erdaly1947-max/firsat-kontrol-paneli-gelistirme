"""Compact, compressed analysis reports for the Fırsat-Kontrol Paneli.

This module intentionally excludes engine diagnostics and raw candle archives.
It preserves candidate decisions, scoring, technical evidence, selected indicator
metrics, BTC context, and conditional entry/stop/target plans.
"""
from __future__ import annotations

import base64
import ctypes
import gzip
import io
import re
import hmac
import time
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

# Legacy-only filename: credentials are migrated out of this file on first report use.
CONFIG_NAME = "chatgpt_baglanti.local.json"
WORKER_BASE_URL = "https://firsat-kontrol-analysis-report.erdaly1947.workers.dev"
RELAY_BASE_URL = "https://firsat-kontrol-market-relay.onrender.com"
# Screenshot testing is isolated from the production relay until the image flow is verified.
IMAGE_RELAY_BASE_URL = "https://firsat-kontrol-test-relay.onrender.com"
IMAGE_BASE_URL = IMAGE_RELAY_BASE_URL
IMAGE_RELAY_HEALTH_URL = f"{IMAGE_RELAY_BASE_URL}/healthz"
IMAGE_RELAY_RETRY_DELAYS = (2.0, 5.0, 8.0)
IMAGE_RELAY_REQUEST_TIMEOUT = 25.0
UPLOAD_URL = f"{RELAY_BASE_URL}/api/report"
READ_URL = f"{WORKER_BASE_URL}/latest"
CREDENTIAL_TARGET = "Firsat-Kontrol-Paneli/ReportUploadToken"
CREDENTIAL_BLOB_MAX_BYTES = 5120
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
TIMEFRAME_ORDER = ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")


class _CredentialFileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _CredentialFileTime),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]

METRIC_FIELDS = (
    "candle_start_ms", "close_time_ms", "close",
    "one_bar_change_pct", "three_bar_change_pct", "positive_return_z",
    "current_volume", "volume_q60_history", "volume_q75_history",
    "volume_measurement_source", "volume_history_complete", "volume_history_sample_count",
    "current_volume_valid", "volume_persistence_history_complete", "recent_volume_window_complete",
    "volume_early", "volume_unusual", "volume_persistence_count",
    "directional_structure", "breakout_level", "previous_resistance",
    "previous_support", "typical_candle_range", "distance_to_resistance_typical_range",
    "distance_to_resistance_atr", "compression_ratio", "compression", "rising_lows",
    "near_resistance", "continuity", "continuity_volume_confirmed", "retest_hold",
    "ema_fast_period", "ema_slow_period", "ema_fast", "ema_slow", "ema_bullish",
    "ema_fast_slope_up", "ema_slow_slope_up", "price_above_ema_fast", "price_above_ema_slow",
    "ema_confirmed_bullish", "ema_cross_up", "macd_fast_period", "macd_slow_period",
    "macd_signal_period", "macd_line", "macd_signal", "macd_histogram", "macd_histogram_rising",
    "rsi_period", "rsi_14", "rsi_zone", "atr_period", "atr_14", "adx_period",
    "plus_di_14", "minus_di_14", "adx_14", "dmi_direction", "trend_direction",
    "confirmed_pivot_count", "support_level", "resistance_level", "nearest_support",
    "nearest_resistance", "fib_support", "fib_resistance", "volume_ratio", "relative_volume",
    "volume_participation", "momentum_score", "trend_score",
)

CANDIDATE_FIELDS = (
    "symbol", "base_asset", "quote_asset", "source", "phase", "state",
    "phase_timeframe", "latest_price", "latest_bar_start_ms", "findings",
    "evidence_groups", "higher_timeframe_context",
    "relative_strength_vs_btc_pct_points", "btc_return_correlation",
    "missing_checks", "source_market_pair", "btcturk_market_pair",
    "category_status", "generated_at_utc", "data_note", "risk_plan",
    "strong_alarm_eligible", "strong_alarm_block_reason", "last_known_phase",
    "data_freshness", "last_stream_update_age_seconds", "opportunity_score",
    "score_0_100", "score_components", "btc_correlation_assessment",
    "final_decision", "decision_class", "decision_reason",
    "strong_opportunity_qualified", "strong_opportunity_gate_reasons",
    "group_category", "group_category_verified", "group_category_source",
    "group_comparable_count", "group_leadership_score", "group_leadership_basis",
    "group_leadership_summary", "liquidity_assessment",
)

def _copy_known(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {key: source[key] for key in fields if key in source}

def _compact_timeframes(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for timeframe in TIMEFRAME_ORDER:
        row = value.get(timeframe)
        if not isinstance(row, dict):
            continue
        compact = _copy_known(
            row,
            ("timeframe", "phase", "state", "data_sufficient", "history_contiguous",
             "closed_bars", "required_closed_bars", "findings", "missing_checks",
             "evidence_groups"),
        )
        metrics = row.get("metrics")
        if isinstance(metrics, dict):
            selected = {
                key: metrics[key]
                for key in METRIC_FIELDS
                if key in metrics and not isinstance(metrics[key], (dict, list, tuple, set))
            }
            fib = metrics.get("fibonacci_levels")
            if isinstance(fib, dict):
                selected["fibonacci_levels"] = {
                    str(k): v for k, v in list(fib.items())[:20]
                    if isinstance(v, (str, int, float, bool)) or v is None
                }
            # Preserve bounded, decision-relevant nested structures from the real engine schema.
            zones = metrics.get("support_resistance_zones")
            if isinstance(zones, list):
                compact_zones = []
                zone_fields = (
                    "kind", "center", "lower", "upper", "touch_count", "strong",
                    "first_touch_ms", "last_touch_ms", "pivot_count", "timeframe",
                )
                for zone in zones[:16]:
                    if isinstance(zone, dict):
                        compact_zone = _copy_known(zone, zone_fields)
                        if compact_zone:
                            compact_zones.append(compact_zone)
                if compact_zones:
                    selected["support_resistance_zones"] = compact_zones

            channel = metrics.get("confirmed_channel")
            if isinstance(channel, dict):
                compact_channel = _copy_known(
                    channel,
                    (
                        "status", "available", "direction", "upper_now", "lower_now",
                        "upper_slope_per_bar", "lower_slope_per_bar", "position_0_to_1",
                        "pivot_high_count", "pivot_low_count", "slope_divergence_atr", "timeframe",
                    ),
                )
                if compact_channel:
                    selected["confirmed_channel"] = compact_channel

            fib = metrics.get("fibonacci")
            if isinstance(fib, dict):
                compact_fib = _copy_known(
                    fib,
                    (
                        "status", "available", "direction", "swing_low", "swing_high",
                        "swing_range", "low_timestamp_ms", "high_timestamp_ms", "timeframe",
                    ),
                )
                for nested_name in ("retracements", "extensions"):
                    levels = fib.get(nested_name)
                    if isinstance(levels, dict):
                        compact_fib[nested_name] = {
                            str(key): value for key, value in list(levels.items())[:12]
                            if isinstance(value, (str, int, float, bool)) or value is None
                        }
                if compact_fib:
                    selected["fibonacci"] = compact_fib

            if selected:
                compact["metrics"] = selected
        result[timeframe] = compact
    return result

def _compact_candidate(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    result = _copy_known(candidate, CANDIDATE_FIELDS)
    result["timeframes"] = _compact_timeframes(candidate.get("timeframes"))
    # Raw candle arrays and repeated per-coin BTC context are deliberately omitted.
    return result

def build_analysis_report(state: Any) -> dict[str, Any]:
    """Build analysis-only data; no diagnostic payload or raw candle history."""
    if not isinstance(state, dict):
        state = {}
    raw_candidates = state.get("candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    candidates = [
        compact for item in raw_candidates
        if (compact := _compact_candidate(item))
    ]
    return {
        "report_type": "analysis",
        "schema_version": 1,
        "application": "FIRSAT-KONTROL PANELİ",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_state_generated_at_utc": state.get("generated_at_utc"),
        "application_version": state.get("application_version"),
        "radar": state.get("radar"),
        "source": state.get("source"),
        "universe": {
            key: state.get(key)
            for key in (
                "universe_mode", "common_pair_count", "scan_symbol_count",
                "universe_generated_at_utc", "btcturk_universe_generated_at_utc",
                "btcturk_universe_mode", "universe_warning", "btcturk_universe_warning",
            )
            if key in state
        },
        "market_context": state.get("btc_market_context"),
        "market_context_freshness": state.get("btc_market_context_freshness"),
        "market_context_warning": state.get("btc_market_context_warning"),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "interpretation_limits": [
            "A/B/C araştırma aşamalarıdır; emir veya kârlılık garantisi değildir.",
            "Giriş, stop ve hedefler koşullu teknik senaryolardır.",
            "Komisyon ve kayma hesaplanmaz; otomatik emir gönderilmez.",
        ],
    }

def gzip_compress_bytes(raw: bytes, *, compresslevel: int = 9) -> bytes:
    """Compress UTF-8 report bytes deterministically for local storage and handoff."""
    if not isinstance(raw, bytes):
        raise TypeError("Sıkıştırılacak içerik bytes olmalıdır.")
    return gzip.compress(raw, compresslevel=compresslevel, mtime=0)


def compress_analysis_report(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    compressed = gzip_compress_bytes(raw, compresslevel=9)
    if len(compressed) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Sıkıştırılmış analiz raporu sınırı aşıyor: {len(compressed)} bayt "
            f"(üst sınır {MAX_UPLOAD_BYTES} bayt)."
        )
    return compressed

def _read_windows_credential() -> str | None:
    """Read the upload token from the current Windows user's Credential Manager."""
    if os.name != "nt":
        return None
    api = None
    credential_pointer = ctypes.POINTER(_CredentialW)()
    try:
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredReadW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.POINTER(ctypes.POINTER(_CredentialW)),
        ]
        api.CredReadW.restype = ctypes.c_int
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        found = api.CredReadW(CREDENTIAL_TARGET, 1, 0, ctypes.byref(credential_pointer))
        if not found or not credential_pointer:
            return None
        record = credential_pointer.contents
        if not record.CredentialBlob or not record.CredentialBlobSize:
            return None
        token = ctypes.string_at(
            record.CredentialBlob, record.CredentialBlobSize
        ).decode("utf-8")
        return token if token and token == token.strip() else None
    except Exception:
        # Credential Manager failures must not stop local report creation or the radar.
        return None
    finally:
        if api is not None and credential_pointer:
            try:
                api.CredFree(ctypes.cast(credential_pointer, ctypes.c_void_p))
            except Exception:
                pass


def _write_windows_credential(token: str) -> bool:
    """Store a token as a Windows generic credential; return success without logging it."""
    if os.name != "nt" or not isinstance(token, str) or not token or token != token.strip():
        return False
    encoded = token.encode("utf-8")
    if len(encoded) > CREDENTIAL_BLOB_MAX_BYTES:
        return False
    try:
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), ctypes.c_uint32]
        api.CredWriteW.restype = ctypes.c_int
        blob = ctypes.create_string_buffer(encoded)
        record = _CredentialW()
        record.Type = 1  # CRED_TYPE_GENERIC
        record.TargetName = CREDENTIAL_TARGET
        record.CredentialBlobSize = len(encoded)
        record.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        record.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE: persists for this Windows user
        record.UserName = "Firsat-Kontrol-Paneli"
        return bool(api.CredWriteW(ctypes.byref(record), 0))
    except Exception:
        return False


def _read_legacy_upload_token(path: Path) -> str | None:
    """Accept only the known Worker endpoint; do not migrate a token for another host."""
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(config, dict):
        return None
    upload_url = config.get("upload_url")
    token = config.get("upload_token")
    if not isinstance(upload_url, str) or not isinstance(token, str):
        return None
    try:
        parsed = urllib.parse.urlsplit(upload_url)
        legacy_expected = urllib.parse.urlsplit(f"{WORKER_BASE_URL}/api/report")
        relay_expected = urllib.parse.urlsplit(UPLOAD_URL)
        valid_url = (
            parsed.scheme.lower() == "https"
            and parsed.netloc.lower() in {legacy_expected.netloc.lower(), relay_expected.netloc.lower()}
            and parsed.path.rstrip("/") == "/api/report"
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return None
    if not valid_url or not token or token != token.strip():
        return None
    return token


def _remove_legacy_config_after_verification(path: Path) -> None:
    """Best-effort cleanup; failure leaves the old file available for another attempt."""
    try:
        path.unlink()
    except OSError:
        pass


def load_connection_config(root: str | Path) -> dict[str, str] | None:
    """Load fixed public endpoints and migrate a legacy token into Windows Credential Manager."""
    legacy_path = Path(root) / CONFIG_NAME
    legacy_token = _read_legacy_upload_token(legacy_path)
    stored_token = _read_windows_credential()

    if isinstance(stored_token, str) and stored_token and stored_token == stored_token.strip():
        if legacy_token and hmac.compare_digest(legacy_token, stored_token):
            _remove_legacy_config_after_verification(legacy_path)
        return {
            "upload_url": UPLOAD_URL,
            "upload_token": stored_token,
            "read_url": READ_URL,
        }

    if not legacy_token:
        return None
    if not _write_windows_credential(legacy_token):
        return None

    # Never delete the plaintext file until the saved value has been read back and matched.
    verified_token = _read_windows_credential()
    if not isinstance(verified_token, str) or not hmac.compare_digest(
        verified_token, legacy_token
    ):
        return None

    _remove_legacy_config_after_verification(legacy_path)
    return {
        "upload_url": UPLOAD_URL,
        "upload_token": verified_token,
        "read_url": READ_URL,
    }

def _report_endpoint(config: dict[str, str], suffix: str = "") -> str:
    """Build a typed upload URL from the configured /api/report endpoint."""
    url = config.get("upload_url", "")
    parsed = urllib.parse.urlsplit(url)
    expected = urllib.parse.urlsplit(UPLOAD_URL)
    if (
        parsed.scheme.lower() != "https"
        or parsed.netloc.lower() != expected.netloc.lower()
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Yükleme adresi sabit ve güvenilir rapor sunucusuna ait olmalıdır.")
    if (
        parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != expected.path
    ):
        raise ValueError("Yükleme adresi sabit /api/report uç noktası olmalıdır.")
    path = parsed.path.rstrip("/") + (f"/{suffix}" if suffix else "")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _post_report(
    config: dict[str, str], endpoint: str, body: bytes, *,
    content_type: str, content_encoding: str | None = None,
) -> dict[str, Any]:
    if not isinstance(body, bytes) or not body:
        raise ValueError("Gönderilecek rapor boş.")
    if len(body) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Gönderilecek rapor {MAX_UPLOAD_BYTES} bayt sınırını aşıyor.")
    token = config.get("upload_token", "")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Yükleme anahtarı yapılandırılmamış.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": "Firsat-Kontrol-Paneli/00",
    }
    if content_encoding:
        headers["Content-Encoding"] = content_encoding
    request = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
    # A report upload replaces the same "latest" record, so retrying a transient
    # connection/server failure is safe and avoids losing a report during relay restarts.
    retry_delays = (1.0, 2.0)
    transient_http_codes = {408, 429, 500, 502, 503, 504}
    for attempt in range(len(retry_delays) + 1):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                response_body = response.read(256 * 1024).decode("utf-8", errors="replace")
                status = response.status
            break
        except urllib.error.HTTPError as exc:
            response_body = exc.read(2048).decode("utf-8", errors="replace")
            if exc.code in transient_http_codes and attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            raise RuntimeError(f"Sunucu HTTP {exc.code}: {response_body}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < len(retry_delays):
                time.sleep(retry_delays[attempt])
                continue
            raise RuntimeError(f"Sunucu bağlantısı başarısız: {exc}") from exc
    try:
        body_json = json.loads(response_body) if response_body else {}
    except json.JSONDecodeError:
        body_json = {}
    if status < 200 or status >= 300 or body_json.get("ok") is not True:
        raise RuntimeError(body_json.get("error") or f"Sunucu beklenmeyen yanıt verdi (HTTP {status}).")
    return body_json


def upload_json_report(
    config: dict[str, str], compressed: bytes, report_kind: str
) -> dict[str, Any]:
    """Upload one gzip-compressed JSON report to its isolated Worker route."""
    if report_kind not in {"analysis", "daily", "troubleshooting"}:
        raise ValueError("Bilinmeyen rapor türü.")
    if not isinstance(compressed, bytes) or not compressed:
        raise ValueError("Gönderilecek sıkıştırılmış rapor boş.")
    if len(compressed) > MAX_UPLOAD_BYTES:
        raise ValueError("Sıkıştırılmış rapor boyut sınırını aşıyor.")
    endpoint = _report_endpoint(config, "" if report_kind == "analysis" else report_kind)
    body_json = _post_report(
        config, endpoint, compressed,
        content_type="application/json; charset=utf-8",
        content_encoding="gzip",
    )
    return {
        "ok": True,
        "report_kind": report_kind,
        "read_url": body_json.get("read_url") or (config.get("read_url", "") if report_kind == "analysis" else ""),
        "candidate_count": body_json.get("candidate_count"),
        "compressed_bytes": len(compressed),
    }


def upload_analysis_report(config: dict[str, str], compressed: bytes) -> dict[str, Any]:
    """Backwards-compatible upload API for the analysis report."""
    return upload_json_report(config, compressed, "analysis")


def upload_troubleshooting_zip(config: dict[str, str], archive: bytes) -> dict[str, Any]:
    """Upload the validated local troubleshooting ZIP as a separate binary object."""
    endpoint = _report_endpoint(config, "troubleshooting-zip")
    body_json = _post_report(
        config, endpoint, archive,
        content_type="application/zip",
    )
    return {
        "ok": True,
        "report_kind": "troubleshooting_zip",
        "read_url": body_json.get("read_url", ""),
        "compressed_bytes": len(archive),
    }


# Screenshot image uploads are deliberately separate from the legacy 8 MiB report API.
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_COUNT = 3
MAX_IMAGE_CONTROL_BYTES = 64 * 1024
_IMAGE_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_IMAGE_TYPES = {".png": ("PNG", "image/png"), ".jpg": ("JPEG", "image/jpeg"), ".jpeg": ("JPEG", "image/jpeg")}


def validate_image_selection_count(count: int) -> int:
    """Return the supported selection count or reject 0 and selections above three."""
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError("Görüntü seçimi sayısı geçersiz.")
    if count < 1:
        raise ValueError("En az bir görüntü seçilmelidir.")
    if count > MAX_IMAGE_COUNT:
        raise ValueError("En fazla üç görüntü seçilebilir.")
    return count


def _safe_image_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename:
        raise ValueError("Görüntü dosya adı geçersiz.")
    name = filename
    if "/" in name or "\\" in name or ":" in name or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError("Görüntü dosya adı yalnızca dosya adını içermelidir.")
    if len(name.encode("utf-8")) > 255 or name in {".", ".."}:
        raise ValueError("Görüntü dosya adı çok uzun veya geçersiz.")
    return name


def validate_image_bytes(data: bytes, filename: str) -> dict[str, Any]:
    """Validate image size, extension, file signature and a full Pillow decode."""
    if not isinstance(data, bytes):
        raise ValueError("Görüntü içeriği bayt biçiminde olmalıdır.")
    if not data:
        raise ValueError("Görüntü dosyası boş.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Görüntü 15 MiB sınırını aşıyor.")

    name = _safe_image_filename(filename)
    suffix = Path(name).suffix.lower()
    expected = _IMAGE_TYPES.get(suffix)
    if expected is None:
        raise ValueError("Yalnızca PNG, JPG ve JPEG dosyaları kabul edilir.")
    expected_format, content_type = expected
    if expected_format == "PNG":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG dosya imzası geçersiz.")
    elif not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("JPEG dosya imzası geçersiz.")

    try:
        from PIL import Image, UnidentifiedImageError

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                detected_format = image.format
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        if detected_format != expected_format:
            raise ValueError("Dosya uzantısı ve gerçek görüntü biçimi eşleşmiyor.")
    except ValueError:
        raise
    except ModuleNotFoundError as exc:
        if exc.name == "PIL" or (isinstance(exc.name, str) and exc.name.startswith("PIL.")):
            raise ValueError(
                "Görüntü doğrulama paketi Pillow kurulu değil. Programı BASLAT.bat ile yeniden açın; "
                "gerekli paketler otomatik kontrol edilip kurulmalıdır."
            ) from exc
        raise ValueError(f"Görüntü bozuk veya açılamıyor: {name}") from exc
    except Exception as exc:
        raise ValueError(f"Görüntü bozuk veya açılamıyor: {name}") from exc

    return {
        "filename": name,
        "format": expected_format,
        "content_type": content_type,
        "size_bytes": len(data),
    }


def validate_image_file(path: str | Path) -> dict[str, Any]:
    """Validate a local file without modifying or recompressing it."""
    file_path = Path(path)
    try:
        if file_path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError(f"{file_path.name}: görüntü 15 MiB sınırını aşıyor.")
        raw = file_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Görüntü dosyası okunamadı: {file_path.name}") from exc
    result = validate_image_bytes(raw, file_path.name)
    result["path"] = str(file_path)
    return result


def make_image_thumbnail(data: bytes, size: tuple[int, int] = (160, 110)) -> bytes:
    """Create PNG bytes for UI preview only; uploaded source bytes remain untouched."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as original:
            preview = original.copy()
        preview.thumbnail(size)
        output = io.BytesIO()
        preview.save(output, format="PNG")
        return output.getvalue()
    except Exception as exc:
        raise ValueError("Görüntü önizlemesi oluşturulamadı.") from exc


def build_image_replacement_plan(existing_images: list[dict[str, Any]], new_count: int) -> dict[str, list[dict[str, Any]]]:
    """Keep the newest current images and mark the oldest entries for replacement."""
    validate_image_selection_count(new_count)
    if not isinstance(existing_images, list) or len(existing_images) > MAX_IMAGE_COUNT:
        raise ValueError("Buluttaki etkin görüntü listesi geçersiz.")
    for image in existing_images:
        if not isinstance(image, dict):
            raise ValueError("Buluttaki etkin görüntü kaydı geçersiz.")

    def uploaded_time(image: dict[str, Any]) -> float:
        value = image.get("uploaded_at")
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0.0

    newest_first = sorted(existing_images, key=uploaded_time, reverse=True)
    keep_count = min(len(newest_first), max(0, MAX_IMAGE_COUNT - new_count))
    return {
        "keep": newest_first[:keep_count],
        "replace": newest_first[keep_count:],
    }


def _validate_image_id(value: Any) -> str:
    if not isinstance(value, str) or not _IMAGE_ID_PATTERN.fullmatch(value):
        raise ValueError("Görüntü kimliği geçersiz.")
    return value


def _image_upload_endpoint(config: dict[str, str], route: str) -> str:
    if route not in {"stage", "commit", "abort"}:
        raise ValueError("Bilinmeyen görüntü aktarım rotası.")
    # Keep screenshot stage/commit/abort requests on the isolated test relay,
    # not on the legacy production report relay.
    parsed = urllib.parse.urlsplit(IMAGE_RELAY_BASE_URL)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Görüntü adresi sabit test geçidine ait olmalıdır.")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, f"/api/images/{route}", "", ""))


def _image_api_request(
    config: dict[str, str], route: str, body: bytes, *, content_type: str,
    filename: str | None = None,
) -> dict[str, Any]:
    max_bytes = MAX_IMAGE_BYTES if route == "stage" else MAX_IMAGE_CONTROL_BYTES
    if not isinstance(body, bytes) or not body or len(body) > max_bytes:
        raise ValueError("Görüntü aktarım gövdesi boş veya boyut sınırını aşıyor.")
    token = config.get("upload_token", "")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Görüntü aktarım anahtarı yapılandırılmamış.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": "Firsat-Kontrol-Paneli/01",
    }
    if filename is not None:
        safe_name = _safe_image_filename(filename)
        encoded_name = base64.urlsafe_b64encode(safe_name.encode("utf-8")).decode("ascii").rstrip("=")
        headers["X-Image-Name-B64"] = encoded_name
    # Wake the free Render service before a side-effectful POST; never blindly replay POST bodies.
    _ensure_image_relay_ready()
    request = urllib.request.Request(
        _image_upload_endpoint(config, route), data=body, method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=90 if route == "stage" else 30) as response:
            raw = response.read(64 * 1024 + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Görüntü sunucusu HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Görüntü sunucusuna bağlantı başarısız: {exc}") from exc
    if len(raw) > 64 * 1024:
        raise RuntimeError("Görüntü sunucusundan beklenmeyen büyüklükte yanıt geldi.")
    try:
        result = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        result = {}
    if status < 200 or status >= 300 or result.get("ok") is not True:
        raise RuntimeError(result.get("error") or f"Görüntü sunucusu beklenmeyen yanıt verdi (HTTP {status}).")
    return result


def _image_relay_get_bytes(
    url: str,
    *,
    label: str,
    headers: dict[str, str],
    max_bytes: int,
    timeout: float = IMAGE_RELAY_REQUEST_TIMEOUT,
    expected_content_type: str | None = None,
) -> bytes:
    """GET from the isolated Render relay, retrying transient cold-start/network failures."""
    retryable_statuses = {408, 425, 429, 500, 502, 503, 504}
    last_problem = "belirsiz bağlantı hatası"
    attempts = len(IMAGE_RELAY_RETRY_DELAYS) + 1

    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(max_bytes + 1)
                status = response.status
                response_content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            lower_detail = detail.casefold()
            # These are configuration errors, not a sleeping relay; retrying cannot fix them.
            permanent_cloudinary_error = (
                "cloudinary bağlantısı ayarlanmadı" in lower_detail
                or "cloudinary bağlantı ayarları geçersiz" in lower_detail
            )
            last_problem = f"HTTP {exc.code}: {detail or exc.reason}"
            if (
                exc.code not in retryable_statuses
                or permanent_cloudinary_error
                or attempt >= attempts - 1
            ):
                raise RuntimeError(f"{label} HTTP {exc.code}: {detail or exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_problem = f"{type(exc).__name__}: {exc}"
            if attempt >= attempts - 1:
                break
        else:
            if status < 200 or status >= 300:
                raise RuntimeError(f"{label} beklenmeyen HTTP durumu: {status}.")
            if len(raw) > max_bytes:
                raise RuntimeError(f"{label} beklenenden büyük.")
            if expected_content_type and response_content_type != expected_content_type:
                raise RuntimeError(f"{label} içerik türü beklenen biçimde değil.")
            return raw

        if attempt < attempts - 1:
            time.sleep(IMAGE_RELAY_RETRY_DELAYS[attempt])

    raise RuntimeError(
        f"{label} {attempts} denemede alınamadı. Adres: {url}. Son hata: {last_problem}. "
        "Render hizmeti uyanıyor veya ağa erişilemiyor olabilir; tekrar deneyin."
    )


def _ensure_image_relay_ready() -> None:
    """Warm and validate the Render relay before manifest reads or image mutations."""
    raw = _image_relay_get_bytes(
        IMAGE_RELAY_HEALTH_URL,
        label="Görüntü test sunucusu sağlık kontrolü",
        headers={"Accept": "application/json", "User-Agent": "Firsat-Kontrol-Paneli/01"},
        max_bytes=8 * 1024,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Görüntü test sunucusunun sağlık yanıtı geçerli JSON değil.") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True or payload.get("version") != 2:
        raise RuntimeError("Görüntü test sunucusu beklenen sürümde değil; /healthz yanıtı doğrulanamadı.")


def fetch_image_manifest() -> list[dict[str, Any]]:
    """Warm the test relay and fetch its public manifest with transient-error retries."""
    _ensure_image_relay_ready()
    url = f"{IMAGE_BASE_URL}/images/manifest"
    raw = _image_relay_get_bytes(
        url,
        label="Buluttaki görüntü listesi",
        headers={"Accept": "application/json", "User-Agent": "Firsat-Kontrol-Paneli/01"},
        max_bytes=128 * 1024,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Buluttaki görüntü listesi geçerli JSON değil.") from exc
    images = payload.get("images") if isinstance(payload, dict) and payload.get("ok") is True else None
    if not isinstance(images, list) or len(images) > MAX_IMAGE_COUNT:
        error_text = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error_text, str) and error_text:
            raise RuntimeError(f"Buluttaki görüntü listesi alınamadı: {error_text}")
        raise RuntimeError("Buluttaki etkin görüntü listesi geçersiz.")
    validated = []
    for image in images:
        if not isinstance(image, dict):
            raise RuntimeError("Buluttaki görüntü kaydı geçersiz.")
        image_id = _validate_image_id(image.get("id"))
        filename = _safe_image_filename(image.get("filename", ""))
        content_type = image.get("content_type")
        if content_type not in {"image/png", "image/jpeg"}:
            raise RuntimeError("Buluttaki görüntünün içerik türü geçersiz.")
        if Path(filename).suffix.lower() not in _IMAGE_TYPES or _IMAGE_TYPES[Path(filename).suffix.lower()][1] != content_type:
            raise RuntimeError("Buluttaki görüntünün adı ve içerik türü eşleşmiyor.")
        size_bytes = image.get("size_bytes")
        if not isinstance(size_bytes, int) or not 1 <= size_bytes <= MAX_IMAGE_BYTES:
            raise RuntimeError("Buluttaki görüntünün boyut bilgisi geçersiz.")
        uploaded_at = image.get("uploaded_at")
        if not isinstance(uploaded_at, str) or not uploaded_at:
            raise RuntimeError("Buluttaki görüntünün yükleme zamanı eksik.")
        validated.append({
            "id": image_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "uploaded_at": uploaded_at,
            "url": f"{IMAGE_BASE_URL}/images/{image_id}",
        })
    return validated

def download_active_image(image_id: str, filename: str, expected_content_type: str) -> bytes:
    """Download an image only through the fixed test relay and validate it before preview."""
    image_id = _validate_image_id(image_id)
    if expected_content_type not in {"image/png", "image/jpeg"}:
        raise ValueError("Buluttaki görüntü içerik türü geçersiz.")
    _ensure_image_relay_ready()
    url = f"{IMAGE_BASE_URL}/images/{image_id}"
    raw = _image_relay_get_bytes(
        url,
        label=f"Buluttaki görüntü {image_id}",
        headers={"Accept": expected_content_type, "User-Agent": "Firsat-Kontrol-Paneli/01"},
        max_bytes=MAX_IMAGE_BYTES,
        timeout=30.0,
        expected_content_type=expected_content_type,
    )
    validate_image_bytes(raw, filename)
    return raw


def upload_image_stage(config: dict[str, str], data: bytes, filename: str) -> dict[str, Any]:
    """Upload one fully validated original image into temporary Cloudinary storage."""
    metadata = validate_image_bytes(data, filename)
    result = _image_api_request(
        config, "stage", data, content_type=metadata["content_type"], filename=metadata["filename"]
    )
    _validate_image_id(result.get("staged_id"))
    return result


def commit_image_uploads(config: dict[str, str], staged_ids: list[str]) -> dict[str, Any]:
    if not isinstance(staged_ids, list) or not 1 <= len(staged_ids) <= MAX_IMAGE_COUNT:
        raise ValueError("1–3 geçici görüntü kimliği gereklidir.")
    ids = [_validate_image_id(item) for item in staged_ids]
    if len(set(ids)) != len(ids):
        raise ValueError("Geçici görüntü kimlikleri benzersiz olmalıdır.")
    body = json.dumps({"staged_ids": ids}, separators=(",", ":")).encode("utf-8")
    return _image_api_request(config, "commit", body, content_type="application/json")


def abort_image_uploads(config: dict[str, str], staged_ids: list[str]) -> dict[str, Any]:
    if not staged_ids:
        return {"ok": True, "aborted_count": 0}
    if not isinstance(staged_ids, list) or len(staged_ids) > MAX_IMAGE_COUNT:
        raise ValueError("Geçici görüntü kimlikleri geçersiz.")
    ids = [_validate_image_id(item) for item in staged_ids]
    body = json.dumps({"staged_ids": ids}, separators=(",", ":")).encode("utf-8")
    return _image_api_request(config, "abort", body, content_type="application/json")


def upload_image_batch(config: dict[str, str], paths: list[str | Path]) -> dict[str, Any]:
    """Stage all selected files separately, then atomically commit them as one group."""
    if not isinstance(paths, (list, tuple)):
        raise ValueError("Görüntü yolu listesi geçersiz.")
    validate_image_selection_count(len(paths))
    staged_ids: list[str] = []
    try:
        for path in paths:
            file_path = Path(path)
            validate_image_file(file_path)
            data = file_path.read_bytes()
            validate_image_bytes(data, file_path.name)
            result = upload_image_stage(config, data, file_path.name)
            staged_id = _validate_image_id(result.get("staged_id"))
            staged_ids.append(staged_id)
        return commit_image_uploads(config, staged_ids)
    except Exception:
        # If the commit response was lost after the server published the manifest, confirm first.
        if len(staged_ids) == len(paths):
            try:
                active = fetch_image_manifest()
                active_ids = {image["id"] for image in active}
                if all(image_id in active_ids for image_id in staged_ids):
                    return {"ok": True, "idempotent": True, "images": active}
            except Exception:
                pass
        if staged_ids:
            try:
                abort_image_uploads(config, staged_ids)
            except Exception:
                pass
        raise
