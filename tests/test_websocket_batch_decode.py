"""Tests for compressed Binance WebSocket relay batches."""
import json
import zlib
import unittest

import binance_erken_firsat_radari as engine


class BinanceWebSocketBatchDecoderTests(unittest.TestCase):
    def test_fkp1_batch_decompresses_and_preserves_every_event_in_order(self):
        events = [
            {"data": {"e": "kline", "k": {"s": "BTCUSDT", "c": "1"}}},
            {"data": {"e": "kline", "k": {"s": "ETHUSDT", "c": "2"}}},
            {"data": {"e": "kline", "k": {"s": "BTCUSDT", "c": "3"}}},
        ]
        lines = [json.dumps(event, separators=(",", ":")) for event in events]
        raw = ("\n" + lines[0] + "\n\n" + lines[1] + "\n" + lines[2] + "\n").encode("utf-8")
        frame = b"FKP1" + zlib.compress(raw)

        decoded = engine._decode_binance_websocket_messages(frame)

        self.assertEqual(decoded, lines)
        symbols = [json.loads(line)["data"]["k"]["s"] for line in decoded]
        self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT", "BTCUSDT"])
        prices = [json.loads(line)["data"]["k"]["c"] for line in decoded]
        self.assertEqual(prices, ["1", "2", "3"])

    def test_plain_binary_and_text_frames_remain_supported(self):
        payload = '{"data":{"e":"kline","k":{"s":"SOLUSDT"}}}'
        self.assertEqual(
            engine._decode_binance_websocket_messages(payload.encode("utf-8")),
            [payload],
        )
        self.assertEqual(
            engine._decode_binance_websocket_messages(payload),
            [payload],
        )

    def test_invalid_fkp1_payload_fails_closed(self):
        with self.assertRaises((zlib.error, UnicodeDecodeError)):
            engine._decode_binance_websocket_messages(b"FKP1not-deflate-data")

    def test_non_text_frame_is_ignored(self):
        self.assertEqual(engine._decode_binance_websocket_messages(None), [])


if __name__ == "__main__":
    unittest.main()
