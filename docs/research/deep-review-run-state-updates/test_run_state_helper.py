"""Tests for the research prototype's command-line seam. Research only, issue #121."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
HELPER = HERE / "run_state_helper.py"
sys.path.insert(0, str(HERE))

import synthetic_records  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HelperTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.run_dir = self.root / "run"
        self.run_dir.mkdir()
        self.record = self.run_dir / "run-state.json"

    def helper(self, *arguments, stdin=None, env=None):
        environment = dict(os.environ)
        environment.update(env or {})
        return subprocess.run(
            [sys.executable, str(HELPER), *arguments], input=stdin, text=True,
            capture_output=True, env=environment, check=False,
        )

    def init(self):
        result = self.helper("init", "--run-dir", str(self.run_dir), "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["sha256"]

    def update(self, ops, expect, **options):
        return self.helper(
            "update", "--run-dir", str(options.get("run_dir", self.run_dir)), "--root", str(self.root),
            "--expect-sha256", expect, stdin=json.dumps({"ops": ops}), env=options.get("env"),
        )

    def apply(self, ops, expect):
        result = self.update(ops, expect)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["sha256"]

    def build_large(self):
        digest = self.init()
        for step in synthetic_records.steps("large"):
            digest = self.apply(step, digest)
        return digest


class UpdateTests(HelperTestCase):
    def test_replaying_the_synthetic_steps_produces_the_reference_record(self):
        digest = self.build_large()
        self.assertEqual(self.record.read_text(encoding="utf-8"), synthetic_records.serialize(synthetic_records.build("large")))
        self.assertEqual(digest, sha256(self.record))

    def test_an_update_preserves_every_unrelated_field_byte_for_byte(self):
        digest = self.build_large()
        before = self.record.read_text(encoding="utf-8")
        old_line = '    "status": "worktree removed; snapshot and run directory pending preservation checks",\n'
        self.assertEqual(before.count(old_line), 1)
        self.apply([{"op": "set", "path": "/cleanup/status", "value": "worktree removed"}], digest)
        after = self.record.read_text(encoding="utf-8")
        self.assertEqual(after, before.replace(old_line, '    "status": "worktree removed",\n'))


class AtomicityAndConcurrencyTests(HelperTestCase):
    CHANGE = [{"op": "set", "path": "/cleanup/status", "value": "worktree removed"}]

    def test_an_interrupted_write_leaves_the_previous_record_intact(self):
        digest = self.build_large()
        before = self.record.read_bytes()
        result = self.update(self.CHANGE, digest, env={"RUN_STATE_HELPER_FAULT": "exit-after-partial-write"})
        self.assertEqual(result.returncode, 70)
        self.assertEqual(self.record.read_bytes(), before)
        leftovers = sorted(path.name for path in self.run_dir.iterdir() if path.name.endswith(".tmp"))
        self.assertEqual(len(leftovers), 1)
        self.assertLess(len((self.run_dir / leftovers[0]).read_bytes()), len(before))
        self.apply(self.CHANGE, digest)

    def test_a_failed_write_removes_its_temporary_file(self):
        digest = self.build_large()
        before = self.record.read_bytes()
        result = self.update(self.CHANGE, digest, env={"RUN_STATE_HELPER_FAULT": "raise-before-replace"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record.read_bytes(), before)
        self.assertEqual([path.name for path in self.run_dir.iterdir() if path.name.endswith(".tmp")], [])

    def test_an_update_based_on_a_stale_record_is_refused(self):
        first = self.init()
        self.apply([{"op": "set", "path": "/cleanup/status", "value": "one"}], first)
        current = self.record.read_bytes()
        result = self.update([{"op": "set", "path": "/cleanup/status", "value": "two"}], first)
        self.assertEqual(result.returncode, 2)
        self.assertIn("stale", result.stderr)
        self.assertEqual(self.record.read_bytes(), current)

    def test_an_update_while_another_holds_the_run_lock_is_refused(self):
        import fcntl

        digest = self.init()
        with open(self.run_dir / ".run-state.lock", "w", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = self.record.read_bytes()
            result = self.update(self.CHANGE, digest)
        self.assertEqual(result.returncode, 2)
        self.assertIn("lock", result.stderr)
        self.assertEqual(self.record.read_bytes(), before)


class ValidationTests(HelperTestCase):
    def assert_refused(self, digest, ops=None, stdin=None, reason=""):
        before = self.record.read_bytes()
        if stdin is None:
            result = self.update(ops, digest)
        else:
            result = self.helper(
                "update", "--run-dir", str(self.run_dir), "--root", str(self.root),
                "--expect-sha256", digest, stdin=stdin,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertEqual(self.record.read_bytes(), before)

    def test_malformed_update_documents_are_refused(self):
        digest = self.init()
        self.assert_refused(digest, stdin="{not json", reason="malformed")
        self.assert_refused(digest, stdin='{"ops": {}}', reason="malformed")
        self.assert_refused(digest, ops=[{"op": "delete", "path": "/cleanup"}], reason="unknown op")
        self.assert_refused(digest, ops=[{"op": "set", "path": "cleanup/status", "value": 1}], reason="path")

    def test_whole_record_and_unknown_fields_cannot_be_written(self):
        digest = self.init()
        self.assert_refused(digest, ops=[{"op": "set", "path": "", "value": {}}], reason="path")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/notes", "value": "x"}], reason="schema")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/cleanup/owner/name", "value": "x"}], reason="path")

    def test_updates_that_violate_the_record_schema_are_refused(self):
        digest = self.init()
        self.assert_refused(digest, ops=[{"op": "set", "path": "/scouts", "value": []}], reason="schema")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/final_report", "value": "done"}], reason="schema")
        self.assert_refused(digest, ops=[{"op": "append", "path": "/scouts", "value": {}}], reason="not an array")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/publication/payload", "value": {"body": "x"}}], reason="schema")

    def test_recorded_evidence_is_append_only(self):
        digest = self.build_large()
        self.assert_refused(digest, ops=[{"op": "set", "path": "/validator_outcomes/0/outcome", "value": "finding"}], reason="append-only")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/hypotheses", "value": []}], reason="append-only")

    def test_baseline_identity_and_publication_payload_are_write_once(self):
        digest = self.build_large()
        self.assert_refused(digest, ops=[{"op": "set", "path": "/baseline/identity/head_sha", "value": "0" * 40}], reason="write-once")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/publication/payload", "value": "{}"}], reason="write-once")

    def test_protected_fields_cannot_be_replaced_through_an_ancestor(self):
        digest = self.build_large()
        self.assert_refused(digest, ops=[{"op": "set", "path": "/publication", "value": {"payload": "REPLACED"}}], reason="protected")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/baseline", "value": {"identity": None, "restorations": []}}], reason="protected")
        self.assert_refused(digest, ops=[{"op": "set", "path": "/pr_discussion", "value": {
            "retrieval_complete": True, "retrieved_at": None, "dispositions": []}}], reason="protected")

    def test_an_update_applies_all_of_its_ops_or_none(self):
        digest = self.init()
        self.assert_refused(digest, ops=[
            {"op": "set", "path": "/cleanup/status", "value": "changed"},
            {"op": "set", "path": "/notes", "value": "x"},
        ], reason="schema")


class ConfinementTests(HelperTestCase):
    def refused(self, *arguments, stdin=None):
        result = self.helper(*arguments, stdin=stdin)
        self.assertEqual(result.returncode, 2, result.stderr)
        return result.stderr

    def test_a_run_directory_path_with_traversal_is_refused(self):
        self.init()
        traversing = f"{self.run_dir}/../run"
        self.assertIn("traversal", self.refused("update", "--run-dir", traversing, "--root", str(self.root),
                                                "--expect-sha256", sha256(self.record), stdin='{"ops": []}'))

    def test_a_run_directory_outside_the_root_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            self.assertIn("outside", self.refused("init", "--run-dir", outside, "--root", str(self.root)))
            self.assertEqual(os.listdir(outside), [])

    def test_a_symlinked_run_directory_is_refused(self):
        self.init()
        alias = self.root / "alias"
        alias.symlink_to(self.run_dir, target_is_directory=True)
        self.assertIn("symlink", self.refused("update", "--run-dir", str(alias), "--root", str(self.root),
                                              "--expect-sha256", sha256(self.record), stdin='{"ops": []}'))

    def test_a_symlinked_ancestor_cannot_escape_the_root(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "run").mkdir()
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            self.assertIn("outside", self.refused("init", "--run-dir", str(self.root / "escape" / "run"), "--root", str(self.root)))
            self.assertEqual(os.listdir(Path(outside) / "run"), [])

    def test_a_symlinked_record_is_refused_and_its_target_untouched(self):
        digest = self.init()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "victim.json"
            target.write_bytes(self.record.read_bytes())
            self.record.unlink()
            self.record.symlink_to(target)
            stderr = self.refused("update", "--run-dir", str(self.run_dir), "--root", str(self.root),
                                  "--expect-sha256", digest, stdin=json.dumps({"ops": [{"op": "set", "path": "/cleanup/status", "value": "x"}]}))
            self.assertIn("symlink", stderr)
            self.assertEqual(sha256(target), digest)
            self.assertTrue(self.record.is_symlink())

    def test_only_a_directory_the_helper_initialized_is_writable(self):
        stranger = self.root / "stranger"
        stranger.mkdir()
        (stranger / "run-state.json").write_text("{}\n", encoding="utf-8")
        digest = sha256(stranger / "run-state.json")
        self.assertIn("not a coordinator-owned run directory", self.refused(
            "update", "--run-dir", str(stranger), "--root", str(self.root), "--expect-sha256", digest,
            stdin=json.dumps({"ops": [{"op": "set", "path": "/cleanup/status", "value": "x"}]})))
        self.assertIn("not empty", self.refused("init", "--run-dir", str(stranger), "--root", str(self.root)))

    def test_the_helper_writes_nothing_but_its_own_files_and_deletes_nothing(self):
        sibling = self.root / "context"
        sibling.mkdir()
        (sibling / "manifest").write_text("evidence\n", encoding="utf-8")
        self.build_large()
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["context", "run"])
        self.assertEqual((sibling / "manifest").read_text(encoding="utf-8"), "evidence\n")
        self.assertEqual(sorted(path.name for path in self.run_dir.iterdir()),
                         [".deep-review-run", ".run-state.lock", "run-state.json"])


class ReceiptTests(HelperTestCase):
    RECEIPT = {"review_id": 5550001, "comment_ids": [1, 2, 3, 4, 5, 6], "posted_at": "2026-10-15T10:50:00Z"}

    def finalize(self, digest):
        return self.helper("finalize-receipt", "--run-dir", str(self.run_dir), "--root", str(self.root),
                           "--expect-sha256", digest, stdin=json.dumps(self.RECEIPT))

    def test_the_receipt_carries_the_recorded_payload_exactly(self):
        digest = self.build_large()
        state = self.record.read_bytes()
        result = self.finalize(digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(state)["publication"]["payload"]
        receipt = json.loads((self.run_dir / "publication-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["payload"].encode("utf-8"), payload.encode("utf-8"))
        self.assertEqual(receipt["payload_sha256"], hashlib.sha256(payload.encode("utf-8")).hexdigest())
        self.assertEqual(receipt["receipt"], self.RECEIPT)
        self.assertEqual(self.record.read_bytes(), state)

    def test_no_receipt_without_a_recorded_payload(self):
        digest = self.init()
        result = self.finalize(digest)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no publication payload", result.stderr)
        self.assertFalse((self.run_dir / "publication-receipt.json").exists())

    def test_an_existing_receipt_is_never_replaced(self):
        digest = self.build_large()
        self.assertEqual(self.finalize(digest).returncode, 0)
        first = (self.run_dir / "publication-receipt.json").read_bytes()
        result = self.finalize(digest)
        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)
        self.assertEqual((self.run_dir / "publication-receipt.json").read_bytes(), first)

    def test_a_receipt_against_a_stale_record_is_refused(self):
        self.build_large()
        result = self.finalize("0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn("stale", result.stderr)


if __name__ == "__main__":
    unittest.main()
