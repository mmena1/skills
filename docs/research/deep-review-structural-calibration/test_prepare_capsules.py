"""Offline CLI regression tests for resolving source commit pairs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("prepare-capsules.py")


class SourcePairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = dict(os.environ)
        for key in list(self.environment):
            if key.startswith("GIT_"):
                del self.environment[key]
        self.environment.update(
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
            GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
            GIT_AUTHOR_DATE="2001-01-01T00:00:00+00:00",
            GIT_COMMITTER_DATE="2001-01-01T00:00:00+00:00",
        )
        self.history = self.root / "history"
        self.history.mkdir()
        self.git(self.history, "init", "--quiet", "--template=")
        self.base = self.commit("base")
        self.head = self.commit("head")
        self.fix = self.commit("future fix")
        self.base_only = self.shallow_source("base-only.git", self.base)
        self.head_only = self.shallow_source("head-only.git", self.head)
        # The failure requires separate object databases, not just separate refs.
        self.assertFalse(self.has_commit(self.base_only, self.head))
        self.assertFalse(self.has_commit(self.head_only, self.base))
        self.runner = self.root / "runner"
        self.runner.mkdir()
        shutil.copyfile(SCRIPT, self.runner / SCRIPT.name)
        (self.runner / "case-catalog.json").write_text(json.dumps({
            "snapshots": [{"id": "fixture", "base": self.base,
                           "head": self.head, "first_fix": self.fix}],
        }))

    def git(self, repository, *arguments, check=True):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=" + os.devnull,
             "-C", str(repository), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
            env=self.environment,
        )

    def commit(self, contents):
        (self.history / "policy.py").write_text(f"POLICY = {contents!r}\n")
        self.git(self.history, "add", "policy.py")
        self.git(self.history, "commit", "--quiet", "-m", contents)
        return self.git(self.history, "rev-parse", "HEAD").stdout.strip().decode()

    def has_commit(self, repository, sha):
        return self.git(repository, "cat-file", "-e", sha + "^{commit}",
                        check=False).returncode == 0

    def shallow_source(self, name, sha):
        repository = self.root / name
        repository.mkdir()
        self.git(repository, "init", "--bare", "--quiet", "--template=")
        self.git(repository, "fetch", "--depth=1", "--no-tags",
                 self.history.as_uri(), sha)
        return repository

    def prepare(self, repositories, output):
        arguments = [sys.executable, str(self.runner / SCRIPT.name)]
        for repository in repositories:
            arguments.extend(["--repository", str(repository)])
        arguments.extend(["--output", str(output), "--seed", "pair-regression"])
        return subprocess.run(arguments, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self.environment, text=True)

    def test_split_sources_fail_actionably_before_creating_output(self):
        output = self.root / "rejected"
        result = self.prepare([self.base_only, self.head_only], output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No supplied repository contains both pinned commits", result.stderr)
        for value in [self.base, self.head, str(self.base_only), str(self.head_only),
                      "bare evaluator depot", "--repository", "fetch", "--depth", "fixture"]:
            self.assertIn(value.lower(), result.stderr.lower())
        self.assertFalse(output.exists())

    def test_complete_depot_after_split_sources_preserves_capsule_guarantees(self):
        depot = self.root / "evaluator.git"
        depot.mkdir()
        self.git(depot, "init", "--bare", "--quiet", "--template=")
        # Populate both endpoints in one depot, as the documented recovery does.
        for sha in [self.base, self.head]:
            self.git(depot, "fetch", "--no-tags", self.history.as_uri(), sha)
        # Future objects may exist in evaluator storage, but cannot enter a capsule.
        self.git(depot, "fetch", "--no-tags", self.history.as_uri(), self.fix)
        outputs = [self.root / "first", self.root / "second"]
        receipts = []
        for output in outputs:
            result = self.prepare([self.base_only, self.head_only, depot], output)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((output / "evaluator-receipt.json").read_text())[0]
            receipts.append(receipt)
            capsule = output / "capsules" / receipt["alias"]
            repository = capsule / "repository"
            review = json.loads((capsule / "review.json").read_text())
            expected_trees = [self.git(self.history, "rev-parse", sha + "^{tree}")
                              .stdout.strip().decode() for sha in [self.base, self.head]]
            self.assertEqual(receipt["tree_hashes"], expected_trees)
            for key, tree in zip(["base", "head"], expected_trees):
                actual_tree = self.git(repository, "rev-parse", review[key] + "^{tree}")
                self.assertEqual(actual_tree.stdout.strip().decode(), tree)
            expected_diff = self.git(self.history, "diff", "--no-ext-diff",
                                     "--no-textconv", "--no-renames", self.base, self.head).stdout
            actual_diff = self.git(repository, "diff", "--no-ext-diff", "--no-textconv",
                                   "--no-renames", review["base"], review["head"]).stdout
            self.assertEqual(actual_diff, expected_diff)
            self.assertEqual(receipt["diff_sha256"], hashlib.sha256(expected_diff).hexdigest())
            for sha in [self.base, self.head, self.fix]:
                self.assertFalse(self.has_commit(repository, sha))
            self.assertEqual(len(self.git(repository, "rev-list", "--all").stdout.splitlines()), 2)
            self.assertEqual(self.git(repository, "remote").stdout, b"")
            self.assertFalse((repository / ".git/objects/info/alternates").exists())
            self.assertEqual(self.git(repository, "fsck", "--full", "--unreachable",
                                      "--no-reflogs").stdout, b"")
        self.assertEqual(receipts[0], receipts[1])


if __name__ == "__main__":
    unittest.main()
