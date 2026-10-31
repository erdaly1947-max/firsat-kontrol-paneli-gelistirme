"""Tests for the optional cloud market-data relay routing."""
import time
import unittest
from unittest.mock import patch

import requests
import ortak_piyasa


class MarketDataRelayTests(unittest.TestCase):
    def test_blank_relay_keeps_official_direct_hosts(self):
        self.assertIsNone(ortak_piyasa.get_market_data_relay_url({}))
        self.assertEqual(ortak_piyasa.get_binance_rest_bases({}), ortak_piyasa.BINANCE_REST_BASES[:1])
        self.assertEqual(
            ortak_piyasa.get_binance_ws_bases({})[0],
            "wss://data-stream.binance.vision:443/stream?streams=",
        )

    def test_relay_origin_is_normalized(self):
        self.assertEqual(
            ortak_piyasa.get_market_data_relay_url({"market_data_relay_url": "https://example.workers.dev/"}),
            "https://example.workers.dev",
        )

    def test_unsafe_relay_origins_are_rejected(self):
        for value in (
            "http://example.workers.dev",
            "https://user:pass@example.workers.dev",
            "https://example.workers.dev/base-path",
            "https://example.workers.dev/?url=hidden",
            "https://api.binance.com",
            "https://api.btcturk.com",
            "https://example.workers.dev:8443",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ortak_piyasa.get_market_data_relay_url({"market_data_relay_url": value})

    def test_direct_hosts_are_first_and_render_is_last_fallback(self):
        settings = {"market_data_relay_url": "https://firsat.example.workers.dev"}
        self.assertEqual(
            ortak_piyasa.get_binance_rest_bases(settings),
            ortak_piyasa.BINANCE_REST_BASES[:1],
        )
        self.assertEqual(
            ortak_piyasa._market_direct_urls(
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT",
                "binance_rest",
            ),
            (
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT",
                *(
                    base + "/api/v3/klines?symbol=BTCUSDT"
                    for base in ortak_piyasa.BINANCE_REST_BASES
                    if base != "https://api.binance.com"
                ),
            ),
        )
        websocket_bases = ortak_piyasa.get_binance_ws_bases(settings)
        self.assertEqual(
            websocket_bases[:-1],
            (
                "wss://data-stream.binance.vision:443/stream?streams=",
                "wss://stream.binance.com:443/stream?streams=",
                "wss://stream.binance.com:9443/stream?streams=",
            ),
        )
        self.assertEqual(
            websocket_bases[-1],
            "wss://firsat.example.workers.dev/ws/binance/stream?streams=",
        )

    @staticmethod
    def _json_response():
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"ok":true}'
        response.headers["Content-Type"] = "application/json"
        return response

    def setUp(self):
        ortak_piyasa._reset_market_route_state_for_tests()

    def test_direct_rest_success_does_not_contact_render(self):
        direct_url = "https://api.binance.com/api/v3/klines"
        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get",
                         return_value=self._json_response()) as request,
        ):
            response = ortak_piyasa.public_get(
                direct_url, params={"symbol": "BTCUSDT", "interval": "5m"}
            )
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], direct_url)
        self.assertEqual(
            ortak_piyasa.get_market_route_status()["binance_rest"]["mode"], "direct"
        )

    def test_direct_fallback_checks_all_binance_hosts_before_render(self):
        relay_url = "https://firsat.example.workers.dev/binance/api/v3/klines"
        direct_urls = ortak_piyasa._market_direct_urls(
            "https://api.binance.com/api/v3/klines", "binance_rest"
        )

        def request(url, **kwargs):
            if url in direct_urls:
                raise requests.exceptions.ConnectTimeout("direct timeout")
            if url == relay_url:
                return self._json_response()
            raise AssertionError("Beklenmeyen bağlantı adresi: " + url)

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request) as mocked,
        ):
            response = ortak_piyasa.public_get(
                direct_urls[0],
                params={"symbol": "BTCUSDT", "interval": "5m"},
            )
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(mocked.call_count, len(direct_urls) + 1)
        self.assertEqual(
            [call.args[0] for call in mocked.call_args_list],
            [*direct_urls, relay_url],
        )
        status = ortak_piyasa.get_market_route_status()["binance_rest"]
        self.assertEqual(status["mode"], "render")
        self.assertEqual(status["last_transport"], "render")
        self.assertGreater(status["retry_direct_in_seconds"], 0)

    def test_alternate_direct_binance_host_avoids_render(self):
        direct_urls = [
            base + "/api/v3/klines" for base in ortak_piyasa.BINANCE_REST_BASES
        ]

        def request(url, **kwargs):
            if url == direct_urls[0]:
                raise requests.exceptions.ConnectTimeout("first host blocked")
            if url == direct_urls[1]:
                return self._json_response()
            raise AssertionError("İkinci doğrudan uç noktadan sonra Render çağrılmamalı.")

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request) as mocked,
        ):
            response = ortak_piyasa.public_get(direct_urls[0])
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual([call.args[0] for call in mocked.call_args_list], direct_urls[:2])
        self.assertEqual(
            ortak_piyasa.get_market_route_status()["binance_rest"]["mode"], "direct"
        )

    def test_tls_runtime_error_uses_render_fallback(self):
        relay_url = "https://firsat.example.workers.dev/btcturk/api/v2/ticker"

        def request(url, **kwargs):
            if url.startswith("https://api.btcturk.com/"):
                raise RuntimeError("TLS direct fallback chain exhausted")
            if url == relay_url:
                return self._json_response()
            raise AssertionError("Beklenmeyen bağlantı adresi: " + url)

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request) as mocked,
        ):
            response = ortak_piyasa.public_get("https://api.btcturk.com/api/v2/ticker")
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(mocked.call_args_list[1].args[0], relay_url)
        self.assertEqual(
            ortak_piyasa.get_market_route_status()["btcturk_rest"]["mode"], "render"
        )

    def test_exchange_rate_limit_does_not_trigger_render_failover(self):
        limited = requests.Response()
        limited.status_code = 429

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(
                ortak_piyasa, "_requests_get",
                side_effect=requests.exceptions.HTTPError("rate limited", response=limited),
            ) as mocked,
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                ortak_piyasa.public_get("https://api.binance.com/api/v3/klines")
        self.assertEqual(mocked.call_count, 1)
        self.assertTrue(mocked.call_args.args[0].startswith("https://api.binance.com/"))

    def test_render_cooldown_avoids_repeating_direct_failures(self):
        relay_url = "https://firsat.example.workers.dev/binance/api/v3/klines"
        ortak_piyasa._market_route_states["binance_rest"] = {
            "mode": "render", "direct_failures": 1,
            "retry_direct_at": time.monotonic() + 120,
            "last_transport": "render", "last_error": "ConnectTimeout",
        }
        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get",
                         return_value=self._json_response()) as mocked,
        ):
            ortak_piyasa.public_get("https://api.binance.com/api/v3/klines")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(mocked.call_args.args[0], relay_url)

    def test_render_failure_during_cooldown_immediately_recovers_direct_route(self):
        relay_url = "https://firsat.example.workers.dev/binance/api/v3/klines"
        direct_url = "https://api.binance.com/api/v3/klines"
        ortak_piyasa._market_route_states["binance_rest"] = {
            "mode": "render", "direct_failures": 1,
            "retry_direct_at": time.monotonic() + 120,
            "last_transport": "render", "last_error": "ConnectTimeout",
        }

        def request(url, **kwargs):
            if url == relay_url:
                raise requests.exceptions.ConnectionError("Render suspended")
            if url == direct_url:
                return self._json_response()
            raise AssertionError("Başarılı ilk doğrudan uçtan sonra yeni host denenmemeli: " + url)

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request) as mocked,
        ):
            response = ortak_piyasa.public_get(direct_url)

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(
            [call.args[0] for call in mocked.call_args_list],
            [relay_url, direct_url],
        )
        status = ortak_piyasa.get_market_route_status()["binance_rest"]
        self.assertEqual(status["mode"], "direct")
        self.assertEqual(status["direct_failures"], 0)

    def test_render_and_direct_failure_during_cooldown_retries_both_routes(self):
        relay_url = "https://firsat.example.workers.dev/binance/api/v3/klines"
        direct_urls = ortak_piyasa._market_direct_urls(
            "https://api.binance.com/api/v3/klines", "binance_rest"
        )
        ortak_piyasa._market_route_states["binance_rest"] = {
            "mode": "render", "direct_failures": 1,
            "retry_direct_at": time.monotonic() + 120,
            "last_transport": "render", "last_error": "ConnectTimeout",
        }

        def request(url, **kwargs):
            raise requests.exceptions.ConnectionError("route unavailable: " + url)

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request) as mocked,
        ):
            with self.assertRaisesRegex(RuntimeError, "doğrudan ve Render piyasa bağlantıları başarısız"):
                ortak_piyasa.public_get("https://api.binance.com/api/v3/klines")

        self.assertEqual(
            [call.args[0] for call in mocked.call_args_list],
            [relay_url, *direct_urls],
        )

    def test_direct_route_is_retested_after_render_cooldown_and_recovers(self):
        ortak_piyasa._market_route_states["binance_rest"] = {
            "mode": "render", "direct_failures": 2,
            "retry_direct_at": time.monotonic() - 1,
            "last_transport": "render", "last_error": "ConnectTimeout",
        }
        direct_url = "https://api.binance.com/api/v3/klines"
        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get",
                         return_value=self._json_response()) as mocked,
        ):
            ortak_piyasa.public_get(direct_url)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(mocked.call_args.args[0], direct_url)
        status = ortak_piyasa.get_market_route_status()["binance_rest"]
        self.assertEqual(status["mode"], "direct")
        self.assertEqual(status["direct_failures"], 0)

    def test_btc_and_binance_route_statuses_are_independent(self):
        def request(url, **kwargs):
            if "api.btcturk.com" in url:
                raise requests.exceptions.ConnectionError("blocked")
            return self._json_response()

        with (
            patch.object(ortak_piyasa, "get_market_data_relay_url",
                         return_value="https://firsat.example.workers.dev"),
            patch.object(ortak_piyasa, "_requests_get", side_effect=request),
        ):
            ortak_piyasa.public_get("https://api.btcturk.com/api/v2/ticker")
            ortak_piyasa.public_get("https://api.binance.com/api/v3/exchangeInfo")
        status = ortak_piyasa.get_market_route_status()
        self.assertEqual(status["btcturk_rest"]["mode"], "render")
        self.assertEqual(status["binance_rest"]["mode"], "direct")

    def test_only_allowlisted_exchange_urls_are_rewritten(self):
        relay = "https://firsat.example.workers.dev"
        self.assertEqual(
            ortak_piyasa._relay_public_exchange_url(
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m", relay
            ),
            "https://firsat.example.workers.dev/binance/api/v3/klines?symbol=BTCUSDT&interval=5m",
        )
        self.assertEqual(
            ortak_piyasa._relay_public_exchange_url(
                "https://api.btcturk.com/api/v2/server/exchangeinfo", relay
            ),
            "https://firsat.example.workers.dev/btcturk/api/v2/server/exchangeinfo",
        )
        self.assertEqual(
            ortak_piyasa._relay_public_exchange_url(
                "https://api.btcturk.com/api/v2/orderbook?pairSymbol=BTCUSDT&limit=25", relay
            ),
            "https://firsat.example.workers.dev/btcturk/api/v2/orderbook?pairSymbol=BTCUSDT&limit=25",
        )
        self.assertEqual(
            ortak_piyasa._relay_public_exchange_url(
                "https://graph-api.btcturk.com/v1/klines/history?symbol=BTCUSDT&resolution=15&from=1&to=2", relay
            ),
            "https://firsat.example.workers.dev/btcturk-graph/v1/klines/history?symbol=BTCUSDT&resolution=15&from=1&to=2",
        )
        with self.assertRaisesRegex(ValueError, "izin listesinden"):
            ortak_piyasa._relay_public_exchange_url(
                "https://api.binance.com/api/v3/account", relay
            )

    def test_non_exchange_urls_are_not_rewritten(self):
        value = "https://example.org/data?x=1"
        self.assertEqual(ortak_piyasa._relay_public_exchange_url(value, "https://firsat.example.workers.dev"), value)


if __name__ == "__main__":
    unittest.main()
