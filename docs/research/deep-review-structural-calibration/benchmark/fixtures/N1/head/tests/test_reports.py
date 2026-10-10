import unittest
from datetime import date

from loans.models import Loan
from loans.reports import active_loans, overdue_members, returned_late


class ReportTests(unittest.TestCase):
    def test_active_loans_keep_order(self):
        loans = [Loan("b1", "m1", date(2026, 1, 5)), Loan("b2", "m2", date(2026, 1, 6), date(2026, 1, 4))]
        self.assertEqual(active_loans(loans), [loans[0]])

    def test_returned_late(self):
        loans = [Loan("b1", "m1", date(2026, 1, 5), date(2026, 1, 9)), Loan("b2", "m2", date(2026, 1, 6), date(2026, 1, 6))]
        self.assertEqual(returned_late(loans), ["b1"])

    def test_overdue_members_first_seen_without_repeats(self):
        loans = [
            Loan("b1", "m2", date(2026, 1, 1)),
            Loan("b2", "m1", date(2026, 1, 2)),
            Loan("b3", "m2", date(2026, 1, 3)),
            Loan("b4", "m3", date(2026, 1, 3), date(2026, 1, 2)),
            Loan("b5", "m4", date(2026, 2, 1)),
        ]
        self.assertEqual(overdue_members(loans, date(2026, 1, 10)), ["m2", "m1"])


if __name__ == "__main__":
    unittest.main()
