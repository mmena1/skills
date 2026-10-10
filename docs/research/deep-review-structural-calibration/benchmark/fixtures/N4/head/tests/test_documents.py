import unittest
from datetime import date

from verification.documents import Document


class DocumentTests(unittest.TestCase):
    def test_document_fields(self):
        self.assertEqual(Document("Ana Diaz", date(2030, 1, 1)).holder_name, "Ana Diaz")


if __name__ == "__main__":
    unittest.main()
