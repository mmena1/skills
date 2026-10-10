import unittest
from datetime import date

from loans.models import Loan
from loans.reports import active_loans, returned_late


class ReportTests(unittest.TestCase):
    def test_active_loans_keep_order(self):
        loans = [Loan("b1", "m1", date(2026, 1, 5)), Loan("b2", "m2", date(2026, 1, 6), date(2026, 1, 4))]
        self.assertEqual(active_loans(loans), [loans[0]])

    def test_returned_late(self):
        loans = [Loan("b1", "m1", date(2026, 1, 5), date(2026, 1, 9)), Loan("b2", "m2", date(2026, 1, 6), date(2026, 1, 6))]
        self.assertEqual(returned_late(loans), ["b1"])


if __name__ == "__main__":
    unittest.main()
