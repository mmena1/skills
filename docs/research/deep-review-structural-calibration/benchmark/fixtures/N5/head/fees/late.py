"""Late-return fee under the rental agreement."""

import math
from decimal import ROUND_HALF_UP, Decimal

from fees.money import CENT, ZERO

DAILY_RATE = Decimal("0.10")


def late_fee(rental_price: Decimal, hours_late: float) -> Decimal:
    if hours_late <= 0:
        return ZERO
    started_days = math.ceil(hours_late / 24)
    fee = rental_price * DAILY_RATE * started_days
    return min(fee, rental_price).quantize(CENT, rounding=ROUND_HALF_UP)
