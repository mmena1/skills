"""The `/reconcile` regression model: readiness classification and scoped reconciliation plans.

A model of the documented workflow over tracker snapshots, never a tracker adapter.
"""

from __future__ import annotations

from .agent_brief import resolve_agent_brief
from .tracker_contract import resolve_issue_authority


# Explicit non-agent triage states. Reconciliation never overrides them.
HELD_TRIAGE_STATES = {"needs-triage", "needs-info", "ready-for-human", "wontfix"}


def reconcile_ready(subject: dict, open_blockers: list, held_labels: set = HELD_TRIAGE_STATES) -> bool:
    """/reconcile's readiness classification for an issue in a validated authority scope."""
    return (
        subject["state"] == "OPEN" and not subject.get("assignees") and not open_blockers
        and not held_labels & set(subject.get("labels", ()))
    )


def standalone_frontier_numbers(issues: list[dict]) -> list[int]:
    """Project readiness across parentless issues that carry a trusted Agent Brief.

    An explicit non-agent triage state holds an issue non-ready; an unlabelled
    planned issue is promoted once its blockers close.
    """
    ready = []
    for issue in issues:
        if issue["parent"] is not None or resolve_agent_brief(issue) is None:
            continue
        if reconcile_ready(issue, issue["open_blockers"]):
            ready.append(issue["number"])
    return sorted(ready)


def reconciliation_plan(
    *, tracker: str, trigger_number: int, issues: list[dict], parents: dict,
    native_dependents: list[int] | None, triage_labels: dict | None = None,
) -> dict:
    """Model the prompt workflow over current tracker snapshots, without tracker writes.

    Parents are direct/native references already resolved by the tracker. Their
    children are in configured parent order. This is a regression model, not a
    tracker adapter or an executable replacement for the reconcile skill.
    """
    by_number = {issue["number"]: issue for issue in issues}
    labels = triage_labels or {role: role for role in HELD_TRIAGE_STATES | {"ready-for-agent"}}
    held_labels = {labels[role] for role in HELD_TRIAGE_STATES}
    ready_label = labels["ready-for-agent"]
    plan = {
        "scopes": {}, "failures": {}, "promotions": [], "removals": [], "noops": [],
        "unresolved_blockers": {}, "frontiers": {}, "writes": [],
    }

    def canonical_blockers(subject: dict) -> list[int]:
        native = subject["native_blockers"]
        return subject["fallback_blockers"] if native is None else native

    def scope_for(subject: dict) -> str | None:
        parent = subject["parent"]
        if parent is not None:
            if parent not in parents or not parents[parent]["approved"]:
                plan["failures"][subject["number"]] = "invalid-parent"
                return None
            return f"parent:{parent}"
        # Reconciliation checks authority without requiring the ready label.
        authority = resolve_issue_authority(tracker=tracker, parent=None, issue=subject, ready_for_agent=True)
        if authority != "standalone":
            plan["failures"][subject["number"]] = authority or "no-authority"
            return None
        return "standalone"

    trigger = by_number[trigger_number]
    scope = scope_for(trigger)
    if scope is None:
        return plan
    if trigger["state"] != "CLOSED":
        plan["failures"][trigger_number] = "unresolved-trigger"
        return plan
    scopes = [scope]
    dependents = native_dependents if native_dependents is not None else [
        subject["number"] for subject in issues
        if subject["state"] == "OPEN" and trigger_number in canonical_blockers(subject)
    ]
    for number in sorted(set(dependents)):
        subject = by_number[number]
        if subject["state"] != "OPEN":
            continue
        scope = scope_for(subject)
        if scope is not None and scope not in scopes:
            scopes.append(scope)
    for scope in scopes:
        if scope == "standalone":
            members = sorted(
                subject["number"] for subject in issues
                if subject["parent"] is None and resolve_agent_brief(subject) is not None
            )
        else:
            members = parents[scope.removeprefix("parent:")]["children"]
        plan["scopes"][scope] = members
        plan["frontiers"][scope] = []
        for number in members:
            subject = by_number[number]
            blockers = [
                blocker for blocker in canonical_blockers(subject)
                if blocker not in by_number or by_number[blocker]["state"] != "CLOSED"
            ]
            if blockers:
                plan["unresolved_blockers"][number] = blockers
            ready = reconcile_ready(subject, blockers, held_labels)
            marked = ready_label in subject["labels"]
            if ready:
                plan["frontiers"][scope].append(number)
            if ready == marked:
                plan["noops"].append(number)
            else:
                plan["promotions" if ready else "removals"].append(number)
                plan["writes"].append((number, "add" if ready else "remove", ready_label))
    return plan
