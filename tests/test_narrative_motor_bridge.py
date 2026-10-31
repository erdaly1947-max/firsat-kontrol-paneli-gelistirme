from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import binance_erken_firsat_radari as radar
import naratif_avcisi as narrative


class NarrativeMotorBridgeTests(unittest.TestCase):
    def test_technical_candidates_are_sent_and_narrative_coins_get_multitimeframe_tracking(self):
        candidate = {
            "symbol": "ETHUSDT",
            "base_asset": "ETH",
            "phase": "B",
            "phase_timeframe": "15m",
            "state": "İLK DOĞRULAMA",
            "latest_price": 3100.0,
            "data_freshness": "CANLI AKIŞ GÜNCEL",
            "opportunity_score": 74.0,
            "final_decision": "İZLE",
            "findings": ["15m fiyat yapısı ve hacim doğrulaması"],
            "relative_strength_vs_btc_pct_points": {"15m": 1.4, "1h": 2.1, "4h": 0.8},
            "btc_return_correlation": {"1h": {"value": 0.72, "observations": 60}},
            "timeframes": {
                "15m": {
                    "phase": "B", "state": "İLK DOĞRULAMA",
                    "data_sufficient": True, "closed_bars": 45,
                    "required_closed_bars": 42,
                    "metrics": {
                        "close": 3100.0, "rsi_14": 63.5,
                        "macd_histogram": 2.2, "adx_14": 28.0,
                        "ema_confirmed_bullish": True,
                    },
                },
            },
        }
        narrative_state = {
            "generated_at_utc": "2026-10-31T14:00:00+00:00",
            "early_watch": [
                {
                    "symbol": "ETH", "narrative_score": 82,
                    "phase": "GÜÇLENME", "narratives": ["Yapay Zekâ (AI)"],
                    "confidence": "ORTA",
                },
                {
                    "symbol": "SOL", "narrative_score": 70,
                    "phase": "YAYILMA", "narratives": ["DeFi"],
                    "confidence": "DÜŞÜK",
                },
            ],
        }
        bridge = radar.build_narrative_motor_bridge_payload(
            [candidate], narrative_state,
            generated_at_utc="2026-10-31T14:01:00+00:00",
            narrative_state_fresh=True,
        )
        self.assertEqual(len(bridge["technical_candidates"]), 1)
        self.assertEqual(bridge["technical_candidates"][0]["symbol"], "ETH")
        watch = {item["symbol"]: item for item in bridge["narrative_technical_watch"]}
        self.assertEqual(watch["ETH"]["technical_phase"], "B")
        self.assertEqual(watch["ETH"]["timeframes"]["15m"]["metrics"]["rsi_14"], 63.5)
        self.assertEqual(watch["SOL"]["technical_status"], "TEKNİK VERİ BEKLENİYOR")
        self.assertEqual(candidate["opportunity_score"], 74.0)
        self.assertNotIn("narrative_score", candidate)

    def test_technical_candidate_research_distinguishes_found_and_missing_evidence(self):
        now = 1793455200.0
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(
                root=Path(temp), clock=lambda: now,
            )
            bridge = {
                "generated_at_utc": stamp,
                "technical_candidates": [
                    {"symbol": "ETH", "phase": "B", "phase_timeframe": "15m",
                     "state": "İLK DOĞRULAMA", "opportunity_score": 74, "latest_price": 3100},
                    {"symbol": "SOL", "phase": "A", "phase_timeframe": "1h",
                     "state": "ERKEN HAZIRLIK", "opportunity_score": 61, "latest_price": 150},
                ],
            }
            events = [{
                "event_id": "news:eth",
                "title": "Ethereum AI infrastructure activity grows",
                "source_name": "CoinDesk",
                "source_kind": "media",
                "published_at": stamp,
                "url": "https://example.test/eth",
                "themes": ["Yapay Zekâ (AI)"],
                "evidence_class": "HABER/KATALİZÖR",
                "symbols": [{"symbol": "ETH", "confidence": "YÜKSEK"}],
            }]
            early_watch = [{
                "symbol": "ETH",
                "narratives": ["Yapay Zekâ (AI)"],
                "narrative_score": 82,
            }]
            statuses = {
                "rss_coindesk": {
                    "name": "CoinDesk", "enabled": True,
                    "status": "BAĞLI", "item_count": 1,
                },
            }
            result = engine._build_technical_candidate_research(
                bridge, events, early_watch, statuses,
            )
        by_symbol = {item["symbol"]: item for item in result["items"]}
        self.assertEqual(result["status"], "GÜNCEL")
        self.assertEqual(by_symbol["ETH"]["status"], "NARATİF EŞLEŞMESİ BULUNDU")
        self.assertEqual(by_symbol["ETH"]["matched_narratives"], ["Yapay Zekâ (AI)"])
        self.assertEqual(by_symbol["SOL"]["status"], "TARAMA YAPILDI — KANIT BULUNAMADI")
        self.assertEqual(by_symbol["SOL"]["technical_phase"], "A")

    def test_stale_technical_handoff_is_not_presented_as_current_research(self):
        now = 1793455200.0
        old_stamp = datetime.fromtimestamp(now - 3600, timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as temp:
            engine = narrative.NarrativeEngine(root=Path(temp), clock=lambda: now)
            result = engine._build_technical_candidate_research(
                {"generated_at_utc": old_stamp,
                 "technical_candidates": [{"symbol": "ETH", "phase": "B"}]},
                [], [], {},
            )
        self.assertFalse(result["handoff_fresh"])
        self.assertEqual(result["items"][0]["status"], "TEKNİK ADAY AKTARIMI ESKİ")


if __name__ == "__main__":
    unittest.main()
