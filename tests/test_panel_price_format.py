import unittest

from arayuz_bicim import format_price


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

    def test_invalid_or_nonpositive_price_is_not_misrepresented_as_zero(self):
        for value in (None, True, False, 0, -0.1, float("nan"), float("inf"), "4.41"):
            with self.subTest(value=value):
                self.assertEqual(format_price(value), "—")


if __name__ == "__main__":
    unittest.main()
