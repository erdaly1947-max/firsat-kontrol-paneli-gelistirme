from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import naratif_avcisi as narrative


class NarrativeParsingTests(unittest.TestCase):
    def test_aixbt_topic_projects_normalizes_v3_associations(self):
        topic = {"id": "topic_0123456789abcdefabcd", "name": "AI agents", "rank": 2}
        rows = narrative.parse_aixbt_topic_projects({
            "data": [
                {"project": {"id": 7, "slug": "ethereum", "name": "Ethereum"},
                 "observedPosts": 15, "distinctAuthors": 8, "shareOfTopicPosts": 0.25,
                 "firstObservedAt": "2026-10-30T10:00:00Z",
                 "lastObservedAt": "2026-10-31T10:00:00Z",
                 "sentiment": {"populated": True, "coverage": 0.8}},
                {"project": {"id": 8, "slug": "", "name": "Missing slug"}},
                {"project": {"id": 9, "slug": "empty-name", "name": ""}},
                {"no_project": True},
            ]
        }, topic)
        self.assertEqual(rows["topic_id"], topic["id"])
        self.assertEqual(len(rows["projects"]), 1)
        self.assertEqual(rows["projects"][0]["name"], "Ethereum")
        self.assertEqual(rows["projects"][0]["observed_posts"], 15)
        self.assertEqual(rows["projects"][0]["sentiment_coverage"], 0.8)

    def test_aixbt_mapping_uses_api_key_and_rotates_five_topics(self):
        from unittest.mock import patch

        class FakeResponse:
            status_code = 200
            headers = {}
            def raise_for_status(self):
                return None
            def json(self):
                return {"data": [{
                    "project": {"id": "eth-id", "slug": "ethereum", "name": "Ethereum"},
                    "observedPosts": 9, "distinctAuthors": 4,
                    "shareOfTopicPosts": 0.4,
                    "sentiment": {"populated": True, "coverage": 1.0},
                }]}

        class FakeSession:
            def __init__(self):
                self.calls = []
            def get(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return FakeResponse()

        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        engine.session = FakeSession()
        engine.clock = narrative.time.time
        engine.cache = {"aixbt_project_mapping": {
            "data": {"by_topic": {}, "next_cursor": 0}
        }}
        topics = [
            {"id": f"topic_{index:020x}", "name": f"Topic {index}", "rank": index}
            for index in range(1, 8)
        ]
        with patch.dict("os.environ", {"AIXBT_API_KEY": "test-secret"}, clear=False):
            first = engine._fetch_aixbt_topic_project_mappings(topics)
        self.assertEqual(len(engine.session.calls), 5)
        self.assertIn("/v3/topics/topic_00000000000000000001/projects", engine.session.calls[0][0])
        self.assertEqual(engine.session.calls[0][1]["headers"]["x-api-key"], "test-secret")
        self.assertEqual(first["last_batch_topic_ids"], [row["id"] for row in topics[:5]])

        engine.cache["aixbt_project_mapping"]["data"] = first
        with patch.dict("os.environ", {"AIXBT_API_KEY": "test-secret"}, clear=False):
            second = engine._fetch_aixbt_topic_project_mappings(topics)
        self.assertEqual(len(engine.session.calls), 10)
        self.assertEqual(second["last_batch_topic_ids"], [topics[i]["id"] for i in [5, 6, 0, 1, 2]])
        self.assertIn(topics[0]["id"], second["by_topic"])
        self.assertEqual(second["by_topic"][topics[0]["id"]]["projects"][0]["name"], "Ethereum")

    def test_aixbt_topic_projects_join_to_common_universe_by_project_name(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        topic = {"id": "topic_0123456789abcdefabcd", "name": "AI Agents", "rank": 1}
        mapping = {
            "by_topic": {
                topic["id"]: {
                    "topic_id": topic["id"], "topic_name": "AI Agents",
                    "topic_rank": 1, "checked_at_utc": "2026-10-31T10:00:00+00:00",
                    "projects": [{
                        "project_id": "eth-id", "slug": "ethereum", "name": "Ethereum",
                        "observed_posts": 12, "distinct_authors": 6,
                        "share_of_topic_posts": 0.3,
                    }],
                }
            }
        }
        events = engine._normalise_events(
            [topic], [], ["ETH"], {"ETH": ["Ethereum"]},
            aixbt_project_mappings=mapping,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source_kind"], "topic_discovery")
        self.assertEqual(events[0]["symbols"][0]["symbol"], "ETH")
        association = events[0]["symbols"][0]["aixbt_topic_associations"][0]
        self.assertEqual(association["project_id"], "eth-id")
        self.assertEqual(association["observed_posts"], 12)

        _narratives, watch = engine._build_narratives(events, {}, [])
        self.assertEqual(watch[0]["symbol"], "ETH")
        self.assertEqual(watch[0]["aixbt_topic_associations"][0]["project_name"], "Ethereum")

    def test_aixbt_topics_accepts_v3_data_list_and_caps_at_top_25(self):
        payload = {"data": [
            {"id": str(i), "name": f"Topic {i}", "summary": "Ethereum layer 2",
             "rank": i, "trend": "up", "postCount": 10, "authorCount": 4}
            for i in range(1, 31)
        ]}
        rows = narrative.parse_aixbt_topics(payload)
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[-1]["name"], "Topic 25")

    def test_aixbt_topics_accepts_nested_data_topics_envelope(self):
        rows = narrative.parse_aixbt_topics({
            "data": {
                "topics": [
                    {"topicId": "t1", "name": "AI agents", "rank": 1,
                     "summary": "AI agents and DePIN", "postCount": 8, "authorCount": 3}
                ]
            }
        })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "t1")
        self.assertEqual(rows[0]["name"], "AI agents")

    def test_cmc_listing_is_marked_as_market_data_not_news(self):
        payload = {"data": {"cryptoCurrencyList": [{
            "symbol": "ETH", "name": "Ethereum", "cmc_rank": 2,
            "quote": {"USD": {"price": 3000, "volume_24h": 1_000_000,
                              "percent_change_24h": 3.5}},
        }]}}
        rows = narrative.parse_cmc_market_listings(payload)
        self.assertEqual(rows[0]["symbol"], "ETH")
        self.assertEqual(rows[0]["percent_change_24h"], 3.5)
        self.assertNotIn("news", rows[0])

    def test_rss_parser_supports_atom_and_rss(self):
        atom = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Ethereum layer 2 update</title>
          <link href="https://example.test/post"/><updated>2026-10-31T09:00:00Z</updated>
          <summary>Optimism and Arbitrum ecosystem</summary></entry></feed>"""
        rss = """<rss version="2.0"><channel><item>
          <title>Solana DeFi news</title><link>https://example.test/sol</link>
          <description>New liquidity protocol</description></item></channel></rss>"""
        atom_rows = narrative.parse_rss_items(atom, source_id="atom", source_name="Atom", source_kind="official")
        rss_rows = narrative.parse_rss_items(rss, source_id="rss", source_name="RSS", source_kind="media")
        self.assertEqual(atom_rows[0]["url"], "https://example.test/post")
        self.assertIn("Optimism", atom_rows[0]["summary"])
        self.assertEqual(rss_rows[0]["url"], "https://example.test/sol")

    def test_rss_parser_rejects_malformed_xml(self):
        with self.assertRaises(ValueError):
            narrative.parse_rss_items("<feed>", source_id="bad", source_name="Bad", source_kind="media")

    def test_ticker_matching_is_boundary_aware_and_marks_short_tickers_uncertain(self):
        rows = narrative.match_symbols(
            "Ethereum (ETH) and $OP discussed. COINBASE has appeared.",
            ["ETH", "OP", "COIN"],
            {"ETH": ["Ethereum"]},
        )
        by_symbol = {row["symbol"]: row for row in rows}
        self.assertEqual(set(by_symbol), {"ETH", "OP"})
        self.assertEqual(by_symbol["ETH"]["confidence"], "YÜKSEK")
        self.assertEqual(by_symbol["OP"]["confidence"], "ORTA")

    def test_theme_classifier_returns_distinct_turkish_labels(self):
        themes = narrative.infer_themes("AI agents and real world asset tokenization")
        self.assertIn("Yapay Zekâ (AI)", themes)
        self.assertIn("Gerçek Dünya Varlıkları (RWA)", themes)



    def test_santiment_project_catalog_parses_exact_ticker_slug_records(self):
        projects = narrative.parse_santiment_projects({
            "data": {"allProjects": [
                {"slug": "ethereum", "ticker": "ETH", "name": "Ethereum"},
                {"slug": "bad slug", "ticker": "BAD", "name": "Bad"},
            ]}
        })
        self.assertEqual(projects, [{"slug": "ethereum", "ticker": "ETH", "name": "Ethereum"}])
        mapped = narrative.map_santiment_projects(
            projects, ["ETH", "UNKNOWN"], {"ETH": ["Ether", "Ethereum"]}
        )
        self.assertEqual(mapped, {"ETH": "ethereum"})

    def test_santiment_ambiguous_ticker_is_not_guessed(self):
        projects = [
            {"slug": "one", "ticker": "ABC", "name": "Alpha"},
            {"slug": "two", "ticker": "ABC", "name": "Beta"},
        ]
        self.assertEqual(narrative.map_santiment_projects(projects, ["ABC"], {}), {})
        self.assertEqual(
            narrative.map_santiment_projects(projects, ["ABC"], {"ABC": ["Beta"]}),
            {"ABC": "two"},
        )

    def test_santiment_per_slug_timeseries_is_normalized(self):
        rows = narrative.parse_santiment_timeseries({
            "data": {"getMetric": {"timeseriesDataPerSlugJson": [
                {"datetime": "2026-10-30T00:00:00Z", "data": [
                    {"slug": "ethereum", "value": 100, "computedAt": "2026-10-30T00:05:00Z"}
                ]},
                {"datetime": "2026-10-31T00:00:00Z", "data": [
                    {"slug": "ethereum", "value": 120}
                ]},
            ]}}
        })
        self.assertEqual([point["value"] for point in rows["ethereum"]], [100.0, 120.0])

    def test_santiment_queries_use_only_free_metrics_and_batched_slugs(self):
        active = narrative.build_santiment_metric_query("active_addresses_24h", ["ethereum", "bitcoin"])
        dev = narrative.build_santiment_metric_query("dev_activity", ["ethereum"])
        self.assertIn("timeseriesDataPerSlugJson", active)
        self.assertIn('slugs: ["bitcoin", "ethereum"]', active)
        self.assertIn('metric: "dev_activity", version: "modern:v1"', dev)
        with self.assertRaises(ValueError):
            narrative.build_santiment_metric_query("social_volume_total", ["ethereum"])

    def test_santiment_summary_compares_recent_activity_windows(self):
        active = {"ethereum": [
            {"datetime": "2026-10-30T00:00:00Z", "value": 100.0},
            {"datetime": "2026-10-31T00:00:00Z", "value": 120.0},
        ]}
        dev = {"ethereum": [
            {"datetime": f"2026-10-{day:02d}T00:00:00Z", "value": 10.0}
            for day in range(18, 32)
        ]}
        summary = narrative.summarize_santiment_asset("ethereum", active, dev)
        self.assertEqual(summary["active_addresses_24h"], 120.0)
        self.assertEqual(summary["active_addresses_change_24h_pct"], 20.0)
        self.assertEqual(summary["dev_activity_7d"], 70.0)
        self.assertEqual(summary["dev_activity_change_7d_pct"], 0.0)

class NarrativeRuntimeTests(unittest.TestCase):
    def test_common_universe_is_preferred_and_local_fallback_is_disclosed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "data" / "single_engine_common_universe.json").write_text(
                json.dumps({"generated_at_utc": "2026-10-31T09:00:00+00:00",
                            "pairs": [{"base_asset": "ETH", "quote_asset": "USDT",
                                       "binance_symbol": "ETHUSDT", "btcturk_symbol": "ETHUSDT"}]}),
                encoding="utf-8",
            )
            symbols, status = narrative._load_common_symbols(root)
            self.assertEqual(symbols, ["ETH"])
            self.assertTrue(status["verified"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "btcturk_usdt_spot.json").write_text(
                json.dumps({"symbols": {"SOL": {"quote": "USDT", "symbol": "SOLUSDT"}}}),
                encoding="utf-8",
            )
            symbols, status = narrative._load_common_symbols(root)
            self.assertEqual(symbols, ["SOL"])
            self.assertFalse(status["verified"])
            self.assertIn("BINANCE", status["mode"])

    def test_republishing_same_headline_does_not_multiply_events(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        symbols = ["ETH"]
        rows = [
            {"title": "Ethereum layer 2 adoption grows", "summary": "Ethereum rollup news",
             "source_id": "feed_a", "source_name": "Feed A", "source_kind": "media",
             "url": "https://a.test", "published_at": "2026-10-31"},
            {"title": "Ethereum layer 2 adoption grows", "summary": "Reprint",
             "source_id": "feed_b", "source_name": "Feed B", "source_kind": "media",
             "url": "https://b.test", "published_at": "2026-10-31"},
        ]
        events = engine._normalise_events([], rows, symbols, {"ETH": ["Ethereum"]})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["republishers"], ["Feed B"])

    def test_narrative_score_is_separate_and_deduplicated_for_each_symbol(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        events = [{
            "event_id": "news:one", "title": "Ethereum and Arbitrum Layer 2 launch",
            "source_id": "coindesk", "source_kind": "media",
            "themes": ["Katman-2 (Layer 2)"],
            "symbols": [
                {"symbol": "ETH", "confidence": "YÜKSEK"},
                {"symbol": "ARB", "confidence": "YÜKSEK"},
            ],
        }]
        narratives, early_watch = engine._build_narratives(
            events,
            {"ETH": {"percent_change_24h": 2.0}, "ARB": {"percent_change_24h": 4.0}},
            [],
        )
        self.assertEqual(len(narratives), 1)
        self.assertIsNotNone(narratives[0]["narrative_score"])
        self.assertEqual(set(narratives[0]["related_coins"]), {"ETH", "ARB"})
        self.assertEqual({item["symbol"] for item in early_watch}, {"ETH", "ARB"})
        self.assertEqual(narratives[0]["interest_direction"], "İLK GÖZLEM")

    def test_historical_narrative_is_never_backfilled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            (root / "ayarlar.json").write_text("{}", encoding="utf-8")
            engine = narrative.NarrativeEngine(root=root, session=object())
            self.assertFalse(engine.previous_state.get("historical_narrative_backfill", False))

    def test_api_keys_are_read_from_environment_not_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            (root / "ayarlar.json").write_text(
                '{"AIXBT_API_KEY":"must-not-be-used","COINGECKO_DEMO_API_KEY":"must-not-be-used","SANTIMENT_API_KEY":"must-not-be-used"}',
                encoding="utf-8",
            )
            engine = narrative.NarrativeEngine(root=root, session=object())
            self.assertNotIn("AIXBT_API_KEY", engine.settings)
            self.assertNotIn("COINGECKO_DEMO_API_KEY", engine.settings)
            self.assertNotIn("SANTIMENT_API_KEY", engine.settings)




    def test_analysis_report_keeps_narrative_separate_from_technical_candidates(self):
        from analysis_report import build_analysis_report
        report = build_analysis_report(
            {"candidates": [{
                "symbol": "ETH", "opportunity_score": 70,
                "narrative_support": {
                    "narrative_score": 61,
                    "narratives": ["Katman-2 (Layer 2)"],
                    "phase": "GÜÇLENME",
                    "confidence": "ORTA",
                },
            }]},
            {
                "status": "ÇALIŞIYOR",
                "generated_at_utc": "2026-10-31T09:00:00+00:00",
                "narratives": [{"name": "Katman-2 (Layer 2)", "narrative_score": 73}],
                "early_watch": [{"symbol": "ARB", "narrative_score": 73}],
                "alerts": [{"alert_type": "YENİ NARATİF", "narrative": "Katman-2"}],
                "source_statuses": {"aixbt_topics": {"name": "AIXBT Topics", "status": "BAĞLI"}},
            },
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["narrative"]["narrative_count"], 1)
        self.assertEqual(report["narrative"]["early_watch"][0]["symbol"], "ARB")
        self.assertEqual(report["narrative"]["alerts"][0]["alert_type"], "YENİ NARATİF")
        self.assertNotIn("narrative_score", report["candidates"][0])
        self.assertEqual(
            report["candidates"][0]["narrative_support"]["narrative_score"], 61
        )
        self.assertFalse(report["narrative"]["historical_narrative_backfill"])





    def test_aixbt_topic_discovery_does_not_count_as_independent_news_publisher(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        events = [{
            "event_id": "aixbt:layer2", "title": "Layer 2 ecosystem",
            "source_id": "aixbt_topics", "source_kind": "topic_discovery",
            "themes": ["Katman-2 (Layer 2)"], "rank": 1,
            "symbols": [{"symbol": "ARB", "confidence": "YÜKSEK"}],
        }]
        narratives, watch = engine._build_narratives(events, {}, [])
        self.assertEqual(narratives[0]["sources"], [])
        self.assertEqual(narratives[0]["coverage"]["independent_news_sources"], 0)
        self.assertEqual(narratives[0]["score_components"]["aixbt_topic_rank"], 100.0)
        self.assertEqual(watch[0]["symbol"], "ARB")

    def test_source_failure_remains_visible_while_cached_response_is_reused(self):
        import logging
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
            engine.cache = {"feed": {
                "data": [{"title": "cached"}],
                "last_attempt_epoch": 100.0,
                "last_success_epoch": 100.0,
            }}
            engine.stop_file = Path(temp) / "stop.flag"
            engine.clock = lambda: 500.0
            engine.logger = logging.getLogger("narrative-test")
            first_status = {}
            result = engine._fetch_source(
                "feed", 300, lambda: (_ for _ in ()).throw(RuntimeError("HTTP 503")),
                first_status, count_fn=len,
            )
            self.assertEqual(result, [{"title": "cached"}])
            self.assertEqual(first_status["status"], "HATA — ÖNCEKİ VERİ VAR")
            second_status = {}
            engine.clock = lambda: 501.0
            engine._fetch_source("feed", 300, lambda: self.fail("cache retry happened too early"),
                                 second_status, count_fn=len)
            self.assertEqual(second_status["status"], "HATA — ÖNCEKİ VERİ VAR")
            self.assertIn("HTTP 503", second_status["error"])

    def test_pending_stop_marker_prevents_new_source_request(self):
        import logging
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            stop_file = Path(temp) / "stop.flag"
            stop_file.write_text("stop", encoding="utf-8")
            engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
            engine.cache = {}
            engine.stop_file = stop_file
            engine.clock = lambda: 1000.0
            engine.logger = logging.getLogger("narrative-test")
            called = []
            status = {}
            result = engine._fetch_source(
                "feed", 300, lambda: called.append(True), status,
            )
            self.assertIsNone(result)
            self.assertEqual(called, [])
            self.assertEqual(status["status"], "DURDURMA İSTENDİ")

    def test_narrative_history_snapshot_is_throttled_to_five_minutes(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
            engine.history_path = Path(temp) / "history.sqlite3"
            narrative_row = {
                "narrative_id": "layer-2",
                "name": "Katman-2 (Layer 2)",
                "phase": "BAŞLANGIÇ",
                "narrative_score": 60.0,
                "interest_direction": "İLK GÖZLEM",
                "confidence": "DÜŞÜK",
            }
            engine._save_history([dict(narrative_row)], [])
            engine._save_history([dict(narrative_row)], [])
            with sqlite3.connect(engine.history_path) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM narrative_snapshots WHERE narrative_id='layer-2'"
                ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_first_observed_history_and_alert_rows_are_persisted(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
            engine.history_path = Path(temp) / "history.sqlite3"
            engine.previous_state = {}
            row = {
                "narrative_id": "rwa",
                "name": "Gerçek Dünya Varlıkları (RWA)",
                "phase": "BAŞLANGIÇ",
                "narrative_score": 55.0,
                "interest_direction": "İLK GÖZLEM",
                "confidence": "DÜŞÜK",
                "last_observed_at_utc": "2026-10-31T09:00:00+00:00",
            }
            engine._save_history([dict(row)], [])
            alerts = engine._alerts([row])
            self.assertEqual(len(alerts), 1)
            with sqlite3.connect(engine.history_path) as connection:
                event = connection.execute(
                    "SELECT alert_type FROM narrative_alerts WHERE narrative_id='rwa'"
                ).fetchone()
            self.assertEqual(event[0], "YENİ NARATİF")




    def test_score_includes_velocity_freshness_price_and_volume_when_available(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        events = [
            {
                "event_id": f"event-{source}",
                "title": "Ethereum real world asset adoption",
                "source_id": source,
                "source_kind": "media",
                "themes": ["Gerçek Dünya Varlıkları (RWA)"],
                "symbols": [{"symbol": "ONDO", "confidence": "YÜKSEK"}],
            }
            for source in ("alpha", "beta", "gamma")
        ]
        previous = [{
            "narrative_id": "gercek-dunya-varliklari-rwa",
            "narrative_score": 20.0,
            "score_version": 2,
        }]
        market = {
            "ONDO": {"percent_change_24h": 20.0, "volume_change_24h": 60.0},
        }
        sources = {
            "rss_alpha": {"age_seconds": 120},
            "rss_beta": {"age_seconds": 180},
            "rss_gamma": {"age_seconds": 240},
        }
        rows, watch = engine._build_narratives(events, market, previous, source_statuses=sources)
        row = rows[0]
        components = row["score_components"]
        self.assertEqual(components["data_freshness"], 100.0)
        self.assertEqual(components["independent_source_families"], 90.0)
        self.assertEqual(components["market_price_reaction_24h"], 70.0)
        self.assertEqual(components["market_volume_reaction_24h"], 80.0)
        self.assertIn("interest_velocity", components)
        self.assertGreater(row["interest_change"], 0)
        self.assertEqual(row["data_freshness_seconds"], 120.0)
        self.assertEqual(watch[0]["symbol"], "ONDO")

    def test_rising_evidence_backed_narratives_rank_before_overheated_themes(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        events = []
        for index, source in enumerate(("a", "b", "c", "d", "e")):
            events.append({
                "event_id": f"meme-{index}",
                "title": f"Meme coin ecosystem update {index}",
                "source_id": source,
                "source_kind": "media",
                "themes": ["Meme Coin Ekosistemi"],
                "symbols": [
                    {"symbol": symbol, "confidence": "YÜKSEK"}
                    for symbol in ("DOGE", "SHIB", "PEPE", "FLOKI", "BONK",
                                   "WIF", "BRETT", "MOG", "TURBO", "NEIRO")
                ],
            })
        events.append({
            "event_id": "rwa-one",
            "title": "Ondo tokenized assets update",
            "source_id": "alpha",
            "source_kind": "media",
            "themes": ["Gerçek Dünya Varlıkları (RWA)"],
            "symbols": [{"symbol": "ONDO", "confidence": "YÜKSEK"}],
        })
        symbols = ("DOGE", "SHIB", "PEPE", "FLOKI", "BONK",
                   "WIF", "BRETT", "MOG", "TURBO", "NEIRO")
        market = {
            symbol: {"percent_change_24h": 30.0, "volume_change_24h": 100.0}
            for symbol in symbols
        }
        market["ONDO"] = {"percent_change_24h": 1.0, "volume_change_24h": 0.0}
        sources = {
            f"rss_{key}": {"age_seconds": 50}
            for key in ("a", "b", "c", "d", "e", "alpha")
        }
        previous = [{
            "narrative_id": "meme-coin-ekosistemi",
            "narrative_score": 0.0,
        }]
        rows, _watch = engine._build_narratives(events, market, previous, source_statuses=sources)
        self.assertEqual(rows[0]["name"], "Gerçek Dünya Varlıkları (RWA)")
        meme = next(item for item in rows if item["name"] == "Meme Coin Ekosistemi")
        self.assertEqual(meme["phase"], "AŞIRI ISINMA")
        self.assertIn("data_freshness", meme["score_components"])
        self.assertIn("market_volume_reaction_24h", meme["score_components"])




    def test_unchanged_evidence_does_not_create_false_interest_acceleration(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        events = [{
            "event_id": "stable-event",
            "title": "Ethereum layer 2 development",
            "source_id": "alpha",
            "source_kind": "media",
            "themes": ["Katman-2 (Layer 2)"],
            "symbols": [{"symbol": "ARB", "confidence": "YÜKSEK"}],
        }]
        market = {"ARB": {"percent_change_24h": 3.0, "volume_change_24h": 5.0}}
        sources = {"rss_alpha": {"age_seconds": 120}}
        first, _ = engine._build_narratives(events, market, [], source_statuses=sources)
        second, _ = engine._build_narratives(events, market, first, source_statuses=sources)
        self.assertAlmostEqual(second[0]["narrative_score"], first[0]["narrative_score"], places=1)
        self.assertEqual(second[0]["interest_direction"], "YATAY")
        self.assertEqual(second[0]["score_components"]["interest_velocity"], 50.0)


if __name__ == "__main__":
    unittest.main()


class NewFreeNarrativeSourcesTests(unittest.TestCase):
    def test_cmc_v3_listing_supports_usd_quote_array(self):
        rows = narrative.parse_cmc_market_listings({"data": [{
            "id": 1027, "symbol": "ETH", "name": "Ethereum", "cmc_rank": 2,
            "quote": [{"symbol": "USD", "price": 3100.5, "volume_24h": 2000000,
                       "percent_change_24h": 2.5, "volume_change_24h": 5.0,
                       "market_cap": 1000000}],
        }]})
        self.assertEqual(rows[0]["id"], 1027)
        self.assertEqual(rows[0]["price"], 3100.5)
        self.assertEqual(rows[0]["percent_change_24h"], 2.5)

    def test_cmc_legacy_listing_envelope_remains_supported(self):
        rows = narrative.parse_cmc_market_listings({"data": {"cryptoCurrencyList": [{
            "symbol": "ETH", "name": "Ethereum",
            "quote": {"USD": {"price": 3000, "percent_change_24h": 3.5}},
        }]}})
        self.assertEqual(rows[0]["symbol"], "ETH")
        self.assertEqual(rows[0]["percent_change_24h"], 3.5)

    def test_cmc_id_map_skips_ambiguous_symbols(self):
        rows = narrative.parse_cmc_id_map({"data": [
            {"id": 1, "symbol": "BTC", "name": "Bitcoin"},
            {"id": 2, "symbol": "ABC", "name": "Project A"},
            {"id": 3, "symbol": "ABC", "name": "Project B"},
        ]})
        lookup = narrative.build_cmc_id_lookup(rows)
        self.assertIn("BTC", lookup)
        self.assertNotIn("ABC", lookup)

    def test_cmc_quotes_parse_batched_id_result(self):
        rows = narrative.parse_cmc_quotes({"data": {
            "1027": {"id": 1027, "symbol": "ETH", "name": "Ethereum",
                     "quote": {"USD": {"price": 3000, "volume_24h": 1000,
                                       "volume_change_24h": 4, "percent_change_24h": 1.5}}}
        }})
        self.assertEqual(rows[0]["id"], 1027)
        self.assertEqual(rows[0]["volume_change_24h"], 4)

    def test_cmc_global_metrics_normalizes_dominance(self):
        result = narrative.parse_cmc_global_metrics({"data": {
            "btc_dominance": 56.2, "eth_dominance": 12.1,
            "quote": {"USD": {"total_market_cap": 2000000, "total_volume_24h": 100000}},
        }})
        self.assertEqual(result["bitcoin_dominance_pct"], 56.2)
        self.assertEqual(result["total_market_cap_usd"], 2000000)

    def test_cmc_fear_greed_and_altcoin_index(self):
        fear = narrative.parse_cmc_fear_greed({"data": {
            "value": 61, "value_classification": "Greed",
            "timestamp": "2026-10-31T12:00:00Z",
        }})
        season = narrative.parse_cmc_altcoin_season({"data": {
            "altcoin_index": 42, "snapshot_time": "2026-10-31T12:00:00Z",
        }})
        self.assertEqual(fear["value"], 61)
        self.assertEqual(fear["classification"], "Greed")
        self.assertEqual(season["index"], 42)

    def test_trendkia_parser_filters_old_and_unrelated_articles(self):
        now = narrative._parse_published_datetime("Sat, 31 Oct 2026 14:00:00 GMT").timestamp()
        source = """# Recent TrendKia articles

## Bitcoin market sees renewed volatility
- URL: https://trendkia.com/en/crypto/bitcoin-market-123
- Category: Crypto
- Published: Sat, 31 Oct 2026 13:31:53 GMT
- Summary: Bitcoin and Ethereum react to a Fed rate outlook.
- Language: en

## Local school recruitment update
- URL: https://trendkia.com/en/career/local-recruitment-456
- Category: Career
- Published: Sat, 31 Oct 2026 13:29:52 GMT
- Summary: New teacher recruitment dates were announced.
- Language: en

## Old Ethereum explainer
- URL: https://trendkia.com/en/crypto/old-ethereum-789
- Category: Crypto
- Published: Mon, 20 Oct 2026 13:29:52 GMT
- Summary: Ethereum historical background.
- Language: en
"""
        rows = narrative.parse_trendkia_articles(source, now_epoch=now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_id"], "trendkia_news")
        self.assertIn("Bitcoin", rows[0]["title"])
        self.assertEqual(rows[0]["url"], "https://trendkia.com/en/crypto/bitcoin-market-123")

    def test_trendkia_rejects_untrusted_url_and_missing_date(self):
        source = """## Bitcoin
- URL: http://trendkia.com/bitcoin
- Category: Crypto
- Published: Sat, 31 Oct 2026 13:31:53 GMT
- Summary: Bitcoin

## Ethereum
- URL: https://trendkia.com/ethereum
- Category: Crypto
- Summary: Ethereum
"""
        self.assertEqual(narrative.parse_trendkia_articles(source), [])

    def test_mcp_text_extraction_and_tool_error(self):
        result = narrative.extract_mcp_text({"result": {
            "content": [{"type": "text", "text": "Recent articles"}],
            "isError": False,
        }})
        self.assertEqual(result, "Recent articles")
        with self.assertRaises(RuntimeError):
            narrative.extract_mcp_text({"result": {"isError": True, "content": []}})

    def test_mcp_sse_transport_extracts_json_rpc_result(self):
        from types import SimpleNamespace
        response = SimpleNamespace(
            headers={"Content-Type": "text/event-stream"},
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"Recent"}]}}\n\n',
        )
        payload = narrative.NarrativeEngine._mcp_response_payload(response)
        self.assertEqual(narrative.extract_mcp_text(payload), "Recent")

    def test_rate_limit_sets_retry_after_cooldown(self):
        import logging
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
            engine.cache = {}
            engine.stop_file = Path(temp) / "stop.flag"
            engine.clock = lambda: 1000.0
            engine.logger = logging.getLogger("narrative-rate-limit-test")
            status = {}
            engine._fetch_source(
                "cmc", 300,
                lambda: (_ for _ in ()).throw(narrative.SourceRateLimited("HTTP 429", 7200)),
                status, count_fn=len,
            )
            self.assertFalse(engine._due("cmc", 300))
            self.assertGreater(engine.cache["cmc"]["retry_after_epoch"], 8000.0)
            self.assertIn("retry_after_utc", status)

    def test_free_source_refresh_intervals_are_conservative(self):
        self.assertGreaterEqual(narrative.SOURCE_INTERVALS["cmc_market_activity"], 1800)
        self.assertGreaterEqual(narrative.SOURCE_INTERVALS["cmc_global_metrics"], 3600)
        self.assertGreaterEqual(narrative.SOURCE_INTERVALS["cmc_id_map"], 3600)
        self.assertGreaterEqual(narrative.SOURCE_INTERVALS["trendkia_news"], 1800)


class CmcNarrativeCategoryTests(unittest.TestCase):
    def test_category_list_keeps_only_known_narrative_themes(self):
        rows = narrative.parse_cmc_categories({"data": [
            {"id": "ai-cat", "name": "AI & Big Data", "title": "Artificial Intelligence & Big Data",
             "description": "AI agent infrastructure", "num_tokens": 18,
             "avg_price_change": 4.0, "market_cap_change": 3.0, "volume_change": 20.0},
            {"id": "other-cat", "name": "Generic Portfolio", "title": "Investment Holdings",
             "description": "Unrelated venture portfolio", "num_tokens": 14,
             "avg_price_change": 20.0, "market_cap_change": 30.0, "volume_change": 80.0},
        ]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "ai-cat")
        self.assertIn("Yapay Zekâ (AI)", rows[0]["themes"])
        self.assertGreater(rows[0]["momentum_score"], 50)

    def test_category_members_require_exact_unique_cmc_id(self):
        summary = {"id": "ai-cat", "name": "AI & Big Data", "title": "AI & Big Data",
                   "description": "AI category", "momentum_score": 77.0}
        payload = {"data": {"1": {
            "id": "ai-cat", "name": "AI & Big Data",
            "coins": [
                {"id": 1027, "symbol": "ETH", "name": "Ethereum",
                 "quote": {"USD": {"price": 3000, "volume_24h": 1000,
                                   "percent_change_24h": 2, "volume_change_24h": 4}}},
                {"id": 777, "symbol": "ABC", "name": "Wrong CMC ID"},
                {"id": 9999, "symbol": "ETH", "name": "Same ticker, different project"},
            ],
        }}}
        result = narrative.parse_cmc_category_detail(payload, summary, {"ETH": 1027, "ABC": 1234})
        self.assertEqual(result["id"], "ai-cat")
        self.assertEqual([coin["symbol"] for coin in result["coins"]], ["ETH"])
        self.assertEqual(result["coins"][0]["price"], 3000)

    def test_category_is_discovery_not_independent_news(self):
        event = narrative.build_cmc_category_event({
            "id": "ai-cat", "name": "AI & Big Data",
            "description": "AI agents and artificial intelligence",
            "momentum_score": 82, "coins": [{"symbol": "FET"}, {"symbol": "RENDER"}],
        })
        self.assertIsNotNone(event)
        self.assertEqual(event["source_kind"], "topic_discovery")
        self.assertEqual(event["source_id"], "cmc_narrative_categories")

    def test_category_rank_is_limited_and_sorted_by_momentum(self):
        categories = [
            {"id": str(i), "themes": ["Yapay Zekâ (AI)"],
             "momentum_score": float(i), "num_tokens": 10}
            for i in range(1, 7)
        ]
        ranked = narrative.rank_cmc_narrative_categories(categories, limit=3)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0]["id"], "6")

    def test_aixbt_post_and_author_counts_add_community_activity_component(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(root=Path(temp), clock=lambda: 1793448000.0)
            event = {
                "event_id": "aixbt:t1", "source_id": "aixbt_topics",
                "source_kind": "topic_discovery", "rank": 2,
                "post_count": 100, "author_count": 25,
                "themes": ["Yapay Zekâ (AI)"],
                "symbols": [{"symbol": "FET", "confidence": "YÜKSEK"}],
            }
            rows, watch = engine._build_narratives([event], {}, [])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["score_version"], 2)
            self.assertIn("aixbt_community_activity", rows[0]["score_components"])
            self.assertEqual(watch[0]["symbol"], "FET")

    def test_dex_and_coingecko_flags_support_discovery_not_news_count(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(root=Path(temp), clock=lambda: 1793448000.0)
            event = {
                "event_id": "aixbt:t2", "source_id": "aixbt_topics",
                "source_kind": "topic_discovery", "rank": 3,
                "themes": ["Yapay Zekâ (AI)"],
                "symbols": [{"symbol": "FET", "confidence": "YÜKSEK"}],
            }
            rows, _watch = engine._build_narratives(
                [event], {"FET": {"dex_activity": True, "coingecko_trending": True}}, []
            )
            self.assertIn("market_discovery_activity", rows[0]["score_components"])
            self.assertEqual(rows[0]["coverage"]["independent_news_sources"], 0)

    def test_new_score_schema_does_not_create_false_interest_velocity(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(root=Path(temp), clock=lambda: 1793448000.0)
            previous = [{
                "narrative_id": "yapay-zeka-ai", "narrative_score": 15.0,
                "score_components": {"old_component": 15.0}, "score_version": 1,
            }]
            event = {
                "event_id": "aixbt:t3", "source_id": "aixbt_topics",
                "source_kind": "topic_discovery", "rank": 1,
                "post_count": 10, "author_count": 5,
                "themes": ["Yapay Zekâ (AI)"],
                "symbols": [{"symbol": "FET", "confidence": "YÜKSEK"}],
            }
            rows, _watch = engine._build_narratives([event], {}, previous)
            self.assertEqual(rows[0]["interest_direction"], "İLK GÖZLEM")
            self.assertIsNone(rows[0]["interest_change"])

    def test_aixbt_and_cmc_category_are_discovery_not_media_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(root=Path(temp), clock=lambda: 1793448000.0)
            aixbt = {
                "event_id": "aixbt:t4", "source_id": "aixbt_topics",
                "source_kind": "topic_discovery", "rank": 2,
                "post_count": 30, "author_count": 10,
                "themes": ["Yapay Zekâ (AI)"],
                "symbols": [{"symbol": "FET", "confidence": "YÜKSEK"}],
            }
            category = narrative.build_cmc_category_event({
                "id": "ai-cat", "name": "AI & Big Data",
                "description": "Artificial intelligence and AI agents",
                "momentum_score": 80, "coins": [{"symbol": "FET"}],
            })
            rows, _watch = engine._build_narratives([aixbt, category], {}, [])
            self.assertEqual(rows[0]["coverage"]["independent_news_sources"], 0)
            self.assertEqual(rows[0]["confidence"], "ORTA")
            self.assertIn("category_market_momentum", rows[0]["score_components"])


class NarrativeMarketDiscoveryMappingTests(unittest.TestCase):
    def test_fresh_cmc_quotes_override_older_category_snapshots(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        rows = engine._market_map(
            [
                {"symbol": "ETH", "name": "Ethereum", "percent_change_24h": -4.0,
                 "volume_24h": 100.0, "volume_change_24h": -5.0, "rank": 2},
                {"symbol": "ETH", "name": "Ethereum", "percent_change_24h": 3.0,
                 "volume_24h": 200.0, "volume_change_24h": 15.0, "rank": 2},
            ],
            [], {}, ["ETH"], {"ETH": ["Ethereum"]},
        )
        self.assertEqual(rows["ETH"]["percent_change_24h"], 3.0)
        self.assertEqual(rows["ETH"]["volume_24h"], 200.0)
        self.assertEqual(rows["ETH"]["volume_change_24h"], 15.0)

    def test_dex_and_coingecko_ticker_only_matches_are_not_discovery_evidence(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        rows = engine._market_map(
            [],
            [{"symbol": "ABC", "name": "Unrelated Project", "description": "Protocol update"}],
            {"coins": [{"item": {"symbol": "ABC", "name": "Another Unrelated Asset"}}]},
            ["ABC"], {"ABC": ["Canonical ABC Project"]},
        )
        self.assertNotIn("dex_activity", rows.get("ABC", {}))
        self.assertNotIn("coingecko_trending", rows.get("ABC", {}))

    def test_dex_and_coingecko_exact_project_name_matches_are_kept(self):
        engine = narrative.NarrativeEngine.__new__(narrative.NarrativeEngine)
        rows = engine._market_map(
            [],
            [{"symbol": "RENDER", "name": "Render Network", "description": "Official profile", "chain": "solana"}],
            {"coins": [{"item": {"symbol": "RENDER", "name": "Render Network"}}]},
            ["RENDER"], {"RENDER": ["Render Network"]},
        )
        self.assertTrue(rows["RENDER"]["dex_activity"])
        self.assertEqual(rows["RENDER"]["dex_chain"], "solana")
        self.assertTrue(rows["RENDER"]["coingecko_trending"])
