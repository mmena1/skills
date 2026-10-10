from dataclasses import dataclass
from decimal import Decimal

from shop.carriers.rates import CarrierRates


@dataclass(frozen=True)
class Line:
    price: Decimal
    quantity: int


@dataclass(frozen=True)
class Cart:
    lines: tuple[Line, ...]
    zone: str
    weight_kg: float


def subtotal(cart: Cart) -> Decimal:
    return sum((line.price * line.quantity for line in cart.lines), Decimal("0.00"))


def delivery_charge(cart: Cart, rates: CarrierRates) -> Decimal:
    if subtotal(cart) >= Decimal("50.00"):
        return Decimal("0.00")
    return rates.quote(cart.zone, cart.weight_kg)
