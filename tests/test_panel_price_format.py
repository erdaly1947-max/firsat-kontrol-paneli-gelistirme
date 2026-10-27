import unittest

from arayuz_bicim import format_price
from radar_core import _display_price, build_trade_plan


class PriceFormattingTests(unittest.TestCase):
    def test_very_small_prices_use_fixed_decimal_not_scientific_notation(self):
        self.assertEqual(format_price(4.41e-9), "0.00000000441")
        self.assertEqual(format_price(4.41e-6), "0.00000441")
        self.assertEqual(format_price(1e-12), "0.000000000001")

    def test_ordinary_prices_remain_readable(self):
        self.assertEqual(format_price(2.193400), "2.1934")
        self.assertEqual(format_price(10.0), "10")
        self.assertEqual(format_price(0.0000012300), "0.00000123")

    def test_significant_decimal_digits_are_not_rounded_away(self):
        self.assertEqual(format_price(1.234567890123456), "1.234567890123456")

    def test_radar_core_display_price_uses_real_decimal_import(self):
        self.assertEqual(_display_price(4.41e-10), "0.000000000441")
        self.assertEqual(_display_price(2.193400), "2.1934")

    def test_build_trade_plan_returns_technical_target_and_stop_text(self):
        candidate = {
            "data_freshness": "CANLI AKIŞ GÜNCEL",
            "phase": "C",
            "phase_timeframe": "15m",
            "latest_price": 2.2,
            "timeframes": {
                "15m": {"metrics": {
                    "close": 2.1, "breakout_level": 2.0, "previous_support": 1.8, "atr_14": 0.1,
                    "support_resistance_zones": [
                        {"kind": "resistance", "center": 2.5, "strong": True, "touch_count": 3}
                    ]
                }}
            }
        }
        plan = build_trade_plan(candidate)
        self.assertIn("1.8 USDT altındaki", plan["invalid_if"])
        self.assertTrue(plan["technical_targets_available"])
        self.assertEqual([item["price"] for item in plan["targets"]], [2.5])
        self.assertEqual(plan["targets"][0]["basis"], "Teyitli direnç bölgesi")

    def test_invalid_or_nonpositive_price_is_not_misrepresented_as_zero(self):
        for value in (None, True, False, 0, -0.1, float("nan"), float("inf"), "4.41"):
            with self.subTest(value=value):
                self.assertEqual(format_price(value), "—")


if __name__ == "__main__":
    unittest.main()
