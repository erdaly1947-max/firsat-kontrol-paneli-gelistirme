"""BtcTurk PRO için bağımsız USDT piyasa verisi ve teknik analiz katmanı.

Yalnızca halka açık BtcTurk piyasa uç noktaları kullanılır. Emir gönderimi,
hesap bağlantısı veya Binance mumlarını BtcTurk işlem planında kullanma yoktur.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import calendar
import math
import time
from typing import Any

import requests

from radar_core import assess_timeframe, build_trade_plan, timeframe_bar_end_ms

BTCTURK_API = "https://api.btcturk.com"
BTCTURK_GRAPH_API = "https://graph-api.btcturk.com"
BINANCE_PUBLIC_BASES = (
    "https://data-api.binance.vision",
    "https://api.binance.com",
)
TIMEFRAMES = ("5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
TIMEFRAME_LABELS = {
    "5m": "5 dakika", "15m": "15 dakika", "30m": "30 dakika",
    "1h": "1 saat", "4h": "4 saat", "1d": "1 gün",
    "1w": "1 hafta", "1M": "1 ay",
}
COMMISSION_RATE = 0.0014
REQUEST_TIMEOUT = 12.0
USER_AGENT = "FirsatKontrolPaneli/01 (public-market-data-only)"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _positive(value: Any) -> float | None:
    result = _number(value)
    return result if result is not None and result > 0 else None


def _request_json(url: str, *, params: dict[str, Any] | None = None,
                  timeout: float = REQUEST_TIMEOUT) -> Any:
    response = requests.get(
        url, params=params, timeout=timeout,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError(str(payload.get("message") or payload.get("code") or "BtcTurk isteği başarısız."))
    return payload


def _response_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if isinstance(data, dict):
        rows = data.get("symbols", data.get("pairs", data.get("data", [])))
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def fetch_btcturk_pro_markets(*, timeout: float = REQUEST_TIMEOUT) -> dict[str, dict[str, Any]]:
    """Return current, exchangeInfo-verified active BtcTurk USDT Spot pairs."""
    payload = _request_json(
        f"{BTCTURK_API}/api/v2/server/exchangeinfo", timeout=timeout,
    )
    markets: dict[str, dict[str, Any]] = {}
    for row in _response_rows(payload):
        name = str(row.get("name") or row.get("symbol") or "").upper().replace("_", "").strip()
        base = str(row.get("numerator") or row.get("baseAsset") or "").upper().strip()
        quote = str(row.get("denominator") or row.get("quoteAsset") or "").upper().strip()
        status = str(row.get("status") or "").upper().strip()
        if not base and name.endswith("USDT"):
            base, quote = name[:-4], "USDT"
        if not (base and quote == "USDT" and name == f"{base}USDT" and status == "TRADING"):
            continue
        filters = row.get("filters")
        price_filter = {}
        if isinstance(filters, list):
            price_filter = next(
                (item for item in filters
                 if isinstance(item, dict) and str(item.get("filterType") or "").upper() == "PRICE_FILTER"),
                {},
            )
        methods = row.get("orderMethods")
        markets[name] = {
            "symbol": name,
            "base": base,
            "quote": quote,
            "status": status,
            "pair_id": row.get("id"),
            "numerator_scale": row.get("numeratorScale"),
            "denominator_scale": row.get("denominatorScale"),
            "has_fraction": row.get("hasFraction"),
            "tick_size": _positive(price_filter.get("tickSize")),
            "minimum_price": _positive(price_filter.get("minPrice")),
            "maximum_price": _positive(price_filter.get("maxPrice")),
            "minimum_order_usdt": _positive(price_filter.get("minExchangeValue")),
            "minimum_amount": _positive(price_filter.get("minAmount")),
            "maximum_amount": _positive(price_filter.get("maxAmount")),
            "order_methods": [str(x).upper() for x in methods] if isinstance(methods, list) else [],
            "metadata_source": "BtcTurk exchangeInfo",
        }
    if not markets:
        raise RuntimeError("BtcTurk exchangeInfo içinde etkin USDT Spot paritesi bulunamadı.")
    return markets


def fetch_btcturk_pro_ticker(symbol: str, *, timeout: float = REQUEST_TIMEOUT) -> dict[str, Any]:
    symbol = str(symbol or "").upper().replace("/", "").replace("_", "").strip()
    if not symbol.endswith("USDT") or len(symbol) < 6:
        raise ValueError("BtcTurk PRO yalnızca USDT Spot paritelerini destekler.")
    payload = _request_json(
        f"{BTCTURK_API}/api/v2/ticker",
        params={"pairSymbol": symbol}, timeout=timeout,
    )
    rows = _response_rows(payload)
    row = next((item for item in rows if str(item.get("pair") or "").upper().replace("_", "") == symbol), None)
    if row is None:
        raise RuntimeError(f"{symbol} için BtcTurk ticker verisi bulunamadı.")
    ticker = {
        "symbol": symbol,
        "last": _positive(row.get("last")),
        "bid": _positive(row.get("bid")),
        "ask": _positive(row.get("ask")),
        "open": _positive(row.get("open")),
        "high_24h": _positive(row.get("high")),
        "low_24h": _positive(row.get("low")),
        "base_volume_24h": _number(row.get("volume")),
        "average_24h": _positive(row.get("average")),
        "change_24h_pct": _number(row.get("dailyPercent")),
        "timestamp_ms": int(_number(row.get("timestamp")) or 0),
        "source": "BtcTurk /api/v2/ticker",
    }
    if ticker["last"] is None or ticker["timestamp_ms"] <= 0:
        raise RuntimeError(f"{symbol} ticker yanıtı geçerli son fiyat/zaman içermiyor.")
    return ticker


def _parse_book_side(raw: Any) -> list[dict[str, float]]:
    levels: list[dict[str, float]] = []
    if not isinstance(raw, list):
        return levels
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        price, quantity = _positive(item[0]), _positive(item[1])
        if price is None or quantity is None:
            continue
        levels.append({"price": price, "quantity": quantity, "quote_value": price * quantity})
    return levels


def fetch_btcturk_pro_orderbook(symbol: str, *, limit: int = 25,
                                timeout: float = REQUEST_TIMEOUT) -> dict[str, Any]:
    symbol = str(symbol or "").upper().replace("/", "").replace("_", "").strip()
    payload = _request_json(
        f"{BTCTURK_API}/api/v2/orderbook",
        params={"pairSymbol": symbol, "limit": max(1, min(100, int(limit)))},
        timeout=timeout,
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError(f"{symbol} emir defteri yanıtı geçersiz.")
    bids = _parse_book_side(data.get("bids"))
    asks = _parse_book_side(data.get("asks"))
    bids.sort(key=lambda x: x["price"], reverse=True)
    asks.sort(key=lambda x: x["price"])
    if not bids or not asks:
        raise RuntimeError(f"{symbol} emir defterinde geçerli alış ve satış kademeleri yok.")
    timestamp = int(_number(data.get("timestamp")) or 0)
    return {
        "symbol": symbol, "bids": bids, "asks": asks,
        "timestamp_ms": timestamp,
        "source": "BtcTurk /api/v2/orderbook",
    }


def _fetch_kline_resolution(symbol: str, resolution: str, days: int,
                            *, now_ms: int | None = None,
                            timeout: float = REQUEST_TIMEOUT) -> list[dict[str, Any]]:
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    end_seconds = current_ms // 1000
    start_seconds = max(1, end_seconds - int(days) * 86400)
    resolutions = (resolution, "D", "1440") if resolution == "1D" else (resolution,)
    errors: list[str] = []
    for selected in dict.fromkeys(resolutions):
        try:
            payload = _request_json(
                f"{BTCTURK_GRAPH_API}/v1/klines/history",
                params={
                    "symbol": symbol, "resolution": selected,
                    "from": start_seconds, "to": end_seconds,
                },
                timeout=timeout,
            )
            if not isinstance(payload, dict) or str(payload.get("s") or "").lower() != "ok":
                raise ValueError(f"Kline durumu başarılı değil: {payload.get('s') if isinstance(payload, dict) else 'yanıt yok'}")
            keys = ("t", "o", "h", "l", "c", "v")
            arrays = [payload.get(key) for key in keys]
            if not all(isinstance(value, list) for value in arrays):
                raise ValueError("Kline yanıtında t/o/h/l/c/v dizilerinden biri yok.")
            count = min(len(value) for value in arrays)
            if count < 1:
                raise ValueError("BtcTurk Kline geçmişi boş.")
            if selected == "1":
                duration_ms = 60_000
            elif selected == "15":
                duration_ms = 15 * 60_000
            elif selected == "30":
                duration_ms = 30 * 60_000
            elif selected == "60":
                duration_ms = 60 * 60_000
            elif selected == "240":
                duration_ms = 240 * 60_000
            else:
                duration_ms = 86_400_000
            bars: list[dict[str, Any]] = []
            for index in range(count):
                timestamp = _number(arrays[0][index])
                values = [_number(arrays[j][index]) for j in range(1, 6)]
                if timestamp is None or any(value is None for value in values):
                    continue
                start_ms = int(timestamp * 1000) if timestamp < 10_000_000_000 else int(timestamp)
                open_, high, low, close, volume = values
                if min(open_, high, low, close) <= 0 or volume < 0:
                    continue
                bars.append({
                    "t": start_ms, "o": open_, "h": high, "l": low,
                    "c": close, "v": volume,
                    "closed": start_ms + duration_ms <= current_ms,
                    "synthetic": False,
                })
            bars.sort(key=lambda item: item["t"])
            unique: dict[int, dict[str, Any]] = {int(bar["t"]): bar for bar in bars}
            result = list(unique.values())
            if result:
                return result
            raise ValueError("Kline yanıtında kullanılabilir mum bulunamadı.")
        except Exception as exc:
            errors.append(f"resolution={selected}: {type(exc).__name__}: {str(exc)[:180]}")
    raise RuntimeError("BtcTurk mum geçmişi alınamadı: " + " | ".join(errors))


def _aggregate_intraday(bars: list[dict[str, Any]], minutes: int,
                        *, now_ms: int | None = None) -> list[dict[str, Any]]:
    """Aggregate complete consecutive 1-minute candles; do not invent quote volume."""
    interval_ms = int(minutes) * 60_000
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for bar in bars:
        start = int(bar["t"]) // interval_ms * interval_ms
        buckets[start].append(bar)
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    result: list[dict[str, Any]] = []
    for start, group in sorted(buckets.items()):
        group.sort(key=lambda item: int(item["t"]))
        expected = [start + index * 60_000 for index in range(minutes)]
        actual = [int(item["t"]) for item in group]
        complete = actual == expected and all(item.get("closed") is True for item in group)
        if not complete or start + interval_ms > current_ms:
            continue
        result.append({
            "t": start, "o": float(group[0]["o"]),
            "h": max(float(item["h"]) for item in group),
            "l": min(float(item["l"]) for item in group),
            "c": float(group[-1]["c"]),
            "v": sum(float(item.get("v", 0) or 0) for item in group),
            "closed": True, "synthetic": False,
            "source_bar_count": len(group),
        })
    return result


def _aggregate_calendar(daily_bars: list[dict[str, Any]], period: str,
                        *, now_ms: int | None = None) -> list[dict[str, Any]]:
    """Aggregate complete UTC daily candles into complete 7-day or calendar-month bars."""
    current_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    buckets: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for bar in daily_bars:
        if bar.get("closed") is not True:
            continue
        day = datetime.fromtimestamp(int(bar["t"]) / 1000, tz=timezone.utc).date()
        if period == "1w":
            key = day - timedelta(days=day.weekday())
        else:
            key = day.replace(day=1)
        buckets[key].append(bar)
    result: list[dict[str, Any]] = []
    for key, group in sorted(buckets.items()):
        group.sort(key=lambda item: int(item["t"]))
        start = datetime(key.year, key.month, key.day, tzinfo=timezone.utc)
        if period == "1w":
            expected_days = 7
            end = start + timedelta(days=7)
        else:
            expected_days = calendar.monthrange(key.year, key.month)[1]
            end = (datetime(key.year + 1, 1, 1, tzinfo=timezone.utc)
                   if key.month == 12 else datetime(key.year, key.month + 1, 1, tzinfo=timezone.utc))
        expected_times = [
            int((start + timedelta(days=index)).timestamp() * 1000)
            for index in range(expected_days)
        ]
        actual_times = [int(item["t"]) for item in group]
        if actual_times != expected_times or int(end.timestamp() * 1000) > current_ms:
            continue
        result.append({
            "t": int(start.timestamp() * 1000),
            "o": float(group[0]["o"]),
            "h": max(float(item["h"]) for item in group),
            "l": min(float(item["l"]) for item in group),
            "c": float(group[-1]["c"]),
            "v": sum(float(item.get("v", 0) or 0) for item in group),
            "closed": True, "synthetic": False,
            "source_bar_count": len(group),
        })
    return result


def fetch_btcturk_pro_candles(symbol: str, *, timeout: float = REQUEST_TIMEOUT) -> dict[str, list[dict[str, Any]]]:
    """Fetch BtcTurk-native candles/volume for the eight panel timeframes."""
    symbol = str(symbol or "").upper().replace("/", "").replace("_", "").strip()
    now_ms = int(time.time() * 1000)
    minute = _fetch_kline_resolution(symbol, "1", 4, now_ms=now_ms, timeout=timeout)
    bars_15m = _fetch_kline_resolution(symbol, "15", 75, now_ms=now_ms, timeout=timeout)
    bars_30m = _fetch_kline_resolution(symbol, "30", 100, now_ms=now_ms, timeout=timeout)
    bars_1h = _fetch_kline_resolution(symbol, "60", 180, now_ms=now_ms, timeout=timeout)
    bars_4h = _fetch_kline_resolution(symbol, "240", 400, now_ms=now_ms, timeout=timeout)
    daily = _fetch_kline_resolution(symbol, "1D", 2200, now_ms=now_ms, timeout=timeout)
    return {
        "5m": _aggregate_intraday(minute, 5, now_ms=now_ms),
        "15m": bars_15m,
        "30m": bars_30m,
        "1h": bars_1h,
        "4h": bars_4h,
        "1d": daily,
        "1w": _aggregate_calendar(daily, "1w", now_ms=now_ms),
        "1M": _aggregate_calendar(daily, "1M", now_ms=now_ms),
    }


def fetch_binance_comparison(symbol: str, *, timeout: float = 7.0) -> dict[str, Any] | None:
    """Small comparison-only quote; never passed to BtcTurk technical calculations."""
    symbol = str(symbol or "").upper().strip()
    for base in BINANCE_PUBLIC_BASES:
        try:
            payload = _request_json(
                f"{base}/api/v3/ticker/24hr",
                params={"symbol": symbol}, timeout=timeout,
            )
            return {
                "symbol": symbol,
                "last": _positive(payload.get("lastPrice")) if isinstance(payload, dict) else None,
                "change_24h_pct": _number(payload.get("priceChangePercent")) if isinstance(payload, dict) else None,
                "source": "Binance yalnızca karşılaştırma",
            }
        except Exception:
            continue
    return None


def _orderbook_metrics(ticker: dict[str, Any], book: dict[str, Any]) -> dict[str, Any]:
    bids = book.get("bids") if isinstance(book.get("bids"), list) else []
    asks = book.get("asks") if isinstance(book.get("asks"), list) else []
    best_bid = (bids[0]["price"] if bids else None) or _positive(ticker.get("bid"))
    best_ask = (asks[0]["price"] if asks else None) or _positive(ticker.get("ask"))
    midpoint = (
        (best_bid + best_ask) / 2.0
        if best_bid is not None and best_ask is not None and best_bid > 0 and best_ask > 0
        else None
    )
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    spread_pct = (
        spread / midpoint * 100.0
        if spread is not None and midpoint and spread >= 0 else None
    )
    bid_depth = (
        sum(level["quote_value"] for level in bids if midpoint and level["price"] >= midpoint * 0.99)
        if midpoint else None
    )
    ask_depth = (
        sum(level["quote_value"] for level in asks if midpoint and level["price"] <= midpoint * 1.01)
        if midpoint else None
    )
    total_depth = (
        bid_depth + ask_depth
        if bid_depth is not None and ask_depth is not None else None
    )
    imbalance_pct = (
        (bid_depth - ask_depth) / total_depth * 100.0
        if total_depth is not None and total_depth > 0 else None
    )
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "midpoint": midpoint,
        "spread": spread,
        "spread_pct": spread_pct,
        "bid_depth_1pct_usdt": bid_depth,
        "ask_depth_1pct_usdt": ask_depth,
        "imbalance_1pct_pct": imbalance_pct,
    }


def _plan_phase(assessments: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    order = ("15m", "30m", "1h", "5m", "4h", "1d", "1w", "1M")
    for phase in ("C", "B"):
        for timeframe in order:
            row = assessments.get(timeframe)
            if isinstance(row, dict) and row.get("phase") == phase and row.get("data_sufficient") is True:
                return phase, timeframe
    return None, None


def analyze_btcturk_pro(symbol: str, markets: dict[str, dict[str, Any]],
                        ticker: dict[str, Any], book: dict[str, Any],
                        bars_by_timeframe: dict[str, list[dict[str, Any]]],
                        settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze the pair exclusively from BtcTurk candles, ticker, and order book."""
    market = markets.get(symbol)
    if not isinstance(market, dict):
        raise ValueError(f"{symbol} etkin BtcTurk USDT Spot evreninde bulunmuyor.")
    settings = settings if isinstance(settings, dict) else {}
    assessments: dict[str, dict[str, Any]] = {}
    for timeframe in TIMEFRAMES:
        bars = bars_by_timeframe.get(timeframe)
        assessments[timeframe] = assess_timeframe(
            bars if isinstance(bars, list) else [], timeframe, settings,
        )
    phase, phase_timeframe = _plan_phase(assessments)
    ticker_ms = int(ticker.get("timestamp_ms") or 0)
    now_ms = int(time.time() * 1000)
    ticker_age = max(0, (now_ms - ticker_ms) / 1000) if ticker_ms else None
    ticker_fresh = ticker_age is not None and ticker_age <= 45
    phase_rows = bars_by_timeframe.get(phase_timeframe) if phase_timeframe else []
    phase_rows = phase_rows if isinstance(phase_rows, list) else []
    last_phase_bar = next(
        (bar for bar in reversed(phase_rows)
         if isinstance(bar, dict) and bar.get("closed") is True),
        None,
    )
    last_candle_start = int(last_phase_bar["t"]) if last_phase_bar else None
    last_candle_end = (
        timeframe_bar_end_ms(phase_timeframe, last_candle_start)
        if phase_timeframe and last_candle_start is not None else None
    )
    candle_age = (
        max(0.0, (now_ms - last_candle_end) / 1000.0)
        if last_candle_end is not None else None
    )
    # Karar #30: ticker eskiyse en son güvenilir BtcTurk kapanmış mumundan
    # açıkça TASLAK etiketli plan gösterilebilir. Bu, canlı fiyatın güncel
    # olduğu anlamına gelmez; planın fiyat referansı ayrıca belirtilir.
    candle_price = _positive(last_phase_bar.get("c")) if last_phase_bar else None
    ticker_price = _positive(ticker.get("last"))
    draft_from_closed_candle = not ticker_fresh and candle_price is not None
    plan_price = ticker_price if ticker_fresh else candle_price
    candidate = {
        "symbol": symbol,
        "base_asset": market["base"],
        "phase": phase,
        "phase_timeframe": phase_timeframe,
        "timeframes": assessments,
        "latest_price": plan_price,
        "data_freshness": "CANLI AKIŞ GÜNCEL" if plan_price is not None else "VERİ ESKİ",
    }
    plan = build_trade_plan(candidate, settings) if phase in ("B", "C") and plan_price is not None else {
        "status": "UYGUN DEĞİL",
        "reason": (
            "BtcTurk tarafında güvenilir fiyat referansı yok; işlem planı oluşturulmadı."
            if phase in ("B", "C")
            else "BtcTurk verisinde aynı zaman diliminde doğrulanmış B/C aşaması yok; giriş/stop/hedef planı üretilmedi."
        ),
    }
    if isinstance(plan, dict) and plan.get("status") not in {"UYGUN DEĞİL", "HESAPLANAMADI", "VERİ ESKİ — PLAN YOK"}:
        plan["draft_from_closed_candle"] = draft_from_closed_candle
        plan["price_reference"] = (
            "SON KAPANMIŞ BTCTURK MUMU — TASLAK"
            if draft_from_closed_candle else "BTCTURK TICKER"
        )
        plan["price_reference_age_seconds"] = candle_age if draft_from_closed_candle else ticker_age
        plan["draft_warning"] = (
            "Canlı ticker güncel değil. Seviyeler son kapanmış BtcTurk mumunun kapanış fiyatıyla taslak olarak hesaplandı; güncel ticker geldiğinde yeniden değerlendirilmelidir."
            if draft_from_closed_candle else None
        )
    market_metrics = _orderbook_metrics(ticker, book)
    book_ms = int(book.get("timestamp_ms") or 0)
    book_age = max(0, (now_ms - book_ms) / 1000) if book_ms else None
    book_fresh = book_age is not None and book_age <= 45
    market_rules_available = (
        market.get("numerator_scale") is not None
        and market.get("denominator_scale") is not None
        and market.get("minimum_order_usdt") is not None
    )
    plan_available = (
        isinstance(plan, dict)
        and plan.get("status") not in {"UYGUN DEĞİL", "HESAPLANAMADI", "VERİ ESKİ — PLAN YOK"}
        and plan.get("technical_targets_available") is True
    )
    if market.get("status") != "TRADING" or not market.get("symbol"):
        readiness = "İŞLEM PLANI OLUŞTURULAMAZ"
        readiness_reason = "BtcTurk tarafında etkin ve doğrulanmış USDT Spot paritesi yok."
    elif not plan_available:
        readiness = "İŞLEM PLANI OLUŞTURULAMAZ"
        readiness_reason = str(plan.get("reason") or "Geçerli BtcTurk teknik giriş ve hedef planı üretilemedi.")
    elif not ticker_fresh or not book_fresh or not market_rules_available or draft_from_closed_candle:
        readiness = "DİKKAT"
        reasons = []
        if not ticker_fresh:
            reasons.append("Canlı ticker güncel değil")
        if not book_fresh:
            reasons.append("Emir defteri güncel değil")
        if not market_rules_available:
            reasons.append("BtcTurk parite işlem kurallarının bir bölümü eksik")
        if draft_from_closed_candle:
            reasons.append("Plan son kapanmış BtcTurk mumundan taslak olarak üretildi")
        readiness_reason = "; ".join(reasons) + ". Güncel veri geldiğinde plan yeniden değerlendirilmelidir."
    else:
        readiness = "İŞLEM YAPILABİLİR"
        readiness_reason = (
            "BtcTurk USDT paritesi, güncel ticker/emir defteri, işlem hassasiyeti ve teknik plan mevcut. "
            "Bu durum emir önerisi veya gerçekleşme garantisi değildir; spread ve derinlik aşağıda ayrıca gösterilir."
        )
    return {
        "symbol": symbol,
        "market": market,
        "ticker": ticker,
        "orderbook": book,
        "market_metrics": market_metrics,
        "assessments": assessments,
        "bars_by_timeframe": bars_by_timeframe,
        "plan": plan,
        "phase": phase,
        "phase_timeframe": phase_timeframe,
        "readiness": readiness,
        "readiness_reason": readiness_reason,
        "ticker_age_seconds": ticker_age,
        "orderbook_age_seconds": book_age,
        "ticker_fresh": ticker_fresh,
        "orderbook_fresh": book_fresh,
        "market_rules_available": market_rules_available,
        "last_candle_start_ms": last_candle_start,
        "last_candle_time_ms": last_candle_end,
        "last_candle_age_seconds": candle_age,
        "draft_from_closed_candle": draft_from_closed_candle,
        "price_reference": plan.get("price_reference") if isinstance(plan, dict) else None,
        "generated_at_ms": now_ms,
        "source_note": "İşlem analizi BtcTurk PRO mum, ticker ve emir defteri verileriyle yapılır. Binance yalnızca karşılaştırma alanında gösterilir.",
    }


