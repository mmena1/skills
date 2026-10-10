from decimal import Decimal

from shop.pricing.delivery import FREE_DELIVERY_MINIMUM, qualifies_for_free_delivery


def delivery_banner(subtotal: Decimal) -> str:
    if qualifies_for_free_delivery(subtotal):
        return "Your order ships free."
    return f"Add {FREE_DELIVERY_MINIMUM - subtotal:.2f} more for free delivery."
