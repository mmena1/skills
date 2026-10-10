import unittest
from decimal import Decimal

from fees.cancellation import cancellation_fee
from fees.late import late_fee


class LateFeeTests(unittest.TestCase):
    def test_started_days_and_cap(self):
        self.assertEqual(late_fee(Decimal("40.05"), 1), Decimal("4.01"))
        self.assertEqual(late_fee(Decimal("40.00"), 25), Decimal("8.00"))
        self.assertEqual(late_fee(Decimal("40.00"), 24 * 30), Decimal("40.00"))
        self.assertEqual(late_fee(Decimal("40.00"), 0), Decimal("0.00"))


class CancellationFeeTests(unittest.TestCase):
    def test_minimum_rounding_and_paid_cap(self):
        self.assertEqual(cancellation_fee(Decimal("20.00"), Decimal("20.00")), Decimal("5.00"))
        self.assertEqual(cancellation_fee(Decimal("99.99"), Decimal("99.99")), Decimal("14.99"))
        self.assertEqual(cancellation_fee(Decimal("99.99"), Decimal("3.00")), Decimal("3.00"))


if __name__ == "__main__":
    unittest.main()