def estimate_orderbook_execution(book: dict[str, Any], notional_usdt: float,
                                 midpoint: float | None = None) -> dict[str, Any]:
    """Estimate market-buy and market-sell impact for a user-entered USDT notional."""
    if notional_usdt <= 0 or not math.isfinite(notional_usdt):
        raise ValueError("İşlem tutarı pozitif ve geçerli bir USDT değeri olmalı.")
    bids, asks = book.get("bids"), book.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        raise ValueError("Alış/satış emir defteri bulunamadı.")
    best_bid, best_ask = bids[0]["price"], asks[0]["price"]
    reference = midpoint or (best_bid + best_ask) / 2.0
    required_base = notional_usdt / reference

    def walk(levels: list[dict[str, float]], amount: float, *, quote_mode: bool) -> dict[str, Any]:
        remaining = amount
        quote_total = 0.0
        base_total = 0.0
        for level in levels:
            price, quantity = level["price"], level["quantity"]
            available_quote = price * quantity
            if quote_mode:
                take_quote = min(remaining, available_quote)
                take_base = take_quote / price
                remaining -= take_quote
            else:
                take_base = min(remaining, quantity)
                take_quote = take_base * price
                remaining -= take_base
            quote_total += take_quote
            base_total += take_base
            if remaining <= max(1e-10, amount * 1e-10):
                break
        filled = remaining <= max(1e-10, amount * 1e-10)
        return {
            "filled": filled,
            "base_quantity": base_total,
            "quote_value": quote_total,
            "average_price": quote_total / base_total if base_total > 0 else None,
            "remaining": max(0.0, remaining),
        }

    buy = walk(asks, notional_usdt, quote_mode=True)
    sell = walk(bids, required_base, quote_mode=False)
    buy_average = buy["average_price"]
    sell_average = sell["average_price"]
    buy_impact = ((buy_average / best_ask) - 1.0) * 100.0 if buy_average else None
    sell_impact = ((best_bid - sell_average) / best_bid) * 100.0 if sell_average else None
    buy_fee = buy["quote_value"] * COMMISSION_RATE if buy["filled"] else None
    sell_fee = sell["quote_value"] * COMMISSION_RATE if sell["filled"] else None
    return {
        "notional_usdt": notional_usdt,
        "required_base_quantity": required_base,
        "buy": {**buy, "slippage_pct_vs_best_ask": buy_impact, "commission_usdt_estimate": buy_fee},
        "sell": {**sell, "slippage_pct_vs_best_bid": sell_impact, "commission_usdt_estimate": sell_fee},
        "commission_rate_entry": COMMISSION_RATE,
        "commission_rate_exit": COMMISSION_RATE,
        "source_note": "Tahmin, girilen tutar için mevcut anlık emir defteri kademelerini tüketir; emir göndermez ve dolum garantisi vermez.",
    }


def format_exchange_price(value: Any, market: dict[str, Any] | None) -> str:
    number = _positive(value)
    if number is None:
        return "—"
    scale = market.get("denominator_scale") if isinstance(market, dict) else None
    try:
        decimals = max(0, min(16, int(scale)))
        return f"{number:,.{decimals}f}"
    except (TypeError, ValueError, OverflowError):
        return f"{number:,.8f}".rstrip("0").rstrip(".")
