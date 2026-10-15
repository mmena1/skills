"""Fidelity tests for the synthetic records against protocol.md at 388a424. Research only, issue #121.

Expected values are copied from the protocol text, not derived from the generator.
"""

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import synthetic_records  # noqa: E402

FULL_REVIEW_ROWS = {
    "zero hypotheses", "surviving hypotheses", "capacity-bounded static validation", "multiple selected scouts",
    "insufficient scout capacity", "validator probes", "scout failure", "validator partial failure",
    "PR-review-overlap", "PR head change", "cleanup",
}
FULL_REVIEW_ONLY_ROWS = {
    "zero hypotheses", "surviving hypotheses", "multiple selected scouts", "insufficient scout capacity", "scout failure",
}
FOLLOW_UP_ROWS = {
    "fixed concern", "persisting defect", "partial fix", "missing prior evidence", "explicitly deferred concern",
    "resolved thread with a persisting defect", "head change during revalidation", "multiple selected concerns",
    "follow-up validator capacity", "record discovery in a later session",
    "discovery when the newest record is a narrower follow-up", "record preservation from a linked worktree",
    "record preservation under a write restriction",
}
CONCERN_OUTCOMES = {"Finding", "Unresolved"}


def final_outcomes(record: dict) -> dict:
    """Each canonical ID's last recorded outcome: a writable adjudication replaces its static transition."""
    finals = {}
    for outcome in record["validator_outcomes"]:
        finals[outcome["hypothesis"]] = outcome
    return finals


class FullReviewFidelityTests(unittest.TestCase):
    def test_only_final_findings_and_unresolved_items_are_published_or_compared(self):
        for profile in ("large", "medium"):
            with self.subTest(profile=profile):
                record = synthetic_records.build(profile)
                finals = final_outcomes(record)
                self.assertNotIn("Needs probe", {o["outcome"] for o in finals.values()})
                published = [c["concern_id"] for c in json.loads(record["publication"]["payload"])["comments"]]
                self.assertTrue(published)
                for concern in published + [d["hypothesis"] for d in record["pr_discussion"]["dispositions"]]:
                    self.assertIn(finals[concern]["outcome"], CONCERN_OUTCOMES, concern)

    def test_the_receipt_has_every_full_review_row(self):
        for profile in ("large", "medium"):
            with self.subTest(profile=profile):
                rows = synthetic_records.build(profile)["runtime_acceptance_receipt"]["rows"]
                self.assertEqual(set(rows), FULL_REVIEW_ROWS)

    def test_read_back_uses_the_pr_wide_comments_endpoint(self):
        for profile in ("large", "medium"):
            with self.subTest(profile=profile):
                source = synthetic_records.build(profile)["publication"]["verification"]["source"]
                self.assertIn("/pulls/42/comments", source)
                self.assertNotIn("/reviews/", source)


class FollowUpFidelityTests(unittest.TestCase):
    def setUp(self):
        self.record = synthetic_records.build("follow-up")
        self.source = synthetic_records.build(synthetic_records.PROFILES["follow-up"]["source"])

    def test_selected_concerns_come_from_the_source_inventory_with_their_final_outcomes(self):
        finals = final_outcomes(self.source)
        selected = self.record["follow_up"]["selected_concerns"]
        self.assertTrue(selected)
        for original in selected:
            concern = original["hypothesis"]["id"]
            self.assertIn(finals[concern]["outcome"], CONCERN_OUTCOMES, concern)
            self.assertEqual(original["original_outcome"], finals[concern])
            self.assertEqual(original["hypothesis"], next(h for h in self.source["hypotheses"] if h["id"] == concern))

    def test_the_receipt_keeps_every_full_review_row_and_adds_the_follow_up_rows(self):
        rows = self.record["runtime_acceptance_receipt"]["rows"]
        self.assertEqual(set(rows), FULL_REVIEW_ROWS | FOLLOW_UP_ROWS)
        for row in FULL_REVIEW_ONLY_ROWS:
            self.assertEqual(rows[row]["status"], "not run", row)


if __name__ == "__main__":
    unittest.main()
