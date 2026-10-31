from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import naratif_avcisi as narrative


class NarrativeParsingTests(unittest.TestCase):
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
            "Ethereum (ETH) and $OP discussed. COINBASE is not COIN.",
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
            self.assertIn("doğrulanmadı", status["mode"])

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
                '{"AIXBT_API_KEY":"must-not-be-used","COINGECKO_DEMO_API_KEY":"must-not-be-used"}',
                encoding="utf-8",
            )
            engine = narrative.NarrativeEngine(root=root, session=object())
            self.assertNotIn("AIXBT_API_KEY", engine.settings)
            self.assertNotIn("COINGECKO_DEMO_API_KEY", engine.settings)




    def test_analysis_report_keeps_narrative_separate_from_technical_candidates(self):
        from analysis_report import build_analysis_report
        report = build_analysis_report(
            {"candidates": [{"symbol": "ETH", "opportunity_score": 70}]},
            {
                "status": "ÇALIŞIYOR",
                "generated_at_utc": "2026-10-31T09:00:00+00:00",
                "narratives": [{"name": "Katman-2 (Layer 2)", "narrative_score": 73}],
                "early_watch": [{"symbol": "ARB", "narrative_score": 73}],
                "source_statuses": {"aixbt_topics": {"name": "AIXBT Topics", "status": "BAĞLI"}},
            },
        )
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["narrative"]["narrative_count"], 1)
        self.assertEqual(report["narrative"]["early_watch"][0]["symbol"], "ARB")
        self.assertNotIn("narrative_score", report["candidates"][0])
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


if __name__ == "__main__":
    unittest.main()
