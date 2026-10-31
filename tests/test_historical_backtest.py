"""Regression tests for the 154th decision: historical closed-candle replay."""
from __future__ import annotations

import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from binance_mum_arsivi import CandleArchive
from radar_core import score_opportunity
import tarihsel_geri_test as backtest


def stamp(value: str = "2026-01-05T00:00:00+00:00") -> int:
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def bar(open_ms: int, *, open_: float = 100.0, high: float = 101.0,
        low: float = 99.0, close: float = 100.0) -> dict:
    return {
        "t": open_ms, "o": open_, "h": high, "l": low, "c": close,
        "v": 10.0, "q": 1000.0, "n": 10, "closed": True, "synthetic": False,
    }


class HistoricalReplayTests(unittest.TestCase):
    def test_as_of_slice_excludes_candle_that_has_not_closed_yet(self):
        start = stamp()
        rows = [
            bar(start, close=100.0),
            bar(start + backtest.FIVE_MINUTES_MS, close=250.0),
        ]
        selected, notes = backtest._bars_as_of(
            rows, "5m", start + backtest.FIVE_MINUTES_MS,
        )
        self.assertEqual([item["t"] for item in selected], [start])
        self.assertEqual(notes, [])

    def test_only_latest_contiguous_candle_suffix_is_used_after_a_gap(self):
        start = stamp()
        rows = [
            bar(start),
            bar(start + 2 * backtest.FIVE_MINUTES_MS, close=103.0),
            bar(start + 3 * backtest.FIVE_MINUTES_MS, close=104.0),
        ]
        suffix, had_gap = backtest._continuous_suffix(rows, "5m")
        self.assertTrue(had_gap)
        self.assertEqual([item["t"] for item in suffix], [
            start + 2 * backtest.FIVE_MINUTES_MS,
            start + 3 * backtest.FIVE_MINUTES_MS,
        ])

    def test_forward_horizon_uses_first_close_at_or_after_deadline(self):
        start = stamp()
        rows = [
            bar(start + index * backtest.FIVE_MINUTES_MS, close=100.0 + index)
            for index in range(13)
        ]
        closes = backtest._series_close_times(rows, "5m")
        outcome = backtest._forward_return(rows, closes, start, 100.0, 3600)
        self.assertEqual(outcome["status"], "HESAPLANDI")
        self.assertEqual(outcome["close_price"], 112.0)
        self.assertEqual(outcome["return_pct"], 12.0)
        self.assertEqual(outcome["actual_elapsed_seconds"], 3600)

    def test_forward_horizon_with_a_candle_gap_is_not_scored(self):
        start = stamp()
        rows = [
            bar(start, close=100.0),
            bar(start + backtest.FIVE_MINUTES_MS, close=101.0),
            bar(start + 3 * backtest.FIVE_MINUTES_MS, close=103.0),
        ]
        closes = backtest._series_close_times(rows, "5m")
        result, issue = backtest._window_bars(rows, closes, start, 600)
        self.assertIsNone(result)
        self.assertIn("mum boşluğu", issue)

    def test_target_after_entry_is_detected_in_chronological_candles(self):
        start = stamp()
        rows = [
            bar(start, high=103.0, low=100.0, close=101.0),  # entry zone
            bar(start + backtest.FIVE_MINUTES_MS, high=109.0, low=103.0, close=108.0),  # target
        ]
        closes = backtest._series_close_times(rows, "5m")
        plan = {
            "entry_zone_low": 100.0, "entry_zone_high": 102.0,
            "entry_reference": 101.0, "stop_loss": 98.0,
            "targets": [{"price": 108.0, "name": "Hedef 1"}],
        }
        result = backtest._evaluate_technical_plan(plan, rows, closes, start)
        self.assertEqual(result["status"], "HEDEF 1 GÖZLENDİ")
        self.assertEqual(result["gross_return_pct"], round((108.0 / 101.0 - 1.0) * 100.0, 5))
        self.assertLess(result["estimated_net_return_pct"], result["gross_return_pct"])
        self.assertIn("gerçek mum içi dolum", result["entry_price_basis"])

    def test_same_candle_entry_and_target_is_reported_as_ambiguous(self):
        start = stamp()
        rows = [bar(start, high=109.0, low=100.0, close=104.0)]
        closes = backtest._series_close_times(rows, "5m")
        plan = {
            "entry_zone_low": 100.0, "entry_zone_high": 102.0,
            "entry_reference": 101.0, "stop_loss": 98.0,
            "targets": [{"price": 108.0}],
        }
        result = backtest._evaluate_technical_plan(plan, rows, closes, start)
        self.assertEqual(
            result["status"], "OLAY SIRASI BELİRSİZ — AYNI MUMDA GİRİŞ/HEDEF",
        )

    def test_same_candle_entry_and_stop_is_reported_as_ambiguous(self):
        start = stamp()
        rows = [bar(start, high=101.0, low=97.0, close=99.0)]
        closes = backtest._series_close_times(rows, "5m")
        plan = {
            "entry_zone_low": 100.0, "entry_zone_high": 102.0,
            "entry_reference": 101.0, "stop_loss": 98.0,
            "targets": [{"price": 108.0}],
        }
        result = backtest._evaluate_technical_plan(plan, rows, closes, start)
        self.assertEqual(
            result["status"], "OLAY SIRASI BELİRSİZ — AYNI MUMDA GİRİŞ/STOP",
        )

    def test_historical_score_does_not_treat_unknown_liquidity_as_a_failure(self):
        result = score_opportunity(
            {
                "data_freshness": "CANLI AKIŞ GÜNCEL",
                "btc_market_context_freshness": "TARİHSEL BTC VERİSİ EKSİK",
                "phase": "A",
                "timeframes": {},
            },
            btc_context={},
            historical=True,
        )
        self.assertIsNone(result["score_components"]["liquidity_tradability"])
        self.assertIsNone(result["strong_opportunity_qualified"])
        self.assertIn("likidite geçmişi yok", result["opportunity_score_basis"])
        self.assertIn("DEĞERLENDİRİLEMEDİ", result["strong_opportunity_qualification_status"])

    def test_candle_archive_lists_distinct_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = CandleArchive(Path(directory) / "candles.sqlite3")
            start = stamp()
            archive.upsert_bars("ETHUSDT", "5m", [bar(start)])
            archive.upsert_bars("BTCUSDT", "5m", [bar(start)])
            archive.upsert_bars("ETHUSDT", "15m", [bar(start)])
            self.assertEqual(archive.list_symbols("5m"), ["BTCUSDT", "ETHUSDT"])
            self.assertEqual(archive.list_symbols("15m"), ["ETHUSDT"])
            self.assertEqual(archive.list_symbols(), ["BTCUSDT", "ETHUSDT"])

    def test_end_to_end_runner_writes_observations_and_summary_from_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "candles.sqlite3"
            archive = CandleArchive(archive_path)
            start = stamp()
            rows = [
                bar(start + index * backtest.FIVE_MINUTES_MS, close=100.0 + index * 0.1)
                for index in range(40)
            ]
            archive.upsert_bars("BTCUSDT", "5m", rows)
            archive.upsert_bars("TESTUSDT", "5m", rows)

            def candidate_stub(symbol, bars_by_interval, btc_bars, pair, settings):
                current = bars_by_interval["5m"][-1]
                return {
                    "symbol": symbol,
                    "phase": "A",
                    "phase_timeframe": "5m",
                    "latest_price": current["c"],
                    "timeframes": {},
                    "findings": ["test kanıtı"],
                    "risk_plan": {},
                }

            def score_stub(candidate, *, btc_context=None, historical=False):
                self.assertTrue(historical)
                return {
                    "opportunity_score": 61,
                    "final_decision": "ERKEN ADAY",
                    "decision_reason": "test kararı",
                    "score_components": {"liquidity_tradability": None},
                    "opportunity_score_basis": "test — geçmiş likidite bilinmiyor",
                    "strong_opportunity_qualified": None,
                    "strong_opportunity_qualification_status": "DEĞERLENDİRİLEMEDİ",
                }

            with (
                patch.object(backtest, "evaluate_binance_candidate", side_effect=candidate_stub),
                patch.object(backtest, "build_trade_plan", return_value={"technical_targets_available": False}),
                patch.object(backtest, "score_opportunity", side_effect=score_stub),
                patch.object(backtest, "score_btc_market_context", return_value={"data_completeness": "TAM"}),
            ):
                result = backtest.run_historical_backtest(
                    archive_path=archive_path,
                    report_dir=root / "reports",
                    symbols=["TESTUSDT"],
                )

            self.assertEqual(result["tested_symbols"], ["TESTUSDT"])
            self.assertGreater(result["candidate_observation_count"], 0)
            self.assertEqual(result["signal_episode_count"], 1)
            self.assertTrue(Path(result["summary_json"]).is_file())
            self.assertTrue(Path(result["observations_csv_gz"]).is_file())
            summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["signal_episode_count"], 1)
            with gzip.open(result["observations_csv_gz"], "rt", encoding="utf-8", newline="") as handle:
                observations = list(csv.DictReader(handle))
            self.assertEqual(len(observations), result["candidate_observation_count"])
            self.assertTrue(all(
                "DEĞERLENDİRİLEMEDİ" in row["strong_opportunity_qualification_status"]
                for row in observations
            ))
            self.assertTrue(all(
                "DEĞERLENDİRİLEMEDİ" in row["narrative_history_status"]
                for row in observations
            ))


if __name__ == "__main__":
    unittest.main()
