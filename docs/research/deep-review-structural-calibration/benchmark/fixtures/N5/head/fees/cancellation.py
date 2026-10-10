"""Workshop cancellation fee under the consumer booking terms."""

from decimal import ROUND_DOWN, Decimal

from fees.money import CENT

RATE = Decimal("0.15")
MINIMUM = Decimal("5.00")


def cancellation_fee(booking_price: Decimal, amount_paid: Decimal) -> Decimal:
    fee = max(booking_price * RATE, MINIMUM)
    return min(fee, amount_paid).quantize(CENT, rounding=ROUND_DOWN)
