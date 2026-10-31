"""Naratif Avcısı: ücretsiz/izinli kaynaklardan canlı tematik ilgi ve erken izleme üretir.

Bu süreç teknik puanı veya güçlü fırsat koşullarını değiştirmez. Tarihsel naratif
verisi olmadığı için yalnızca ilk gerçek gözlemden itibaren geçmiş kaydı oluşturur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
RUN_DIR = ROOT / "run"
SETTINGS_PATH = ROOT / "ayarlar.json"
COMMON_UNIVERSE_PATH = DATA_DIR / "single_engine_common_universe.json"
LOCAL_UNIVERSE_PATH = ROOT / "btcturk_usdt_spot.json"
CACHE_PATH = DATA_DIR / "naratif_kaynak_onbellek.json"
STATE_PATH = DATA_DIR / "naratif_state.json"
HISTORY_PATH = DATA_DIR / "naratif_gecmisi.sqlite3"
LOG_PATH = LOG_DIR / "naratif_avcisi.log"

AIXBT_TOPICS_URL = "https://api.aixbt.tech/v3/topics"
CMC_LISTINGS_URL = "https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/listings/latest"
DEX_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_COMMUNITY_URL = "https://api.dexscreener.com/community-takeovers/latest/v1"
COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
SANTIMENT_GRAPHQL_URL = "https://api.santiment.net/graphql"

DEFAULT_FEEDS = [
    {"id": "ethereum_foundation", "name": "Ethereum Foundation", "url": "https://blog.ethereum.org/en/feed.xml", "kind": "official"},
    {"id": "coindesk", "name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "kind": "media"},
    {"id": "cointelegraph", "name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "kind": "media"},
    {"id": "the_block", "name": "The Block", "url": "https://www.theblock.co/rss.xml", "kind": "media"},
]
SOURCE_INTERVALS = {
    "aixbt_topics": 300,
    "cmc_market_activity": 600,
    "dex_profiles": 600,
    "dex_community": 900,
    "coingecko_trending": 600,
    "santiment_project_catalog": 30 * 86400,
    "santiment_active_addresses": 6 * 3600,
    "santiment_dev_activity": 6 * 3600,
}
MAX_SOURCE_ITEMS = 500
MAX_RSS_ITEMS_PER_FEED = 100
MAX_SANTIMENT_SYMBOLS = 30
USER_AGENT = "FirsatKontrolPaneli-NarrativeResearch/1.0 (+local desktop research client)"

THEME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Yapay Zekâ (AI)", ("artificial intelligence", "ai agent", "ai agents", "agentic", "machine learning", "yapay zeka")),
    ("Gerçek Dünya Varlıkları (RWA)", ("real world asset", "real-world asset", "tokenized asset", "tokenisation", "tokenization", "rwa")),
    ("Merkeziyetsiz Fiziksel Altyapı (DePIN)", ("depin", "decentralized physical infrastructure", "decentralised physical infrastructure")),
    ("Merkeziyetsiz Finans (DeFi)", ("defi", "decentralized finance", "decentralised finance", "yield farming", "liquidity protocol")),
    ("Katman-2 (Layer 2)", ("layer 2", "layer-2", "rollup", "optimistic rollup", "zk rollup", "l2 network")),
    ("Yeniden Stake Etme (Restaking)", ("restaking", "re-staking", "liquid restaking")),
    ("Gerçek Getiri (Real Yield)", ("real yield", "fee-sharing", "revenue sharing")),
    ("Oyun ve Metaverse (Gaming)", ("gaming", "gamefi", "metaverse", "web3 game")),
    ("Meme Coin Ekosistemi", ("meme coin", "memecoin", "meme token")),
    ("Kurumsal Benimseme", ("institutional adoption", "institutional investment", "corporate treasury", "institutional")),
    ("Borsa Yatırım Fonu (ETF)", ("spot etf", "etf approval", "etf inflow", "exchange traded fund")),
    ("Gizlilik (Privacy)", ("privacy protocol", "zero knowledge", "zero-knowledge", "zk proof")),
    ("Stablecoin Ekosistemi", ("stablecoin", "payment settlement", "stable asset")),
    ("Gerçek Zamanlı Veri ve Oracle", ("oracle network", "real-time data", "oracle integration")),
    ("Merkeziyetsiz Sosyal (SocialFi)", ("socialfi", "decentralized social", "decentralised social")),
)

KNOWN_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("Bitcoin",),
    "ETH": ("Ethereum", "Ether"),
    "BNB": ("BNB Chain", "Binance Coin"),
    "SOL": ("Solana",),
    "XRP": ("Ripple",),
    "ADA": ("Cardano",),
    "DOGE": ("Dogecoin",),
    "AVAX": ("Avalanche",),
    "LINK": ("Chainlink",),
    "DOT": ("Polkadot",),
    "RENDER": ("Render Network",),
    "PYTH": ("Pyth Network",),
    "INJ": ("Injective",),
    "NEAR": ("NEAR Protocol",),
    "ARB": ("Arbitrum",),
    "OP": ("Optimism",),
    "SUI": ("Sui Network",),
    "APT": ("Aptos",),
    "AAVE": ("Aave Protocol",),
    "ONDO": ("Ondo Finance",),
    "HYPE": ("Hyperliquid",),
    "FET": ("Artificial Superintelligence Alliance", "Fetch.ai"),
    "AIXBT": ("aixbt",),
    "MORPHO": ("Morpho Protocol",),
    "EIGEN": ("EigenLayer",),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value
    except (OSError, ValueError, TypeError):
        return fallback


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("topics", "cryptoCurrencyList", "list", "items", "results", "tokens"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    for key in ("topics", "items", "results", "tokens"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def parse_aixbt_topics(payload: Any) -> list[dict[str, Any]]:
    """Normalize the keyless AIXBT v3 Topics response (currently a top-25 window)."""
    result = []
    for index, item in enumerate(_records(payload), start=1):
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        rank = item.get("rank", index)
        try:
            rank = max(1, int(rank))
        except (TypeError, ValueError):
            rank = index
        result.append({
            "id": str(item.get("id") or item.get("topicId") or name),
            "name": name[:180],
            "summary": str(item.get("summary") or item.get("description") or "")[:1200],
            "trend": item.get("trend"),
            "rank": rank,
            "post_count": _safe_int(item.get("postCount") or item.get("post_count")),
            "author_count": _safe_int(item.get("authorCount") or item.get("author_count")),
            "last_seen_at": item.get("lastSeenAt") or item.get("updatedAt"),
        })
    return result[:25]


def parse_cmc_market_listings(payload: Any) -> list[dict[str, Any]]:
    """Normalize CoinMarketCap keyless public listings as market activity, never as news."""
    result = []
    for item in _records(payload):
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not symbol or not name:
            continue
        quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
        usd = quote.get("USD") if isinstance(quote.get("USD"), dict) else quote
        result.append({
            "symbol": symbol,
            "name": name,
            "slug": str(item.get("slug") or ""),
            "rank": _safe_int(item.get("cmc_rank") or item.get("rank")),
            "price": _safe_float(usd.get("price")),
            "volume_24h": _safe_float(usd.get("volume_24h")),
            "volume_change_24h": _safe_float(usd.get("volume_change_24h")),
            "percent_change_24h": _safe_float(usd.get("percent_change_24h")),
            "market_cap": _safe_float(usd.get("market_cap")),
        })
    return result[:MAX_SOURCE_ITEMS]


def parse_dex_records(payload: Any) -> list[dict[str, Any]]:
    result = []
    for item in _records(payload):
        chain = str(item.get("chainId") or item.get("chain_id") or "")
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "")
        links = item.get("links") if isinstance(item.get("links"), list) else []
        url = next((str(link.get("url")) for link in links if isinstance(link, dict) and link.get("url")), "")
        result.append({
            "chain": chain,
            "symbol": symbol,
            "name": name,
            "description": description[:1000],
            "url": url,
            "source_kind": "dex_community_activity",
        })
    return result[:MAX_SOURCE_ITEMS]


def parse_rss_items(xml_text: str, *, source_id: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    """Parse both RSS 2.0 and Atom without adding an XML dependency."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"RSS/Atom XML okunamadı: {exc}") from exc
    result = []
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1].lower()
        if local not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        for child in list(node):
            child_name = child.tag.rsplit("}", 1)[-1].lower()
            if child_name == "link":
                link = child.attrib.get("href") or (child.text or "")
            else:
                link = ""
            text = (child.text or "").strip()
            if child_name in ("title", "description", "summary", "content", "published", "updated", "pubdate", "guid"):
                fields[child_name] = re.sub(r"<[^>]+>", " ", text)
            if link:
                fields["link"] = link.strip()
        title = fields.get("title", "").strip()
        if not title:
            continue
        result.append({
            "id": _event_id(title),
            "title": title[:300],
            "summary": (fields.get("summary") or fields.get("description") or fields.get("content") or "")[:1800],
            "url": fields.get("link", "")[:1000],
            "published_at": fields.get("published") or fields.get("updated") or fields.get("pubdate") or "",
            "source_id": source_id,
            "source_name": source_name,
            "source_kind": source_kind,
        })
        if len(result) >= MAX_RSS_ITEMS_PER_FEED:
            break
    return result



