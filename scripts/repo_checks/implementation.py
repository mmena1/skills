"""The `/implement` regression models: start gate, branch gate, and branch-satisfied blockers.

Models of the documented workflow over tracker and Git snapshots, never executable
workflow implementations.
"""

from __future__ import annotations

from .agent_brief import is_trusted_author
from .reconciliation import HELD_TRIAGE_STATES, reconcile_ready
from .tracker_contract import (
    missing_tracker_capabilities, resolve_issue_authority, tracker_defines_branch_satisfied_blockers,
)


AUTHORITY_GRANTED = {"parent", "standalone"}


def inverse_patch(patch: str) -> str:
    """The modelled patch that undoes `patch`, standing in for an equal `git patch-id`."""
    return patch[1:] if patch.startswith("-") else "-" + patch


def branch_satisfied_blocker(
    *, blocker: dict, history: list[dict], attributable: frozenset = frozenset(),
    confirmed_later: frozenset = frozenset(),
) -> tuple[str, list[str]]:
    """Model the optional branch-satisfied validation of one open blocker at the current HEAD.

    `history` is every commit reachable from HEAD, oldest first, each with its touched
    paths, `This reverts commit` trailers, and modelled patch. `attributable` holds the
    recorded commits of tickets in the same chain on this branch, and `confirmed_later`
    the later commits the user confirmed. Returns ("satisfied", commits), or the failed
    condition and the commits (or blocker references) involved. Nothing here writes.
    """
    if not blocker["assignees"]:
        return "unclaimed", []
    records = sorted(blocker["records"], key=lambda record: record["created_at"])
    if any(record["author"].get("permission") is None for record in records):
        return "lookup-failed", []
    trusted = [record for record in records if is_trusted_author(record["author"])]
    successes = [record for record in trusted if record["outcome"] == "succeeded"]
    manual = blocker.get("manual") or {}
    confirmed = manual["commits"] if manual.get("verified") and manual.get("confirmed") else None
    if successes:
        latest = successes[-1]
        if any(record["outcome"] != "succeeded" and record["created_at"] > latest["created_at"] for record in trusted):
            return "conflicting-records", list(latest["commits"])
        if len({frozenset(record["commits"]) for record in successes}) > 1 or (
            confirmed is not None and set(confirmed) != set(latest["commits"])
        ):
            return "conflicting-records", sorted({sha for record in successes for sha in record["commits"]})
        commits, named = list(latest["commits"]), latest.get("branch_satisfied", [])
    elif any(record["outcome"] != "succeeded" for record in trusted) and confirmed is not None:
        return "conflicting-records", list(confirmed)
    elif confirmed is not None:
        commits, named = list(confirmed), manual.get("branch_satisfied", [])
    else:
        return "no-evidence", []
    if not commits:
        return "no-evidence", []
    reachable = [entry["sha"] for entry in history]
    missing = [sha for sha in commits if sha not in reachable]
    if missing:
        return "missing-commits", missing
    unnamed = [reference for reference in blocker["open_blockers"] if reference not in named]
    if unnamed:
        return "unrecorded-blocker", [str(reference) for reference in unnamed]
    own = [entry for entry in history if entry["sha"] in commits]
    inverses = {inverse_patch(entry["patch"]) for entry in own}
    reverting = [
        entry["sha"] for entry in history
        if entry["sha"] not in commits and (set(entry["reverts"]) & set(commits) or entry["patch"] in inverses)
    ]
    if reverting:
        return "reverted", reverting
    paths = {path for entry in own for path in entry["paths"]}
    first = reachable.index(own[0]["sha"])
    touching = [
        entry["sha"] for entry in history[first + 1:]
        if entry["sha"] not in commits and paths & set(entry["paths"])
        and entry["sha"] not in attributable and entry["sha"] not in confirmed_later
    ]
    if touching:
        return "later-path-change", touching
    return "satisfied", commits


def implementation_start_gate(
    *, tracker: str, required: set[str], ticket: dict, branch_satisfaction: dict | None = None,
    override: bool = False, held_labels: set = HELD_TRIAGE_STATES,
) -> str:
    """Model /implement's authority and ticket-state start gates: "start" or the stop reason.

    `branch_satisfaction` maps open blockers to their branch-satisfied verdicts. It counts
    only when the tracker defines the optional operation, and substitutes only for the
    blockers it validates. Readiness then follows /reconcile's classification as if those
    blockers were closed, never more broadly. A user override waives only the ticket-state
    gate, never authority or the readiness standalone authority needs.
    """
    if set(missing_tracker_capabilities(tracker)) & required:
        return "stale-tracker"
    satisfied = {
        blocker for blocker, verdict in (branch_satisfaction or {}).items() if verdict == "satisfied"
    } if tracker_defines_branch_satisfied_blockers(tracker) else set()
    remaining = [blocker for blocker in ticket["open_blockers"] if blocker not in satisfied]
    ready = ticket["ready"]
    if ticket["open_blockers"] and not remaining:
        ready = reconcile_ready(ticket, remaining, held_labels)
    authority = resolve_issue_authority(
        tracker=tracker, parent=ticket["parent"], issue=ticket, ready_for_agent=ready,
    )
    if authority not in AUTHORITY_GRANTED:
        return authority or "no-authority"
    if override:
        return "start"
    if ticket["state"] != "OPEN" or remaining or not ready:
        return "not-ready"
    return "start"


def implementation_branch_gate(*, current: str, detached: bool, default: str, created: bool) -> str:
    """Model /implement's branch gate, which runs before the claim: "continue", "branch", or "stop".

    A detached HEAD, such as a harness-provided isolated working copy, branches from the
    current HEAD like the default branch does. An empty name that is not a detached HEAD
    and a failed branch creation stop; no existing branch is ever replaced to make room.
    """
    if detached or current == default:
        return "branch" if created else "stop"
    return "continue" if current else "stop"
