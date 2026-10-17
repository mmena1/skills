"""The implementation-review citation model: revision-aware source anchors and commit attribution.

Models the coordinator's documented verification over a real Git repository: anchors are
checked against the side they name, and a claim about one commit against that commit's own
patch. The pinned command strings are the ones implementation-review documents.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .common import fail


BLOB_TYPE_COMMAND = "git cat-file -t <sha>:<path>"
LINE_COUNT_COMMAND = "git cat-file -p <sha>:<path> | awk 'END { print NR }'"
COMMIT_PATCH_COMMAND = "git show --format= --find-renames <commit>"

ANCHOR = re.compile(r"`(?P<path>[^`]+):(?P<lines>[^`:]+)`(?: \((?P<side>new|old)\))?$")
HUNK_HEADER = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
# The disposable repository ignores the caller's Git configuration, such as diff.noprefix or hooks.
ISOLATED = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *arguments: str, tolerate_failure: bool = False) -> bytes | None:
    """Run one Git command in `repo` and return its raw output, or None for a tolerated failure."""
    try:
        result = subprocess.run(["git", *arguments], cwd=repo, capture_output=True, env=ISOLATED)
    except OSError as error:
        fail(f"git is required to check implementation-review citations: {error}")
    if result.returncode:
        if tolerate_failure:
            return None
        fail(f"git {arguments[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def documented(command: str, **values: str) -> list[str]:
    """The Git arguments of one pinned command before any pipe, with its placeholders filled."""
    arguments = command.partition(" | ")[0].split(" ")[1:]
    for name, value in values.items():
        arguments = [argument.replace(f"<{name}>", value) for argument in arguments]
    return arguments


def parse_anchor(text: str) -> dict | None:
    """Parse "`<path>:<start>[-<end>]` (new|old)"; None when the text is not an anchor at all."""
    match = ANCHOR.match(text.strip())
    if not match:
        return None
    start, _, end = match["lines"].partition("-")
    return {"path": match["path"], "start": start, "end": end or start, "side": match["side"]}


def hunk_coordinates(diff: str) -> list[dict]:
    """Number every hunk line from its header, the rule reviewers apply: context advances both sides."""
    entries: list[dict] = []
    old_path = new_path = None
    old = new = 0
    in_hunk = False

    def entry(old_line: int | None, new_line: int | None, text: str) -> None:
        entries.append({"old_path": old_path, "new_path": new_path, "old": old_line, "new": new_line, "text": text})

    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            old_path = new_path = None
            in_hunk = False
            continue
        if not in_hunk:
            if line.startswith("--- "):
                old_path = None if line == "--- /dev/null" else line[4:].removeprefix("a/")
            elif line.startswith("+++ "):
                new_path = None if line == "+++ /dev/null" else line[4:].removeprefix("b/")
            elif header := HUNK_HEADER.match(line):
                old, new, in_hunk = int(header["old"]), int(header["new"]), True
            continue
        if header := HUNK_HEADER.match(line):
            old, new = int(header["old"]), int(header["new"])
        elif line.startswith("-"):
            entry(old, None, line)
            old += 1
        elif line.startswith("+"):
            entry(None, new, line)
            new += 1
        elif line.startswith(" "):
            entry(old, new, line)
            old += 1
            new += 1
    return entries


def line_count(content: bytes) -> int:
    """The record count `awk 'END { print NR }'` reports, including a final line without a newline."""
    return content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)


def anchor_verdict(repo: Path, anchor: dict | None, *, base: str, head: str) -> str:
    """Verify one anchor: "verified", "invalid-anchor", "missing-path", or "out-of-range".

    A `(new)` anchor is checked at the reviewed head and an `(old)` anchor at the review
    base, so a deleted or pre-rename path is valid on its old side only.
    """
    if anchor is None or anchor["side"] is None:
        return "invalid-anchor"
    if not (anchor["start"].isdigit() and anchor["end"].isdigit()):
        return "invalid-anchor"
    start, end = int(anchor["start"]), int(anchor["end"])
    if start < 1 or end < start:
        return "invalid-anchor"
    values = {"sha": head if anchor["side"] == "new" else base, "path": anchor["path"]}
    kind = git(repo, *documented(BLOB_TYPE_COMMAND, **values), tolerate_failure=True)
    if kind is None or kind.strip() != b"blob":
        return "missing-path"
    if end > line_count(git(repo, *documented(LINE_COUNT_COMMAND, **values))):
        return "out-of-range"
    return "verified"


def attribution_verdict(repo: Path, claim: dict, *, commits: list[str]) -> str:
    """Check that one commit added, tested, or removed the quoted line: "supported", "unsupported", or "outside-range".

    Only the named commit's own patch counts; the cumulative diff and commit-list order are not evidence.
    The whole patch is read with rename detection before the claimed path's section is selected, so a
    pure rename contributes no added or removed lines.
    """
    if claim["commit"] not in commits:
        return "outside-range"
    patch = git(repo, *documented(COMMIT_PATCH_COMMAND, commit=claim["commit"])).decode(errors="replace")
    marker = "-" if claim["change"] == "removed" else "+"
    changed = [
        entry["text"][1:] for entry in hunk_coordinates(patch)
        if claim["path"] in (entry["old_path"], entry["new_path"]) and entry["text"].startswith(marker)
    ]
    return "supported" if any(claim["quote"] in line for line in changed) else "unsupported"


def review_outcome(axes: dict) -> dict:
    """Aggregate per-axis verdicts after at most one correction per failed finding or attribution.

    A finding that points at code needs at least one anchor, and every anchor it carries
    must verify. One still failing after its correction leaves its axis, and the review,
    incomplete while the other axis keeps its results. An attribution still unsupported
    stays as a cumulative finding with its commit attribution undecided.
    """
    result: dict = {"axes": {}}
    for name, axis in axes.items():
        unverified = [
            index for index, finding in enumerate(axis["findings"])
            if ((finding["code"] and not finding["anchors"]) or any(verdict != "verified" for verdict in finding["anchors"]))
            and axis["corrections"].get(index) != "verified"
        ]
        undecided = [
            index for index, verdict in enumerate(axis["attributions"])
            if verdict != "supported" and axis["attribution_corrections"].get(index) != "supported"
        ]
        result["axes"][name] = {
            "status": "incomplete" if unverified else "complete", "unverified": unverified, "undecided": undecided,
        }
    complete = all(entry["status"] == "complete" for entry in result["axes"].values())
    result["overall"] = "complete" if complete else "incomplete"
    return result
