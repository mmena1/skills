import unittest
from decimal import Decimal

from shop.carriers.rates import CarrierRates


class RateTests(unittest.TestCase):
    def test_remote_and_heavy(self):
        self.assertEqual(CarrierRates().quote("island", 21), Decimal("17.70"))
        self.assertEqual(CarrierRates().quote("city", 1), Decimal("3.90"))


if __name__ == "__main__":
    unittest.main()
