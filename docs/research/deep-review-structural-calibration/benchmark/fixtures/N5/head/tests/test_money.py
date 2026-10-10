import unittest
from decimal import Decimal

from fees.money import CENT


class MoneyTests(unittest.TestCase):
    def test_cent(self):
        self.assertEqual(CENT, Decimal("0.01"))


if __name__ == "__main__":
    unittest.main()
