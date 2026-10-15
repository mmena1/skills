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
# references/output-template.md: the receipt status vocabulary, and the follow-up marking of full-review-only rows.
STATUSES = {"PASS", "FAIL", "NOT EXERCISED"}
FULL_REVIEW_ONLY_EVIDENCE = "Not run: full review only"
# Scenarios no synthetic record models an observation for, so a PASS would be an inferred pass.
NEVER_OBSERVED = {
    "capacity-bounded static validation", "insufficient scout capacity", "scout failure", "validator partial failure",
    "PR head change", "partial fix", "missing prior evidence", "head change during revalidation",
    "follow-up validator capacity", "record discovery in a later session",
    "discovery when the newest record is a narrower follow-up", "record preservation from a linked worktree",
    "record preservation under a write restriction",
}


def passes_only_where_observed(test: unittest.TestCase, record: dict) -> None:
    """Every status is in the template's vocabulary, and a PASS needs the observation it claims in the record."""
    rows = record["runtime_acceptance_receipt"]["rows"]
    finals = final_outcomes(record)
    statuses = [o.get("status") for o in finals.values()]
    follow_up = record["follow_up"] or {}
    threads = {t["concern"]: t["state"] for t in follow_up.get("thread_states", [])}
    backing = {
        "zero hypotheses": not record["hypotheses"] and record["record"]["mode"] == "full",
        "surviving hypotheses": bool(record["hypotheses"]),
        "multiple selected scouts": len(record["scouts"]) > 1,
        "validator probes": bool(record["baseline"]["restorations"])
        and any(o["phase"] == "writable" for o in record["validator_outcomes"]),
        "PR-review-overlap": bool(record["pr_discussion"]["retrieval_complete"] and record["pr_discussion"]["dispositions"]),
        "cleanup": record["cleanup"]["status"] != "pending",
        "fixed concern": "Addressed" in statuses,
        "persisting defect": "Not addressed" in statuses,
        "explicitly deferred concern": bool(follow_up.get("deferred")),
        "resolved thread with a persisting defect": any(
            finals[c].get("status") == "Not addressed" and threads.get(c) == "resolved" for c in threads if c in finals),
        "multiple selected concerns": len(follow_up.get("selected_concerns", [])) - len(follow_up.get("deferred", [])) > 1,
    }
    for row, value in rows.items():
        test.assertIn(value["status"], STATUSES, row)
        if row in NEVER_OBSERVED:
            test.assertEqual(value["status"], "NOT EXERCISED", row)
        if value["status"] == "PASS":
            test.assertTrue(backing.get(row, False), f"{row} is PASS without the observation it needs")


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

    def test_the_receipt_passes_only_observed_scenarios(self):
        for profile in ("large", "medium"):
            with self.subTest(profile=profile):
                record = synthetic_records.build(profile)
                passes_only_where_observed(self, record)
                self.assertEqual(record["runtime_acceptance_receipt"]["rows"]["surviving hypotheses"]["status"], "PASS")

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
            self.assertEqual(rows[row], {"status": "NOT EXERCISED", "evidence": FULL_REVIEW_ONLY_EVIDENCE}, row)

    def test_the_receipt_passes_only_observed_scenarios(self):
        passes_only_where_observed(self, self.record)
        self.assertEqual(self.record["runtime_acceptance_receipt"]["rows"]["explicitly deferred concern"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
