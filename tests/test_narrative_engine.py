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



if __name__ == "__main__":
    unittest.main()
