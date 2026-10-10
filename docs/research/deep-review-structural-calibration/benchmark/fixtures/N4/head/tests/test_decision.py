import unittest
from datetime import date

from verification.decision import next_step
from verification.documents import Document
from verification.evidence import EvidenceStatus, check_evidence

TODAY = date(2026, 3, 1)


class DecisionTests(unittest.TestCase):
    def test_missing_is_an_upload_request_not_a_rejection(self):
        check = check_evidence(None, "Ana Diaz", TODAY)
        self.assertIs(check.status, EvidenceStatus.MISSING)
        self.assertEqual(next_step(check).action, "request_upload")

    def test_invalid_reports_every_failure(self):
        check = check_evidence(Document("Ana Ruiz", date(2025, 1, 1)), "Ana Diaz", TODAY)
        self.assertEqual(next_step(check).action, "reject")
        self.assertEqual(len(next_step(check).applicant_messages), 2)

    def test_valid_is_approved(self):
        check = check_evidence(Document("ana diaz", date(2030, 1, 1)), "Ana Diaz", TODAY)
        self.assertEqual(next_step(check).action, "approve")


if __name__ == "__main__":
    unittest.main()
