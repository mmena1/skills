from decimal import Decimal

FREE_DELIVERY_MINIMUM = Decimal("50.00")


def qualifies_for_free_delivery(subtotal: Decimal) -> bool:
    return subtotal >= FREE_DELIVERY_MINIMUM
