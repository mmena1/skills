#!/usr/bin/env python3
"""Export isolated, source-only review capsules. This never invokes a model.

The catalog, source repositories, this program and receipts are evaluator-only.
Give a reviewer exactly one capsule, under an independently enforced read boundary.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile


def git(repository, *arguments, data=None, environment=None, check=True):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repository), *arguments],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=check, env=environment,
    )


def source_for_pair(repositories, base, head):
    for repository in repositories:
        if all(git(repository, "cat-file", "-e", sha + "^{commit}", check=False).returncode == 0
               for sha in [base, head]):
            return repository
    raise RuntimeError(
        f"No supplied repository contains both pinned commits: base {base}, head {head}. "
        "Fetch both exact SHAs without --depth into one bare evaluator depot, then pass "
        "its path with --repository. Checked: " + ", ".join(str(path) for path in repositories)
    )


def export(repository, sha, target):
    archive = git(repository, "archive", "--format=tar", sha).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        for member in bundle.getmembers():
            parts = Path(member.name).parts
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"Non-regular archive member: {member.name}")
            if member.name.startswith("/") or ".." in parts or ".git" in parts:
                raise RuntimeError(f"Unsafe archive member: {member.name}")
            destination = target / member.name
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.extractfile(member).read())
                destination.chmod(member.mode & 0o777)
            else:
                raise RuntimeError(f"Unsupported archive member: {member.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="20261009-pilot")
    args = parser.parse_args()
    catalog = json.loads(Path(__file__).with_name("case-catalog.json").read_text())
    case_sources = []
    for case in catalog["snapshots"]:
        try:
            source = source_for_pair(args.repository, case["base"], case["head"])
        except RuntimeError as error:
            parser.error(f"{case['id']}: {error}")
        case_sources.append((case, source))
    # Requiring a new directory prevents mixing artifacts or retaining stale objects.
    args.output.mkdir(parents=True, exist_ok=False)
    capsules = args.output / "capsules"
    capsules.mkdir()
    environment = dict(os.environ)
    environment.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
        GIT_AUTHOR_NAME="Calibration", GIT_AUTHOR_EMAIL="calibration@example.invalid",
        GIT_COMMITTER_NAME="Calibration", GIT_COMMITTER_EMAIL="calibration@example.invalid",
        GIT_AUTHOR_DATE="2000-01-01T00:00:00+00:00",
        GIT_COMMITTER_DATE="2000-01-01T00:00:00+00:00",
    )
    for key in [key for key in environment if key.startswith("GIT_")]:
        if key not in {
            "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
            "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE",
        }:
            del environment[key]
    receipts = []
    for case, source in case_sources:
        alias = hashlib.sha256((args.seed + case["id"]).encode()).hexdigest()[:16]
        root = capsules / alias
        repository = root / "repository"
        repository.mkdir(parents=True)
        git(repository, "init", "--quiet", "--template=", environment=environment)
        commits = []
        trees = []
        for name in ["base", "head"]:
            if commits:
                for entry in repository.iterdir():
                    if entry.name == ".git":
                        continue
                    import shutil
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
            export(source, case[name], repository)
            git(repository, "add", "--all", "--force", environment=environment)
            tree = git(repository, "write-tree", environment=environment).stdout.strip().decode()
            original_tree = git(source, "rev-parse", case[name] + "^{tree}").stdout.strip().decode()
            if tree != original_tree:
                raise RuntimeError(f"Export changed source tree for {case['id']} {name}")
            trees.append(tree)
            parents = ["-p", commits[-1]] if commits else []
            commit = git(repository, "commit-tree", tree, *parents,
                         data=("Snapshot " + name + "\n").encode(),
                         environment=environment).stdout.strip().decode()
            commits.append(commit)
        git(repository, "update-ref", "refs/heads/review", commits[1], environment=environment)
        git(repository, "symbolic-ref", "HEAD", "refs/heads/review", environment=environment)
        original_diff = git(source, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                            case["base"], case["head"]).stdout
        capsule_diff = git(repository, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                           *commits).stdout
        if original_diff != capsule_diff:
            raise RuntimeError(f"Diff mismatch: {case['id']}")
        forbidden = {row["first_fix"] for row in catalog["snapshots"]}
        denied = all(git(repository, "cat-file", "-e", sha, check=False).returncode != 0
                     for sha in forbidden)
        log_count = len(git(repository, "rev-list", "--all").stdout.splitlines())
        fsck = git(repository, "fsck", "--full", "--unreachable", "--no-reflogs").stdout
        remote = git(repository, "remote").stdout
        alternate = repository / ".git/objects/info/alternates"
        if not denied or log_count != 2 or fsck or remote or alternate.exists():
            raise RuntimeError(f"History isolation failure: {case['id']}")
        (root / "review.json").write_text(json.dumps({
            "repository": "repository", "base": commits[0], "head": commits[1],
            "scope": "Complete base-to-head diff and surrounding tracked source and tests.",
            "history_mode": "Two synthetic snapshots; original commit history intentionally withheld.",
        }, indent=2) + "\n")
        receipts.append({
            "case": case["id"], "alias": alias, "original_base": case["base"],
            "original_head": case["head"], "synthetic_base": commits[0],
            "synthetic_head": commits[1], "tree_hashes": trees,
            "diff_sha256": hashlib.sha256(capsule_diff).hexdigest(),
            "tree_and_diff_equality": "PASS", "fix_object_absence": "PASS",
            "two_commit_graph_no_remotes_no_alternates_no_unreachable_objects": "PASS",
            "model_review": "NOT EXERCISED", "host_filesystem_network_confinement": "NOT EXERCISED",
        })
    (args.output / "evaluator-receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(f"PASS: {len(receipts)} capsules; exact source trees/diffs; future fix objects absent.")
    print("NOT EXERCISED: reviewer execution and host filesystem/network confinement.")


if __name__ == "__main__":
    main()
