"""Naratif Avcısı: ücretsiz/izinli kaynaklardan canlı tematik ilgi ve erken izleme üretir.

Bu süreç teknik puanı veya güçlü fırsat koşullarını değiştirmez. Tarihsel naratif
verisi olmadığı için yalnızca ilk gerçek gözlemden itibaren geçmiş kaydı oluşturur.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
import unicodedata
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

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
MOTOR_BRIDGE_FILENAME = "naratif_motor_koprusu.json"
MOTOR_BRIDGE_MAX_AGE_SECONDS = 1800
LOG_PATH = LOG_DIR / "naratif_avcisi.log"

AIXBT_TOPICS_URL = "https://api.aixbt.tech/v3/topics"
AIXBT_TOPIC_PROJECTS_URL = "https://api.aixbt.tech/v3/topics/{topic_id}/projects"
CMC_KEYLESS_BASE_URL = "https://pro-api.coinmarketcap.com/public-api"
CMC_LISTINGS_URL = f"{CMC_KEYLESS_BASE_URL}/v3/cryptocurrency/listings/latest"
CMC_ID_MAP_URL = f"{CMC_KEYLESS_BASE_URL}/v1/cryptocurrency/map"
CMC_QUOTES_URL = f"{CMC_KEYLESS_BASE_URL}/v3/cryptocurrency/quotes/latest"
CMC_GLOBAL_METRICS_URL = f"{CMC_KEYLESS_BASE_URL}/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = f"{CMC_KEYLESS_BASE_URL}/v3/fear-and-greed/latest"
CMC_ALTCOIN_SEASON_URL = f"{CMC_KEYLESS_BASE_URL}/v1/altcoin-season-index/latest"
CMC100_INDEX_URL = f"{CMC_KEYLESS_BASE_URL}/v3/index/cmc100-latest"
CMC20_INDEX_URL = f"{CMC_KEYLESS_BASE_URL}/v3/index/cmc20-latest"
CMC_CATEGORIES_URL = f"{CMC_KEYLESS_BASE_URL}/v1/cryptocurrency/categories"
CMC_CATEGORY_URL = f"{CMC_KEYLESS_BASE_URL}/v1/cryptocurrency/category"
TRENDKIA_MCP_URL = "https://trendkia.com/mcp"
MCP_PROTOCOL_VERSION = "2025-03-26"
DEX_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_COMMUNITY_URL = "https://api.dexscreener.com/community-takeovers/latest/v1"
DEX_TOKENS_URL = "https://api.dexscreener.com/tokens/v1"
COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
SANTIMENT_GRAPHQL_URL = "https://api.santiment.net/graphql"
DEFILLAMA_BASE_URL = "https://api.llama.fi"
DEFILLAMA_PROTOCOLS_URL = f"{DEFILLAMA_BASE_URL}/protocols"
DEFILLAMA_CHAINS_URL = f"{DEFILLAMA_BASE_URL}/v2/chains"
DEFILLAMA_STABLECOIN_CHAINS_URL = f"{DEFILLAMA_BASE_URL}/stablecoinchains"
DEFILLAMA_STABLECOIN_HISTORY_URL = f"{DEFILLAMA_BASE_URL}/stablecoincharts/all"
DEFILLAMA_DEX_OVERVIEW_URL = f"{DEFILLAMA_BASE_URL}/overview/dexs"
DEFILLAMA_FEES_OVERVIEW_URL = f"{DEFILLAMA_BASE_URL}/overview/fees"

DEFAULT_FEEDS = [
    {"id": "ethereum_foundation", "name": "Ethereum Foundation", "url": "https://blog.ethereum.org/en/feed.xml", "kind": "official"},
    {"id": "coindesk", "name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "kind": "media"},
    {"id": "cointelegraph", "name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "kind": "media"},
    {"id": "the_block", "name": "The Block", "url": "https://www.theblock.co/rss.xml", "kind": "media"},
    {"id": "decrypt", "name": "Decrypt", "url": "https://decrypt.co/feed", "kind": "media"},
    {"id": "bitcoin_magazine", "name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed", "kind": "media"},
    {"id": "the_defiant", "name": "The Defiant", "url": "https://thedefiant.io/feed/", "kind": "media"},
]
SOURCE_INTERVALS = {
    "aixbt_topics": 300,
    "aixbt_project_mapping": 3600,
    "cmc_market_activity": 3600,
    "cmc_id_map": 6 * 3600,
    "cmc_quotes": 3600,
    "cmc_global_metrics": 3600,
    "cmc_fear_greed": 3600,
    "cmc_altcoin_season": 4 * 3600,
    "cmc100_index": 6 * 3600,
    "cmc20_index": 6 * 3600,
    "cmc_narrative_categories": 6 * 3600,
    "cmc_category_detail": 12 * 3600,
    "cmc_category_details_batch": 6 * 3600,
    "trendkia_news": 1800,
    "dex_profiles": 600,
    "dex_community": 900,
    "dex_market_activity": 900,
    "coingecko_trending": 600,
    "santiment_project_catalog": 30 * 86400,
    "santiment_active_addresses": 6 * 3600,
    "santiment_dev_activity": 6 * 3600,
    "defillama_protocols": 3 * 3600,
    "defillama_chains": 3 * 3600,
    "defillama_stablecoin_chains": 6 * 3600,
    "defillama_stablecoin_history": 6 * 3600,
    "defillama_dex_overview": 3 * 3600,
    "defillama_fees_overview": 3 * 3600,
}
MAX_SOURCE_ITEMS = 500
MAX_CMC_CATEGORY_ITEMS = 5000
MAX_CMC_CATEGORY_DETAIL_CANDIDATES = 200
CMC_CATEGORY_PRIORITY_WINDOW = 12
CMC_CATEGORY_DISPLAY_WINDOW = 18
CMC_CATEGORY_MAX_DISPLAY_ITEMS = 30
CMC_CATEGORY_DETAIL_BATCH_SIZE = 3
CMC_CATEGORY_EXPLORATION_SLOTS = 1
CMC_CATEGORY_RECENT_DETAIL_SECONDS = 48 * 3600
CMC_CATEGORY_EXPLORATION_MIN_TOKENS = 2
CMC_CATEGORY_EXPLORATION_MIN_MOMENTUM = 60.0
MAX_RSS_ITEMS_PER_FEED = 100
RSS_DEFAULT_INTERVAL_SECONDS = 1800
RSS_MIN_INTERVAL_SECONDS = 900
RSS_DEDUP_WINDOW_SECONDS = 72 * 3600
MAX_SANTIMENT_SYMBOLS = 30
MAX_AIXBT_TOPICS_PER_REFRESH = 5
MAX_DEX_ACTIVITY_BATCHES_PER_REFRESH = 2
MAX_DEX_ACTIVITY_ADDRESSES_PER_BATCH = 30
MAX_DEX_ACTIVITY_CANDIDATES = 180
MAX_AIXBT_PROJECTS_PER_TOPIC = 50
AIXBT_PROJECT_MAPPING_MAX_AGE_SECONDS = 8 * 3600
USER_AGENT = "FirsatKontrolPaneli-NarrativeResearch/1.0 (+local desktop research client)"

THEME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Yapay Zekâ (AI)", ("artificial intelligence", "ai & big data", "ai agent", "ai agents", "agentic", "machine learning", "yapay zeka")),
    ("Gerçek Dünya Varlıkları (RWA)", ("real world asset", "real-world asset", "tokenized asset", "tokenisation", "tokenization", "rwa")),
    ("Merkeziyetsiz Fiziksel Altyapı (DePIN)", ("depin", "decentralized physical infrastructure", "decentralised physical infrastructure")),
    ("Merkeziyetsiz Finans (DeFi)", ("defi", "decentralized finance", "decentralised finance", "yield farming", "liquidity protocol")),
    ("Katman-1 (Layer 1)", ("layer 1", "layer-1", "layer one", "layer1", "l1 network")),
    ("Katman-2 (Layer 2)", ("layer 2", "layer-2", "rollup", "optimistic rollup", "zk rollup", "l2 network")),
    ("Yeniden Stake Etme (Restaking)", ("restaking", "re-staking", "liquid restaking")),
    ("Gerçek Getiri (Real Yield)", ("real yield", "fee-sharing", "revenue sharing")),
    ("Oyun ve Metaverse (Gaming)", ("gaming", "gamefi", "metaverse", "web3 game")),
    ("Meme Coin Ekosistemi", ("meme coin", "memecoin", "meme token")),
    ("Kurumsal Benimseme", ("institutional adoption", "institutional investment", "corporate treasury", "institutional")),
    ("Borsa Yatırım Fonu (ETF)", ("spot etf", "etf approval", "etf inflow", "exchange traded fund")),
    ("Gizlilik (Privacy)", ("privacy protocol", "zero knowledge", "zero-knowledge", "zk proof")),
    ("Stablecoin Ekosistemi", ("stablecoin", "payment settlement", "stable asset")),
    ("Gerçek Zamanlı Veri ve Oracle", ("oracle network", "real-time data", "oracle integration", "oracles")),
    ("Modüler Blokzincir", ("modular blockchain", "modular network", "modular chain")),
    ("Zincirler Arası Bağlantı", ("cross-chain", "cross chain", "interoperability", "bridge protocol")),
    ("Merkeziyetsiz Bilim (DeSci)", ("desci", "decentralized science", "decentralised science")),
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


def _timestamp_age_seconds(value: Any, now_epoch: float | None = None) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (now_epoch if now_epoch is not None else time.time()) - parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


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
        for key in ("topics", "projects", "cryptoCurrencyList", "list", "items", "results", "tokens"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    for key in ("topics", "projects", "items", "results", "tokens"):
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


def parse_aixbt_topic_projects(payload: Any, topic: dict[str, Any]) -> dict[str, Any]:
    """Normalize one AIXBT v3 topic→project association response."""
    topic_id = str(topic.get("id") or topic.get("topic_id") or "").strip()
    projects = []
    for item in _records(payload):
        project = item.get("project")
        if not isinstance(project, dict):
            continue
        project_id = project.get("id")
        slug = str(project.get("slug") or "").strip()
        name = str(project.get("name") or "").strip()
        if not slug or not name:
            continue
        sentiment = item.get("sentiment") if isinstance(item.get("sentiment"), dict) else {}
        projects.append({
            "project_id": str(project_id) if project_id is not None else None,
            "slug": slug[:120],
            "name": name[:180],
            "observed_posts": _safe_int(item.get("observedPosts")),
            "distinct_authors": _safe_int(item.get("distinctAuthors")),
            "share_of_topic_posts": _safe_float(item.get("shareOfTopicPosts")),
            "first_observed_at": item.get("firstObservedAt"),
            "last_observed_at": item.get("lastObservedAt"),
            "sentiment_populated": sentiment.get("populated"),
            "sentiment_coverage": _safe_float(sentiment.get("coverage")),
        })
    return {
        "topic_id": topic_id,
        "topic_name": str(topic.get("name") or "")[:180],
        "topic_rank": _safe_int(topic.get("rank")),
        "checked_at_utc": utc_now(),
        "projects": projects[:MAX_AIXBT_PROJECTS_PER_TOPIC],
    }


def _cmc_data_records(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("cryptoCurrencyList", "list", "items", "results", "tokens"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        if any(key in data for key in ("id", "symbol", "name", "quote", "value")):
            return [data]
        rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("id", _safe_int(key))
                rows.append(row)
        return rows
    return _records(payload)


def _cmc_usd_quote(item: dict[str, Any]) -> dict[str, Any]:
    quote = item.get("quote")
    if isinstance(quote, list):
        for entry in quote:
            if isinstance(entry, dict) and str(entry.get("symbol") or "").upper() == "USD":
                return entry
        return next((entry for entry in quote if isinstance(entry, dict)), {})
    if isinstance(quote, dict):
        usd = quote.get("USD")
        return usd if isinstance(usd, dict) else quote
    return {}


def parse_cmc_id_map(payload: Any) -> list[dict[str, Any]]:
    rows = []
    for item in _cmc_data_records(payload):
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        cmc_id = _safe_int(item.get("id"))
        if symbol and name and cmc_id is not None:
            rows.append({
                "id": cmc_id, "symbol": symbol, "name": name,
                "slug": str(item.get("slug") or ""),
                "is_active": _safe_int(item.get("is_active")),
            })
    return rows[:2000]


def build_cmc_id_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        cmc_id = _safe_int(row.get("id"))
        if symbol and cmc_id is not None:
            grouped.setdefault(symbol, {})[cmc_id] = row
    return {
        symbol: dict(next(iter(items.values())))
        for symbol, items in grouped.items() if len(items) == 1
    }


def parse_cmc_market_listings(payload: Any) -> list[dict[str, Any]]:
    """Normalize CMC Keyless listings as market activity, never as news."""
    result = []
    for item in _cmc_data_records(payload):
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not symbol or not name:
            continue
        usd = _cmc_usd_quote(item)
        result.append({
            "id": _safe_int(item.get("id")), "symbol": symbol, "name": name,
            "slug": str(item.get("slug") or ""),
            "rank": _safe_int(item.get("cmc_rank") or item.get("rank")),
            "price": _safe_float(usd.get("price")),
            "volume_24h": _safe_float(usd.get("volume_24h")),
            "volume_change_24h": _safe_float(usd.get("volume_change_24h")),
            "percent_change_24h": _safe_float(usd.get("percent_change_24h")),
            "market_cap": _safe_float(usd.get("market_cap")),
        })
    return result[:MAX_SOURCE_ITEMS]


def parse_cmc_quotes(payload: Any) -> list[dict[str, Any]]:
    rows = []
    for item in _cmc_data_records(payload):
        symbol = str(item.get("symbol") or "").strip().upper()
        cmc_id = _safe_int(item.get("id"))
        if not symbol or cmc_id is None:
            continue
        usd = _cmc_usd_quote(item)
        rows.append({
            "id": cmc_id, "symbol": symbol, "name": str(item.get("name") or ""),
            "slug": str(item.get("slug") or ""),
            "rank": _safe_int(item.get("cmc_rank")),
            "price": _safe_float(usd.get("price")),
            "volume_24h": _safe_float(usd.get("volume_24h")),
            "volume_change_24h": _safe_float(usd.get("volume_change_24h")),
            "percent_change_24h": _safe_float(usd.get("percent_change_24h")),
            "market_cap": _safe_float(usd.get("market_cap")),
            "last_updated": str(usd.get("last_updated") or item.get("last_updated") or ""),
        })
    return rows[:250]


def cmc_category_momentum_score(item: dict[str, Any]) -> float | None:
    """Bound category price/cap/volume changes to a transparent 0..100 score component."""
    changes = (
        _safe_float(item.get("avg_price_change")),
        _safe_float(item.get("market_cap_change")),
        _safe_float(item.get("volume_change")),
    )
    if not any(value is not None for value in changes):
        return None
    price_change, cap_change, volume_change = changes
    score = 50.0 + (price_change or 0.0) * 0.7 + (cap_change or 0.0) * 0.25 + (volume_change or 0.0) * 0.25
    return round(max(0.0, min(100.0, score)), 1)


def parse_cmc_categories(payload: Any) -> list[dict[str, Any]]:
    """Keep the full CMC category catalogue and flag strong, not-yet-classified movers."""
    rows = []
    for item in _cmc_data_records(payload):
        category_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or item.get("title") or "").strip()
        title = str(item.get("title") or name).strip()
        description = str(item.get("description") or "").strip()
        if not category_id or not name:
            continue
        themes = infer_themes(" ".join((name, title, description)))
        row = {
            "id": category_id,
            "name": name[:180],
            "title": title[:180],
            "description": description[:600],
            "num_tokens": _safe_int(item.get("num_tokens")),
            "avg_price_change": _safe_float(item.get("avg_price_change")),
            "market_cap": _safe_float(item.get("market_cap")),
            "market_cap_change": _safe_float(item.get("market_cap_change")),
            "volume": _safe_float(item.get("volume")),
            "volume_change": _safe_float(item.get("volume_change")),
            "last_updated": str(item.get("last_updated") or ""),
            "themes": themes,
        }
        row["momentum_score"] = cmc_category_momentum_score(row)
        # An unmapped category is only a provisional discovery candidate when at least
        # two projects and all three market-change measures move positively together.
        # This is one CMC evidence family, not an independent confirmation.
        emerging_candidate = (
            not themes
            and (row.get("num_tokens") or 0) >= CMC_CATEGORY_EXPLORATION_MIN_TOKENS
            and row.get("momentum_score") is not None
            and row["momentum_score"] >= CMC_CATEGORY_EXPLORATION_MIN_MOMENTUM
            and row.get("avg_price_change") is not None
            and row["avg_price_change"] > 0
            and row.get("market_cap_change") is not None
            and row["market_cap_change"] > 0
            and row.get("volume_change") is not None
            and row["volume_change"] > 0
        )
        row["is_emerging_candidate"] = bool(emerging_candidate)
        row["is_narrative_candidate"] = bool(themes) or bool(emerging_candidate)
        row["category_classification"] = (
            "TANINAN_TEMA" if themes else
            "YENI_KATEGORI_ADAYI" if emerging_candidate else
            "SINIFLANDIRILMAMIS"
        )
        rows.append(row)
    rows.sort(
        key=lambda item: (
            item.get("is_narrative_candidate") is True,
            item.get("momentum_score") is not None,
            item.get("momentum_score") if item.get("momentum_score") is not None else -1,
            item.get("num_tokens") or 0,
        ),
        reverse=True,
    )
    return rows[:MAX_CMC_CATEGORY_ITEMS]


def rank_cmc_narrative_categories(
    categories: list[dict[str, Any]],
    limit: int = MAX_CMC_CATEGORY_DETAIL_CANDIDATES,
) -> list[dict[str, Any]]:
    """Rank known themes and high-activity unclassified category candidates."""
    rows = [
        item for item in categories
        if isinstance(item, dict)
        and (
            bool(item.get("themes"))
            or item.get("is_emerging_candidate") is True
            or item.get("category_classification") == "YENI_KATEGORI_ADAYI"
        )
    ]
    rows.sort(
        key=lambda item: (
            item.get("momentum_score") is not None,
            item.get("momentum_score") if item.get("momentum_score") is not None else -1,
            item.get("num_tokens") or 0,
            str(item.get("name") or "").casefold(),
        ),
        reverse=True,
    )
    maximum = min(MAX_CMC_CATEGORY_DETAIL_CANDIDATES, max(1, int(limit)))
    return rows[:maximum]


def select_cmc_category_detail_batch(
    categories: list[dict[str, Any]],
    cache: dict[str, Any],
    *,
    batch_size: int = CMC_CATEGORY_DETAIL_BATCH_SIZE,
    priority_window: int = CMC_CATEGORY_PRIORITY_WINDOW,
    exploration_slots: int = CMC_CATEGORY_EXPLORATION_SLOTS,
) -> list[dict[str, Any]]:
    """Use two slots for the priority window and one for rotating wider-universe discovery."""
    unique_rows = []
    seen_ids: set[str] = set()
    for row in categories:
        if not isinstance(row, dict):
            continue
        category_id = str(row.get("id") or "").strip()
        if not category_id or category_id in seen_ids:
            continue
        seen_ids.add(category_id)
        unique_rows.append(row)
    if not unique_rows or batch_size <= 0:
        return []

    def refresh_sort_key(row: dict[str, Any]) -> tuple[float, float, int, str]:
        entry = cache.get("cmc_category_" + str(row.get("id") or ""))
        entry = entry if isinstance(entry, dict) else {}
        last_success = _safe_float(entry.get("last_success_epoch")) or 0.0
        momentum = _safe_float(row.get("momentum_score"))
        return (
            last_success,
            -(momentum if momentum is not None else -1.0),
            -(_safe_int(row.get("num_tokens")) or 0),
            str(row.get("id") or ""),
        )

    priority_count = max(1, int(priority_window))
    priority_rows = unique_rows[:priority_count]
    exploration_rows = unique_rows[priority_count:]
    selected: list[dict[str, Any]] = []

    if not exploration_rows:
        return sorted(unique_rows, key=refresh_sort_key)[:batch_size]

    exploration_count = min(max(0, int(exploration_slots)), len(exploration_rows), batch_size)
    priority_slots = min(len(priority_rows), max(0, batch_size - exploration_count))
    selected.extend(sorted(priority_rows, key=refresh_sort_key)[:priority_slots])
    selected_ids = {str(row.get("id") or "") for row in selected}

    for row in sorted(exploration_rows, key=refresh_sort_key):
        if len(selected) >= batch_size or len(selected) - priority_slots >= exploration_count:
            break
        row_id = str(row.get("id") or "")
        if row_id not in selected_ids:
            selected.append(row)
            selected_ids.add(row_id)

    if len(selected) < batch_size:
        for row in sorted(unique_rows, key=refresh_sort_key):
            if len(selected) >= batch_size:
                break
            row_id = str(row.get("id") or "")
            if row_id not in selected_ids:
                selected.append(row)
                selected_ids.add(row_id)
    return selected[:batch_size]


def parse_cmc_category_detail(
    payload: Any,
    category_summary: dict[str, Any],
    allowed_cmc_ids_by_symbol: dict[str, int],
) -> dict[str, Any]:
    """Keep category members only when their CMC IDs match unique IDs in the shared USDT universe."""
    records = _cmc_data_records(payload)
    wanted_id = str(category_summary.get("id") or "")
    category = next(
        (item for item in records
         if str(item.get("id") or "") == wanted_id and isinstance(item.get("coins"), list)),
        None,
    )
    if category is None:
        category = next((item for item in records if isinstance(item.get("coins"), list)), None)
    if category is None:
        return {}
    coins = []
    for item in category.get("coins", []):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        cmc_id = _safe_int(item.get("id"))
        if not symbol or cmc_id is None or allowed_cmc_ids_by_symbol.get(symbol) != cmc_id:
            continue
        usd = _cmc_usd_quote(item)
        coins.append({
            "id": cmc_id, "symbol": symbol, "name": str(item.get("name") or ""),
            "slug": str(item.get("slug") or ""), "rank": _safe_int(item.get("cmc_rank")),
            "price": _safe_float(usd.get("price")),
            "volume_24h": _safe_float(usd.get("volume_24h")),
            "volume_change_24h": _safe_float(usd.get("volume_change_24h")),
            "percent_change_24h": _safe_float(usd.get("percent_change_24h")),
            "market_cap": _safe_float(usd.get("market_cap")),
            "last_updated": str(usd.get("last_updated") or item.get("last_updated") or ""),
        })
    return {
        "id": wanted_id,
        "name": str(category_summary.get("name") or category.get("name") or ""),
        "title": str(category_summary.get("title") or category.get("title") or ""),
        "description": str(category_summary.get("description") or category.get("description") or "")[:1200],
        "num_tokens": _safe_int(category_summary.get("num_tokens") or category.get("num_tokens")),
        "avg_price_change": _safe_float(category_summary.get("avg_price_change")),
        "market_cap": _safe_float(category_summary.get("market_cap")),
        "market_cap_change": _safe_float(category_summary.get("market_cap_change")),
        "volume": _safe_float(category_summary.get("volume")),
        "volume_change": _safe_float(category_summary.get("volume_change")),
        "momentum_score": _safe_float(category_summary.get("momentum_score")),
        "last_updated": str(category_summary.get("last_updated") or category.get("last_updated") or ""),
        "coins": coins[:1000],
    }


def build_cmc_category_event(category: dict[str, Any]) -> dict[str, Any] | None:
    """Create CMC-only discovery evidence, including provisional candidates awaiting coin mapping."""
    coins = category.get("coins") if isinstance(category.get("coins"), list) else []
    symbols = sorted({
        str(item.get("symbol") or "").strip().upper()
        for item in coins if isinstance(item, dict) and item.get("symbol")
    })
    name = str(category.get("name") or category.get("title") or "").strip()
    if not name:
        return None
    category_id = str(category.get("id") or "")
    searchable = " ".join((name, str(category.get("title") or ""), str(category.get("description") or "")))
    themes = list(category.get("themes") or infer_themes(searchable))
    is_emerging_candidate = (
        category.get("is_emerging_candidate") is True
        or category.get("category_classification") == "YENI_KATEGORI_ADAYI"
    )
    if not themes and is_emerging_candidate:
        themes = [f"CMC Kategori Adayı: {name[:90]}"]
    if not themes:
        return None
    known_theme = bool(infer_themes(searchable))
    detail_checked = category.get("_detail_checked") is True
    mapping_status = (
        "COIN EŞLEŞMESİ DOĞRULANDI" if symbols else
        "AYRINTI ALINDI; ORTAK USDT EVRENİNDE EŞLEŞEN COIN YOK" if detail_checked else
        "COIN EŞLEŞMESİ BEKLENİYOR"
    )
    return {
        "event_id": "cmc_category:" + category_id,
        "title": name[:300],
        "summary": str(category.get("description") or "")[:1200],
        "url": "https://coinmarketcap.com/cryptocurrency-category/",
        "source_id": "cmc_narrative_categories",
        "source_name": "CoinMarketCap Tematik Kategorileri",
        "source_kind": "topic_discovery",
        "published_at": str(category.get("last_updated") or ""),
        "symbols": [{"symbol": symbol, "confidence": "YÜKSEK"} for symbol in symbols],
        "themes": themes,
        "category_id": category_id,
        "category_classification": (
            "TANINAN_TEMA" if known_theme else "YENI_KATEGORI_ADAYI"
        ),
        "category_mapping_status": mapping_status,
        "category_momentum_score": _safe_float(category.get("momentum_score")),
        "category_avg_price_change": _safe_float(category.get("avg_price_change")),
        "category_market_cap_change": _safe_float(category.get("market_cap_change")),
        "category_volume_change": _safe_float(category.get("volume_change")),
        "category_num_tokens": _safe_int(category.get("num_tokens")),
        "evidence_class": (
            "TEMATİK KATEGORİ KEŞFİ" if known_theme
            else "YENİ CMC KATEGORİ ADAYI — DOĞRULAMA BEKLİYOR"
        ),
    }


def parse_cmc_global_metrics(payload: Any) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return {}
    usd = _cmc_usd_quote(data)
    return {
        "total_market_cap_usd": _safe_float(usd.get("total_market_cap") or data.get("total_market_cap")),
        "total_volume_24h_usd": _safe_float(usd.get("total_volume_24h") or data.get("total_volume_24h")),
        "bitcoin_dominance_pct": _safe_float(data.get("btc_dominance") or data.get("bitcoin_dominance")),
        "ethereum_dominance_pct": _safe_float(data.get("eth_dominance") or data.get("ethereum_dominance")),
        "last_updated": str(data.get("last_updated") or data.get("timestamp") or ""),
    }


def _cmc_single_snapshot(payload: Any) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        data = data[0] if data else {}
    return dict(data) if isinstance(data, dict) else {}


def parse_cmc_fear_greed(payload: Any) -> dict[str, Any]:
    data = _cmc_single_snapshot(payload)
    return {
        "value": _safe_int(data.get("value") or data.get("fear_greed_index")),
        "classification": str(data.get("value_classification") or data.get("classification") or ""),
        "timestamp": str(data.get("timestamp") or data.get("update_time") or data.get("last_updated") or ""),
    }


def parse_cmc_altcoin_season(payload: Any) -> dict[str, Any]:
    data = _cmc_single_snapshot(payload)
    return {
        "index": _safe_int(data.get("altcoin_index") or data.get("value")),
        "snapshot_time": str(data.get("snapshot_time") or data.get("timestamp") or ""),
        "yearly_high": _safe_int(data.get("yearly_high")),
        "yearly_low": _safe_int(data.get("yearly_low")),
    }


def parse_cmc_index_snapshot(payload: Any) -> dict[str, Any]:
    data = _cmc_single_snapshot(payload)
    if not data:
        return {}
    keep = ("id", "name", "symbol", "value", "price", "percent_change_24h", "last_updated", "timestamp")
    return {key: data[key] for key in keep if key in data}


def _parse_published_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


TRENDKIA_RELEVANCE_TERMS = (
    "crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "ether", "eth",
    "altcoin", "token", "blockchain", "binance", "solana", "defi", "stablecoin",
    "federal reserve", "fed", "interest rate", "inflation", "economy", "economic",
    "finance", "financial", "etf", "regulation", "central bank", "treasury",
    "dollar", "bond yield", "cpi", "pce", "nonfarm", "recession", "geopolitical",
    "क्रिप्टो", "बिटकॉइन", "एथेरियम", "फेड", "डॉलर", "मुद्रास्फीति", "महंगाई",
)


def parse_trendkia_articles(
    markdown_text: str, *, now_epoch: float | None = None, max_age_seconds: int = 72 * 3600
) -> list[dict[str, Any]]:
    """Extract current crypto/macro stories from TrendKia's public MCP feed."""
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        return []
    now = float(now_epoch if now_epoch is not None else time.time())
    rows = []
    sections = re.findall(r"(?ms)^##\s+(.+?)\s*\n(.*?)(?=^##\s+|\Z)", markdown_text)
    for title, block in sections:
        fields: dict[str, str] = {}
        for line in block.splitlines():
            match = re.match(r"^\s*-\s*([^:]+):\s*(.*)$", line)
            if match:
                fields[match.group(1).strip().lower()] = match.group(2).strip()
        url = fields.get("url", "")
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or (parsed_url.hostname or "").lower() not in {"trendkia.com", "www.trendkia.com"}:
            continue
        published = _parse_published_datetime(fields.get("published") or fields.get("date"))
        if published is None:
            continue
        age = now - published.timestamp()
        if age < -6 * 3600 or age > max_age_seconds:
            continue
        category, summary, tags = fields.get("category", ""), fields.get("summary", ""), fields.get("tags", "")
        searchable = " ".join((title, category, summary, tags)).casefold()
        if not any(term in searchable for term in TRENDKIA_RELEVANCE_TERMS):
            continue
        clean_title = re.sub(r"\s+", " ", title).strip()
        if not clean_title:
            continue
        rows.append({
            "id": "trendkia:" + _event_id(clean_title), "title": clean_title[:300],
            "summary": summary[:1800], "url": url[:1000],
            "published_at": published.isoformat(timespec="seconds"),
            "source_id": "trendkia_news", "source_name": "TrendKia News",
            "source_kind": "media", "category": category[:120], "tags": tags[:500],
        })
    return rows[:50]


