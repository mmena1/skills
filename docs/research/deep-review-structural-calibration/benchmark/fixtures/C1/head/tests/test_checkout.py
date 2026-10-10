import unittest
from decimal import Decimal

from shop.carriers.rates import CarrierRates
from shop.checkout.banner import delivery_banner
from shop.checkout.cart import Cart, Line, delivery_charge


class CheckoutTests(unittest.TestCase):
    def test_free_delivery_and_quote(self):
        rates = CarrierRates()
        self.assertEqual(delivery_charge(Cart((Line(Decimal("25.00"), 2),), "city", 1), rates), Decimal("0.00"))
        self.assertEqual(delivery_charge(Cart((Line(Decimal("10.00"), 1),), "island", 1), rates), Decimal("11.20"))

    def test_banner(self):
        self.assertEqual(delivery_banner(Decimal("50.00")), "Your order ships free.")
        self.assertEqual(delivery_banner(Decimal("45.50")), "Add 4.50 more for free delivery.")


if __name__ == "__main__":
    unittest.main()
