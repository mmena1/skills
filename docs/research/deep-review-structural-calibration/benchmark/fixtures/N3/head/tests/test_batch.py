import os
import tempfile
import unittest
from decimal import Decimal

from ledger.batch import record_batch
from ledger.entries import Entry, format_entry
from ledger.writer import LedgerWriter


class BatchTests(unittest.TestCase):
    def test_format_is_pure(self):
        self.assertEqual(format_entry(Entry("t1", Decimal("2.005"), "tea\tcake")), "t1\t2.00\ttea cake")

    def test_record_batch_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "till.txt")
            record_batch(path, [Entry("t1", Decimal("1"), "a")])
            record_batch(path, [Entry("t1", Decimal("2"), "b")])
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "t1\t1.00\ta\nt1\t2.00\tb\n")

    def test_append_requires_open_writer(self):
        with self.assertRaises(RuntimeError):
            LedgerWriter("unused").append("x")


if __name__ == "__main__":
    unittest.main()
