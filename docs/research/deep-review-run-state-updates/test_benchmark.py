"""Tests that candidate C's measured edits really apply. Research only, issue #121."""

from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import benchmark  # noqa: E402
import synthetic_records  # noqa: E402


class NativeEditReplayTests(unittest.TestCase):
    def test_every_profile_replays_to_the_exact_reference_record(self):
        for profile in synthetic_records.PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory:
                replayed = benchmark.replay_native_edits(profile, Path(directory))
                self.assertEqual(len(replayed), len(synthetic_records.steps(profile)))
                self.assertTrue(all(replayed), "every step makes at least one edit")
                self.assertEqual((Path(directory) / f"{profile}-run-state.json").read_text(encoding="utf-8"),
                                 synthetic_records.serialize(synthetic_records.build(profile)))

    def test_a_replayed_edit_changes_only_its_region(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            before = '{\n  "a": {\n    "status": "x"\n  },\n  "b": {\n    "status": "x"\n  }\n}\n'
            after = before.replace('"b": {\n    "status": "x"', '"b": {\n    "status": "y"')
            path.write_text(before, encoding="utf-8")
            edits = benchmark.replay_step(path, after)
            self.assertEqual(path.read_text(encoding="utf-8"), after)
            self.assertEqual(len(edits), 1)
            old, new, size = edits[0]
            self.assertEqual(before.count(old), 1)
            self.assertIn('"b"', old)
            self.assertEqual(size, len(before.encode("utf-8")))

    def test_an_ambiguous_anchor_widens_until_unique(self):
        old, new = benchmark.unique_edit(["x\n", "x\n"], ["x\n", "y\n"], (1, 2, 1, 2))
        self.assertEqual((old, new), ("x\nx\n", "x\ny\n"))


if __name__ == "__main__":
    unittest.main()
