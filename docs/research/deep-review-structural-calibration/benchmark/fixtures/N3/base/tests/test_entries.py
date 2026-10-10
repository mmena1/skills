import unittest
from decimal import Decimal

from ledger.entries import Entry


class EntryTests(unittest.TestCase):
    def test_entry_is_value(self):
        self.assertEqual(Entry("t1", Decimal("1.00"), "x"), Entry("t1", Decimal("1.00"), "x"))


if __name__ == "__main__":
    unittest.main()
