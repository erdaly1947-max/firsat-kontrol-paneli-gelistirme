import gzip
import io
import json
import urllib.error
import unittest
from unittest import mock

from analysis_report import (
    READ_URL,
    UPLOAD_URL,
    build_analysis_report,
    compress_analysis_report,
    gzip_compress_bytes,
    upload_analysis_report,
)


class AnalysisReportTests(unittest.TestCase):
    def test_report_keeps_decision_and_risk_plan_but_drops_raw_candles(self):
        state = {
            "application_version": "00",
            "generated_at_utc": "2026-10-26T12:00:00Z",
            "status": "RUNNING",
            "runtime_diagnostics": {"secret": "must-not-appear"},
            "btc_market_context": {"status": "BULLISH"},
            "candidates": [{
                "symbol": "ABCUSDT",
                "opportunity_score": 82,
                "final_decision": "GİRİŞ KOŞULU BEKLE",
                "risk_plan": {"entry_zone_low": 1.2, "stop_loss": 1.1, "targets": [{"price": 1.4}]},
                "recent_closed_candles": {"1h": [{"close": 1.0}]},
                "btc_market_context": {"duplicated": True},
                "timeframes": {"1h": {
                    "phase": "B",
                    "data_sufficient": True,
                    "findings": ["yükselen dipler"],
                    "metrics": {"rsi_14": 61.2, "macd_histogram": 0.02, "unused_blob": "drop",
                    "fibonacci": {"status": "TEYİTLİ SALINIM", "available": True, "direction": "down",
                        "retracements": {"retracement_0_618": 1.78}, "raw_blob": "drop"},
                    "support_resistance_zones": [{"kind": "support", "center": 1.2, "lower": 1.19,
                        "upper": 1.21, "touch_count": 3, "strong": True, "raw_blob": "drop"}],
                    "confirmed_channel": {"status": "TEYİTLİ KANAL", "available": True,
                        "direction": "YÜKSELEN", "upper_now": 1.4, "lower_now": 1.2, "raw_blob": "drop"}},
                }},
            }],
        }
        report = build_analysis_report(state)
        self.assertEqual(report["report_type"], "analysis")
        self.assertEqual(report["candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["final_decision"], "GİRİŞ KOŞULU BEKLE")
        self.assertEqual(candidate["risk_plan"]["stop_loss"], 1.1)
        self.assertNotIn("recent_closed_candles", candidate)
        self.assertNotIn("btc_market_context", candidate)
        self.assertNotIn("runtime_diagnostics", report)
        self.assertEqual(candidate["timeframes"]["1h"]["metrics"]["rsi_14"], 61.2)
        self.assertNotIn("unused_blob", candidate["timeframes"]["1h"]["metrics"])
        metrics = candidate["timeframes"]["1h"]["metrics"]
        self.assertEqual(metrics["fibonacci"]["retracements"]["retracement_0_618"], 1.78)
        self.assertNotIn("raw_blob", metrics["fibonacci"])
        self.assertEqual(metrics["support_resistance_zones"][0]["center"], 1.2)
        self.assertNotIn("raw_blob", metrics["support_resistance_zones"][0])
        self.assertEqual(metrics["confirmed_channel"]["direction"], "YÜKSELEN")
        self.assertNotIn("raw_blob", metrics["confirmed_channel"])

    def test_gzip_round_trip_and_size_reduction(self):
        state = {"candidates": [{"symbol": "ABCUSDT", "findings": ["yükselen dip"] * 100}]}
        payload = build_analysis_report(state)
        compressed = compress_analysis_report(payload)
        decoded = json.loads(gzip.decompress(compressed).decode("utf-8"))
        self.assertEqual(decoded["candidate_count"], 1)
        self.assertLess(len(compressed), len(json.dumps(payload, ensure_ascii=False).encode("utf-8")))

    def test_gzip_compress_bytes_round_trip(self):
        raw = ("Fırsat-Kontrol Paneli raporu\n" * 100).encode("utf-8")
        compressed = gzip_compress_bytes(raw)
        self.assertEqual(gzip.decompress(compressed), raw)
        self.assertLess(len(compressed), len(raw))
        self.assertEqual(compressed, gzip_compress_bytes(raw))

    def test_analysis_upload_posts_gzip_json_to_the_fixed_relay(self):
        payload = {
            "report_type": "analysis",
            "schema_version": 1,
            "candidate_count": 1,
            "candidates": [{"symbol": "ABCUSDT", "final_decision": "İZLE"}],
        }
        raw_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(raw_json)
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 201
        response.read.return_value = json.dumps({
            "ok": True,
            "report_type": "analysis",
            "candidate_count": 1,
            "read_url": READ_URL,
        }).encode("utf-8")
        config = {"upload_url": UPLOAD_URL, "upload_token": "test-upload-token", "read_url": READ_URL}

        with mock.patch("analysis_report.urllib.request.urlopen", return_value=response) as urlopen:
            result = upload_analysis_report(config, compressed)

        request = urlopen.call_args.args[0]
        headers = {name.lower(): value for name, value in request.header_items()}
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, UPLOAD_URL)
        self.assertEqual(headers["authorization"], "Bearer test-upload-token")
        self.assertEqual(headers["content-encoding"], "gzip")
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(gzip.decompress(request.data), raw_json)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 25)
        self.assertEqual(result["report_kind"], "analysis")
        self.assertEqual(result["read_url"], READ_URL)
        self.assertEqual(result["candidate_count"], 1)

    def test_analysis_upload_retries_transient_connection_failure(self):
        payload = {
            "report_type": "analysis",
            "schema_version": 1,
            "candidate_count": 1,
            "candidates": [{"symbol": "ABCUSDT"}],
        }
        compressed = gzip.compress(json.dumps(payload).encode("utf-8"))
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = json.dumps({"ok": True, "candidate_count": 1}).encode("utf-8")
        config = {"upload_url": UPLOAD_URL, "upload_token": "test-upload-token", "read_url": READ_URL}

        with mock.patch(
            "analysis_report.urllib.request.urlopen",
            side_effect=[urllib.error.URLError("connection reset"), response],
        ) as urlopen, mock.patch("analysis_report.time.sleep") as sleep:
            result = upload_analysis_report(config, compressed)

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1.0)
        self.assertTrue(result["ok"])

    def test_analysis_upload_does_not_retry_permanent_http_401(self):
        payload = {
            "report_type": "analysis",
            "schema_version": 1,
            "candidate_count": 1,
            "candidates": [{"symbol": "ABCUSDT"}],
        }
        compressed = gzip.compress(json.dumps(payload).encode("utf-8"))
        config = {"upload_url": UPLOAD_URL, "upload_token": "test-upload-token", "read_url": READ_URL}
        denied = urllib.error.HTTPError(
            UPLOAD_URL, 401, "Unauthorized", {}, io.BytesIO(b'{"ok":false,"error":"denied"}'),
        )

        with mock.patch("analysis_report.urllib.request.urlopen", side_effect=denied) as urlopen, \
             mock.patch("analysis_report.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "Sunucu HTTP 401"):
                upload_analysis_report(config, compressed)

        urlopen.assert_called_once()
        sleep.assert_not_called()

    def test_invalid_nan_is_not_silently_serialized(self):
        with self.assertRaises(ValueError):
            compress_analysis_report({"report_type": "analysis", "bad": float("nan")})


if __name__ == "__main__":
    unittest.main()