def extract_mcp_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("TrendKia MCP beklenen JSON-RPC yanıtını döndürmedi.")
    if payload.get("error"):
        raise RuntimeError(f"TrendKia MCP JSON-RPC hatası: {str(payload.get('error'))[:400]}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("TrendKia MCP yanıtında result alanı bulunamadı.")
    if result.get("isError"):
        raise RuntimeError("TrendKia MCP aracı hata döndürdü.")
    content = result.get("content")
    texts = [
        str(item.get("text") or "")
        for item in content if isinstance(item, dict) and item.get("type") == "text"
    ] if isinstance(content, list) else []
    if texts:
        return chr(10).join(texts)
    structured = result.get("structuredContent")
    if isinstance(structured, str):
        return structured
    if isinstance(structured, (dict, list)):
        return json.dumps(structured, ensure_ascii=False)
    raise RuntimeError("TrendKia MCP yanıtında okunabilir içerik bulunamadı.")


class SourceRateLimited(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.retry_after_seconds = max(0, int(retry_after_seconds))


def _retry_after_seconds(value: Any) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return max(0, min(24 * 3600, int(float(raw))))
    except ValueError:
        parsed = _parse_published_datetime(raw)
        return max(0, min(24 * 3600, int(parsed.timestamp() - time.time()))) if parsed else 0




def parse_dex_records(
    payload: Any,
    *,
    source_kind: str = "dex_community_activity",
) -> list[dict[str, Any]]:
    """Normalize DEX Screener profile/community records and retain token addresses."""
    result = []
    for item in _records(payload):
        chain = str(item.get("chainId") or item.get("chain_id") or "").strip().lower()
        token_address = str(
            item.get("tokenAddress") or item.get("token_address")
            or item.get("address") or ""
        ).strip()
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "")
        links = item.get("links") if isinstance(item.get("links"), list) else []
        url = next(
            (str(link.get("url")) for link in links if isinstance(link, dict) and link.get("url")),
            "",
        )
        socials = item.get("socials") if isinstance(item.get("socials"), list) else []
        result.append({
            "chain": chain,
            "token_address": token_address,
            "symbol": symbol,
            "name": name,
            "description": description[:1000],
            "url": url[:1000],
            "links": [dict(link) for link in links[:12] if isinstance(link, dict)],
            "socials": [dict(row) for row in socials[:12] if isinstance(row, dict)],
            "source_kind": source_kind,
        })
    return result[:MAX_SOURCE_ITEMS]


def _dex_address_key(value: Any) -> str:
    address = str(value or "").strip()
    return address.lower() if address.startswith("0x") else address


def build_dex_token_candidates(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Collect explicit chain+tokenAddress pairs from the latest DEX feeds."""
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        chain = str(row.get("chain") or "").strip().lower()
        address = str(row.get("token_address") or "").strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", chain):
            continue
        if not re.fullmatch(r"[A-Za-z0-9]{20,100}", address):
            continue
        key = (chain, _dex_address_key(address))
        item = unique.setdefault(key, {
            "chain": chain,
            "token_address": address,
            "name": str(row.get("name") or "")[:180],
            "symbol": str(row.get("symbol") or "").upper()[:32],
        })
        if not item["name"] and row.get("name"):
            item["name"] = str(row.get("name"))[:180]
        if not item["symbol"] and row.get("symbol"):
            item["symbol"] = str(row.get("symbol")).upper()[:32]
    return list(unique.values())[:MAX_DEX_ACTIVITY_CANDIDATES]


def parse_dex_market_pairs(payload: Any) -> list[dict[str, Any]]:
    """Normalize real pair snapshots returned by DEX Screener tokens/v1."""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("pairs") or payload.get("data") or payload.get("results") or []
        if isinstance(rows, dict):
            rows = rows.get("pairs") or rows.get("items") or []
    else:
        rows = []
    if not isinstance(rows, list):
        return []

    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        base = item.get("baseToken") if isinstance(item.get("baseToken"), dict) else {}
        quote_token = item.get("quoteToken") if isinstance(item.get("quoteToken"), dict) else {}
        liquidity = item.get("liquidity") if isinstance(item.get("liquidity"), dict) else {}
        volume = item.get("volume") if isinstance(item.get("volume"), dict) else {}
        txns = item.get("txns") if isinstance(item.get("txns"), dict) else {}
        price_change = item.get("priceChange") if isinstance(item.get("priceChange"), dict) else {}
        chain = str(item.get("chainId") or item.get("chain_id") or "").strip().lower()
        if not chain or not base.get("address") or not quote_token.get("address"):
            continue
        pair_address = str(item.get("pairAddress") or item.get("pair_address") or "").strip()
        if not pair_address:
            pair_address = _event_id(
                f"{chain}|{base.get('address')}|{quote_token.get('address')}"
            )
        periods = ("m5", "h1", "h6", "h24")
        normalized_txns = {}
        for period in periods:
            entry = txns.get(period) if isinstance(txns.get(period), dict) else {}
            normalized_txns[period] = {
                "buys": max(0, _safe_int(entry.get("buys")) or 0),
                "sells": max(0, _safe_int(entry.get("sells")) or 0),
            }
        created_ms = _safe_float(item.get("pairCreatedAt"))
        result.append({
            "chain": chain,
            "dex_id": str(item.get("dexId") or ""),
            "pair_address": pair_address,
            "pair_id": f"{chain}:{pair_address}",
            "url": str(item.get("url") or "")[:1000],
            "base_token": {
                "address": str(base.get("address") or ""),
                "name": str(base.get("name") or ""),
                "symbol": str(base.get("symbol") or "").upper(),
            },
            "quote_token": {
                "address": str(quote_token.get("address") or ""),
                "name": str(quote_token.get("name") or ""),
                "symbol": str(quote_token.get("symbol") or "").upper(),
            },
            "price_usd": _safe_float(item.get("priceUsd")),
            "price_native": _safe_float(item.get("priceNative")),
            "volume_usd": {
                period: _safe_float(volume.get(period))
                for period in periods
            },
            "transactions": normalized_txns,
            "price_change_pct": {
                period: _safe_float(price_change.get(period))
                for period in periods
            },
            "liquidity_usd": _safe_float(liquidity.get("usd")),
            "fdv_usd": _safe_float(item.get("fdv")),
            "market_cap_usd": _safe_float(item.get("marketCap")),
            "pair_created_at_ms": created_ms,
        })
    return result[:5000]


def _dex_exact_name_symbol(
    name: str,
    symbols: list[str],
    aliases: dict[str, list[str]],
) -> str | None:
    """Map only a unique exact full project-name or alias; never guess from ticker similarity."""
    normalized = re.sub(r"[^0-9a-zçğıöşü]+", " ", str(name or "").casefold()).strip()
    if len(normalized) < 3:
        return None
    matches = []
    for symbol in symbols:
        if any(
            re.sub(r"[^0-9a-zçğıöşü]+", " ", str(alias or "").casefold()).strip() == normalized
            for alias in aliases.get(symbol, [])
        ):
            matches.append(symbol)
    matches = sorted(set(matches))
    return matches[0] if len(matches) == 1 else None


def aggregate_dex_market_activity(
    pairs: list[dict[str, Any]],
    candidates: list[dict[str, str]],
    symbols: list[str],
    aliases: dict[str, list[str]],
    *,
    now_epoch: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Aggregate pair liquidity, USD volume and transaction flow for uniquely matched assets."""
    candidate_keys = {
        (str(row.get("chain") or "").lower(), _dex_address_key(row.get("token_address")))
        for row in candidates if isinstance(row, dict)
    }
    aggregates: dict[str, dict[str, Any]] = {}
    seen_pairs: set[str] = set()
    now_value = now_epoch if now_epoch is not None else time.time()

    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        pair_id = str(pair.get("pair_id") or "")
        if not pair_id or pair_id in seen_pairs:
            continue
        seen_pairs.add(pair_id)
        chain = str(pair.get("chain") or "").lower()
        sides = (
            ("base", pair.get("base_token") if isinstance(pair.get("base_token"), dict) else {}),
            ("quote", pair.get("quote_token") if isinstance(pair.get("quote_token"), dict) else {}),
        )
        matched_sides = []
        for side_name, token in sides:
            if (chain, _dex_address_key(token.get("address"))) not in candidate_keys:
                continue
            symbol = _dex_exact_name_symbol(str(token.get("name") or ""), symbols, aliases)
            if symbol:
                matched_sides.append((side_name, symbol))

        for side_name, symbol in matched_sides:
            row = aggregates.setdefault(symbol, {
                "pair_ids": set(),
                "chains": set(),
                "dex_ids": set(),
                "liquidity_usd": 0.0,
                "volume_usd_m5": 0.0,
                "volume_usd_h1": 0.0,
                "volume_usd_h6": 0.0,
                "volume_usd_h24": 0.0,
                "buys_h24": 0,
                "sells_h24": 0,
                "weighted_price_sum": 0.0,
                "price_weight_sum": 0.0,
                "weighted_change_sum": 0.0,
                "change_weight_sum": 0.0,
                "market_cap_usd": None,
                "fdv_usd": None,
                "top_pairs": [],
            })
            if pair_id in row["pair_ids"]:
                continue
            row["pair_ids"].add(pair_id)
            row["chains"].add(chain)
            dex_id = str(pair.get("dex_id") or "")
            if dex_id:
                row["dex_ids"].add(dex_id)

            liquidity_usd = max(0.0, _safe_float(pair.get("liquidity_usd")) or 0.0)
            row["liquidity_usd"] += liquidity_usd
            volume = pair.get("volume_usd") if isinstance(pair.get("volume_usd"), dict) else {}
            for period in ("m5", "h1", "h6", "h24"):
                row[f"volume_usd_{period}"] += max(0.0, _safe_float(volume.get(period)) or 0.0)

            txns = pair.get("transactions") if isinstance(pair.get("transactions"), dict) else {}
            h24_txns = txns.get("h24") if isinstance(txns.get("h24"), dict) else {}
            buys = max(0, _safe_int(h24_txns.get("buys")) or 0)
            sells = max(0, _safe_int(h24_txns.get("sells")) or 0)
            if side_name == "quote":
                buys, sells = sells, buys
            row["buys_h24"] += buys
            row["sells_h24"] += sells

            price_usd = _safe_float(pair.get("price_usd"))
            price_native = _safe_float(pair.get("price_native"))
            token_price = price_usd if side_name == "base" else (
                price_usd / price_native
                if price_usd is not None and price_native is not None and price_native > 0
                else None
            )
            weight = max(1.0, liquidity_usd)
            if token_price is not None and token_price > 0:
                row["weighted_price_sum"] += token_price * weight
                row["price_weight_sum"] += weight

            price_changes = pair.get("price_change_pct") if isinstance(pair.get("price_change_pct"), dict) else {}
            change = _safe_float(price_changes.get("h24"))
            if change is not None:
                if side_name == "quote" and 1.0 + change / 100.0 > 0:
                    change = (1.0 / (1.0 + change / 100.0) - 1.0) * 100.0
                row["weighted_change_sum"] += change * weight
                row["change_weight_sum"] += weight

            for field in ("market_cap_usd", "fdv_usd"):
                value = _safe_float(pair.get(field))
                if value is not None and value > 0:
                    row[field] = value if row[field] is None else max(row[field], value)

            created_ms = _safe_float(pair.get("pair_created_at_ms"))
            pair_age_hours = (
                max(0.0, (now_value - created_ms / 1000.0) / 3600.0)
                if created_ms and created_ms > 0 else None
            )
            row["top_pairs"].append({
                "chain": chain,
                "dex_id": dex_id,
                "pair_address": pair.get("pair_address"),
                "url": pair.get("url"),
                "base_symbol": (pair.get("base_token") or {}).get("symbol"),
                "quote_symbol": (pair.get("quote_token") or {}).get("symbol"),
                "liquidity_usd": liquidity_usd,
                "volume_usd_h24": max(0.0, _safe_float(volume.get("h24")) or 0.0),
                "buys_h24": buys,
                "sells_h24": sells,
                "price_change_24h_pct": change,
                "pair_age_hours": round(pair_age_hours, 1) if pair_age_hours is not None else None,
            })

    result: dict[str, dict[str, Any]] = {}
    for symbol, row in aggregates.items():
        top_pairs = sorted(
            row["top_pairs"],
            key=lambda item: (item.get("liquidity_usd") or 0.0, item.get("volume_usd_h24") or 0.0),
            reverse=True,
        )[:5]
        result[symbol] = {
            "symbol": symbol,
            "pair_count": len(row["pair_ids"]),
            "chain_count": len(row["chains"]),
            "chains": sorted(row["chains"]),
            "dex_ids": sorted(row["dex_ids"]),
            "liquidity_usd": round(row["liquidity_usd"], 2),
            "volume_usd_m5": round(row["volume_usd_m5"], 2),
            "volume_usd_h1": round(row["volume_usd_h1"], 2),
            "volume_usd_h6": round(row["volume_usd_h6"], 2),
            "volume_usd_h24": round(row["volume_usd_h24"], 2),
            "buys_h24": row["buys_h24"],
            "sells_h24": row["sells_h24"],
            "transactions_h24": row["buys_h24"] + row["sells_h24"],
            "buy_sell_ratio_h24": round(row["buys_h24"] / row["sells_h24"], 3) if row["sells_h24"] else None,
            "current_price_usd": round(row["weighted_price_sum"] / row["price_weight_sum"], 10)
            if row["price_weight_sum"] else None,
            "price_change_24h_pct": round(row["weighted_change_sum"] / row["change_weight_sum"], 2)
            if row["change_weight_sum"] else None,
            "market_cap_usd": row["market_cap_usd"],
            "fdv_usd": row["fdv_usd"],
            "top_pairs": top_pairs,
            "scope": "SON DEX PROFİL/TOPLULUK TOKEN LİSTELERİNDEKİ ADRESLER",
        }
    return result




def parse_defillama_protocols(payload: Any) -> list[dict[str, Any]]:
    """Normalize the public protocol catalogue without relying on paid endpoints."""
    result = []
    for item in _records(payload):
        name = str(item.get("name") or item.get("displayName") or "").strip()
        if not name:
            continue
        chains = item.get("chains") if isinstance(item.get("chains"), list) else []
        raw_chain_tvls = item.get("chainTvls") if isinstance(item.get("chainTvls"), dict) else {}
        chain_tvls = {}
        for chain, amount in raw_chain_tvls.items():
            value = _safe_float(amount)
            if value is None and isinstance(amount, dict):
                value = _safe_float(amount.get("tvl") or amount.get("totalLiquidityUSD"))
            if value is not None:
                chain_tvls[str(chain)] = value
        result.append({
            "id": str(item.get("id") or ""),
            "slug": str(item.get("slug") or item.get("module") or "").strip().lower(),
            "name": name[:180],
            "symbol": str(item.get("symbol") or "").strip().upper()[:32],
            "category": str(item.get("category") or ""),
            "chains": sorted({str(chain) for chain in chains if str(chain).strip()}),
            "tvl_usd": _safe_float(item.get("tvl")),
            "change_1d_pct": _safe_float(item.get("change_1d")),
            "change_7d_pct": _safe_float(item.get("change_7d")),
            "market_cap_usd": _safe_float(item.get("mcap")),
            "chain_tvls": chain_tvls,
        })
    result.sort(
        key=lambda row: (
            row.get("tvl_usd") is not None,
            row.get("tvl_usd") if row.get("tvl_usd") is not None else -1.0,
        ),
        reverse=True,
    )
    return result[:5000]


def parse_defillama_chains(payload: Any) -> list[dict[str, Any]]:
    """Normalize current TVL by chain."""
    result = []
    for item in _records(payload):
        name = str(item.get("name") or "").strip()
        tvl = _safe_float(item.get("tvl"))
        if not name or tvl is None:
            continue
        result.append({
            "name": name[:100],
            "tvl_usd": tvl,
            "chain_id": _safe_int(item.get("chainId")),
            "token_symbol": str(item.get("tokenSymbol") or "").upper(),
            "gecko_id": str(item.get("gecko_id") or ""),
            "cmc_id": str(item.get("cmcId") or ""),
        })
    result.sort(key=lambda row: row["tvl_usd"], reverse=True)
    return result[:300]


def parse_defillama_stablecoin_chains(payload: Any) -> list[dict[str, Any]]:
    """Normalize current stablecoin supply by chain, using the reported USD peg amount."""
    result = []
    for item in _records(payload):
        name = str(item.get("name") or item.get("chain") or "").strip()
        raw = item.get("totalCirculating") or item.get("total_circulating")
        if isinstance(raw, dict):
            amount = _safe_float(raw.get("peggedUSD"))
        else:
            amount = _safe_float(raw)
        if not name or amount is None:
            continue
        result.append({"name": name[:100], "supply_usd": amount})
    result.sort(key=lambda row: row["supply_usd"], reverse=True)
    return result[:300]


def parse_defillama_stablecoin_history(payload: Any) -> list[dict[str, Any]]:
    """Normalize historical aggregate stablecoin circulation."""
    rows = payload if isinstance(payload, list) else _records(payload)
    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        timestamp = _safe_int(item.get("date") or item.get("timestamp"))
        raw = item.get("totalCirculating")
        if isinstance(raw, dict):
            amount = _safe_float(raw.get("peggedUSD"))
        else:
            amount = _safe_float(raw)
        if timestamp is None or amount is None:
            continue
        result.append({"timestamp": timestamp, "supply_usd": amount})
    result.sort(key=lambda row: row["timestamp"])
    return result[-1200:]


def parse_defillama_overview(payload: Any, *, metric: str) -> dict[str, Any]:
    """Normalize DEX-volume or fees overview protocol rows, excluding large chart payloads."""
    if isinstance(payload, dict):
        raw_rows = payload.get("protocols") if isinstance(payload.get("protocols"), list) else []
        all_chains = payload.get("allChains") if isinstance(payload.get("allChains"), list) else []
    else:
        raw_rows = []
        all_chains = []
    result = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("displayName") or "").strip()
        if not name:
            continue
        result.append({
            "slug": str(item.get("slug") or item.get("module") or "").strip().lower(),
            "name": name[:180],
            "symbol": str(item.get("symbol") or "").strip().upper()[:32],
            "category": str(item.get("category") or ""),
            "total_24h_usd": _safe_float(
                item.get("total24h") or item.get("total24H") or item.get("dailyFees")
                or item.get("dailyVolume")
            ),
            "total_7d_usd": _safe_float(item.get("total7d") or item.get("total7D")),
            "change_1d_pct": _safe_float(item.get("change_1d")),
            "chains": sorted({
                str(chain) for chain in (
                    item.get("chains") if isinstance(item.get("chains"), list) else []
                ) if str(chain).strip()
            }),
            "metric": metric,
        })
    result.sort(
        key=lambda row: (
            row.get("total_24h_usd") is not None,
            row.get("total_24h_usd") if row.get("total_24h_usd") is not None else -1.0,
        ),
        reverse=True,
    )
    return {
        "metric": metric,
        "protocols": result[:3000],
        "all_chains": [str(row) for row in all_chains[:300] if str(row).strip()],
    }


def summarize_defillama_stablecoin_history(
    rows: list[dict[str, Any]],
    *,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    """Compare latest global stablecoin supply against nearby 24h and 7d observations."""
    points = [
        row for row in rows
        if isinstance(row, dict)
        and _safe_int(row.get("timestamp")) is not None
        and _safe_float(row.get("supply_usd")) is not None
    ]
    if not points:
        return {}
    points.sort(key=lambda row: int(row["timestamp"]))
    latest = points[-1]
    latest_time = int(latest["timestamp"])
    latest_supply = float(latest["supply_usd"])
    result: dict[str, Any] = {
        "latest_supply_usd": latest_supply,
        "latest_timestamp": latest_time,
        "sample_count": len(points),
    }
    for label, target_seconds, tolerance_seconds in (
        ("change_24h_pct", 24 * 3600, 12 * 3600),
        ("change_7d_pct", 7 * 86400, 36 * 3600),
        ("change_30d_pct", 30 * 86400, 72 * 3600),
    ):
        target = latest_time - target_seconds
        previous = min(points[:-1], key=lambda row: abs(int(row["timestamp"]) - target)) if len(points) > 1 else None
        if previous is None:
            continue
        delta = abs(int(previous["timestamp"]) - target)
        old_value = _safe_float(previous.get("supply_usd"))
        if delta <= tolerance_seconds and old_value and old_value > 0:
            result[label] = round((latest_supply / old_value - 1.0) * 100.0, 3)
    return result


def _defillama_name_key(value: Any) -> str:
    return re.sub(r"[^0-9a-zçğıöşü]+", " ", str(value or "").casefold()).strip()


def attach_defillama_protocol_activity(
    market_map: dict[str, dict[str, Any]],
    protocols: list[dict[str, Any]],
    dex_overview: dict[str, Any],
    fees_overview: dict[str, Any],
    symbols: list[str],
    aliases: dict[str, list[str]],
) -> int:
    """Attach protocol TVL and DeFi activity only to unique full-name or protocol-token matches."""
    symbol_counts: dict[str, int] = {}
    for protocol in protocols:
        symbol = str(protocol.get("symbol") or "").strip().upper()
        if symbol and symbol in symbols:
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

    def overview_index(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = value.get("protocols") if isinstance(value, dict) else None
        result: dict[str, dict[str, Any]] = {}
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            for candidate in (item.get("slug"), item.get("name")):
                key = _defillama_name_key(candidate)
                if key:
                    result[key] = item
        return result

    dex_index = overview_index(dex_overview)
    fees_index = overview_index(fees_overview)
    matched = 0
    for protocol in protocols:
        if not isinstance(protocol, dict):
            continue
        raw_symbol = str(protocol.get("symbol") or "").strip().upper()
        symbol = (
            raw_symbol if raw_symbol in symbols and symbol_counts.get(raw_symbol) == 1
            else _dex_exact_name_symbol(str(protocol.get("name") or ""), symbols, aliases)
        )
        if not symbol:
            continue
        key_slug = _defillama_name_key(protocol.get("slug"))
        key_name = _defillama_name_key(protocol.get("name"))
        dex_row = dex_index.get(key_slug) or dex_index.get(key_name) or {}
        fees_row = fees_index.get(key_slug) or fees_index.get(key_name) or {}
        item = {
            "slug": protocol.get("slug"),
            "name": protocol.get("name"),
            "symbol": raw_symbol,
            "category": protocol.get("category"),
            "tvl_usd": _safe_float(protocol.get("tvl_usd")),
            "tvl_change_1d_pct": _safe_float(protocol.get("change_1d_pct")),
            "tvl_change_7d_pct": _safe_float(protocol.get("change_7d_pct")),
            "market_cap_usd": _safe_float(protocol.get("market_cap_usd")),
            "chains": protocol.get("chains", []),
            "chain_tvls": protocol.get("chain_tvls", {}),
            "dex_volume_24h_usd": _safe_float(dex_row.get("total_24h_usd")),
            "dex_volume_7d_usd": _safe_float(dex_row.get("total_7d_usd")),
            "dex_volume_change_1d_pct": _safe_float(dex_row.get("change_1d_pct")),
            "fees_24h_usd": _safe_float(fees_row.get("total_24h_usd")),
            "fees_7d_usd": _safe_float(fees_row.get("total_7d_usd")),
            "fees_change_1d_pct": _safe_float(fees_row.get("change_1d_pct")),
        }
        if not any(item.get(k) is not None for k in (
            "tvl_usd", "dex_volume_24h_usd", "fees_24h_usd"
        )):
            continue
        target = market_map.setdefault(symbol, {"symbol": symbol})
        rows = target.setdefault("defillama_protocols", [])
        if not any(
            str(old.get("slug") or "").casefold() == str(item.get("slug") or "").casefold()
            and str(old.get("name") or "").casefold() == str(item.get("name") or "").casefold()
            for old in rows if isinstance(old, dict)
        ):
            rows.append(item)
            matched += 1

    for value in market_map.values():
        if isinstance(value, dict) and isinstance(value.get("defillama_protocols"), list):
            value["defillama_protocols"].sort(
                key=lambda row: (
                    _safe_float(row.get("tvl_usd")) is not None,
                    _safe_float(row.get("tvl_usd")) or 0.0,
                ),
                reverse=True,
            )
            value["defillama_protocols"] = value["defillama_protocols"][:5]
    return matched


def build_defillama_global_context(
    protocols: list[dict[str, Any]],
    chains: list[dict[str, Any]],
    stablecoin_chains: list[dict[str, Any]],
    stablecoin_history: list[dict[str, Any]],
    dex_overview: dict[str, Any],
    fees_overview: dict[str, Any],
) -> dict[str, Any]:
    """Build a compact market-wide DeFi summary, separate from technical scoring."""
    stablecoin_total = sum(
        _safe_float(row.get("supply_usd")) or 0.0
        for row in stablecoin_chains if isinstance(row, dict)
    )
    history_summary = summarize_defillama_stablecoin_history(stablecoin_history)
    dex_rows = dex_overview.get("protocols", []) if isinstance(dex_overview, dict) else []
    fee_rows = fees_overview.get("protocols", []) if isinstance(fees_overview, dict) else []
    return {
        "protocol_count": len(protocols),
        "chain_count": len(chains),
        "sum_listed_chain_tvl_usd": round(sum(
            _safe_float(row.get("tvl_usd")) or 0.0
            for row in chains if isinstance(row, dict)
        ), 2),
        "top_chains": chains[:10],
        "stablecoin_chain_count": len(stablecoin_chains),
        "sum_listed_stablecoin_supply_usd": round(stablecoin_total, 2),
        "top_stablecoin_chains": stablecoin_chains[:10],
        "stablecoin_history": history_summary,
        "dex_protocol_count": len(dex_rows) if isinstance(dex_rows, list) else 0,
        "top_dex_protocols": dex_rows[:10] if isinstance(dex_rows, list) else [],
        "fees_protocol_count": len(fee_rows) if isinstance(fee_rows, list) else 0,
        "top_fee_protocols": fee_rows[:10] if isinstance(fee_rows, list) else [],
        "scope_note": "DeFiLlama genel DeFi bağlamı ve protokol verisidir; teknik puana veya güçlü fırsat koşullarına eklenmez.",
    }


def canonicalize_news_url(value: str) -> str:
    """Normalize article URLs and discard tracking-only query parameters."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme.lower() == "https" and port == 443)
                     or (parsed.scheme.lower() == "http" and port == 80)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    ignored = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "source"}
    query = [
        (key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in ignored
    ]
    query.sort(key=lambda row: (row[0].casefold(), row[1]))
    return urlunparse(("https", netloc, path, "", urlencode(query, doseq=True), ""))


def normalize_news_title(value: str) -> str:
    """Normalize editorial punctuation and whitespace without discarding meaningful words."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^0-9a-zçğıöşü]+", " ", text)
    return " ".join(text.split())


def _news_timestamp_epoch(value: str) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _news_headlines_are_near_duplicates(
    left_title: str,
    right_title: str,
    left_date: str,
    right_date: str,
    left_symbols: set[str] | None = None,
    right_symbols: set[str] | None = None,
) -> bool:
    """Merge only very similar headlines published close together, avoiding broad topic matches."""
    left = normalize_news_title(left_title)
    right = normalize_news_title(right_title)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) < 32:
        return False
    left_epoch = _news_timestamp_epoch(left_date)
    right_epoch = _news_timestamp_epoch(right_date)
    if left_epoch is None or right_epoch is None:
        return False
    if abs(left_epoch - right_epoch) > RSS_DEDUP_WINDOW_SECONDS:
        return False
    left_symbol_set = left_symbols or set()
    right_symbol_set = right_symbols or set()
    if left_symbol_set and right_symbol_set and not (left_symbol_set & right_symbol_set):
        return False
    left_tokens = {token for token in left.split() if len(token) > 2}
    right_tokens = {token for token in right.split() if len(token) > 2}
    if min(len(left_tokens), len(right_tokens)) < 4:
        return False
    shared = left_tokens & right_tokens
    shorter_coverage = len(shared) / min(len(left_tokens), len(right_tokens))
    union = left_tokens | right_tokens
    jaccard = len(shared) / len(union) if union else 0.0
    sequence_ratio = SequenceMatcher(None, left, right, autojunk=False).ratio()
    return (
        sequence_ratio >= 0.93
        or (sequence_ratio >= 0.87 and shorter_coverage >= 0.90 and jaccard >= 0.76)
    )


def parse_rss_items(xml_text: str, *, source_id: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    """Parse RSS 2.0 and Atom, preferring article links over feed/self/hub links."""
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
        article_links: list[str] = []
        fallback_links: list[str] = []
        for child in list(node):
            child_name = child.tag.rsplit("}", 1)[-1].lower()
            text = "".join(child.itertext()).strip()
            if child_name == "link":
                candidate = str(child.attrib.get("href") or text).strip()
                rel = str(child.attrib.get("rel") or "alternate").strip().lower()
                if candidate:
                    if rel in ("", "alternate"):
                        article_links.append(candidate)
                    else:
                        fallback_links.append(candidate)
                continue
            if child_name in (
                "title", "description", "summary", "content", "published",
                "updated", "pubdate", "guid", "date",
            ):
                clean = html.unescape(re.sub(r"<[^>]+>", " ", text))
                fields[child_name] = " ".join(clean.split())
        title = fields.get("title", "").strip()
        if not title:
            continue
        url = next(iter(article_links or fallback_links), "")
        guid = fields.get("guid", "").strip()
        if not url and guid.startswith(("https://", "http://")):
            url = guid
        canonical_url = canonicalize_news_url(url)
        normalized_title = normalize_news_title(title)
        published_at = (
            fields.get("published") or fields.get("updated")
            or fields.get("pubdate") or fields.get("date") or ""
        )
        fingerprint = _event_id("url:" + canonical_url) if canonical_url else _event_id("title:" + normalized_title)
        result.append({
            "id": fingerprint,
            "title": title[:300],
            "title_fingerprint": _event_id(normalized_title),
            "summary": (fields.get("summary") or fields.get("description") or fields.get("content") or "")[:1800],
            "url": url[:1000],
            "canonical_url": canonical_url,
            "guid": guid[:1000],
            "published_at": published_at[:120],
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
        self.motor_bridge_path = self.data_dir / MOTOR_BRIDGE_FILENAME
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
        self.mcp_session_id: str | None = None
        self.mcp_protocol_version = MCP_PROTOCOL_VERSION
        self.mcp_request_id = 1
        self.trendkia_initialized = False
        self.trendkia_tool_names: set[str] = set()
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
        if response.status_code == 429:
            raise SourceRateLimited("Kaynak HTTP 429 hız sınırı yanıtı verdi.",
                                    _retry_after_seconds(response.headers.get("Retry-After")))
        if response.status_code == 418:
            raise RuntimeError("Kaynak HTTP 418 hız sınırı yanıtı verdi; alternatif hostla aşılmadı.")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("status"), dict):
            error_code = payload["status"].get("error_code")
            if error_code not in (None, 0, "0"):
                raise RuntimeError(f"CoinMarketCap API hatası {error_code}: {str(payload['status'].get('error_message') or '')[:300]}")
        return payload

    def _fetch_aixbt_topic_project_mappings(self, topics: list[dict[str, Any]]) -> dict[str, Any]:
        """Fetch five rotating topic→project pages per hour; retain recent topic snapshots."""
        api_key = os.environ.get("AIXBT_API_KEY", "").strip()
        if not api_key:
            return {"by_topic": {}, "next_cursor": 0, "checked_at_utc": utc_now()}

        eligible = []
        seen = set()
        for topic in sorted(
            (row for row in topics if isinstance(row, dict)),
            key=lambda row: _safe_int(row.get("rank")) or 999,
        ):
            topic_id = str(topic.get("id") or "").strip()
            if not re.fullmatch(r"topic_[a-f0-9]{20}", topic_id) or topic_id in seen:
                continue
            seen.add(topic_id)
            eligible.append(topic)
        if not eligible:
            return {"by_topic": {}, "next_cursor": 0, "checked_at_utc": utc_now(),
                    "eligible_topic_count": 0}

        previous = self._cached_data("aixbt_project_mapping")
        previous = previous if isinstance(previous, dict) else {}
        previous_topics = previous.get("by_topic")
        previous_topics = previous_topics if isinstance(previous_topics, dict) else {}
        eligible_ids = {str(row["id"]) for row in eligible}
        by_topic = {
            topic_id: item for topic_id, item in previous_topics.items()
            if topic_id in eligible_ids and isinstance(item, dict)
            and (_timestamp_age_seconds(item.get("checked_at_utc"), self.clock())
                 or 0.0) <= AIXBT_PROJECT_MAPPING_MAX_AGE_SECONDS
        }
        cursor = (_safe_int(previous.get("next_cursor")) or 0) % len(eligible)
        batch_size = min(MAX_AIXBT_TOPICS_PER_REFRESH, len(eligible))
        selected = [eligible[(cursor + offset) % len(eligible)] for offset in range(batch_size)]

        for topic in selected:
            topic_id = str(topic["id"])
            payload = self._get_json(
                AIXBT_TOPIC_PROJECTS_URL.format(topic_id=topic_id),
                headers={"x-api-key": api_key},
                params={"ranking": "trend", "limit": MAX_AIXBT_PROJECTS_PER_TOPIC},
            )
            by_topic[topic_id] = parse_aixbt_topic_projects(payload, topic)

        return {
            "by_topic": by_topic,
            "next_cursor": (cursor + batch_size) % len(eligible),
            "checked_at_utc": utc_now(),
            "last_batch_topic_ids": [str(row["id"]) for row in selected],
            "eligible_topic_count": len(eligible),
        }

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
        if response.status_code == 429:
            raise SourceRateLimited("RSS kaynağı HTTP 429 hız sınırı yanıtı verdi.",
                                    _retry_after_seconds(response.headers.get("Retry-After")))
        if response.status_code == 418:
            raise RuntimeError("RSS kaynağı HTTP 418 hız sınırı yanıtı verdi.")
        response.raise_for_status()
        return response.text

    @staticmethod
    def _mcp_response_payload(response: Any) -> dict[str, Any]:
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in content_type:
            normalized = response.text.replace(chr(13) + chr(10), chr(10))
            for block in reversed(normalized.split(chr(10) + chr(10))):
                data_lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
                if not data_lines:
                    continue
                try:
                    value = json.loads(chr(10).join(data_lines))
                except ValueError:
                    continue
                if isinstance(value, dict) and ("result" in value or "error" in value):
                    return value
            raise RuntimeError("TrendKia MCP SSE yanıtında JSON-RPC sonucu bulunamadı.")
        try:
            value = response.json()
        except ValueError as exc:
            raise RuntimeError("TrendKia MCP geçerli JSON/SSE yanıtı döndürmedi.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("TrendKia MCP yanıtı JSON nesnesi değil.")
        return value

    def _post_mcp(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.mcp_session_id:
            headers["MCP-Session-Id"] = self.mcp_session_id
            headers["MCP-Protocol-Version"] = self.mcp_protocol_version
        response = self.session.post(
            TRENDKIA_MCP_URL,
            data=json.dumps(payload, ensure_ascii=False),
            headers=headers,
            timeout=20,
        )
        if response.status_code == 429:
            raise SourceRateLimited("TrendKia MCP HTTP 429 hız sınırı yanıtı verdi.",
                                    _retry_after_seconds(response.headers.get("Retry-After")))
        session_id = response.headers.get("MCP-Session-Id")
        if session_id:
            self.mcp_session_id = session_id
        if response.status_code == 202 or not response.content:
            return {}
        response.raise_for_status()
        return self._mcp_response_payload(response)

    def _ensure_trendkia(self) -> None:
        if self.trendkia_initialized:
            return
        request_id = self.mcp_request_id
        self.mcp_request_id += 1
        initialized = self._post_mcp({
            "jsonrpc": "2.0", "id": request_id, "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "FirsatKontrolPaneli", "version": "1.0"},
            },
        })
        result = initialized.get("result") if isinstance(initialized, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError("TrendKia MCP initialize el sıkışması tamamlanamadı.")
        self.mcp_protocol_version = str(result.get("protocolVersion") or MCP_PROTOCOL_VERSION)
        self._post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized"})
        list_id = self.mcp_request_id
        self.mcp_request_id += 1
        listed = self._post_mcp({
            "jsonrpc": "2.0", "id": list_id, "method": "tools/list", "params": {},
        })
        if listed.get("error"):
            raise RuntimeError(f"TrendKia MCP araç listesi alınamadı: {str(listed['error'])[:300]}")
        rows = (listed.get("result") or {}).get("tools", [])
        if not isinstance(rows, list):
            raise RuntimeError("TrendKia MCP araç listesi beklenen biçimde değil.")
        self.trendkia_tool_names = {
            str(item.get("name")) for item in rows if isinstance(item, dict) and item.get("name")
        }
        if "list_recent_articles" not in self.trendkia_tool_names:
            raise RuntimeError("TrendKia MCP list_recent_articles aracı bulunamadı.")
        self.trendkia_initialized = True

    def _fetch_trendkia_recent(self) -> list[dict[str, Any]]:
        self._ensure_trendkia()
        call_id = self.mcp_request_id
        self.mcp_request_id += 1
        result = self._post_mcp({
            "jsonrpc": "2.0", "id": call_id, "method": "tools/call",
            "params": {
                "name": "list_recent_articles",
                "arguments": {"limit": 30, "lang": "en"},
            },
        })
        return parse_trendkia_articles(extract_mcp_text(result), now_epoch=self.clock())

    def _due(self, key: str, interval: int) -> bool:
        entry = self.cache.get(key) if isinstance(self.cache.get(key), dict) else {}
        now = self.clock()
        retry_after = _safe_float(entry.get("retry_after_epoch"))
        if retry_after is not None and now < retry_after:
            return False
        last = _safe_float(entry.get("last_attempt_epoch")) or 0.0
        return now - last >= interval

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
                    "retry_after_epoch": None,
                    "rate_limit_failures": 0,
                }
                last_success = success
                last_error = None
                status["status"] = "BAĞLI"
                status["last_success_utc"] = datetime.fromtimestamp(success, timezone.utc).isoformat(timespec="seconds")
                self.logger.info("%s kaynağı yenilendi.", key)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                failure_count = int(_safe_int(entry.get("rate_limit_failures")) or 0)
                updated_entry = {**entry, "last_attempt_epoch": attempted, "last_error": last_error}
                if isinstance(exc, SourceRateLimited):
                    failure_count = min(8, failure_count + 1)
                    exponential_delay = min(6 * 3600, 60 * (2 ** (failure_count - 1)))
                    delay = max(interval, exponential_delay, exc.retry_after_seconds)
                    retry_after_epoch = attempted + delay
                    updated_entry["retry_after_epoch"] = retry_after_epoch
                    updated_entry["rate_limit_failures"] = failure_count
                    status["retry_after_utc"] = datetime.fromtimestamp(
                        retry_after_epoch, timezone.utc
                    ).isoformat(timespec="seconds")
                self.cache[key] = updated_entry
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
        seen_urls: set[str] = set()
        seen_ids: set[str] = set()
        for index, item in enumerate(feeds):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            canonical_url = canonicalize_news_url(url)
            name = str(item.get("name") or f"RSS {index + 1}").strip()
            raw_id = str(item.get("id") or f"rss_{index + 1}").strip().lower()
            feed_id = re.sub(r"[^a-z0-9_-]+", "_", raw_id).strip("_")[:64]
            kind = str(item.get("kind") or "media").strip().lower()
            parsed = urlparse(url)
            if parsed.scheme.lower() != "https" or not parsed.netloc or not canonical_url:
                continue
            if kind not in ("official", "media"):
                kind = "media"
            if not feed_id or feed_id in seen_ids or canonical_url in seen_urls:
                continue
            seen_ids.add(feed_id)
            seen_urls.add(canonical_url)
            result.append({"id": feed_id, "name": name[:100], "url": url, "kind": kind})
        return result[:20]

    def _fetch_dex_market_activity(
        self,
        dex_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Rotate two bounded 30-token pair requests per refresh."""
        candidates = build_dex_token_candidates(dex_rows)
        if not candidates:
            return {
                "pairs": [],
                "token_candidates": [],
                "candidate_token_count": 0,
                "requested_token_count": 0,
                "batch_request_count": 0,
                "chain_batch_count": 0,
                "partial_errors": [],
                "checked_at_utc": utc_now(),
                "scope": "GÜNCEL PROFİL/TOPLULUK AKIŞINDA TOKEN ADRESİ BULUNMADI",
            }

        by_chain: dict[str, list[dict[str, str]]] = {}
        for candidate in candidates:
            by_chain.setdefault(candidate["chain"], []).append(candidate)
        batches: list[tuple[str, list[dict[str, str]]]] = []
        for chain in sorted(by_chain):
            rows = by_chain[chain]
            for offset in range(0, len(rows), MAX_DEX_ACTIVITY_ADDRESSES_PER_BATCH):
                batches.append((chain, rows[offset:offset + MAX_DEX_ACTIVITY_ADDRESSES_PER_BATCH]))
        if not batches:
            return {
                "pairs": [],
                "token_candidates": candidates,
                "candidate_token_count": len(candidates),
                "requested_token_count": 0,
                "batch_request_count": 0,
                "chain_batch_count": 0,
                "partial_errors": [],
                "checked_at_utc": utc_now(),
                "scope": "SORGULANABİLİR ZİNCİR/ADRES GRUBU BULUNAMADI",
            }

        rotation = self.cache.get("dex_market_activity_rotation")
        rotation = rotation if isinstance(rotation, dict) else {}
        rotation_data = rotation.get("data") if isinstance(rotation.get("data"), dict) else {}
        cursor = (_safe_int(rotation_data.get("next_cursor")) or 0) % len(batches)
        batch_count = min(MAX_DEX_ACTIVITY_BATCHES_PER_REFRESH, len(batches))
        selected = [batches[(cursor + index) % len(batches)] for index in range(batch_count)]

        pairs: list[dict[str, Any]] = []
        errors: list[str] = []
        requested_tokens = 0
        completed_requests = 0
        for chain, token_rows in selected:
            addresses = [row["token_address"] for row in token_rows]
            requested_tokens += len(addresses)
            address_path = quote(",".join(addresses), safe=",")
            url = f"{DEX_TOKENS_URL}/{quote(chain, safe='')}/{address_path}"
            try:
                payload = self._get_json(url)
                batch_pairs = parse_dex_market_pairs(payload)
                pairs.extend(batch_pairs)
                completed_requests += 1
                if not batch_pairs:
                    errors.append(f"{chain}: geçerli pair kaydı dönmedi.")
            except Exception as exc:
                errors.append(f"{chain}: {type(exc).__name__}: {str(exc)[:220]}")

        self.cache["dex_market_activity_rotation"] = {
            "data": {
                "next_cursor": (cursor + batch_count) % len(batches),
                "batch_count": len(batches),
                "last_batch_chains": [chain for chain, _rows in selected],
            },
            "last_attempt_epoch": self.clock(),
            "last_success_epoch": self.clock() if completed_requests else (
                _safe_float(rotation.get("last_success_epoch")) or 0.0
            ),
            "last_error": "; ".join(errors)[:500] if errors else None,
        }
        unique_pairs = {}
        for pair in pairs:
            pair_id = str(pair.get("pair_id") or "")
            if pair_id:
                unique_pairs[pair_id] = pair

        if completed_requests == 0 and errors:
            raise RuntimeError("; ".join(errors)[:500])

        return {
            "pairs": list(unique_pairs.values()),
            "token_candidates": candidates,
            "candidate_token_count": len(candidates),
            "requested_token_count": requested_tokens,
            "batch_request_count": completed_requests,
            "selected_batch_count": batch_count,
            "chain_batch_count": len(batches),
            "selected_chains": [chain for chain, _rows in selected],
            "partial_errors": errors,
            "checked_at_utc": utc_now(),
            "scope": "SON DEX PROFİL/TOPLULUK TOKEN LİSTELERİNDEKİ ADRESLER",
        }

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

        tracked_symbols, _universe_status = _load_common_symbols(self.root)
        tracked_symbols = sorted({str(symbol).strip().upper() for symbol in tracked_symbols if str(symbol).strip()})[:200]
        cmc_map_status = _source_status(
            "cmc_id_map",
            role="CMC kanonik coin kimliği; ortak USDT evrenini CMC ID değerleriyle eşleştirir.",
            enabled=bool(tracked_symbols),
            status="BEKLİYOR" if tracked_symbols else "ORTAK USDT EVRENİ YOK — DEVRE DIŞI",
        )
        cmc_map = self._fetch_source(
            "cmc_id_map", SOURCE_INTERVALS["cmc_id_map"],
            lambda: parse_cmc_id_map(self._get_json(CMC_ID_MAP_URL, params={"symbol": ",".join(tracked_symbols)})),
            cmc_map_status, count_fn=lambda value: len(value or []),
        ) if tracked_symbols else []
        statuses["cmc_id_map"] = cmc_map_status
        cmc_lookup = build_cmc_id_lookup(cmc_map or [])
        cmc_ids = sorted({str(row["id"]) for row in cmc_lookup.values() if _safe_int(row.get("id")) is not None})
        cmc_quotes_status = _source_status(
            "cmc_quotes",
            role="CMC Keyless USD fiyat/hacim; benzersiz CMC ID ile eşleşen ortak evren coinleri.",
            enabled=bool(cmc_ids),
            status="BEKLİYOR" if cmc_ids else "BENZERSİZ CMC ID YOK — DEVRE DIŞI",
        )
        cmc_quotes = self._fetch_source(
            "cmc_quotes", SOURCE_INTERVALS["cmc_quotes"],
            lambda: parse_cmc_quotes(self._get_json(
                CMC_QUOTES_URL,
                params={"id": ",".join(cmc_ids[:200]), "convert": "USD", "skip_invalid": "true"},
            )),
            cmc_quotes_status, count_fn=lambda value: len(value or []),
        ) if cmc_ids else []
        statuses["cmc_quotes"] = cmc_quotes_status
        cmc_id_by_symbol = {
            symbol: int(row["id"])
            for symbol, row in build_cmc_id_lookup(cmc_map or []).items()
            if _safe_int(row.get("id")) is not None
        }
        category_list_status = _source_status(
            "cmc_narrative_categories",
            role="CMC ücretsiz Keyless tema kategorileri; kabul edilmiş kripto temalarına uyan kategorileri keşfeder.",
        )
        cmc_categories = self._fetch_source(
            "cmc_narrative_categories",
            SOURCE_INTERVALS["cmc_narrative_categories"],
            lambda: parse_cmc_categories(self._get_json(
                CMC_CATEGORIES_URL, params={"start": 1, "limit": 5000}
            )),
            category_list_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["cmc_narrative_categories"] = category_list_status
        ranked_categories = rank_cmc_narrative_categories(
            cmc_categories or [],
            limit=MAX_CMC_CATEGORY_DETAIL_CANDIDATES,
        )
        category_list_status["narrative_candidate_count"] = len(ranked_categories)
        category_list_status["emerging_candidate_count"] = sum(
            item.get("is_emerging_candidate") is True for item in ranked_categories
        )
        category_list_status["catalogue_scope_limit"] = MAX_CMC_CATEGORY_ITEMS

        batch_key = "cmc_category_details_batch"
        batch_entry = self.cache.get(batch_key)
        batch_entry = batch_entry if isinstance(batch_entry, dict) else {}
        selected_categories = (
            select_cmc_category_detail_batch(ranked_categories, self.cache)
            if ranked_categories and self._due(batch_key, SOURCE_INTERVALS[batch_key])
            else []
        )
        selected_category_ids: set[str] = set()
        if selected_categories:
            batch_success = 0
            batch_errors = []
            for category in selected_categories:
                category_id = str(category.get("id") or "")
                if not category_id:
                    continue
                cache_key = "cmc_category_" + category_id
                category_status = _source_status(
                    cache_key,
                    role=f"CMC kategori coin eşleştirmesi: {category.get('name')}; ortak USDT evreniyle CMC ID doğrulaması.",
                )
                detail = self._fetch_source(
                    cache_key,
                    SOURCE_INTERVALS["cmc_category_detail"],
                    lambda item=category: parse_cmc_category_detail(
                        self._get_json(
                            CMC_CATEGORY_URL,
                            params={"id": str(item.get("id")), "start": 1, "limit": 1000, "convert": "USD"},
                        ),
                        item,
                        cmc_id_by_symbol,
                    ),
                    category_status,
                    count_fn=lambda value: len(value.get("coins", [])) if isinstance(value, dict) else 0,
                )
                category_status["name"] = f"CMC Kategori: {category.get('name') or category_id}"
                statuses[cache_key] = category_status
                selected_category_ids.add(category_id)
                if isinstance(detail, dict) and category_status.get("status") in ("BAĞLI", "ÖNBELLEK"):
                    batch_success += 1
                elif category_status.get("error"):
                    batch_errors.append(str(category_status["error"]))

            previous_success = _safe_float(batch_entry.get("last_success_epoch"))
            batch_attempt = self.clock()
            self.cache[batch_key] = {
                "data": {"last_category_ids": sorted(selected_category_ids)},
                "last_attempt_epoch": batch_attempt,
                "last_success_epoch": batch_attempt if batch_success else previous_success,
                "last_error": "; ".join(batch_errors)[:500] if batch_errors else None,
            }

        # Keep the leading discovery window visible, plus recently detailed long-tail candidates.
        display_categories = list(ranked_categories[:CMC_CATEGORY_DISPLAY_WINDOW])
        display_ids = {str(item.get("id") or "") for item in display_categories}
        now_epoch = self.clock()
        for category in ranked_categories[CMC_CATEGORY_DISPLAY_WINDOW:]:
            if len(display_categories) >= CMC_CATEGORY_MAX_DISPLAY_ITEMS:
                break
            category_id = str(category.get("id") or "")
            if not category_id or category_id in display_ids:
                continue
            entry = self.cache.get("cmc_category_" + category_id)
            entry = entry if isinstance(entry, dict) else {}
            cached_detail = entry.get("data")
            last_success = _safe_float(entry.get("last_success_epoch"))
            if (
                isinstance(cached_detail, dict)
                and last_success is not None
                and 0 <= now_epoch - last_success <= CMC_CATEGORY_RECENT_DETAIL_SECONDS
            ):
                display_categories.append(category)
                display_ids.add(category_id)

        category_details: list[dict[str, Any]] = []
        category_detail_by_id: dict[str, dict[str, Any]] = {}
        for category in display_categories:
            category_id = str(category.get("id") or "")
            if not category_id:
                continue
            cache_key = "cmc_category_" + category_id
            cached_entry = self.cache.get(cache_key)
            cached_entry = cached_entry if isinstance(cached_entry, dict) else {}
            cached_detail = cached_entry.get("data")
            if isinstance(cached_detail, dict):
                merged_detail = {
                    **cached_detail,
                    **category,
                    "coins": cached_detail.get("coins", [])
                    if isinstance(cached_detail.get("coins"), list) else [],
                    "_detail_checked": True,
                }
                category_details.append(merged_detail)
                category_detail_by_id[category_id] = merged_detail

            if cache_key not in statuses:
                last_success = _safe_float(cached_entry.get("last_success_epoch"))
                cached_error = str(cached_entry.get("last_error") or "")
                source_status = (
                    "ÖNBELLEK" if isinstance(cached_detail, dict)
                    else ("ERİŞİLEMEDİ" if cached_error else "SIRADA — KOTA KORUNUYOR")
                )
                category_status = _source_status(
                    cache_key,
                    role=f"CMC kategori coin eşleştirmesi: {category.get('name')}; CMC ID doğrulamalı.",
                    status=source_status,
                )
                category_status["name"] = f"CMC Kategori: {category.get('name')}"
                category_status["item_count"] = (
                    len(cached_detail.get("coins", []))
                    if isinstance(cached_detail, dict) and isinstance(cached_detail.get("coins"), list)
                    else 0
                )
                if last_success:
                    category_status["last_success_utc"] = datetime.fromtimestamp(
                        last_success, timezone.utc
                    ).isoformat(timespec="seconds")
                    category_status["age_seconds"] = round(max(0.0, now_epoch - last_success), 1)
                if cached_error:
                    category_status["error"] = cached_error
                statuses[cache_key] = category_status

        category_events = []
        for category in display_categories:
            category_id = str(category.get("id") or "")
            event_category = category_detail_by_id.get(category_id, category)
            event = build_cmc_category_event(event_category)
            if event is not None:
                category_events.append(event)
        category_coin_rows = [
            coin
            for detail in category_details
            for coin in (detail.get("coins", []) if isinstance(detail.get("coins"), list) else [])
            if isinstance(coin, dict)
        ]
        batch_cache_now = self.cache.get(batch_key)
        batch_cache_now = batch_cache_now if isinstance(batch_cache_now, dict) else {}
        batch_status = _source_status(
            batch_key,
            role="CMC kategori ayrıntı kotası: altı saatte en fazla üç istek; iki öncelikli kategori ve bir geniş evren rotasyon adayı.",
            status=(
                "BAĞLI" if category_details
                else "BEKLİYOR" if ranked_categories
                else "UYGUN KATEGORİ ADAYI BULUNAMADI"
            ),
        )
        batch_status["item_count"] = len(category_details)
        batch_status["candidate_count"] = len(ranked_categories)
        batch_status["priority_window"] = CMC_CATEGORY_PRIORITY_WINDOW
        batch_status["exploration_slots"] = CMC_CATEGORY_EXPLORATION_SLOTS
        attempt_epoch = _safe_float(batch_cache_now.get("last_attempt_epoch")) or 0.0
        success_epoch = _safe_float(batch_cache_now.get("last_success_epoch")) or 0.0
        if attempt_epoch:
            batch_status["last_attempt_utc"] = datetime.fromtimestamp(attempt_epoch, timezone.utc).isoformat(timespec="seconds")
        if success_epoch:
            batch_status["last_success_utc"] = datetime.fromtimestamp(success_epoch, timezone.utc).isoformat(timespec="seconds")
            batch_status["age_seconds"] = round(max(0.0, now_epoch - success_epoch), 1)
        statuses[batch_key] = batch_status

        market_context: dict[str, Any] = {}
        cmc_context_sources = (
            ("cmc_global_metrics", CMC_GLOBAL_METRICS_URL, SOURCE_INTERVALS["cmc_global_metrics"],
             parse_cmc_global_metrics, "Toplam piyasa değeri/hacmi ve BTC/ETH hâkimiyeti; teknik puana girmez.",
             {"convert": "USD"}),
            ("cmc_fear_greed", CMC_FEAR_GREED_URL, SOURCE_INTERVALS["cmc_fear_greed"],
             parse_cmc_fear_greed, "CMC Korku ve Açgözlülük; piyasa bağlamıdır.", None),
            ("cmc_altcoin_season", CMC_ALTCOIN_SEASON_URL, SOURCE_INTERVALS["cmc_altcoin_season"],
             parse_cmc_altcoin_season, "Altcoin Sezon Endeksi; piyasa rejimi bağlamıdır.", None),
            ("cmc100_index", CMC100_INDEX_URL, SOURCE_INTERVALS["cmc100_index"],
             parse_cmc_index_snapshot, "CMC100 piyasa endeksi; genel piyasa bağlamıdır.", None),
            ("cmc20_index", CMC20_INDEX_URL, SOURCE_INTERVALS["cmc20_index"],
             parse_cmc_index_snapshot, "CMC20 piyasa endeksi; genel piyasa bağlamıdır.", None),
        )
        for source_key, source_url, interval, parser, role, params in cmc_context_sources:
            source_status = _source_status(source_key, role=role)
            value = self._fetch_source(
                source_key, interval,
                lambda url=source_url, parse=parser, query=params: parse(self._get_json(url, params=query)),
                source_status, count_fn=lambda item: 1 if isinstance(item, dict) and item else 0,
            )
            statuses[source_key] = source_status
            market_context[source_key] = value if isinstance(value, dict) else {}

        defillama_specs = (
            ("defillama_protocols", DEFILLAMA_PROTOCOLS_URL, SOURCE_INTERVALS["defillama_protocols"],
             parse_defillama_protocols, "Ücretsiz protokol TVL kataloğu; ad ve token sembolüyle ortak USDT evrenine eşleştirilir.", None),
            ("defillama_chains", DEFILLAMA_CHAINS_URL, SOURCE_INTERVALS["defillama_chains"],
             parse_defillama_chains, "Ücretsiz zincir TVL özeti; genel piyasa bağlamıdır.", None),
            ("defillama_stablecoin_chains", DEFILLAMA_STABLECOIN_CHAINS_URL, SOURCE_INTERVALS["defillama_stablecoin_chains"],
             parse_defillama_stablecoin_chains, "Zincirlere göre stablecoin arzı; genel likidite bağlamıdır.", None),
            ("defillama_stablecoin_history", DEFILLAMA_STABLECOIN_HISTORY_URL, SOURCE_INTERVALS["defillama_stablecoin_history"],
             parse_defillama_stablecoin_history, "Toplam stablecoin arzının geçmişi; 24 saat/7 gün/30 gün değişimi için kullanılır.", None),
            ("defillama_dex_overview", DEFILLAMA_DEX_OVERVIEW_URL, SOURCE_INTERVALS["defillama_dex_overview"],
             parse_defillama_overview, "DEX protokollerinin 24 saat/7 gün hacim özeti; grafik yükü hariç tutulur.", {"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true"}),
            ("defillama_fees_overview", DEFILLAMA_FEES_OVERVIEW_URL, SOURCE_INTERVALS["defillama_fees_overview"],
             parse_defillama_overview, "Protokol ücretleri özeti; günlük ücret verisi, grafik yükü hariç tutulur.", {"excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true", "dataType": "dailyFees"}),
        )
        defillama_values: dict[str, Any] = {}
        defillama_status_rows = []
        for source_key, source_url, interval, parser, role, params in defillama_specs:
            source_status = _source_status(source_key, role=role)
            value = self._fetch_source(
                source_key,
                interval,
                lambda url=source_url, parse=parser, query=params: parse(
                    self._get_json(url, params=query)
                ) if parse is not parse_defillama_overview else parse(
                    self._get_json(url, params=query),
                    metric="dailyFees" if "fees" in source_key else "dex_volume",
                ),
                source_status,
                count_fn=lambda item: (
                    len(item.get("protocols", [])) if isinstance(item, dict) and isinstance(item.get("protocols"), list)
                    else len(item or [])
                ),
            )
            statuses[source_key] = source_status
            defillama_values[source_key] = value
            defillama_status_rows.append(source_status)

        defillama_protocols = defillama_values.get("defillama_protocols")
        defillama_protocols = defillama_protocols if isinstance(defillama_protocols, list) else []
        defillama_chains = defillama_values.get("defillama_chains")
        defillama_chains = defillama_chains if isinstance(defillama_chains, list) else []
        defillama_stablecoin_chains = defillama_values.get("defillama_stablecoin_chains")
        defillama_stablecoin_chains = defillama_stablecoin_chains if isinstance(defillama_stablecoin_chains, list) else []
        defillama_stablecoin_history = defillama_values.get("defillama_stablecoin_history")
        defillama_stablecoin_history = defillama_stablecoin_history if isinstance(defillama_stablecoin_history, list) else []
        defillama_dex_overview = defillama_values.get("defillama_dex_overview")
        defillama_dex_overview = defillama_dex_overview if isinstance(defillama_dex_overview, dict) else {}
        defillama_fees_overview = defillama_values.get("defillama_fees_overview")
        defillama_fees_overview = defillama_fees_overview if isinstance(defillama_fees_overview, dict) else {}
        market_context["defillama"] = build_defillama_global_context(
            defillama_protocols,
            defillama_chains,
            defillama_stablecoin_chains,
            defillama_stablecoin_history,
            defillama_dex_overview,
            defillama_fees_overview,
        )
        successful_defillama = [
            row for row in defillama_status_rows
            if row.get("status") in ("BAĞLI", "ÖNBELLEK", "HATA — ÖNCEKİ VERİ VAR", "ESKİ VERİ")
        ]
        parent_defillama = _source_status(
            "defillama",
            role="Ücretsiz, anahtarsız DeFiLlama protokol TVL, zincir TVL, stablecoin arzı, DEX hacmi ve protokol ücretleri.",
            enabled=True,
            status="BAĞLI" if any(row.get("status") == "BAĞLI" for row in successful_defillama)
            else ("ÖNBELLEK" if successful_defillama else "ERİŞİLEMEDİ"),
        )
        parent_defillama["item_count"] = sum(
            int(row.get("item_count") or 0) for row in successful_defillama
        )
        parent_defillama["last_success_utc"] = max(
            (str(row.get("last_success_utc")) for row in successful_defillama if row.get("last_success_utc")),
            default=None,
        )
        parent_defillama["error"] = "; ".join(
            str(row.get("error")) for row in defillama_status_rows if row.get("error")
        )[:500] or None
        statuses["defillama"] = parent_defillama

        trendkia_status = _source_status(
            "trendkia_news",
            role="Herkese açık TrendKia MCP haber akışı; kripto/makro filtreli ve tarih kontrollü.",
        )
        trendkia_events = self._fetch_source(
            "trendkia_news", SOURCE_INTERVALS["trendkia_news"],
            self._fetch_trendkia_recent, trendkia_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["trendkia_news"] = trendkia_status
        rss_events: list[dict[str, Any]] = list(trendkia_events or [])

        dex_profiles_status = _source_status("dex_profiles", role="DEX token/proje profil görünürlüğü; haber doğrulaması değildir.")
        dex_profiles = self._fetch_source(
            "dex_profiles", SOURCE_INTERVALS["dex_profiles"],
            lambda: parse_dex_records(self._get_json(DEX_PROFILES_URL), source_kind="dex_token_profile"),
            dex_profiles_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["dex_profiles"] = dex_profiles_status

        dex_community_status = _source_status("dex_community", role="Topluluk/DEX profil hareketi; bağımsız haber teyidi değildir.")
        dex_community = self._fetch_source(
            "dex_community", SOURCE_INTERVALS["dex_community"],
            lambda: parse_dex_records(self._get_json(DEX_COMMUNITY_URL), source_kind="dex_community_activity"),
            dex_community_status,
            count_fn=lambda value: len(value or []),
        )
        statuses["dex_community"] = dex_community_status

        dex_market_status = _source_status(
            "dex_market_activity",
            role="DEX Screener gerçek pair faaliyeti: son profil/topluluk token adresleri; fiyat, hacim, likidite ve alış/satış.",
        )
        dex_market_activity = self._fetch_source(
            "dex_market_activity",
            SOURCE_INTERVALS["dex_market_activity"],
            lambda: self._fetch_dex_market_activity(
                (dex_profiles or []) + (dex_community or [])
            ),
            dex_market_status,
            count_fn=lambda value: len(value.get("pairs", []))
            if isinstance(value, dict) and isinstance(value.get("pairs"), list) else 0,
        )
        if isinstance(dex_market_activity, dict):
            dex_market_status["candidate_token_count"] = dex_market_activity.get("candidate_token_count", 0)
            dex_market_status["requested_token_count"] = dex_market_activity.get("requested_token_count", 0)
            dex_market_status["batch_request_count"] = dex_market_activity.get("batch_request_count", 0)
            dex_market_status["selected_chains"] = dex_market_activity.get("selected_chains", [])
            dex_market_status["partial_errors"] = dex_market_activity.get("partial_errors", [])
            if dex_market_activity.get("scope") and not dex_market_activity.get("pairs"):
                dex_market_status["status"] = "ADRES/PAIR VERİSİ BEKLENİYOR"
            elif dex_market_activity.get("partial_errors"):
                dex_market_status["status"] = "KISMİ VERİ — BAZI ZİNCİR SORGULARI BAŞARISIZ"
        statuses["dex_market_activity"] = dex_market_status

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

        for feed in self._feed_list():
            key = f"rss_{feed['id']}"
            interval = int(
                self.settings.get("narrative_rss_interval_seconds", RSS_DEFAULT_INTERVAL_SECONDS)
                or RSS_DEFAULT_INTERVAL_SECONDS
            )
            interval = max(RSS_MIN_INTERVAL_SECONDS, min(interval, 86400))
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

        aixbt_key = os.environ.get("AIXBT_API_KEY", "").strip()
        aixbt_mapping_status = _source_status(
            "aixbt_project_mapping",
            role="AIXBT v3 konu→proje eşlemesi; en fazla beş konu/saat, ilk 50 proje/konu, yalnızca keşif kanıtı.",
            enabled=bool(aixbt_key),
            status="BEKLİYOR" if aixbt_key else "API ANAHTARI YOK — DEVRE DIŞI",
        )
        if aixbt_key:
            aixbt_project_mappings = self._fetch_source(
                "aixbt_project_mapping",
                SOURCE_INTERVALS["aixbt_project_mapping"],
                lambda: self._fetch_aixbt_topic_project_mappings(topics or []),
                aixbt_mapping_status,
                count_fn=lambda value: sum(
                    len(item.get("projects", []))
                    for item in (value.get("by_topic", {}).values() if isinstance(value, dict)
                                 and isinstance(value.get("by_topic"), dict) else [])
                    if isinstance(item, dict)
                ),
            )
            if isinstance(aixbt_project_mappings, dict):
                aixbt_mapping_status["topics_scanned"] = len(aixbt_project_mappings.get("by_topic", {}))
                aixbt_mapping_status["topics_in_last_batch"] = len(aixbt_project_mappings.get("last_batch_topic_ids", []))
                if not aixbt_project_mappings.get("eligible_topic_count"):
                    aixbt_mapping_status["status"] = "GEÇERLİ TOPIC ID YOK — SORGULANMADI"
        else:
            aixbt_project_mappings = None
            aixbt_mapping_status["item_count"] = 0
        aixbt_mapping_status["name"] = "AIXBT Konu→Proje"
        statuses["aixbt_project_mapping"] = aixbt_mapping_status
        statuses["x_api"] = _source_status(
            "x_api",
            role="X paylaşım akışı; bu sürümde API bağlantısı veya veri toplama yok.",
            enabled=False,
            status="BAĞLI DEĞİL — ENTEGRASYON YOK",
        )
        statuses["reddit"] = _source_status(
            "reddit",
            role="Reddit Data API; başvuru gönderildi ancak açık erişim onayı ve OAuth bilgileri bekleniyor.",
            enabled=False,
            status="ONAY BEKLİYOR — API ÇAĞRISI YOK",
        )
        statuses["the_fly"] = _source_status(
            "the_fly",
            role="Ücretsiz geliştirici planı olsa da içerik toplama/birleştirme kullanım izni netleşmedi; otomatik çağrı yapılmaz.",
            enabled=False,
            status="KULLANIM İZNİ BEKLİYOR — API ÇAĞRISI YOK",
        )
        statuses["investing_calendar"] = _source_status(
            "investing_calendar",
            role="Investing.com ekonomik takvimi resmi Türkçe sayfada harici tarayıcıda açılır; veri otomatik çekilmez.",
            enabled=False,
            status="HARİCİ TAKVİM — OTOMATİK VERİ AKTARIMI YOK",
        )
        return statuses, rss_events, {
            "topics": topics or [],
            "aixbt_project_mappings": aixbt_project_mappings,
            "cmc": cmc or [],
            "cmc_id_map": cmc_map or [],
            "cmc_quotes": cmc_quotes or [],
            "cmc_category_details": category_details,
            "cmc_category_events": category_events,
            "cmc_category_coins": category_coin_rows,
            "market_context": market_context,
            "defillama": {
                "protocols": defillama_protocols,
                "chains": defillama_chains,
                "stablecoin_chains": defillama_stablecoin_chains,
                "stablecoin_history": defillama_stablecoin_history,
                "dex_overview": defillama_dex_overview,
                "fees_overview": defillama_fees_overview,
            },
            "dex_profiles": dex_profiles or [],
            "dex_community": dex_community or [],
            "dex_market_activity": dex_market_activity if isinstance(dex_market_activity, dict) else {},
            "coingecko": cg or {},
        }

    def _save_santiment_observations(
        self,
        slug_map: dict[str, str],
        active_rows: dict[str, list[dict[str, Any]]],
        dev_rows: dict[str, list[dict[str, Any]]],
    ) -> dict[str, int]:
        """Persist provider timestamped Santiment samples once, retaining collection timestamps."""
        counts = {"active_addresses_24h": 0, "dev_activity": 0}
        if not slug_map:
            return counts
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        observed_now = utc_now()
        metrics = (
            ("active_addresses_24h", active_rows),
            ("dev_activity", dev_rows),
        )
        with sqlite3.connect(self.history_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS santiment_observations (
                    asset_slug TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    sample_at_utc TEXT NOT NULL,
                    value REAL NOT NULL,
                    computed_at_utc TEXT,
                    first_observed_at_utc TEXT NOT NULL,
                    last_observed_at_utc TEXT NOT NULL,
                    PRIMARY KEY (asset_slug, metric, sample_at_utc)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_santiment_observations_symbol_metric_time
                ON santiment_observations(symbol, metric, sample_at_utc)
            """)
            for symbol, slug in slug_map.items():
                for metric, rows_by_slug in metrics:
                    for point in rows_by_slug.get(slug, []):
                        if not isinstance(point, dict):
                            continue
                        sample_at = str(point.get("datetime") or "").strip()
                        value = _safe_float(point.get("value"))
                        if not sample_at or value is None:
                            continue
                        computed_at = str(point.get("computed_at") or "").strip() or None
                        connection.execute(
                            """
                            INSERT INTO santiment_observations
                            (asset_slug, symbol, metric, sample_at_utc, value,
                             computed_at_utc, first_observed_at_utc, last_observed_at_utc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(asset_slug, metric, sample_at_utc) DO UPDATE SET
                                symbol = excluded.symbol,
                                value = excluded.value,
                                computed_at_utc = COALESCE(
                                    excluded.computed_at_utc,
                                    santiment_observations.computed_at_utc
                                ),
                                last_observed_at_utc = excluded.last_observed_at_utc
                            """,
                            (
                                slug, symbol, metric, sample_at, value, computed_at,
                                observed_now, observed_now,
                            ),
                        )
                        counts[metric] += 1
        return counts

    def _load_santiment_observation_history(
        self,
        slug: str,
        *,
        active_limit: int = 72,
        dev_limit: int = 30,
    ) -> dict[str, Any]:
        """Read the most recent provider samples and their first/last local collection times."""
        if not self.history_path.exists():
            return {}
        metrics = (
            ("active_addresses_24h", max(1, int(active_limit))),
            ("dev_activity", max(1, int(dev_limit))),
        )
        history: dict[str, Any] = {
            "asset_slug": slug,
            "active_addresses_24h": [],
            "dev_activity": [],
            "tracked_since_utc": None,
            "last_collected_at_utc": None,
        }
        try:
            with sqlite3.connect(self.history_path) as connection:
                for metric, limit in metrics:
                    rows = connection.execute(
                        """
                        SELECT sample_at_utc, value, computed_at_utc,
                               first_observed_at_utc, last_observed_at_utc
                        FROM santiment_observations
                        WHERE asset_slug=? AND metric=?
                        ORDER BY sample_at_utc DESC
                        LIMIT ?
                        """,
                        (slug, metric, limit),
                    ).fetchall()
                    rows.reverse()
                    history[metric] = [
                        {
                            "datetime": row[0],
                            "value": float(row[1]),
                            "computed_at": row[2],
                            "first_observed_at_utc": row[3],
                            "last_observed_at_utc": row[4],
                        }
                        for row in rows
                    ]
                metadata = connection.execute(
                    """
                    SELECT MIN(first_observed_at_utc), MAX(last_observed_at_utc),
                           COUNT(*)
                    FROM santiment_observations
                    WHERE asset_slug=?
                    """,
                    (slug,),
                ).fetchone()
            if metadata:
                history["tracked_since_utc"] = metadata[0]
                history["last_collected_at_utc"] = metadata[1]
                history["observation_count"] = int(metadata[2] or 0)
            history["active_point_count"] = len(history["active_addresses_24h"])
            history["dev_point_count"] = len(history["dev_activity"])
        except sqlite3.Error:
            self.logger.exception("Santiment gözlem geçmişi okunamadı: %s", slug)
            return {}
        return history if history.get("observation_count", 0) else {}

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
            cached_projects = self._cached_data("santiment_project_catalog")
            candidate_symbols = rank_santiment_candidate_symbols(events, MAX_SANTIMENT_SYMBOLS)
            cached_slug_map = map_santiment_projects(
                cached_projects if isinstance(cached_projects, list) else [],
                candidate_symbols,
                aliases,
            )
            history_only: dict[str, dict[str, Any]] = {}
            for symbol, slug in cached_slug_map.items():
                history = self._load_santiment_observation_history(slug)
                if history:
                    history_only[symbol] = {
                        "asset_slug": slug,
                        "observation_history": history,
                    }
            statuses["santiment_history"] = _source_status(
                "santiment_history",
                role="Önceden kaydedilmiş Santiment örnekleri; yerel SQLite geçmişi, API anahtarından bağımsız okunur.",
                enabled=True,
                status="KAYITLI GEÇMİŞ VAR" if history_only else "HENÜZ KAYIT YOK",
            )
            statuses["santiment_history"]["item_count"] = sum(
                item["observation_history"].get("observation_count", 0)
                for item in history_only.values()
            )
            return history_only
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
        history_status = _source_status(
            "santiment_history",
            role="Yerel SQLite gözlem geçmişi; sağlayıcının zaman damgalı örneklerini saklar ve yinelenen örnekleri günceller.",
        )
        try:
            saved_counts = self._save_santiment_observations(slug_map, active_rows, dev_rows)
            history_status["status"] = "KAYDEDİLDİ" if sum(saved_counts.values()) else "YENİ ÖRNEK YOK"
            history_status["item_count"] = sum(saved_counts.values())
            history_status["active_addresses_points"] = saved_counts["active_addresses_24h"]
            history_status["dev_activity_points"] = saved_counts["dev_activity"]
        except (OSError, sqlite3.Error) as exc:
            history_status["status"] = "KAYIT HATASI"
            history_status["error"] = str(exc)[:500]
            self.logger.exception("Santiment gözlem geçmişi kaydedilemedi.")
        statuses["santiment_history"] = history_status

        result: dict[str, dict[str, Any]] = {}
        for symbol, slug in slug_map.items():
            summary = summarize_santiment_asset(slug, active_rows, dev_rows)
            observation_history = self._load_santiment_observation_history(slug)
            if summary or observation_history:
                summary = dict(summary)
                summary["asset_slug"] = slug
                if observation_history:
                    summary["observation_history"] = observation_history
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
        category_events: list[dict[str, Any]] | None = None,
        aixbt_project_mappings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        events: dict[str, dict[str, Any]] = {}
        mapping_root = aixbt_project_mappings if isinstance(aixbt_project_mappings, dict) else {}
        mappings_by_topic = mapping_root.get("by_topic")
        mappings_by_topic = mappings_by_topic if isinstance(mappings_by_topic, dict) else {}
        for topic in topics:
            title = str(topic.get("name") or "").strip()
            summary = str(topic.get("summary") or "")
            text = f"{title} {summary}"
            key = "aixbt:" + str(topic.get("id") or _event_id(title))
            matched_by_symbol = {
                str(match.get("symbol") or "").upper(): dict(match)
                for match in match_symbols(text, symbols, aliases)
            }
            mapping = mappings_by_topic.get(str(topic.get("id") or ""), {})
            project_associations = mapping.get("projects", []) if isinstance(mapping, dict) else []
            for project in project_associations:
                if not isinstance(project, dict):
                    continue
                project_text = f"{project.get('name') or ''} {project.get('slug') or ''}"
                for match in match_symbols(project_text, symbols, aliases):
                    if match.get("confidence") != "YÜKSEK":
                        continue
                    symbol = str(match.get("symbol") or "").upper()
                    row = matched_by_symbol.setdefault(symbol, dict(match))
                    association = {
                        "topic_id": mapping.get("topic_id"),
                        "topic_name": mapping.get("topic_name"),
                        "topic_rank": mapping.get("topic_rank"),
                        "project_id": project.get("project_id"),
                        "project_name": project.get("name"),
                        "project_slug": project.get("slug"),
                        "observed_posts": project.get("observed_posts"),
                        "distinct_authors": project.get("distinct_authors"),
                        "share_of_topic_posts": project.get("share_of_topic_posts"),
                        "first_observed_at": project.get("first_observed_at"),
                        "last_observed_at": project.get("last_observed_at"),
                        "mapping_checked_at_utc": mapping.get("checked_at_utc"),
                    }
                    associations = row.setdefault("aixbt_topic_associations", [])
                    if association not in associations:
                        associations.append(association)
            matches = list(matched_by_symbol.values())
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
                "project_association_count": len(project_associations),
                "evidence_class": "NARATİF KEŞFİ",
            }

        news_event_keys: list[str] = []
        for raw in rss_events:
            title = str(raw.get("title") or "").strip()
            if not title:
                continue
            summary = str(raw.get("summary") or "")
            published_at = str(raw.get("published_at") or "")
            text = f"{title} {summary}"
            matches = match_symbols(text, symbols, aliases)
            match_symbols_set = {
                str(match.get("symbol") or "").upper()
                for match in matches if isinstance(match, dict) and match.get("symbol")
            }
            canonical_url = canonicalize_news_url(
                str(raw.get("canonical_url") or raw.get("url") or "")
            )
            normalized_title = normalize_news_title(title)
            fingerprint = _event_id("url:" + canonical_url) if canonical_url else _event_id("title:" + normalized_title)
            proposed_key = "news:" + fingerprint

            duplicate_key = proposed_key if proposed_key in events else None
            duplicate_reason = "URL" if duplicate_key and canonical_url else (
                "BAŞLIK" if duplicate_key else ""
            )
            if duplicate_key is None:
                for existing_key in news_event_keys:
                    existing = events.get(existing_key, {})
                    existing_url = canonicalize_news_url(
                        str(existing.get("canonical_url") or existing.get("url") or "")
                    )
                    if canonical_url and existing_url and canonical_url == existing_url:
                        duplicate_key = existing_key
                        duplicate_reason = "URL"
                        break
                    if normalize_news_title(str(existing.get("title") or "")) == normalized_title:
                        duplicate_key = existing_key
                        duplicate_reason = "BAŞLIK"
                        break
                    existing_symbols = {
                        str(match.get("symbol") or "").upper()
                        for match in existing.get("symbols", [])
                        if isinstance(match, dict) and match.get("symbol")
                    }
                    if _news_headlines_are_near_duplicates(
                        title,
                        str(existing.get("title") or ""),
                        published_at,
                        str(existing.get("published_at") or ""),
                        match_symbols_set,
                        existing_symbols,
                    ):
                        duplicate_key = existing_key
                        duplicate_reason = "BENZER BAŞLIK"
                        break

            if duplicate_key is not None:
                # Republished copies remain visible as publisher metadata, not separate
                # independent news evidence or additional narrative score components.
                existing = events[duplicate_key]
                source_id = str(raw.get("source_id") or "rss")
                source_name = str(raw.get("source_name") or source_id)
                publisher_ids = existing.setdefault(
                    "publisher_ids",
                    [str(existing.get("source_id") or "")],
                )
                if source_id and source_id not in publisher_ids:
                    publisher_ids.append(source_id)
                republishers = existing.setdefault("republishers", [])
                if source_name and source_name != existing.get("source_name") and source_name not in republishers:
                    republishers.append(source_name)
                alternate_urls = existing.setdefault("alternate_urls", [])
                raw_url = str(raw.get("url") or "")
                if raw_url and raw_url != existing.get("url") and raw_url not in alternate_urls:
                    alternate_urls.append(raw_url[:1000])
                existing["duplicate_match"] = duplicate_reason
                existing["duplicate_publisher_count"] = max(0, len(publisher_ids) - 1)
                if len(summary) > len(str(existing.get("summary") or "")):
                    existing["summary"] = summary[:1800]
                if not existing.get("published_at") and published_at:
                    existing["published_at"] = published_at
                continue

            themes = infer_themes(text)
            if not themes:
                themes = [f"{match['symbol']} Proje Gelişmeleri" for match in matches[:3]]
            key = proposed_key
            # Hash collisions or a previous discovery event with the same identifier
            # must not overwrite a different event.
            if key in events:
                key = "news:" + _event_id(key + "|" + normalized_title + "|" + str(raw.get("source_id") or ""))
            event = {
                "event_id": key,
                "title": title,
                "summary": summary[:1800],
                "url": str(raw.get("url") or "")[:1000],
                "canonical_url": canonical_url,
                "source_id": str(raw.get("source_id") or "rss"),
                "source_name": str(raw.get("source_name") or "RSS"),
                "source_kind": str(raw.get("source_kind") or "media"),
                "published_at": published_at[:120],
                "symbols": matches,
                "themes": themes or ["Piyasa Gelişmeleri"],
                "publisher_ids": [str(raw.get("source_id") or "rss")],
                "republishers": [],
                "alternate_urls": [],
                "duplicate_publisher_count": 0,
                "evidence_class": "HABER/KATALİZÖR",
            }
            events[key] = event
            news_event_keys.append(key)
        for category_event in category_events or []:
            if isinstance(category_event, dict):
                event_id = str(category_event.get("event_id") or "")
                if event_id:
                    events[event_id] = dict(category_event)
        return list(events.values())

    def _market_map(
        self,
        market_rows: list[dict[str, Any]],
        dex_rows: list[dict[str, Any]],
        coingecko: Any,
        symbols: list[str],
        aliases: dict[str, list[str]],
        dex_market_activity: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        allowed = set(symbols)
        # Category detail snapshots can be older than the hourly CMC quote feed.
        # Merge only populated fields so the latest data (passed last) takes precedence.
        for row in market_rows:
            base = str(row.get("symbol") or "").upper()
            if base not in allowed:
                continue
            item = result.setdefault(base, {"symbol": base})
            fields = {
                "symbol": base,
                "name": row.get("name"),
                "percent_change_24h": row.get("percent_change_24h"),
                "volume_24h": row.get("volume_24h"),
                "volume_change_24h": row.get("volume_change_24h"),
                "cmc_rank": row.get("rank"),
                "market_activity_source": "CoinMarketCap anahtarsız listeleme",
            }
            item.update({key: value for key, value in fields.items() if value is not None})

        for row in dex_rows:
            text = " ".join(str(row.get(key) or "") for key in ("symbol", "name", "description"))
            for match in match_symbols(text, symbols, aliases):
                if match.get("confidence") != "YÜKSEK":
                    continue
                item = result.setdefault(match["symbol"], {"symbol": match["symbol"]})
                item["dex_activity"] = True
                item["dex_chain"] = row.get("chain") or item.get("dex_chain")

        if isinstance(coingecko, dict):
            for item in coingecko.get("coins", []) if isinstance(coingecko.get("coins"), list) else []:
                coin = item.get("item") if isinstance(item, dict) else None
                if not isinstance(coin, dict):
                    continue
                project_text = " ".join(
                    str(coin.get(key) or "") for key in ("name", "symbol")
                )
                for match in match_symbols(project_text, symbols, aliases):
                    if match.get("confidence") != "YÜKSEK":
                        continue
                    result.setdefault(match["symbol"], {"symbol": match["symbol"]})[
                        "coingecko_trending"
                    ] = True

        dex_root = dex_market_activity if isinstance(dex_market_activity, dict) else {}
        dex_pairs = dex_root.get("pairs") if isinstance(dex_root.get("pairs"), list) else []
        dex_candidates = build_dex_token_candidates(
            dex_root.get("token_candidates", [])
            if isinstance(dex_root.get("token_candidates"), list) else []
        )
        dex_aggregates = aggregate_dex_market_activity(
            dex_pairs, dex_candidates, symbols, aliases,
        ) if dex_candidates and dex_pairs else {}
        for symbol, metrics in dex_aggregates.items():
            item = result.setdefault(symbol, {"symbol": symbol})
            item["dex_market_activity"] = metrics
            item["dex_activity"] = True
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
                    "aixbt_rank": None, "aixbt_post_count": 0, "aixbt_author_count": 0,
                    "category_momentum_scores": [],
                    "aixbt_project_associations": {},
                })
                group["events"].append(event)
                source_id = str(event.get("source_id") or "")
                if event.get("source_kind") in ("official", "media"):
                    group["news_sources"].add(source_id)
                elif event.get("source_kind") == "topic_discovery":
                    # AIXBT and CMC categories are discovery sources, not editorial publishers.
                    group["discovery_sources"].add(source_id)
                    rank = _safe_int(event.get("rank"))
                    if source_id == "aixbt_topics" and rank and (
                        group["aixbt_rank"] is None or rank < group["aixbt_rank"]
                    ):
                        group["aixbt_rank"] = rank
                    if source_id == "aixbt_topics":
                        group["aixbt_post_count"] = max(
                            group["aixbt_post_count"], _safe_int(event.get("post_count")) or 0
                        )
                        group["aixbt_author_count"] = max(
                            group["aixbt_author_count"], _safe_int(event.get("author_count")) or 0
                        )
                    category_score = _safe_float(event.get("category_momentum_score"))
                    if category_score is not None:
                        group["category_momentum_scores"].append(category_score)
                for match in event.get("symbols", []):
                    base = str(match.get("symbol") or "").upper()
                    if base:
                        group["coins"][base] = max(
                            group["coins"].get(base, 0),
                            2 if match.get("confidence") == "YÜKSEK" else 1,
                        )
                        associations = match.get("aixbt_topic_associations")
                        if isinstance(associations, list) and associations:
                            target = group["aixbt_project_associations"].setdefault(base, [])
                            for association in associations:
                                if isinstance(association, dict) and association not in target:
                                    target.append(association)

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
            ) if previous_row.get("score_version") == 2 else None
            components: dict[str, float] = {}

            if topic_rank is not None:
                components["aixbt_topic_rank"] = round(max(0.0, 100.0 - (topic_rank - 1) * 4.0), 1)
            activity_scores = []
            if group["aixbt_post_count"]:
                posts = group["aixbt_post_count"]
                activity_scores.append(100.0 * posts / (posts + 100.0))
            if group["aixbt_author_count"]:
                authors = group["aixbt_author_count"]
                activity_scores.append(100.0 * authors / (authors + 25.0))
            if activity_scores:
                components["aixbt_community_activity"] = round(
                    sum(activity_scores) / len(activity_scores), 1
                )
            if group["category_momentum_scores"]:
                components["category_market_momentum"] = round(
                    sum(group["category_momentum_scores"]) / len(group["category_momentum_scores"]), 1
                )
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

            discovery_coin_count = sum(
                bool(market_map.get(symbol, {}).get("dex_activity"))
                or bool(market_map.get(symbol, {}).get("coingecko_trending"))
                for symbol in symbols
            )
            if symbols and discovery_coin_count:
                components["market_discovery_activity"] = round(
                    min(100.0, 100.0 * discovery_coin_count / len(symbols)), 1
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
            diverse_discovery = len(discovery_sources) >= 2 or (bool(sources) and bool(discovery_sources))
            confidence = (
                "YÜKSEK" if len(sources) >= 3 and len(group_events) >= 3 else
                "ORTA" if len(sources) >= 2 or diverse_discovery else "DÜŞÜK"
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
                "score_version": 2,
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
                "aixbt_project_associations": group["aixbt_project_associations"],
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
                    "aixbt_topic_associations": [],
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
                for association in group["aixbt_project_associations"].get(symbol, []):
                    if association not in watch["aixbt_topic_associations"]:
                        watch["aixbt_topic_associations"].append(association)
                watch["sources"].update(sources)
                watch["discovery_sources"].update(discovery_sources)
                if confidence == "YÜKSEK" or (confidence == "ORTA" and watch["confidence"] == "DÜŞÜK"):
                    watch["confidence"] = confidence

        # Actual DEX pair activity can create a separate early-watch row.
        # It is market data, not editorial news or a technical trading signal.
        for symbol, market_row in market_map.items():
            dex_activity = market_row.get("dex_market_activity") if isinstance(market_row, dict) else None
            if not isinstance(dex_activity, dict) or not dex_activity.get("pair_count"):
                continue
            if symbol not in early_watch:
                early_watch[symbol] = {
                    "symbol": symbol,
                    "narrative_score": None,
                    "phase": "BELİRSİZ",
                    "interest_direction": "İLK GÖZLEM",
                    "data_freshness_seconds": None,
                    "narratives": ["DEX gerçek piyasa faaliyeti"],
                    "sources": set(),
                    "discovery_sources": {"dex_market_activity"},
                    "aixbt_topic_associations": [],
                    "confidence": "DÜŞÜK",
                    "market_activity": market_row,
                    "reason": (
                        "Gerçek DEX pair verisinde fiyat, hacim, likidite ve alış/satış faaliyeti görüldü. "
                        "Bu piyasa keşif kaydıdır; haber teyidi, teknik aday veya güçlü fırsat değildir."
                    ),
                }

        for symbol, market_row in market_map.items():
            defi_protocols = market_row.get("defillama_protocols") if isinstance(market_row, dict) else None
            if not isinstance(defi_protocols, list) or not defi_protocols:
                continue
            if symbol in early_watch:
                early_watch[symbol]["discovery_sources"].add("defillama_protocols")
                if "DeFiLlama protokol verisi" not in early_watch[symbol]["narratives"]:
                    early_watch[symbol]["narratives"].append("DeFiLlama protokol verisi")
                continue
            early_watch[symbol] = {
                "symbol": symbol,
                "narrative_score": None,
                "phase": "BELİRSİZ",
                "interest_direction": "İLK GÖZLEM",
                "data_freshness_seconds": None,
                "narratives": ["DeFiLlama protokol verisi"],
                "sources": set(),
                "discovery_sources": {"defillama_protocols"},
                "aixbt_topic_associations": [],
                "confidence": "DÜŞÜK",
                "market_activity": market_row,
                "reason": (
                    "DeFiLlama'da ortak USDT evrenindeki coinle tam adı veya tekil protokol token sembolü eşleşen "
                    "protokol verisi bulundu. Bu bir piyasa bağlamı kaydıdır; haber teyidi veya işlem sinyali değildir."
                ),
            }

        for watch in early_watch.values():
            watch["sources"] = sorted(watch["sources"])
            watch["discovery_sources"] = sorted(watch["discovery_sources"])
            watch["narratives"] = sorted(set(watch["narratives"]))
            watch["aixbt_topic_associations"].sort(
                key=lambda item: (
                    _safe_int(item.get("topic_rank")) or 999,
                    -(_safe_int(item.get("observed_posts")) or 0),
                    str(item.get("project_name") or ""),
                )
            )

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


    def _build_technical_candidate_research(
        self,
        bridge_state: dict[str, Any],
        events: list[dict[str, Any]],
        early_watch: list[dict[str, Any]],
        source_statuses: dict[str, Any],
        market_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a source-separated research bundle for each fresh A/B/C technical candidate."""
        bridge_state = bridge_state if isinstance(bridge_state, dict) else {}
        market_map = market_map if isinstance(market_map, dict) else {}
        generated = str(bridge_state.get("generated_at_utc") or "").strip()
        try:
            parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            bridge_age = max(0.0, self.clock() - parsed.timestamp())
        except (TypeError, ValueError, OverflowError):
            bridge_age = None
        bridge_fresh = bridge_age is not None and bridge_age <= MOTOR_BRIDGE_MAX_AGE_SECONDS
        raw_candidates = bridge_state.get("technical_candidates")
        raw_candidates = raw_candidates if isinstance(raw_candidates, list) else []

        watch_by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in early_watch
            if isinstance(item, dict) and item.get("symbol")
        }
        events_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            for match in event.get("symbols", []) if isinstance(event.get("symbols"), list) else []:
                if not isinstance(match, dict):
                    continue
                symbol = str(match.get("symbol") or "").strip().upper()
                if symbol:
                    events_by_symbol.setdefault(symbol, []).append(event)

        source_groups = {
            "haber": lambda key: key.startswith("rss_") or key == "trendkia_news",
            "kesif": lambda key: key in (
                "aixbt_topics", "aixbt_project_mapping", "cmc_narrative_categories",
            ) or key.startswith("cmc_category_"),
            "dex": lambda key: key in ("dex_profiles", "dex_community", "dex_market_activity"),
            "defillama": lambda key: key == "defillama" or key.startswith("defillama_"),
            "santiment": lambda key: key == "santiment" or key.startswith("santiment_"),
            "piyasa": lambda key: key in (
                "cmc_market_activity", "cmc_id_map", "cmc_quotes", "coingecko_trending",
            ),
        }
        source_coverage: dict[str, dict[str, Any]] = {}
        checked_sources: list[str] = []
        checked_market_sources: list[str] = []
        for key, source_row in source_statuses.items():
            if not isinstance(source_row, dict):
                continue
            group = next((name for name, predicate in source_groups.items() if predicate(key)), None)
            if group is None or source_row.get("enabled") is False:
                continue
            status = str(source_row.get("status") or "")
            item_count = _safe_int(source_row.get("item_count")) or 0
            usable = status in ("BAĞLI", "ÖNBELLEK") and item_count > 0
            source_coverage[key] = {
                "group": group,
                "name": str(source_row.get("name") or key),
                "status": status or "DURUM BİLİNMİYOR",
                "usable": usable,
                "item_count": item_count,
                "last_success_utc": source_row.get("last_success_utc"),
                "age_seconds": _safe_float(source_row.get("age_seconds")),
                "error": str(source_row.get("error") or "")[:240] or None,
            }
            if usable:
                display_name = str(source_row.get("name") or key)
                if group in ("haber", "kesif") and display_name not in checked_sources:
                    checked_sources.append(display_name)
                if group in ("dex", "defillama", "santiment", "piyasa") and display_name not in checked_market_sources:
                    checked_market_sources.append(display_name)

        result_rows = []
        seen_symbols: set[str] = set()
        counts = {
            "candidates_with_narrative": 0,
            "candidates_with_news": 0,
            "candidates_with_dex_activity": 0,
            "candidates_with_defi_activity": 0,
            "candidates_with_santiment_data": 0,
            "candidates_with_market_data": 0,
            "candidates_with_any_evidence": 0,
        }

        for candidate in raw_candidates[:100]:
            if not isinstance(candidate, dict):
                continue
            symbol = str(candidate.get("symbol") or "").strip().upper()
            if not symbol or len(symbol) > 32 or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            # Never combine an old technical handoff with new source evidence as though both
            # describe the same observation time. The bundle exposes freshness explicitly.
            matches = events_by_symbol.get(symbol, []) if bridge_fresh else []
            watch = watch_by_symbol.get(symbol, {}) if bridge_fresh else {}
            themes = watch.get("narratives") if isinstance(watch.get("narratives"), list) else []
            coin_market = market_map.get(symbol, {})
            coin_market = coin_market if isinstance(coin_market, dict) else {}

            news_sources = sorted({
                str(event.get("source_name") or event.get("source_id") or "")
                for event in matches
                if event.get("source_kind") in ("official", "media")
                and (event.get("source_name") or event.get("source_id"))
            })
            discovery_sources = sorted({
                str(event.get("source_name") or event.get("source_id") or "")
                for event in matches
                if event.get("source_kind") == "topic_discovery"
                and (event.get("source_name") or event.get("source_id"))
            })

            matching_events = []
            for event in matches[:8]:
                matching_events.append({
                    "event_id": event.get("event_id"),
                    "title": str(event.get("title") or "")[:220],
                    "source_name": event.get("source_name"),
                    "source_kind": event.get("source_kind"),
                    "published_at": event.get("published_at"),
                    "url": event.get("url"),
                    "themes": event.get("themes", [])[:5]
                    if isinstance(event.get("themes"), list) else [],
                    "republishers": event.get("republishers", [])[:5]
                    if isinstance(event.get("republishers"), list) else [],
                    "evidence_class": event.get("evidence_class"),
                })

            # Market evidence is separate from news/discovery evidence and is never scored.
            dex = coin_market.get("dex_market_activity")
            dex = dex if isinstance(dex, dict) else None
            defi_rows = coin_market.get("defillama_protocols")
            defi_rows = defi_rows if isinstance(defi_rows, list) else []
            santiment = coin_market.get("santiment")
            santiment = santiment if isinstance(santiment, dict) else None

            cmc_evidence = {}
            for field in (
                "name", "percent_change_24h", "volume_24h",
                "volume_change_24h", "cmc_rank", "market_activity_source",
            ):
                if coin_market.get(field) is not None:
                    cmc_evidence[field] = coin_market.get(field)

            dex_evidence = None
            if dex:
                dex_evidence = {
                    "pair_count": _safe_int(dex.get("pair_count")) or 0,
                    "chain_count": _safe_int(dex.get("chain_count")) or 0,
                    "chains": list(dex.get("chains", []))[:12]
                    if isinstance(dex.get("chains"), list) else [],
                    "liquidity_usd": _safe_float(dex.get("liquidity_usd")),
                    "volume_usd_m5": _safe_float(dex.get("volume_usd_m5")),
                    "volume_usd_h1": _safe_float(dex.get("volume_usd_h1")),
                    "volume_usd_h6": _safe_float(dex.get("volume_usd_h6")),
                    "volume_usd_h24": _safe_float(dex.get("volume_usd_h24")),
                    "buys_h24": _safe_int(dex.get("buys_h24")),
                    "sells_h24": _safe_int(dex.get("sells_h24")),
                    "transactions_h24": _safe_int(dex.get("transactions_h24")),
                    "buy_sell_ratio_h24": _safe_float(dex.get("buy_sell_ratio_h24")),
                    "current_price_usd": _safe_float(dex.get("current_price_usd")),
                    "price_change_24h_pct": _safe_float(dex.get("price_change_24h_pct")),
                    "top_pairs": [
                        {
                            key: pair.get(key)
                            for key in (
                                "chain", "dex_id", "pair_address", "url", "base_symbol",
                                "quote_symbol", "liquidity_usd", "volume_usd_h24",
                                "buys_h24", "sells_h24", "price_change_24h_pct",
                            )
                        }
                        for pair in (dex.get("top_pairs") if isinstance(dex.get("top_pairs"), list) else [])[:3]
                        if isinstance(pair, dict)
                    ],
                }

            defi_evidence = []
            for protocol in defi_rows[:3]:
                if not isinstance(protocol, dict):
                    continue
                defi_evidence.append({
                    "name": protocol.get("name"),
                    "slug": protocol.get("slug"),
                    "symbol": protocol.get("symbol"),
                    "category": protocol.get("category"),
                    "tvl_usd": _safe_float(protocol.get("tvl_usd")),
                    "tvl_change_1d_pct": _safe_float(protocol.get("tvl_change_1d_pct")),
                    "tvl_change_7d_pct": _safe_float(protocol.get("tvl_change_7d_pct")),
                    "dex_volume_24h_usd": _safe_float(protocol.get("dex_volume_24h_usd")),
                    "dex_volume_7d_usd": _safe_float(protocol.get("dex_volume_7d_usd")),
                    "fees_24h_usd": _safe_float(protocol.get("fees_24h_usd")),
                    "fees_7d_usd": _safe_float(protocol.get("fees_7d_usd")),
                    "chains": list(protocol.get("chains", []))[:8]
                    if isinstance(protocol.get("chains"), list) else [],
                })

            santiment_evidence = None
            if santiment:
                santiment_evidence = {
                    "asset_slug": santiment.get("asset_slug"),
                    "active_addresses_24h": _safe_float(santiment.get("active_addresses_24h")),
                    "active_addresses_change_24h_pct": _safe_float(santiment.get("active_addresses_change_24h_pct")),
                    "dev_activity_7d": _safe_float(santiment.get("dev_activity_7d")),
                    "dev_activity_change_7d_pct": _safe_float(santiment.get("dev_activity_change_7d_pct")),
                    "observation_history": None,
                }
                history = santiment.get("observation_history")
                if isinstance(history, dict):
                    santiment_evidence["observation_history"] = {
                        "tracked_since_utc": history.get("tracked_since_utc"),
                        "last_collected_at_utc": history.get("last_collected_at_utc"),
                        "observation_count": _safe_int(history.get("observation_count")) or 0,
                        "active_addresses_24h": (
                            history.get("active_addresses_24h", [])[-6:]
                            if isinstance(history.get("active_addresses_24h"), list) else []
                        ),
                        "dev_activity": (
                            history.get("dev_activity", [])[-7:]
                            if isinstance(history.get("dev_activity"), list) else []
                        ),
                    }

            has_cmc = bool(cmc_evidence)
            has_dex = bool(dex_evidence and dex_evidence.get("pair_count"))
            has_defi = bool(defi_evidence)
            has_santiment = bool(santiment_evidence and any(
                santiment_evidence.get(field) is not None
                for field in (
                    "active_addresses_24h", "active_addresses_change_24h_pct",
                    "dev_activity_7d", "dev_activity_change_7d_pct",
                )
            ))
            has_news = bool(news_sources)
            has_narrative = bool(themes)
            any_evidence = bool(matches or has_cmc or has_dex or has_defi or has_santiment)

            if not bridge_fresh:
                research_status = "TEKNİK ADAY AKTARIMI ESKİ"
            elif has_narrative and (has_dex or has_defi or has_santiment):
                research_status = "NARATİF + PİYASA KANITI BULUNDU"
            elif has_narrative:
                research_status = "NARATİF EŞLEŞMESİ BULUNDU"
            elif any_evidence:
                research_status = "PİYASA/PROJE KANITI VAR — NARATİF EŞLEŞMESİ YOK"
            elif checked_sources or checked_market_sources:
                research_status = "TARAMA YAPILDI — KANIT EŞLEŞMESİ BULUNAMADI"
            else:
                research_status = "KAYNAK VERİSİ EKSİK — DEĞERLENDİRİLEMEDİ"

            findings = []
            if has_news:
                findings.append(f"{len(news_sources)} bağımsız editoryal yayıncı eşleşti; yinelenen yayınlar ikinci teyit sayılmadı.")
            elif matches:
                findings.append("Coinle ilişkili keşif/duyuru kaydı var; bağımsız editoryal yayıncı eşleşmesi bulunmadı.")
            if has_cmc:
                change = _safe_float(cmc_evidence.get("percent_change_24h"))
                volume_change = _safe_float(cmc_evidence.get("volume_change_24h"))
                if change is not None:
                    findings.append(f"CMC son piyasa verisi 24 saatlik fiyat değişimini %{change:+.2f} gösteriyor.")
                if volume_change is not None:
                    findings.append(f"CMC 24 saatlik hacim değişimi %{volume_change:+.2f}.")
            if has_dex:
                findings.append(
                    f"DEX'te {dex_evidence['pair_count']} işlem çifti, "
                    f"{dex_evidence['chain_count']} zincir, "
                    f"{_safe_float(dex_evidence.get('liquidity_usd')) or 0.0:,.0f} USD likidite ve "
                    f"{_safe_float(dex_evidence.get('volume_usd_h24')) or 0.0:,.0f} USD 24s hacim kaydı var."
                )
                buys = dex_evidence.get("buys_h24")
                sells = dex_evidence.get("sells_h24")
                if buys is not None and sells is not None:
                    findings.append(f"DEX 24 saat işlem yönü: {buys} alış / {sells} satış.")
            if has_defi:
                for protocol in defi_evidence[:2]:
                    tvl_change = protocol.get("tvl_change_7d_pct")
                    dex_volume = protocol.get("dex_volume_24h_usd")
                    fees = protocol.get("fees_24h_usd")
                    parts = [f"{protocol.get('name') or 'Protokol'}"]
                    if protocol.get("tvl_usd") is not None:
                        parts.append(f"TVL {_safe_float(protocol.get('tvl_usd')):,.0f} USD")
                    if tvl_change is not None:
                        parts.append(f"7g TVL %{float(tvl_change):+.2f}")
                    if dex_volume is not None:
                        parts.append(f"24s DEX hacmi {_safe_float(dex_volume):,.0f} USD")
                    if fees is not None:
                        parts.append(f"24s ücret {_safe_float(fees):,.0f} USD")
                    findings.append(" · ".join(parts) + ".")
            if has_santiment:
                active_change = santiment_evidence.get("active_addresses_change_24h_pct")
                dev_change = santiment_evidence.get("dev_activity_change_7d_pct")
                if active_change is not None:
                    findings.append(f"Santiment aktif adres değişimi (24s): %{float(active_change):+.2f}.")
                if dev_change is not None:
                    findings.append(f"Santiment geliştirici etkinliği değişimi (7g): %{float(dev_change):+.2f}.")
                history = santiment_evidence.get("observation_history")
                if isinstance(history, dict) and history.get("observation_count"):
                    findings.append(
                        f"Santiment yerel gözlem geçmişinde {history['observation_count']} örnek var; "
                        f"ilk yerel kayıt {history.get('tracked_since_utc') or '—'}."
                    )

            missing = []
            if not matches:
                missing.append("Haber/keşif akışlarında coinle eşleşen olay bulunmadı.")
            if not has_cmc:
                missing.append("CMC coin piyasa verisi eşleşmedi.")
            if not has_dex:
                missing.append("Seçilen DEX profil/topluluk adreslerinde eşleşen gerçek pair verisi bulunmadı.")
            if not has_defi:
                missing.append("DeFiLlama protokol verisiyle güvenilir coin eşleşmesi bulunmadı.")
            if not has_santiment:
                missing.append("Santiment ücretsiz ölçümlerinde coin için veri yok veya API erişimi etkin değil.")
            if not bridge_fresh:
                missing.append("Teknik aday aktarımı 30 dakikalık güncellik sınırını aştı; güncel aday teyidi bekleniyor.")

            coverage = {
                group: {
                    "available_count": sum(
                        1 for value in source_coverage.values()
                        if value.get("group") == group and value.get("usable") is True
                    ),
                    "sources": [
                        key for key, value in source_coverage.items()
                        if value.get("group") == group
                    ],
                }
                for group in source_groups
            }
            result_rows.append({
                "symbol": symbol,
                "status": research_status,
                "technical_phase": candidate.get("phase"),
                "technical_phase_timeframe": candidate.get("phase_timeframe"),
                "technical_state": candidate.get("state"),
                "technical_score": _safe_float(candidate.get("opportunity_score")),
                "technical_decision": candidate.get("final_decision"),
                "technical_price": _safe_float(candidate.get("latest_price")),
                "matched_narratives": list(themes[:8]),
                "news_sources": news_sources,
                "discovery_sources": discovery_sources,
                "matching_event_count": len(matches),
                "matching_events": matching_events,
                "checked_sources": checked_sources,
                "checked_market_sources": checked_market_sources,
                "source_coverage": coverage,
                "market_evidence": {
                    "cmc": cmc_evidence or None,
                    "dex": dex_evidence,
                    "defillama_protocols": defi_evidence,
                    "santiment": santiment_evidence,
                },
                "research_findings": findings[:10],
                "missing_evidence": missing[:10],
                "evidence_counts": {
                    "independent_news_publishers": len(news_sources),
                    "discovery_sources": len(discovery_sources),
                    "matching_events": len(matches),
                    "dex_pairs": dex_evidence.get("pair_count", 0) if dex_evidence else 0,
                    "defillama_protocols": len(defi_evidence),
                    "santiment_observations": (
                        santiment_evidence.get("observation_history", {}).get("observation_count", 0)
                        if santiment_evidence and isinstance(santiment_evidence.get("observation_history"), dict)
                        else 0
                    ),
                },
                "handoff_generated_at_utc": generated or None,
                "handoff_fresh": bridge_fresh,
                "market_data_generated_at_utc": utc_now(),
                "researched_at_utc": utc_now(),
                "scope_note": (
                    "Teknik A/B/C adayları mevcut haber/keşif kayıtları ve aynı döngüde toplanmış "
                    "CMC, DEX, DeFiLlama ve Santiment verileriyle hedefli eşleştirilir. Coin başına "
                    "yeni API isteği yapılmaz. Veri yokluğu olumsuz sinyal veya sıfır değer sayılmaz."
                ),
                "score_separation_note": (
                    "Bu araştırma teknik puanı, A/B/C aşamasını, likidite kapılarını veya güçlü fırsat "
                    "koşullarını değiştirmez; yalnızca açıklayıcı kanıt sunar."
                ),
            })
            counts["candidates_with_narrative"] += int(has_narrative)
            counts["candidates_with_news"] += int(has_news)
            counts["candidates_with_dex_activity"] += int(has_dex)
            counts["candidates_with_defi_activity"] += int(has_defi)
            counts["candidates_with_santiment_data"] += int(has_santiment)
            counts["candidates_with_market_data"] += int(has_cmc)
            counts["candidates_with_any_evidence"] += int(any_evidence)

        status = (
            "GÜNCEL" if bridge_fresh and result_rows
            else "GÜNCEL — TEKNİK ADAY YOK" if bridge_fresh
            else "TEKNİK MOTOR AKTARIMI ESKİ/BEKLENİYOR"
        )
        return {
            "status": status,
            "generated_at_utc": utc_now(),
            "handoff_generated_at_utc": generated or None,
            "handoff_age_seconds": round(bridge_age, 1) if bridge_age is not None else None,
            "handoff_fresh": bridge_fresh,
            "technical_candidate_count": len(result_rows),
            **counts,
            "sources_checked": checked_sources,
            "market_sources_checked": checked_market_sources,
            "source_coverage": source_coverage,
            "items": result_rows,
            "score_separation_note": (
                "Araştırma sonucu teknik puana veya güçlü fırsat kapılarına eklenmez; "
                "naratif puanı da teknik adayı değiştirmez."
            ),
        }

    def _attach_technical_tracking(
        self,
        early_watch: list[dict[str, Any]],
        bridge_state: dict[str, Any],
        *,
        bridge_fresh: bool,
    ) -> dict[str, Any]:
        """Attach technical-engine observations to narrative watch rows without changing scores."""
        raw_rows = bridge_state.get("narrative_technical_watch")
        raw_rows = raw_rows if isinstance(raw_rows, list) else []
        by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in raw_rows
            if isinstance(item, dict) and item.get("symbol")
        }
        for item in early_watch:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            tracking = by_symbol.get(symbol)
            if bridge_fresh and tracking:
                item["technical_tracking"] = {
                    **tracking,
                    "fresh": tracking.get("active") is True
                    and tracking.get("data_freshness") == "CANLI AKIŞ GÜNCEL",
                }
            else:
                item["technical_tracking"] = {
                    "symbol": symbol,
                    "status": (
                        "TEKNİK MOTOR VERİSİ ESKİ"
                        if not bridge_fresh else "TEKNİK ÖLÇÜM BEKLENİYOR"
                    ),
                    "technical_status": (
                        "TEKNİK MOTOR VERİSİ ESKİ"
                        if not bridge_fresh else "TEKNİK ÖLÇÜM BEKLENİYOR"
                    ),
                    "fresh": False,
                    "technical_phase": None,
                    "technical_state": None,
                    "technical_score": None,
                    "timeframes": {},
                }
        return {
            "status": "GÜNCEL" if bridge_fresh else "TEKNİK MOTOR VERİSİ ESKİ/BEKLENİYOR",
            "generated_at_utc": bridge_state.get("generated_at_utc"),
            "age_seconds": _timestamp_age_seconds(bridge_state.get("generated_at_utc"), self.clock()),
            "tracked_coin_count": len(raw_rows),
        }

    def run_cycle(self) -> dict[str, Any]:
        statuses, rss_events, source_data = self._collect_sources()
        symbols, universe = _load_common_symbols(self.root)
        unique_cmc_rows = list(build_cmc_id_lookup(source_data["cmc_id_map"]).values())
        aliases = self._aliases(unique_cmc_rows or source_data["cmc"])
        events = self._normalise_events(
            source_data["topics"], rss_events, symbols, aliases,
            source_data.get("cmc_category_events", []),
            source_data.get("aixbt_project_mappings"),
        )
        market_map = self._market_map(
            source_data["cmc_category_coins"] + source_data["cmc"] + source_data["cmc_quotes"],
            source_data["dex_profiles"] + source_data["dex_community"],
            source_data["coingecko"],
            symbols,
            aliases,
            source_data.get("dex_market_activity", {}),
        )
        defillama_data = source_data.get("defillama", {}) if isinstance(source_data.get("defillama"), dict) else {}
        defillama_matched_protocols = attach_defillama_protocol_activity(
            market_map,
            defillama_data.get("protocols", []) if isinstance(defillama_data.get("protocols"), list) else [],
            defillama_data.get("dex_overview", {}) if isinstance(defillama_data.get("dex_overview"), dict) else {},
            defillama_data.get("fees_overview", {}) if isinstance(defillama_data.get("fees_overview"), dict) else {},
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
        bridge_state = _read_json(self.motor_bridge_path, {})
        if not isinstance(bridge_state, dict):
            bridge_state = {}
        technical_candidate_research = self._build_technical_candidate_research(
            bridge_state, events, early_watch, statuses, market_map,
        )
        technical_watch_bridge = self._attach_technical_tracking(
            early_watch,
            bridge_state,
            bridge_fresh=technical_candidate_research.get("handoff_fresh") is True,
        )
        self._save_history(narratives, events)
        alerts = self._alerts(narratives)
        news_statuses = [
            item for key, item in statuses.items()
            if key.startswith("rss_") or key == "trendkia_news"
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
        category_status = statuses.get("cmc_narrative_categories", {})
        category_connected = bool(
            isinstance(category_status, dict)
            and category_status.get("status") in ("BAĞLI", "ÖNBELLEK")
            and category_status.get("item_count", 0) > 0
        )
        santiment_status = statuses.get("santiment", {})
        santiment_connected = bool(
            isinstance(santiment_status, dict)
            and santiment_status.get("status") in ("BAĞLI", "ÖNBELLEK")
        )
        defillama_status = statuses.get("defillama", {})
        defillama_connected = bool(
            isinstance(defillama_status, dict)
            and defillama_status.get("status") in ("BAĞLI", "ÖNBELLEK")
        )
        errors = [
            f"{item['name']}: {item['status']}"
            for item in statuses.values()
            if item.get("enabled") and item.get("status") in ("ERİŞİLEMEDİ", "HATA — ÖNCEKİ VERİ VAR", "ESKİ VERİ")
        ]
        state = {
            "schema_version": 1,
            "engine": "Naratif Avcısı",
            "status": "ÇALIŞIYOR" if (connected_news or topic_connected or category_connected or santiment_connected or defillama_connected) else "KAYNAK VERİSİ BEKLENİYOR",
            "generated_at_utc": utc_now(),
            "first_observed_only": True,
            "historical_narrative_backfill": False,
            "source_statuses": statuses,
            "source_coverage": {
                "news_feeds_connected": connected_news,
                "news_feeds_enabled": enabled_news,
                "aixbt_topic_source_connected": topic_connected,
                "aixbt_project_mapping_connected": statuses.get("aixbt_project_mapping", {}).get("status") in ("BAĞLI", "ÖNBELLEK"),
                "aixbt_project_mapping_count": statuses.get("aixbt_project_mapping", {}).get("item_count", 0),
                "cmc_category_source_connected": category_connected,
                "topic_sources_connected": int(topic_connected) + int(category_connected),
                "evidence_sources_connected": connected_news + int(topic_connected) + int(category_connected),
                "event_count": len(events),
                "narrative_count": len(narratives),
                "early_watch_count": len(early_watch),
                "technical_candidate_count": technical_candidate_research.get("technical_candidate_count", 0),
                "technical_candidates_with_narrative": technical_candidate_research.get("candidates_with_narrative", 0),
                "technical_candidates_with_news": technical_candidate_research.get("candidates_with_news", 0),
                "technical_candidates_with_dex_activity": technical_candidate_research.get("candidates_with_dex_activity", 0),
                "technical_candidates_with_defi_activity": technical_candidate_research.get("candidates_with_defi_activity", 0),
                "technical_candidates_with_santiment_data": technical_candidate_research.get("candidates_with_santiment_data", 0),
                "technical_candidates_with_any_market_data": technical_candidate_research.get("candidates_with_market_data", 0),
                "technical_candidates_with_any_research_evidence": technical_candidate_research.get("candidates_with_any_evidence", 0),
                "narrative_coin_technical_watch_count": technical_watch_bridge.get("tracked_coin_count", 0),
                "errors": errors,
            },
            "universe": universe,
            "narratives": narratives,
            "early_watch": early_watch,
            "technical_candidate_research": technical_candidate_research,
            "technical_watch_bridge": technical_watch_bridge,
            "alerts": alerts,
            "market_context": source_data.get("market_context", {}),
            "market_activity": {
                "cmc_role": "MARKET_ACTIVITY_NOT_NEWS",
                "cmc_coin_count": len(source_data["cmc"]),
                "cmc_universe_quotes_count": len(source_data["cmc_quotes"]),
                "cmc_unique_id_count": len(build_cmc_id_lookup(source_data["cmc_id_map"])),
                "cmc_theme_category_count": len(source_data["cmc_category_details"]),
                "cmc_theme_coin_matches": len(source_data["cmc_category_coins"]),
                "dex_profiles_count": len(source_data["dex_profiles"]),
                "dex_community_count": len(source_data["dex_community"]),
                "dex_market_pair_count": len(source_data.get("dex_market_activity", {}).get("pairs", []))
                if isinstance(source_data.get("dex_market_activity"), dict) else 0,
                "dex_market_candidate_token_count": source_data.get("dex_market_activity", {}).get("candidate_token_count", 0)
                if isinstance(source_data.get("dex_market_activity"), dict) else 0,
                "dex_market_batch_request_count": source_data.get("dex_market_activity", {}).get("batch_request_count", 0)
                if isinstance(source_data.get("dex_market_activity"), dict) else 0,
                "dex_market_coin_count": sum(
                    1 for item in market_map.values()
                    if isinstance(item, dict) and isinstance(item.get("dex_market_activity"), dict)
                ),
                "aixbt_project_topic_count": len(
                    source_data.get("aixbt_project_mappings", {}).get("by_topic", {})
                    if isinstance(source_data.get("aixbt_project_mappings"), dict) else {}
                ),
                "aixbt_project_association_count": statuses.get("aixbt_project_mapping", {}).get("item_count", 0),
                "santiment_coin_count": len(santiment_map),
                "santiment_symbols": sorted(santiment_map),
                "santiment_history_observation_count": statuses.get("santiment_history", {}).get("item_count", 0),
                "defillama_protocol_count": len(source_data.get("defillama", {}).get("protocols", []))
                if isinstance(source_data.get("defillama"), dict) else 0,
                "defillama_matched_protocol_count": defillama_matched_protocols,
                "defillama_matched_coin_count": sum(
                    1 for item in market_map.values()
                    if isinstance(item, dict) and isinstance(item.get("defillama_protocols"), list)
                ),
            },
            "limits": [
                "AIXBT ücretsiz/anahtarsız Topics uç noktası mevcut ilk 25 konuyu verir; tüm AIXBT konu arşivi değildir.",
                "AIXBT v3 konu→proje eşlemesi AIXBT_API_KEY ile çalışır; saatte en fazla beş konu ve konu başına ilk 50 proje sorgulanır. İlk 25 konu beş saatlik döngüyle sırayla taranır; 429 yanıtında kademeli bekleme uygulanır.",
                "CoinMarketCap Keyless Public API hesap, kayıt, API anahtarı veya kart istemez; ortak IP kotası nedeniyle çağrılar seyrek ve seri yapılır.",
                "CMC ID Map sembol çakışmalarını tahmin etmez; tekil CMC ID eşleşmesi bulunmayan coinlerin quote verisi atlanır.",
                "CMC Global Metrics, Fear and Greed, Altcoin Season, CMC100 ve CMC20 piyasa bağlamıdır; teknik puan, güçlü fırsat kapısı ve teknik alarmı değiştirmez.",
                "CMC fiyat/hacim verisi yalnızca mevcut naratif piyasa tepkisi alanını tamamlar; teknik radar puanına aktarılmaz.",
                "CMC Categories Keyless uçları her altı saatte bir 5.000 kayda kadar kategori kataloğunu alır; tanınan temalar ve güçlü ama henüz sınıflandırılmayan kategori adayları korunur. Ayrıntı sorguları altı saatte en fazla üçtür: iki öncelikli kategori ve bir geniş evren rotasyon adayı.",
                "Kategori coinleri yalnızca ortak Binance–BtcTurk USDT evrenindeki benzersiz CMC ID eşleşmesiyle erken izlemeye alınır; sembol benzerliği tek başına yeterli değildir.",
                "AIXBT gönderi/katılımcı sayısı ve konu→proje eşlemesi topluluk keşif verisidir; bağımsız haber teyidi veya teknik puan sayılmaz. Proje yalnızca ortak USDT evrenindeki yüksek güvenli ad/alias eşleşmesiyle erken izlemeye alınır.",
                "DEX Screener profil/topluluk akışından alınan token adresleri için gerçek pair verisi; fiyat, likidite, hacim ve alış/satış işlemlerini kapsar. Her 15 dakikada en fazla iki istek, istek başına 30 adres; zincir/adres grupları rotasyonla taranır.",
                "DEX pair faaliyeti yalnızca son profil/topluluk listelerinde görünen token adreslerini kapsar; tüm DEX evreninin eksiksiz taraması değildir. Tekil tam proje adı eşleşmesiyle erken izlemeye bağlanır; haber teyidi, teknik puan veya güçlü fırsat koşulu değildir.",
                "DEX Screener ve CoinGecko trend işaretleri eşleşen coinlerde piyasa keşif etkinliğini destekler; bağımsız haber teyidi değildir.",
                "TrendKia herkese açık MCP üzerinden API anahtarı veya kart olmadan okunur; 30 yazılık akış 30 dakikada bir alınır ve 72 saat filtresinden geçirilir.",
                "TrendKia yalnızca naratif haber kanıtıdır; teknik puanı ve güçlü fırsat koşullarını değiştirmez.",
                "Investing.com ekonomik takvimi yalnızca resmi Türkçe sayfaya harici bağlantı olarak açılır; API bulunmadığı için veri otomatik çekilmez veya saklanmaz.",
                "The Fly ve Reddit otomatik entegrasyonları erişim/kullanım izni doğrulanmadan çağrılmaz.",
                "CoinGecko Demo API anahtarı yoksa devre dışıdır; anahtar gizli ortam değişkeninden okunur.",
                "DEX profil/topluluk hareketi organik ilgi veya bağımsız haber teyidi olarak tek başına yorumlanmaz.",
                "DeFiLlama yalnızca anahtarsız ücretsiz API uçlarını kullanır; protokol TVL, zincir TVL, stablecoin arzı, DEX hacmi ve günlük protokol ücretleri önbellekle seyrek yenilenir. Protokoller ortak USDT evrenine yalnızca tekil tam ad veya benzersiz protokol token sembolüyle eşleştirilir; DeFi verisi teknik/naratif puan ve güçlü fırsat koşullarını değiştirmez.",
                "DeFiLlama ücretsiz /pools getiri uç noktası 13 Kasım 2026'da kapatılacağı duyurulduğundan bu entegrasyonda kullanılmaz; ücretli API veya anahtar gerekmez.",
                "Santiment yalnızca ücretsiz active_addresses_24h ve dev_activity modern:v1 ölçümlerini, en fazla 30 eşleşen aday coin için altı saatte bir toplu sorgular.",
                "Free API aylık 1.000 çağrı sınırı içinde tahmini kullanım yaklaşık 241 çağrı/30 gündür; ücretli/kısıtlı ölçümler çağrılmaz.",
                "Santiment API anahtarı yalnızca SANTIMENT_API_KEY ortam değişkeninden okunur; ayarlar dosyasına veya rapora yazılmaz.",
                "Kaynağın geçmiş verisi geri doldurulmaz; naratif geçmişi bu motorun ilk gözleminden başlar.",
                "Naratif puanı teknik puandan ayrıdır; teknik eşikleri, likidite kapılarını ve güçlü alarm koşullarını değiştirmez.",
                "Teknik A/B/C adayları her döngüde mevcut haber/keşif kanıtları ve proje aliaslarıyla ayrı araştırma listesine alınır; kaynak kanıtı bulunmaması veri eksikliğiyle karıştırılmaz.",
                "Naratif erken izleme coinleri teknik motor tarafından sekiz zaman diliminde ölçülür; teknik görünüm ve geçmiş kayıt naratif puanına eklenmez.",
                "Motorlar arası aktarım yerel naratif_motor_koprusu.json dosyasıyla yapılır; köprü verisi 30 dakikadan eskiyse güncel sayılmaz.",
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
