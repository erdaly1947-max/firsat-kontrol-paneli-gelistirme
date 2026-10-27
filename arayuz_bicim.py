"""UI-safe number formatting shared by the desktop panel and unit tests."""
from decimal import Decimal, InvalidOperation
import math


def format_price(value: object) -> str:
    """Format positive numeric prices in fixed-point notation without dropping precision."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return "—"
    try:
        rendered = format(Decimal(str(number)), "f")
    except (InvalidOperation, ValueError, OverflowError):
        return "—"
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"