def parse_santiment_projects(payload: Any) -> list[dict[str, str]]:
    """Normalize the public Santiment project catalogue without guessing tickers."""
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("allProjects") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip().lower()
        ticker = str(item.get("ticker") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not slug or not ticker or not name or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
            continue
        if slug in seen:
            continue
        seen.add(slug)
        result.append({"slug": slug, "ticker": ticker, "name": name})
    return result[:1000]


def map_santiment_projects(
    projects: list[dict[str, Any]],
    symbols: list[str],
    aliases: dict[str, list[str]],
) -> dict[str, str]:
    """Map exact tickers; duplicate tickers require a unique exact-name match."""
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for project in projects:
        ticker = str(project.get("ticker") or "").strip().upper()
        if ticker and project.get("slug"):
            by_ticker.setdefault(ticker, []).append(project)
    mapped: dict[str, str] = {}
    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").strip().upper()
        candidates = by_ticker.get(symbol, [])
        if len(candidates) == 1:
            mapped[symbol] = str(candidates[0]["slug"])
            continue
        expected_names = {
            str(value).strip().casefold()
            for value in aliases.get(symbol, [])
            if str(value).strip()
        }
        expected_names.add(symbol.casefold())
        exact = [
            item for item in candidates
            if str(item.get("name") or "").strip().casefold() in expected_names
        ]
        if len(exact) == 1:
            mapped[symbol] = str(exact[0]["slug"])
    return mapped


def parse_santiment_timeseries(payload: Any) -> dict[str, list[dict[str, Any]]]:
    """Normalize timeseriesDataPerSlugJson responses to slug-indexed point lists."""
    data = payload.get("data") if isinstance(payload, dict) else None
    metric_data = data.get("getMetric") if isinstance(data, dict) else None
    raw = metric_data.get("timeseriesDataPerSlugJson") if isinstance(metric_data, dict) else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        raw = raw["data"]
    if not isinstance(raw, list):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for bucket in raw:
        if not isinstance(bucket, dict):
            continue
        bucket_datetime = str(bucket.get("datetime") or "")
        entries = bucket.get("data")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                slug = str(entry.get("slug") or "").strip().lower()
                value = _safe_float(entry.get("value"))
                if slug and value is not None:
                    result.setdefault(slug, []).append({
                        "datetime": str(entry.get("datetime") or bucket_datetime),
                        "value": value,
                        "computed_at": entry.get("computedAt") or entry.get("computed_at"),
                    })
        else:
            slug = str(bucket.get("slug") or "").strip().lower()
            value = _safe_float(bucket.get("value"))
            if slug and value is not None:
                result.setdefault(slug, []).append({
                    "datetime": bucket_datetime,
                    "value": value,
                    "computed_at": bucket.get("computedAt") or bucket.get("computed_at"),
                })
    for points in result.values():
        points.sort(key=lambda point: str(point.get("datetime") or ""))
    return result


def build_santiment_metric_query(metric: str, slugs: list[str]) -> str:
    """Build queries for the two documented Free Access metrics only."""
    safe_slugs = sorted({
        str(slug).strip().lower()
        for slug in slugs
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", str(slug).strip().lower())
    })
    if not safe_slugs:
        raise ValueError("Santiment sorgusu için geçerli proje eşlemesi yok.")
    selector = json.dumps(safe_slugs, ensure_ascii=True)
    if metric == "active_addresses_24h":
        return (
            'query { getMetric(metric: "active_addresses_24h") { '
            'timeseriesDataPerSlugJson(selector: {slugs: ' + selector +
            '}, from: "utc_now-2d", to: "utc_now", interval: "1h", '
            'includeComputedAt: true) } }'
        )
    if metric == "dev_activity":
        return (
            'query { getMetric(metric: "dev_activity", version: "modern:v1") { '
            'timeseriesDataPerSlugJson(selector: {slugs: ' + selector +
            '}, from: "utc_now-15d", to: "utc_now", interval: "1d", '
            'includeIncompleteData: false, includeComputedAt: true) } }'
        )
    raise ValueError(f"Santiment metriği ücretsiz entegrasyon kapsamında değil: {metric}")


def summarize_santiment_asset(
    slug: str,
    active_rows: dict[str, list[dict[str, Any]]],
    dev_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Create transparent comparisons; this data never enters the narrative score."""
    result: dict[str, Any] = {"asset_slug": slug}
    active = active_rows.get(slug, [])
    if active:
        latest = active[-1]
        result["active_addresses_24h"] = latest["value"]
        result["active_addresses_observed_at_utc"] = latest.get("datetime")
        try:
            latest_dt = datetime.fromisoformat(str(latest.get("datetime")).replace("Z", "+00:00"))
            target_dt = latest_dt - timedelta(hours=24)
            prior = min(
                active[:-1],
                key=lambda point: abs(
                    (datetime.fromisoformat(str(point.get("datetime")).replace("Z", "+00:00")) - target_dt).total_seconds()
                ),
            ) if len(active) > 1 else None
            if prior:
                prior_dt = datetime.fromisoformat(str(prior.get("datetime")).replace("Z", "+00:00"))
                if abs((prior_dt - target_dt).total_seconds()) <= 3 * 3600 and prior["value"] != 0:
                    result["active_addresses_change_24h_pct"] = round(
                        (latest["value"] / prior["value"] - 1.0) * 100.0, 2
                    )
        except (TypeError, ValueError, OverflowError):
            pass
    dev = dev_rows.get(slug, [])
    if dev:
        recent = dev[-7:]
        previous = dev[-14:-7]
        result["dev_activity_7d"] = round(sum(point["value"] for point in recent), 2)
        result["dev_activity_observed_at_utc"] = dev[-1].get("datetime")
        if len(recent) == 7 and len(previous) == 7:
            previous_total = sum(point["value"] for point in previous)
            if previous_total != 0:
                result["dev_activity_change_7d_pct"] = round(
                    (sum(point["value"] for point in recent) / previous_total - 1.0) * 100.0, 2
                )
    return result if len(result) > 1 else {}


def rank_santiment_candidate_symbols(events: list[dict[str, Any]], limit: int = 30) -> list[str]:
    """Prioritize coins actually mentioned in current discovery/news events."""
    scores: dict[str, float] = {}
    for event in events:
        rank = _safe_int(event.get("rank"))
        weight = max(1.0, 26.0 - rank) if rank is not None and rank > 0 else 1.0
        if event.get("source_kind") in ("official", "media"):
            weight += 2.0
        for match in event.get("symbols", []) if isinstance(event.get("symbols"), list) else []:
            if not isinstance(match, dict):
                continue
            symbol = str(match.get("symbol") or "").strip().upper()
            if symbol:
                confidence = 1.5 if match.get("confidence") == "YÜKSEK" else 1.0
                scores[symbol] = scores.get(symbol, 0.0) + weight * confidence
    return [
        symbol for symbol, _ in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:max(1, limit)]
    ]


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_id(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _narrative_slug(value: str) -> str:
    """Create stable ASCII IDs while preserving Turkish letters semantically."""
    folded = str(value or "").casefold().translate(str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    }))
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:80] or "genel"


def _load_common_symbols(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    """Prefer the last saved Binance/BtcTurk intersection, otherwise disclose the local-list fallback."""
    common_path = root / "data" / "single_engine_common_universe.json"
    payload = _read_json(common_path, {})
    pairs = payload.get("pairs") if isinstance(payload, dict) else None
    symbols = []
    if isinstance(pairs, list):
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            base = str(pair.get("base_asset") or "").strip().upper()
            quote = str(pair.get("quote_asset") or "").strip().upper()
            binance_symbol = str(pair.get("binance_symbol") or "").strip().upper()
            btcturk_symbol = str(pair.get("btcturk_symbol") or "").strip().upper()
            if base and quote == "USDT" and binance_symbol == f"{base}USDT" and btcturk_symbol == f"{base}USDT":
                symbols.append(base)
    symbols = sorted(set(symbols))
    if symbols:
        return symbols, {
            "mode": "KAYITLI ORTAK BINANCE–BTCTURK EVRENİ",
            "count": len(symbols),
            "generated_at_utc": payload.get("generated_at_utc"),
            "verified": True,
        }

    local = {}
    for local_path in (root / "data" / "btcturk_usdt_spot.json", root / "btcturk_usdt_spot.json"):
        candidate = _read_json(local_path, {})
        if isinstance(candidate, dict) and isinstance(candidate.get("symbols"), dict) and candidate["symbols"]:
            local = candidate
            break
    local_symbols = local.get("symbols") if isinstance(local, dict) else None
    fallback = []
    if isinstance(local_symbols, dict):
        for base, item in local_symbols.items():
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").upper()
            if str(item.get("quote") or "").upper() == "USDT" and symbol == f"{str(base).upper()}USDT":
                fallback.append(str(base).upper())
    fallback = sorted(set(fallback))
    return fallback, {
        "mode": "YEREL BTCTURK LİSTESİ — BINANCE KESİŞİMİ HENÜZ DOĞRULANMADI",
        "count": len(fallback),
        "generated_at_utc": local.get("generated_at_utc") if isinstance(local, dict) else None,
        "verified": False,
        "warning": "Naratif tarama kapsamı mevcut yerel USDT listesiyle sınırlı; ortak Binance evreni teyit edilmedi.",
    }


def _symbol_regex(symbol: str) -> re.Pattern[str] | None:
    base = str(symbol or "").upper()
    if len(base) < 2:
        return None
    # Two-character tickers are matched only when explicitly prefixed with "$";
    # this keeps common words such as "op" from becoming project mentions.
    prefix = r"\$" if len(base) == 2 else r"\$?"
    return re.compile(r"(?<![A-Za-z0-9])" + prefix + re.escape(base) + r"(?![A-Za-z0-9])")


def match_symbols(text: str, symbols: list[str], aliases: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Match full project names case-insensitively and ticker symbols conservatively."""
    raw = str(text or "")
    matched: dict[str, dict[str, Any]] = {}
    alias_map = aliases or {}
    for symbol in symbols:
        base = symbol.upper()
        for alias in alias_map.get(base, []):
            if len(alias.strip()) >= 4 and re.search(r"(?<!\w)" + re.escape(alias.strip()) + r"(?!\w)", raw, re.IGNORECASE):
                matched[base] = {"symbol": base, "confidence": "YÜKSEK", "match": alias}
                break
        if base in matched:
            continue
        pattern = _symbol_regex(base)
        if pattern and pattern.search(raw):
            # Short tickers are retained as uncertain, not promoted as an exact project match.
            confidence = "ORTA" if len(base) >= 4 or "$" + base in raw else "DÜŞÜK"
            matched[base] = {"symbol": base, "confidence": confidence, "match": "sembol"}
    return [matched[key] for key in sorted(matched)]


def infer_themes(text: str) -> list[str]:
    content = str(text or "").casefold()
    return [label for label, words in THEME_RULES if any(word in content for word in words)]


def _source_status(name: str, *, role: str, enabled: bool = True, status: str = "BEKLİYOR") -> dict[str, Any]:
    return {
        "id": name,
        "name": name.replace("_", " ").title(),
        "role": role,
        "enabled": enabled,
        "status": status,
        "last_attempt_utc": None,
        "last_success_utc": None,
        "item_count": 0,
        "age_seconds": None,
        "error": None,
    }


class NarrativeEngine:
    def __init__(
        self,
        root: Path = ROOT,
        *,
        stop_file: Path | None = None,
        session: Any = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.log_dir = self.root / "logs"
        self.settings_path = self.root / "ayarlar.json"
        self.cache_path = self.data_dir / "naratif_kaynak_onbellek.json"
        self.state_path = self.data_dir / "naratif_state.json"
        self.history_path = self.data_dir / "naratif_gecmisi.sqlite3"
        self.stop_file = Path(stop_file) if stop_file else self.root / "run" / "stop_narrative.flag"
        self.session = session or requests.Session()
        self.clock = clock
        self.settings = _read_json(self.settings_path, {})
        if not isinstance(self.settings, dict):
            self.settings = {}
        # Secrets are sourced only from environment variables, never from ayarlar.json.
        self.settings = {
            key: value for key, value in self.settings.items()
            if str(key).upper() not in {"AIXBT_API_KEY", "COINGECKO_DEMO_API_KEY", "SANTIMENT_API_KEY"}
        }
        self.cache = _read_json(self.cache_path, {})
        if not isinstance(self.cache, dict):
            self.cache = {}
        self.previous_state = _read_json(self.state_path, {})
        if not isinstance(self.previous_state, dict):
            self.previous_state = {}
        self.logger = self._logger()

    def _logger(self) -> logging.Logger:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"naratif_avcisi_{self.root.resolve()}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            handler = logging.FileHandler(self.log_dir / "naratif_avcisi.log", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            logger.addHandler(handler)
        return logger

    def _get_json(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
            params=params,
            timeout=10,
        )
        if response.status_code in (418, 429):
            raise RuntimeError(f"Kaynak hız sınırı yanıtı verdi: HTTP {response.status_code}; alternatif hostla aşılmadı.")
        response.raise_for_status()
        return response.json()

    def _post_graphql(self, query: str) -> Any:
        api_key = os.environ.get("SANTIMENT_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("SANTIMENT_API_KEY ortam değişkeni bulunamadı.")
        response = self.session.post(
            SANTIMENT_GRAPHQL_URL,
            data=query,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/graphql",
                "Authorization": f"Apikey {api_key}",
            },
            timeout=10,
        )
        if response.status_code in (418, 429):
            raise RuntimeError(f"Santiment API hız sınırı yanıtı verdi: HTTP {response.status_code}.")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("errors"):
            errors = payload["errors"]
            message = "; ".join(
                str(item.get("message") or item)[:220] if isinstance(item, dict) else str(item)[:220]
                for item in errors[:3]
            ) if isinstance(errors, list) else str(errors)[:500]
            raise RuntimeError(f"Santiment GraphQL hatası: {message}")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise RuntimeError("Santiment API beklenen GraphQL veri yapısını döndürmedi.")
        return payload

    def _get_text(self, url: str) -> str:
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
            timeout=10,
        )
        if response.status_code in (418, 429):
            raise RuntimeError(f"RSS kaynağı hız sınırı yanıtı verdi: HTTP {response.status_code}.")
        response.raise_for_status()
        return response.text

    def _due(self, key: str, interval: int) -> bool:
        entry = self.cache.get(key) if isinstance(self.cache.get(key), dict) else {}
        last = _safe_float(entry.get("last_attempt_epoch")) or 0.0
        return self.clock() - last >= interval

    def _cached_data(self, key: str) -> Any:
        entry = self.cache.get(key) if isinstance(self.cache.get(key), dict) else {}
        return entry.get("data")

    def _fetch_source(
        self,
        key: str,
        interval: int,
        fetcher: Callable[[], Any],
        status: dict[str, Any],
        *,
        count_fn: Callable[[Any], int] | None = None,
    ) -> Any:
        entry = self.cache.get(key) if isinstance(self.cache.get(key), dict) else {}
        data = entry.get("data")
        last_success = entry.get("last_success_epoch")
        last_attempt = entry.get("last_attempt_epoch")
        last_error = entry.get("last_error")
        if self._due(key, interval):
            if self.stop_file.exists():
                status["status"] = "DURDURMA İSTENDİ"
                status["item_count"] = len(data) if isinstance(data, list) else 0
                return data
            attempted = self.clock()
            last_attempt = attempted
            status["last_attempt_utc"] = datetime.fromtimestamp(attempted, timezone.utc).isoformat(timespec="seconds")
            self.cache[key] = {**entry, "last_attempt_epoch": attempted}
            try:
                fresh = fetcher()
                data = fresh
                success = self.clock()
                self.cache[key] = {
                    "data": fresh,
                    "last_attempt_epoch": attempted,
                    "last_success_epoch": success,
                    "last_error": None,
                }
                last_success = success
                last_error = None
                status["status"] = "BAĞLI"
                status["last_success_utc"] = datetime.fromtimestamp(success, timezone.utc).isoformat(timespec="seconds")
                self.logger.info("%s kaynağı yenilendi.", key)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                self.cache[key] = {**entry, "last_attempt_epoch": attempted, "last_error": last_error}
                status["status"] = "HATA — ÖNCEKİ VERİ VAR" if data is not None else "ERİŞİLEMEDİ"
                status["error"] = last_error
                self.logger.warning("%s kaynağı başarısız: %s", key, last_error)
        else:
            if last_error:
                status["status"] = "HATA — ÖNCEKİ VERİ VAR" if data is not None else "ERİŞİLEMEDİ"
                status["error"] = str(last_error)
            else:
                status["status"] = "ÖNBELLEK"
        if last_success:
            age = max(0.0, self.clock() - float(last_success))
            status["age_seconds"] = round(age, 1)
            status["last_success_utc"] = datetime.fromtimestamp(float(last_success), timezone.utc).isoformat(timespec="seconds")
            if age > max(interval * 3, 3600) and data is not None:
                status["status"] = "ESKİ VERİ"
        if count_fn:
            try:
                status["item_count"] = count_fn(data)
            except Exception:
                status["item_count"] = 0
        status["last_attempt_utc"] = (
            datetime.fromtimestamp(float(last_attempt), timezone.utc).isoformat(timespec="seconds")
            if last_attempt else status["last_attempt_utc"]
        )
        return data

    def _feed_list(self) -> list[dict[str, str]]:
        custom = self.settings.get("narrative_rss_feeds")
        feeds = custom if isinstance(custom, list) and custom else DEFAULT_FEEDS
        result = []
        for index, item in enumerate(feeds):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            name = str(item.get("name") or f"RSS {index + 1}").strip()
            feed_id = str(item.get("id") or f"rss_{index + 1}").strip()
            kind = str(item.get("kind") or "media").strip().lower()
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                continue
            result.append({"id": feed_id, "name": name, "url": url, "kind": kind})
        return result[:20]

    def _collect_sources(self) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        statuses: dict[str, Any] = {}
        topics = self._fetch_source(
            "aixbt_topics", SOURCE_INTERVALS["aixbt_topics"],
            lambda: parse_aixbt_topics(self._get_json(AIXBT_TOPICS_URL)),
            statuses.setdefault("aixbt_topics", _source_status("aixbt_topics", role="Ücretsiz konu/naratif keşfi; AIXBT'nin mevcut ilk 25 konusu.")),
            count_fn=lambda value: len(value or []),
        )
        cmc_status = _source_status("cmc_market_activity", role="Ücretsiz anahtarsız listeleme; yalnızca piyasa aktivitesi, haber değildir.")
        cmc = self._fetch_source(
            "cmc_market_activity", SOURCE_INTERVALS["cmc_market_activity"],
            lambda: parse_cmc_market_listings(self._get_json(
                CMC_LISTINGS_URL, params={"start": 1, "limit": 100, "convert": "USD"}
            )),
            cmc_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["cmc_market_activity"] = cmc_status

        dex_profiles_status = _source_status("dex_profiles", role="DEX token/proje profil görünürlüğü; haber doğrulaması değildir.")
        dex_profiles = self._fetch_source(
            "dex_profiles", SOURCE_INTERVALS["dex_profiles"],
            lambda: parse_dex_records(self._get_json(DEX_PROFILES_URL)),
            dex_profiles_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["dex_profiles"] = dex_profiles_status

        dex_community_status = _source_status("dex_community", role="Topluluk/DEX profil hareketi; bağımsız haber teyidi değildir.")
        dex_community = self._fetch_source(
            "dex_community", SOURCE_INTERVALS["dex_community"],
            lambda: parse_dex_records(self._get_json(DEX_COMMUNITY_URL)),
            dex_community_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["dex_community"] = dex_community_status

        cg_key = os.environ.get("COINGECKO_DEMO_API_KEY", "").strip()
        cg_status = _source_status(
            "coingecko_trending",
            role="Demo API anahtarı varsa trend verisi; haber kaynağı değildir.",
            enabled=bool(cg_key),
            status="BEKLİYOR" if cg_key else "API ANAHTARI YOK — DEVRE DIŞI",
        )
        if cg_key:
            cg = self._fetch_source(
                "coingecko_trending", SOURCE_INTERVALS["coingecko_trending"],
                lambda: self._get_json(COINGECKO_TRENDING_URL, headers={"x-cg-demo-api-key": cg_key}),
                cg_status,
                count_fn=lambda value: len(value.get("coins", [])) if isinstance(value, dict) else len(value or []),
            )
        else:
            cg = self._cached_data("coingecko_trending")
            cg_status["item_count"] = 0
        statuses["coingecko_trending"] = cg_status

        rss_events: list[dict[str, Any]] = []
        for feed in self._feed_list():
            key = f"rss_{feed['id']}"
            interval = int(self.settings.get("narrative_rss_interval_seconds", 900) or 900)
            interval = max(300, min(interval, 86400))
            status = _source_status(key, role=f"{feed['kind']} RSS/Atom yayın akışı.")
            data = self._fetch_source(
                key, interval,
                lambda f=feed: parse_rss_items(
                    self._get_text(f["url"]),
                    source_id=f["id"], source_name=f["name"], source_kind=f["kind"],
                ),
                status,
                count_fn=lambda value: len(value or []),
            )
            statuses[key] = status
            if isinstance(data, list):
                rss_events.extend(item for item in data if isinstance(item, dict))

        # The free AIXBT topic list is keyless; richer topic->project mappings are not
        # silently assumed to be available. Keep the optional entitlement visibly separate.
        aixbt_key = os.environ.get("AIXBT_API_KEY", "").strip()
        statuses["aixbt_project_mapping"] = _source_status(
            "aixbt_project_mapping",
            role="AIXBT konu→proje eşlemesi; ek API anahtarı/hesap yetkisi gerektirebilir, varsayılan olarak kullanılmaz.",
            enabled=False,
            status="EK API ERİŞİMİ GEREKİR — KULLANILMIYOR" if not aixbt_key else "YETKİ DOĞRULANMADI — KULLANILMIYOR",
        )
        statuses["x_api"] = _source_status(
            "x_api",
            role="X paylaşım akışı; bu sürümde API bağlantısı veya veri toplama yok.",
            enabled=False,
            status="BAĞLI DEĞİL — ENTEGRASYON YOK",
        )
        statuses["reddit"] = _source_status(
            "reddit",
            role="Reddit gönderi/topluluk akışı; bu sürümde API bağlantısı veya veri toplama yok.",
            enabled=False,
            status="BAĞLI DEĞİL — ENTEGRASYON YOK",
        )
        return statuses, rss_events, {
            "topics": topics or [],
            "cmc": cmc or [],
            "dex_profiles": dex_profiles or [],
            "dex_community": dex_community or [],
            "coingecko": cg or {},
        }

    def _collect_santiment(
        self,
        statuses: dict[str, Any],
        events: list[dict[str, Any]],
        aliases: dict[str, list[str]],
    ) -> dict[str, dict[str, Any]]:
        api_key = os.environ.get("SANTIMENT_API_KEY", "").strip()
        if not api_key:
            statuses["santiment"] = _source_status(
                "santiment",
                role="Santiment Individuals Free plan; API anahtarı SANTIMENT_API_KEY ortam değişkeninden okunur.",
                enabled=False,
                status="API ANAHTARI YOK — DEVRE DIŞI",
            )
            return {}
        catalog_status = _source_status(
            "santiment_project_catalog",
            role="Coin sembolünü Santiment proje koduyla yalnızca birebir eşleştirir; 30 günde bir yenilenir.",
        )
        projects = self._fetch_source(
            "santiment_project_catalog",
            SOURCE_INTERVALS["santiment_project_catalog"],
            lambda: parse_santiment_projects(self._post_graphql(
                "query { allProjects(page: 1, pageSize: 500) { slug name ticker } }"
            )),
            catalog_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["santiment_project_catalog"] = catalog_status
        candidate_symbols = rank_santiment_candidate_symbols(events, MAX_SANTIMENT_SYMBOLS)
        slug_map = map_santiment_projects(projects or [], candidate_symbols, aliases)
        slugs = list(dict.fromkeys(slug_map.values()))

        def collect_metric(metric: str, key: str, role: str) -> dict[str, list[dict[str, Any]]]:
            status = _source_status(key, role=role)
            if not slugs:
                cached = self._cached_data(key)
                status["status"] = "EŞLEŞEN VARLIK YOK — SORGULANMADI"
                status["item_count"] = len(cached) if isinstance(cached, dict) else 0
                statuses[key] = status
                return cached if isinstance(cached, dict) else {}
            data = self._fetch_source(
                key,
                SOURCE_INTERVALS[key],
                lambda: parse_santiment_timeseries(self._post_graphql(
                    build_santiment_metric_query(metric, slugs)
                )),
                status,
                count_fn=lambda value: len(value or {}),
            )
            statuses[key] = status
            return data if isinstance(data, dict) else {}

        active_rows = collect_metric(
            "active_addresses_24h",
            "santiment_active_addresses",
            "Ücretsiz active_addresses_24h ölçümü; en fazla 30 coin, altı saatte bir.",
        )
        dev_rows = collect_metric(
            "dev_activity",
            "santiment_dev_activity",
            "Ücretsiz dev_activity modern:v1 ölçümü; en fazla 30 coin, altı saatte bir.",
        )
        result: dict[str, dict[str, Any]] = {}
        for symbol, slug in slug_map.items():
            summary = summarize_santiment_asset(slug, active_rows, dev_rows)
            if summary:
                result[symbol] = summary
        metric_statuses = [
            statuses.get("santiment_active_addresses", {}),
            statuses.get("santiment_dev_activity", {}),
        ]
        successful = [
            row for row in metric_statuses
            if isinstance(row, dict) and row.get("status") in (
                "BAĞLI", "ÖNBELLEK", "HATA — ÖNCEKİ VERİ VAR", "ESKİ VERİ"
            )
        ]
        parent = _source_status(
            "santiment",
            role="Individuals Free plan: yalnızca ücretsiz active_addresses_24h ve dev_activity modern:v1 ölçümleri. Kısıtlı metrikler çağrılmaz.",
            enabled=True,
            status="BAĞLI" if any(row.get("status") == "BAĞLI" for row in successful) else (
                "ÖNBELLEK" if successful else "ERİŞİLEMEDİ"
            ),
        )
        parent["item_count"] = len(result)
        errors = [
            str(row.get("error")) for row in metric_statuses
            if isinstance(row, dict) and row.get("error")
        ]
        parent["error"] = "; ".join(errors)[:500] if errors else None
        successful_times = [
            str(row.get("last_success_utc"))
            for row in [catalog_status, *metric_statuses]
            if isinstance(row, dict) and row.get("last_success_utc")
        ]
        parent["last_success_utc"] = max(successful_times) if successful_times else None
        statuses["santiment"] = parent
        return result

    def _aliases(self, market_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
        aliases = {symbol: list(values) for symbol, values in KNOWN_ALIASES.items()}
        for item in market_rows:
            symbol = str(item.get("symbol") or "").upper()
            name = str(item.get("name") or "").strip()
            if symbol and name and name.casefold() != symbol.casefold():
                aliases.setdefault(symbol, []).append(name)
        return aliases

    def _normalise_events(
        self,
        topics: list[dict[str, Any]],
        rss_events: list[dict[str, Any]],
        symbols: list[str],
        aliases: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        events: dict[str, dict[str, Any]] = {}
        for topic in topics:
            title = str(topic.get("name") or "").strip()
            summary = str(topic.get("summary") or "")
            text = f"{title} {summary}"
            key = "aixbt:" + str(topic.get("id") or _event_id(title))
            matches = match_symbols(text, symbols, aliases)
            events[key] = {
                "event_id": key,
                "title": title,
                "summary": summary,
                "url": "",
                "source_id": "aixbt_topics",
                "source_name": "AIXBT Topics",
                "source_kind": "topic_discovery",
                "published_at": str(topic.get("last_seen_at") or ""),
                "symbols": matches,
                "themes": infer_themes(text) or [title[:90]],
                "rank": topic.get("rank"),
                "trend": topic.get("trend"),
                "post_count": topic.get("post_count"),
                "author_count": topic.get("author_count"),
                "evidence_class": "NARATİF KEŞFİ",
            }

        for raw in rss_events:
            title = str(raw.get("title") or "").strip()
            summary = str(raw.get("summary") or "")
            text = f"{title} {summary}"
            fingerprint = _event_id(title)
            key = "news:" + fingerprint
            matches = match_symbols(text, symbols, aliases)
            if key in events:
                # Exact/syndicated headline is one event. Republishing never multiplies
                # independent confirmations or the narrative source-diversity score.
                publishers = events[key].setdefault("republishers", [])
                source_name = str(raw.get("source_name") or raw.get("source_id") or "")
                if source_name and source_name not in publishers:
                    publishers.append(source_name)
                continue
            themes = infer_themes(text)
            if not themes:
                themes = [f"{match['symbol']} Proje Gelişmeleri" for match in matches[:3]]
            events[key] = {
                "event_id": key,
                "title": title,
                "summary": summary,
                "url": str(raw.get("url") or ""),
                "source_id": str(raw.get("source_id") or "rss"),
                "source_name": str(raw.get("source_name") or "RSS"),
                "source_kind": str(raw.get("source_kind") or "media"),
                "published_at": str(raw.get("published_at") or ""),
                "symbols": matches,
                "themes": themes or ["Piyasa Gelişmeleri"],
                "evidence_class": "HABER/KATALİZÖR",
            }
        return list(events.values())

    def _market_map(
        self,
        market_rows: list[dict[str, Any]],
        dex_rows: list[dict[str, Any]],
        coingecko: Any,
        symbols: list[str],
        aliases: dict[str, list[str]],
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        allowed = set(symbols)
        for row in market_rows:
            base = str(row.get("symbol") or "").upper()
            if base in allowed:
                result[base] = {
                    "symbol": base, "name": row.get("name"),
                    "percent_change_24h": row.get("percent_change_24h"),
                    "volume_24h": row.get("volume_24h"),
                    "volume_change_24h": row.get("volume_change_24h"),
                    "cmc_rank": row.get("rank"),
                    "market_activity_source": "CoinMarketCap anahtarsız listeleme",
                }
        for row in dex_rows:
            text = " ".join(str(row.get(key) or "") for key in ("symbol", "name", "description"))
            for match in match_symbols(text, symbols, aliases):
                item = result.setdefault(match["symbol"], {"symbol": match["symbol"]})
                item["dex_activity"] = True
                item["dex_chain"] = row.get("chain") or item.get("dex_chain")
        if isinstance(coingecko, dict):
            for item in coingecko.get("coins", []) if isinstance(coingecko.get("coins"), list) else []:
                coin = item.get("item") if isinstance(item, dict) else None
                if not isinstance(coin, dict):
                    continue
                ticker = str(coin.get("symbol") or "").upper()
                if ticker in allowed:
                    result.setdefault(ticker, {"symbol": ticker})["coingecko_trending"] = True
        return result

    def _build_narratives(
        self,
        events: list[dict[str, Any]],
        market_map: dict[str, dict[str, Any]],
        previous_rows: list[dict[str, Any]],
        source_statuses: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Score themes from available evidence; missing evidence remains visible."""
        source_statuses = source_statuses if isinstance(source_statuses, dict) else {}
        previous = {
            str(item.get("narrative_id")): item
            for item in previous_rows if isinstance(item, dict) and item.get("narrative_id")
        }
        grouped: dict[str, dict[str, Any]] = {}
        for event in events:
            for theme in event.get("themes", []) or ["Piyasa Gelişmeleri"]:
                key = _narrative_slug(str(theme))
                group = grouped.setdefault(key, {
                    "narrative_id": key, "name": str(theme), "events": [],
                    "coins": {}, "news_sources": set(), "discovery_sources": set(),
                    "aixbt_rank": None,
                })
                group["events"].append(event)
                source_id = str(event.get("source_id") or "")
                if event.get("source_kind") in ("official", "media"):
                    group["news_sources"].add(source_id)
                elif event.get("source_kind") == "topic_discovery":
                    # AIXBT is narrative discovery intelligence, not an editorial publisher.
                    group["discovery_sources"].add(source_id)
                    rank = _safe_int(event.get("rank"))
                    if rank and (group["aixbt_rank"] is None or rank < group["aixbt_rank"]):
                        group["aixbt_rank"] = rank
                for match in event.get("symbols", []):
                    base = str(match.get("symbol") or "").upper()
                    if base:
                        group["coins"][base] = max(
                            group["coins"].get(base, 0),
                            2 if match.get("confidence") == "YÜKSEK" else 1,
                        )

        narratives: list[dict[str, Any]] = []
        early_watch: dict[str, dict[str, Any]] = {}
        for key, group in grouped.items():
            group_events = group["events"]
            symbols = sorted(group["coins"])
            sources = sorted(group["news_sources"] - {""})
            discovery_sources = sorted(group["discovery_sources"] - {""})
            topic_rank = group["aixbt_rank"]
            previous_row = previous.get(key, {})
            old_score = _safe_float(previous_row.get("narrative_score"))
            previous_components = previous_row.get("score_components")
            previous_static_components = (
                [
                    _safe_float(value)
                    for name, value in previous_components.items()
                    if name != "interest_velocity" and _safe_float(value) is not None
                ]
                if isinstance(previous_components, dict) else []
            )
            old_base_score = (
                round(sum(previous_static_components) / len(previous_static_components), 1)
                if previous_static_components else old_score
            )
            components: dict[str, float] = {}

            if topic_rank is not None:
                components["aixbt_topic_rank"] = round(max(0.0, 100.0 - (topic_rank - 1) * 4.0), 1)
            if group_events:
                components["distinct_evidence_events"] = round(
                    min(100.0, len({e["event_id"] for e in group_events}) * 25.0), 1
                )
            if sources:
                components["independent_source_families"] = round(min(100.0, len(sources) * 30.0), 1)
            if symbols:
                components["project_spread"] = round(min(100.0, len(symbols) * 20.0), 1)

            source_ids = set(sources) | set(discovery_sources)
            source_ages = []
            for source_id in source_ids:
                source_key = source_id if source_id in source_statuses else f"rss_{source_id}"
                source_row = source_statuses.get(source_key)
                age_value = _safe_float(source_row.get("age_seconds")) if isinstance(source_row, dict) else None
                if age_value is not None and age_value >= 0:
                    source_ages.append(age_value)
            freshest_source_age = min(source_ages) if source_ages else None
            if freshest_source_age is not None:
                if freshest_source_age <= 300:
                    freshness_score = 100.0
                elif freshest_source_age <= 900:
                    freshness_score = 80.0
                elif freshest_source_age <= 1800:
                    freshness_score = 60.0
                elif freshest_source_age <= 3600:
                    freshness_score = 40.0
                else:
                    freshness_score = 10.0
                components["data_freshness"] = freshness_score

            market_changes = [
                _safe_float(market_map.get(symbol, {}).get("percent_change_24h"))
                for symbol in symbols
            ]
            market_changes = [value for value in market_changes if value is not None]
            average_change = sum(market_changes) / len(market_changes) if market_changes else None
            if average_change is not None:
                components["market_price_reaction_24h"] = round(
                    max(0.0, min(100.0, 50.0 + average_change)), 1
                )

            volume_changes = [
                _safe_float(market_map.get(symbol, {}).get("volume_change_24h"))
                for symbol in symbols
            ]
            volume_changes = [value for value in volume_changes if value is not None]
            average_volume_change = (
                sum(volume_changes) / len(volume_changes) if volume_changes else None
            )
            if average_volume_change is not None:
                components["market_volume_reaction_24h"] = round(
                    max(0.0, min(100.0, 50.0 + average_volume_change * 0.5)), 1
                )

            # Measure acceleration from the preceding static evidence score.
            # Velocity is a bounded adjustment around the neutral 50 point, not an
            # averaged component that would lower a stable theme by itself.
            static_score = round(sum(components.values()) / len(components), 1) if components else None
            preliminary_change = (
                static_score - old_base_score
                if static_score is not None and old_base_score is not None else None
            )
            score = static_score
            if preliminary_change is not None:
                velocity_score = round(
                    max(0.0, min(100.0, 50.0 + preliminary_change * 2.0)), 1
                )
                components["interest_velocity"] = velocity_score
                velocity_adjustment = max(-10.0, min(10.0, (velocity_score - 50.0) * 0.2))
                score = round(max(0.0, min(100.0, static_score + velocity_adjustment)), 1)
            change = round(preliminary_change, 1) if preliminary_change is not None else None
            direction = (
                "İLK GÖZLEM" if change is None else
                "YÜKSELİYOR" if change >= 5 else
                "DÜŞÜYOR" if change <= -5 else "YATAY"
            )
            confidence = (
                "YÜKSEK" if len(sources) >= 3 and len(group_events) >= 3 else
                "ORTA" if len(sources) >= 2 else "DÜŞÜK"
            )

            if not components or not group_events:
                phase = "BELİRSİZ"
            elif change is not None and change <= -10:
                phase = "ZAYIFLAMA"
            elif score is not None and score >= 85 and average_change is not None and average_change >= 20:
                phase = "AŞIRI ISINMA"
            elif score is not None and score >= 65 and len(sources) >= 2:
                phase = "GÜÇLENME"
            elif len(symbols) >= 2 or len(sources) >= 2:
                phase = "YAYILMA"
            else:
                phase = "BAŞLANGIÇ"

            event_rows = sorted(
                group_events,
                key=lambda e: str(e.get("published_at") or ""),
                reverse=True,
            )
            coverage_missing = [
                name for name, available in (
                    ("önceki gözlem / ilgi hızı", old_score is not None),
                    ("AIXBT konu sırası", topic_rank is not None),
                    ("bağımsız haber kaynağı", bool(sources)),
                    ("ortak evrende eşleşen coin", bool(symbols)),
                    ("kaynak veri güncelliği", freshest_source_age is not None),
                    ("24 saatlik fiyat tepkisi", average_change is not None),
                    ("24 saatlik hacim tepkisi", average_volume_change is not None),
                ) if not available
            ]
            narrative = {
                "narrative_id": key,
                "name": group["name"],
                "phase": phase,
                "narrative_score": score,
                "score_components": components,
                "interest_direction": direction,
                "interest_change": change,
                "confidence": confidence,
                "coverage": {
                    "event_count": len({e["event_id"] for e in group_events}),
                    "independent_news_sources": len(sources),
                    "discovery_sources": len(discovery_sources),
                    "related_coin_count": len(symbols),
                    "available_components": len(components),
                    "missing": coverage_missing,
                },
                "related_coins": symbols,
                "sources": sources,
                "discovery_sources": discovery_sources,
                "data_freshness_seconds": round(freshest_source_age, 1) if freshest_source_age is not None else None,
                "market_reaction_24h_pct_avg": round(average_change, 2) if average_change is not None else None,
                "average_volume_change_24h": round(average_volume_change, 2) if average_volume_change is not None else None,
                "first_observed_at_utc": None,
                "last_observed_at_utc": utc_now(),
                "latest_events": [
                    {
                        "title": e.get("title"),
                        "source": e.get("source_name"),
                        "source_kind": e.get("source_kind"),
                        "published_at": e.get("published_at"),
                        "url": e.get("url"),
                        "republishers": e.get("republishers", []),
                    }
                    for e in event_rows[:12]
                ],
            }
            narratives.append(narrative)

            for symbol in symbols:
                watch = early_watch.setdefault(symbol, {
                    "symbol": symbol,
                    "narrative_score": score,
                    "phase": phase,
                    "interest_direction": direction,
                    "data_freshness_seconds": narrative["data_freshness_seconds"],
                    "narratives": [],
                    "sources": set(),
                    "discovery_sources": set(),
                    "confidence": confidence,
                    "market_activity": market_map.get(symbol, {}),
                    "reason": "Teknik sinyalden bağımsız naratif erken izleme; teknik puan ve güçlü alarm değişmez.",
                })
                current_score = _safe_float(watch.get("narrative_score"))
                if score is not None and (current_score is None or score > current_score):
                    watch["narrative_score"] = score
                    watch["phase"] = phase
                    watch["interest_direction"] = direction
                    watch["data_freshness_seconds"] = narrative["data_freshness_seconds"]
                watch["narratives"].append(group["name"])
                watch["sources"].update(sources)
                watch["discovery_sources"].update(discovery_sources)
                if confidence == "YÜKSEK" or (confidence == "ORTA" and watch["confidence"] == "DÜŞÜK"):
                    watch["confidence"] = confidence

        for watch in early_watch.values():
            watch["sources"] = sorted(watch["sources"])
            watch["discovery_sources"] = sorted(watch["discovery_sources"])
            watch["narratives"] = sorted(set(watch["narratives"]))

        # Rising, evidence-backed and non-overheated themes lead the list;
        # incomplete themes remain visible below them.
        narratives.sort(key=lambda item: (
            item.get("phase") != "AŞIRI ISINMA",
            item.get("interest_direction") == "YÜKSELİYOR",
            item.get("confidence") == "YÜKSEK",
            item.get("coverage", {}).get("independent_news_sources", 0),
            item.get("narrative_score") is not None,
            item.get("narrative_score") if item.get("narrative_score") is not None else -1,
        ), reverse=True)
        watch_rows = sorted(
            early_watch.values(),
            key=lambda item: (
                item.get("phase") != "AŞIRI ISINMA",
                item.get("interest_direction") == "YÜKSELİYOR",
                item.get("narrative_score") is not None,
                item.get("narrative_score") if item.get("narrative_score") is not None else -1,
            ),
            reverse=True,
        )
        return narratives, watch_rows

    def _save_history(self, narratives: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.history_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS narrative_snapshots (
                    observed_at_utc TEXT NOT NULL,
                    narrative_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phase TEXT,
                    score REAL,
                    interest_direction TEXT,
                    confidence TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (observed_at_utc, narrative_id)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS narrative_events (
                    event_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_name TEXT,
                    source_kind TEXT,
                    published_at TEXT,
                    first_observed_at_utc TEXT NOT NULL,
                    url TEXT,
                    symbols_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS narrative_alerts (
                    alert_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL,
                    narrative_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            """)
            now = utc_now()
            for item in events:
                connection.execute(
                    """INSERT OR IGNORE INTO narrative_events
                    (event_id,title,source_name,source_kind,published_at,first_observed_at_utc,url,symbols_json,payload_json)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        item["event_id"], item.get("title", ""), item.get("source_name", ""),
                        item.get("source_kind", ""), item.get("published_at", ""), now,
                        item.get("url", ""), json.dumps(item.get("symbols", []), ensure_ascii=False),
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
            for item in narratives:
                previous = connection.execute(
                    """SELECT observed_at_utc, phase, score, interest_direction, confidence
                    FROM narrative_snapshots WHERE narrative_id=?
                    ORDER BY observed_at_utc DESC LIMIT 1""",
                    (item["narrative_id"],),
                ).fetchone()
                write_snapshot = previous is None
                if previous is not None:
                    try:
                        previous_epoch = datetime.fromisoformat(
                            str(previous[0]).replace("Z", "+00:00")
                        ).timestamp()
                    except (TypeError, ValueError, OverflowError):
                        previous_epoch = 0.0
                    score_changed = (
                        previous[2] is None and item.get("narrative_score") is not None
                    ) or (
                        previous[2] is not None and item.get("narrative_score") is None
                    ) or (
                        previous[2] is not None and item.get("narrative_score") is not None
                        and abs(float(previous[2]) - float(item["narrative_score"])) >= 1.0
                    )
                    write_snapshot = bool(
                        previous[1] != item["phase"]
                        or score_changed
                        or previous[3] != item["interest_direction"]
                        or previous[4] != item["confidence"]
                        or time.time() - previous_epoch >= 300
                    )
                if write_snapshot:
                    connection.execute(
                        """INSERT OR IGNORE INTO narrative_snapshots
                        (observed_at_utc,narrative_id,name,phase,score,interest_direction,confidence,payload_json)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            now, item["narrative_id"], item["name"], item["phase"],
                            item.get("narrative_score"), item["interest_direction"], item["confidence"],
                            json.dumps(item, ensure_ascii=False),
                        ),
                    )
                row = connection.execute(
                    "SELECT MIN(observed_at_utc) FROM narrative_snapshots WHERE narrative_id=?",
                    (item["narrative_id"],),
                ).fetchone()
                item["first_observed_at_utc"] = row[0] if row and row[0] else now

    def _alerts(self, narratives: list[dict[str, Any]]) -> list[dict[str, Any]]:
        old = {
            str(item.get("narrative_id")): str(item.get("phase") or "")
            for item in self.previous_state.get("narratives", [])
            if isinstance(item, dict)
        }
        prior_ids = set(old)
        alerts = list(self.previous_state.get("alerts", [])) if isinstance(self.previous_state.get("alerts"), list) else []
        seen = {str(item.get("alert_id")) for item in alerts if isinstance(item, dict)}
        for item in narratives:
            key = str(item["narrative_id"])
            previous_phase = old.get(key)
            alert_type = None
            if previous_phase is None:
                alert_type = "YENİ NARATİF"
            elif previous_phase not in ("YAYILMA", "GÜÇLENME") and item["phase"] in ("YAYILMA", "GÜÇLENME"):
                alert_type = item["phase"] + " AŞAMASINA GEÇİŞ"
            if alert_type:
                alert_id = hashlib.sha256(f"{key}|{alert_type}|{item.get('last_observed_at_utc')}".encode()).hexdigest()[:24]
                if alert_id not in seen:
                    alerts.append({
                        "alert_id": alert_id,
                        "created_at_utc": utc_now(),
                        "narrative_id": key,
                        "narrative": item["name"],
                        "phase": item["phase"],
                        "alert_type": alert_type,
                        "message": (
                            f"{item['name']} naratifi {alert_type.lower()} olarak kaydedildi. "
                            f"Naratif puanı: {item.get('narrative_score')}; güven: {item.get('confidence')}. "
                            "Bu bildirim teknik alım sinyali veya güçlü fırsat alarmı değildir."
                        ),
                    })
                    seen.add(alert_id)
        # Alerts are durable notifications, but are not orders or technical strong signals.
        with sqlite3.connect(self.history_path) as connection:
            for item in alerts[-50:]:
                if not isinstance(item, dict):
                    continue
                connection.execute(
                    """INSERT OR IGNORE INTO narrative_alerts
                    (alert_id,created_at_utc,narrative_id,alert_type,message)
                    VALUES (?,?,?,?,?)""",
                    (
                        item.get("alert_id"), item.get("created_at_utc", utc_now()),
                        item.get("narrative_id", ""), item.get("alert_type", ""),
                        item.get("message", ""),
                    ),
                )
        return alerts[-50:]

    def run_cycle(self) -> dict[str, Any]:
        statuses, rss_events, source_data = self._collect_sources()
        symbols, universe = _load_common_symbols(self.root)
        aliases = self._aliases(source_data["cmc"])
        events = self._normalise_events(source_data["topics"], rss_events, symbols, aliases)
        market_map = self._market_map(
            source_data["cmc"],
            source_data["dex_profiles"] + source_data["dex_community"],
            source_data["coingecko"],
            symbols,
            aliases,
        )
        santiment_map = self._collect_santiment(statuses, events, aliases)
        # Supplementary detail only: the narrative scorer reads price/volume fields, not this nested field.
        for symbol, metrics in santiment_map.items():
            market_map.setdefault(symbol, {"symbol": symbol})["santiment"] = metrics
        narratives, early_watch = self._build_narratives(
            events,
            market_map,
            self.previous_state.get("narratives", []) if isinstance(self.previous_state.get("narratives"), list) else [],
            source_statuses=statuses,
        )
        self._save_history(narratives, events)
        alerts = self._alerts(narratives)
        news_statuses = [
            item for key, item in statuses.items() if key.startswith("rss_")
        ]
        topic_status = statuses.get("aixbt_topics", {})
        connected_news = sum(
            item.get("status") in ("BAĞLI", "ÖNBELLEK")
            and item.get("item_count", 0) > 0
            for item in news_statuses
        )
        enabled_news = sum(bool(item.get("enabled")) for item in news_statuses)
        topic_connected = bool(
            isinstance(topic_status, dict)
            and topic_status.get("status") in ("BAĞLI", "ÖNBELLEK")
            and topic_status.get("item_count", 0) > 0
        )
        santiment_status = statuses.get("santiment", {})
        santiment_connected = bool(
            isinstance(santiment_status, dict)
            and santiment_status.get("status") in ("BAĞLI", "ÖNBELLEK")
        )
        errors = [
            f"{item['name']}: {item['status']}"
            for item in statuses.values()
            if item.get("enabled") and item.get("status") in ("ERİŞİLEMEDİ", "HATA — ÖNCEKİ VERİ VAR", "ESKİ VERİ")
        ]
        state = {
            "schema_version": 1,
            "engine": "Naratif Avcısı",
            "status": "ÇALIŞIYOR" if (connected_news or topic_connected or santiment_connected) else "KAYNAK VERİSİ BEKLENİYOR",
            "generated_at_utc": utc_now(),
            "first_observed_only": True,
            "historical_narrative_backfill": False,
            "source_statuses": statuses,
            "source_coverage": {
                "news_feeds_connected": connected_news,
                "news_feeds_enabled": enabled_news,
                "aixbt_topic_source_connected": topic_connected,
                "topic_sources_connected": int(topic_connected),
                "evidence_sources_connected": connected_news + int(topic_connected),
                "event_count": len(events),
                "narrative_count": len(narratives),
                "early_watch_count": len(early_watch),
                "errors": errors,
            },
            "universe": universe,
            "narratives": narratives,
            "early_watch": early_watch,
            "alerts": alerts,
            "market_activity": {
                "cmc_role": "MARKET_ACTIVITY_NOT_NEWS",
                "cmc_coin_count": len(source_data["cmc"]),
                "dex_profiles_count": len(source_data["dex_profiles"]),
                "dex_community_count": len(source_data["dex_community"]),
                "santiment_coin_count": len(santiment_map),
                "santiment_symbols": sorted(santiment_map),
            },
            "limits": [
                "AIXBT ücretsiz/anahtarsız Topics uç noktası mevcut ilk 25 konuyu verir; tüm AIXBT konu arşivi değildir.",
                "AIXBT konu→proje ayrıntılı eşlemesi ek API erişimi gerektirebilir ve bu sürümde kullanılmaz.",
                "CoinMarketCap anahtarsız listeleme verisi piyasa aktivitesidir; haber veya bağımsız haber teyidi sayılmaz.",
                "CoinGecko Demo API anahtarı yoksa devre dışıdır; anahtar gizli ortam değişkeninden okunur.",
                "DEX profil/topluluk hareketi organik ilgi veya bağımsız haber teyidi olarak tek başına yorumlanmaz.",
                "Santiment yalnızca ücretsiz active_addresses_24h ve dev_activity modern:v1 ölçümlerini, en fazla 30 eşleşen aday coin için altı saatte bir toplu sorgular.",
                "Free API aylık 1.000 çağrı sınırı içinde tahmini kullanım yaklaşık 241 çağrı/30 gündür; ücretli/kısıtlı ölçümler çağrılmaz.",
                "Santiment API anahtarı yalnızca SANTIMENT_API_KEY ortam değişkeninden okunur; ayarlar dosyasına veya rapora yazılmaz.",
                "Kaynağın geçmiş verisi geri doldurulmaz; naratif geçmişi bu motorun ilk gözleminden başlar.",
                "Naratif puanı teknik puandan ayrıdır; teknik eşikleri, likidite kapılarını ve güçlü alarm koşullarını değiştirmez.",
            ],
        }
        self.previous_state = state
        _atomic_json(self.cache_path, self.cache)
        _atomic_json(self.state_path, state)
        return state

    def run(self, *, once: bool = False, poll_seconds: int = 15) -> int:
        self.stop_file.parent.mkdir(parents=True, exist_ok=True)
        # The panel clears this marker before process creation. Do not unlink it here:
        # an immediate user stop between Popen() and run() must not be lost.
        self.logger.info("Naratif Avcısı başlatıldı; teknik radardan ayrı süreçte çalışıyor.")
        try:
            while not self.stop_file.exists():
                try:
                    self.run_cycle()
                except Exception:
                    self.logger.exception("Naratif Avcısı turu hata verdi; sonraki tur devam edecek.")
                if once:
                    break
                deadline = self.clock() + max(5, poll_seconds)
                while not self.stop_file.exists() and self.clock() < deadline:
                    time.sleep(0.5)
        finally:
            current = _read_json(self.state_path, {})
            if isinstance(current, dict):
                current["process_status"] = "DURDURULDU"
                current["process_stopped_at_utc"] = utc_now()
                _atomic_json(self.state_path, current)
            self.logger.info("Naratif Avcısı durduruldu.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop-file", default=str(RUN_DIR / "stop_narrative.flag"))
    parser.add_argument("--once", action="store_true", help="Kaynakları bir kez yenile ve çık.")
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args()
    return NarrativeEngine(stop_file=Path(args.stop_file)).run(
        once=args.once, poll_seconds=max(5, args.poll_seconds),
    )


if __name__ == "__main__":
    raise SystemExit(main())
