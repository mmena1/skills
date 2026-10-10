"""Carrier contract rules: zone rates, remote fallback and surcharges."""

from decimal import Decimal

RATE_TABLE = {"city": Decimal("3.90"), "regional": Decimal("5.50"), "national": Decimal("7.20")}
REMOTE_SURCHARGE = Decimal("4.00")
HEAVY_LIMIT_KG = 20
HEAVY_SURCHARGE = Decimal("6.50")


class CarrierRates:
    def __init__(self, table=RATE_TABLE):
        self._table = dict(table)

    def quote(self, zone: str, weight_kg: float) -> Decimal:
        if zone in self._table:
            price = self._table[zone]
        else:
            price = self._table["national"] + REMOTE_SURCHARGE
        if weight_kg > HEAVY_LIMIT_KG:
            price += HEAVY_SURCHARGE
        return price
