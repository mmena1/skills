"""Reconciliation groups: the `/reconcile` plan scenarios and its tracker migration contract."""

from __future__ import annotations

import re

from ..agent_brief import AGENT_BRIEF_HEADING
from ..common import ROOT, fail
from ..reconciliation import HELD_TRIAGE_STATES, reconciliation_plan
from ..tracker_contract import (
    RETIRED_STANDALONE_RECORD, missing_tracker_capabilities, tracker_is_current, tracker_standalone_authority,
)


def validate_reconciliation() -> None:
    """Exercise authority-scoped readiness through the reconciliation plan seam."""
    tracker = (ROOT / "skills/setup-skills/issue-tracker-github.md").read_text(encoding="utf-8")
    brief = "\n".join((
        AGENT_BRIEF_HEADING, "**Category:** bug", "**Summary:** reconcile readiness",
        "**Current behavior:** A dependent is missed.", "**Desired behavior:** It becomes ready.",
        "**Acceptance criteria:**", "- [ ] Eligible dependents become ready.", "**Out of scope:** Implementation",
    ))

    def issue(number: int, parent: str | None = None, **overrides) -> dict:
        return {
            "number": number, "parent": parent, "body": brief,
            "author": {"user_type": "User", "permission": "admin"}, "comments": [],
            "state": "OPEN", "assignees": [], "labels": [],
            "native_blockers": [], "fallback_blockers": [], **overrides,
        }

    trigger = issue(98, "A", state="CLOSED")
    dependent = issue(104, native_blockers=[98])
    sibling = issue(99, "A")
    subjects = [dependent, sibling, trigger, issue(105, state="CLOSED", labels=["ready-for-agent"])]
    parents = {"A": {"approved": True, "children": [99, 98]}}
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=98, issues=subjects, parents=parents, native_dependents=[104],
    )
    if plan["frontiers"] != {"parent:A": [99], "standalone": [104]} or plan["promotions"] != [99, 104]:
        fail("a resolved parent-backed trigger missed its direct standalone dependent or its own siblings")
    if plan["removals"] != [105] or plan["scopes"]["standalone"] != [104, 105]:
        fail("the selected standalone scope omitted a closed candidate with stale readiness")

    # A standalone trigger selects the dependent's own parent, including all its
    # children in parent order, rather than treating that dependent as standalone.
    subjects = [issue(1, state="CLOSED"), issue(3, "B", native_blockers=[1]), issue(2, "B")]
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=subjects,
        parents={"B": {"approved": True, "children": [3, 2]}}, native_dependents=[3],
    )
    if plan["frontiers"] != {"standalone": [], "parent:B": [3, 2]} or plan["promotions"] != [3, 2]:
        fail("a standalone trigger did not reconcile its dependent under that dependent's parent")

    # Held triage labels are mapped, and apply to both authority branches.
    mapping = {role: f"team:{role}" for role in HELD_TRIAGE_STATES | {"ready-for-agent"}}
    held = [
        issue(10 + offset, parent, labels=[mapping[role], mapping["ready-for-agent"]])
        for offset, (parent, role) in enumerate(
            (parent, role) for parent in ("A", None) for role in sorted(HELD_TRIAGE_STATES)
        )
    ]
    subjects = [trigger, *held]
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=98, issues=subjects,
        parents={"A": {"approved": True, "children": [98, 10, 11, 12, 13]}},
        native_dependents=[14], triage_labels=mapping,
    )
    if plan["promotions"] or plan["removals"] != list(range(10, 18)):
        fail("held triage states were not preserved across both authority branches")
    if plan["writes"] != [(number, "remove", "team:ready-for-agent") for number in range(10, 18)]:
        fail("reconciliation changed a held triage label instead of only its stale ready marker")

    # The reverse endpoint is canonical even when empty. When it is unavailable,
    # invert each candidate's canonical blockers, falling back only per issue.
    subjects = [
        issue(1, "A", state="CLOSED"), issue(2, "B", native_blockers=[1], fallback_blockers=[9]),
        issue(3, "C", native_blockers=[], fallback_blockers=[1]),
        issue(4, "B", native_blockers=None, fallback_blockers=[1]),
        issue(5, "B", native_blockers=[1, 9], labels=["ready-for-agent"]),
        issue(6, "B", assignees=["owner"], labels=["ready-for-agent"]),
        issue(7, "B", state="CLOSED", labels=["ready-for-agent"]),
        issue(8, "D", native_blockers=[2]), issue(9, "C"),
        issue(10, "C", native_blockers=[1], state="CLOSED"),
        issue(11, "B", native_blockers=[999], labels=["ready-for-agent"]),
    ]
    parents = {
        "A": {"approved": True, "children": [1]},
        "B": {"approved": True, "children": [7, 6, 5, 4, 2, 11]},
        "C": {"approved": True, "children": [3, 9, 10]},
        "D": {"approved": True, "children": [8]},
    }
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=subjects, parents=parents, native_dependents=None,
    )
    if plan["frontiers"] != {"parent:A": [], "parent:B": [4, 2]}:
        fail("fallback discovery recomputed an unrelated or merely transitive scope, or missed a direct dependent")
    if plan["promotions"] != [4, 2] or plan["removals"] != [7, 6, 5, 11]:
        fail("native/fallback precedence, remaining blockers, assignments, or stale closed readiness is incorrect")
    if plan["unresolved_blockers"] != {5: [9], 11: [999]}:
        fail("open or unresolvable blockers were not reported")
    empty = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=subjects, parents=parents, native_dependents=[],
    )
    if empty["scopes"] != {"parent:A": [1]} or empty["writes"]:
        fail("empty native discovery incorrectly fell back to text")

    # Apply only planned readiness operations to copied labels, then check that a
    # rerun selects the same ordered frontiers with zero additional writes.
    updated = [{**subject, "labels": list(subject["labels"])} for subject in subjects]
    for number, operation, label in plan["writes"]:
        subject = next(subject for subject in updated if subject["number"] == number)
        if operation == "add":
            subject["labels"].append(label)
        else:
            subject["labels"].remove(label)
    repeated = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=updated, parents=parents, native_dependents=None,
    )
    if repeated["writes"] or repeated["frontiers"] != plan["frontiers"]:
        fail("unchanged reconciliation rerun made writes or changed deterministic frontier order")
    for before, after in zip(subjects, updated):
        if {k: v for k, v in before.items() if k != "labels"} != {k: v for k, v in after.items() if k != "labels"}:
            fail("reconciliation modified state outside readiness labels")

    # Each direct dependent supplies its own authority. A trusted body or another
    # scope's approval cannot rescue a present invalid parent or failed permission.
    invalids = [
        issue(2, "unapproved"), issue(3, "missing"), issue(4, body="No brief"),
        issue(5, author={"user_type": "User", "permission": None, "author_association": "OWNER"}),
        issue(6, author={"user_type": "Bot", "permission": "admin"}),
        issue(7, author={"user_type": "User", "permission": "read"}),
    ]
    subjects = [issue(1, "A", state="CLOSED"), *invalids, issue(8, "B"), issue(9, "B")]
    parents = {
        "A": {"approved": True, "children": [1]},
        "unapproved": {"approved": False, "children": [2]},
        "B": {"approved": True, "children": [9, 8]},
    }
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=subjects, parents=parents,
        native_dependents=[2, 3, 4, 5, 6, 7, 8, 9, 8],
    )
    if plan["failures"] != {2: "invalid-parent", 3: "invalid-parent", 4: "no-authority", 5: "no-authority", 6: "no-authority", 7: "no-authority"}:
        fail("dependent authority failures were not reported independently")
    if plan["scopes"] != {"parent:A": [1], "parent:B": [9, 8]} or plan["promotions"] != [9, 8]:
        fail("an invalid dependent borrowed authority or duplicate scopes caused repeated mutations")

    # Neither readiness nor the trigger's authority is required of, or transferred
    # to, a valid standalone dependent. Comment precedence remains the shared rule.
    trusted_comment = {"body": brief, "created_at": "2026-01-01", "user_type": "User", "permission": "write"}
    untrusted_comment = {**trusted_comment, "created_at": "2026-01-02", "permission": "read"}
    commented = issue(2, body="No body brief", comments=[trusted_comment, untrusted_comment])
    plan = reconciliation_plan(
        tracker=tracker, trigger_number=1, issues=[subjects[0], commented], parents=parents, native_dependents=[2],
    )
    if plan["promotions"] != [2] or plan["frontiers"] != {"parent:A": [], "standalone": [2]}:
        fail("a trusted comment brief did not authorize a planned standalone dependent")

    local = (ROOT / "skills/setup-skills/issue-tracker-local.md").read_text(encoding="utf-8")
    incomplete = (ROOT / "tests/fixtures/tracker-contract/standalone-incomplete.md").read_text(encoding="utf-8")
    modes = {
        "parent-only": (local, "requires-parent"),
        "incomplete": (incomplete, "stale-tracker"),
        "undeclared": ("## Implementation workflow", "stale-tracker"),
        "ambiguous": (local + "\n" + tracker, "stale-tracker"),
        "retired": (tracker + "\n" + RETIRED_STANDALONE_RECORD, "stale-tracker"),
    }
    for name, (document, reason) in modes.items():
        plan = reconciliation_plan(
            tracker=document, trigger_number=1, issues=[subjects[0], issue(2), issue(8, "B"), issue(9, "B")],
            parents=parents, native_dependents=[2, 8],
        )
        if plan["failures"] != {2: reason} or plan["promotions"] != [9, 8]:
            fail(f"{name} standalone mode borrowed authority or stopped independently valid parent-backed work")

    stopped = [
        issue(1, "A"), issue(1, "unapproved", state="CLOSED"), issue(1, "missing", state="CLOSED"),
        issue(1, state="CLOSED", body="No authority"),
    ]
    for subject in stopped:
        plan = reconciliation_plan(
            tracker=tracker, trigger_number=1, issues=[subject, issue(8, "B"), issue(9, "B")],
            parents=parents, native_dependents=[8],
        )
        if plan["writes"] or plan["scopes"] or not plan["failures"]:
            fail("an open or unauthorized trigger permitted reconciliation writes")
    for name, (document, reason) in modes.items():
        plan = reconciliation_plan(
            tracker=document, trigger_number=1, issues=[issue(1, state="CLOSED"), issue(8, "B"), issue(9, "B")],
            parents=parents, native_dependents=[8],
        )
        if plan["writes"] or plan["scopes"] or plan["failures"] != {1: reason}:
            fail(f"a {name} tracker accepted a standalone reconciliation trigger")


def validate_reconciliation_contract() -> None:
    """Older trigger-only trackers need discovery and scope migration together."""
    reconcile = (ROOT / "skills/reconcile/SKILL.md").read_text(encoding="utf-8")
    setup = (ROOT / "skills/setup-skills/SKILL.md").read_text(encoding="utf-8")
    for document, required in (
        (reconcile, "Resolve each dependent's own authority"),
        (reconcile, "The trigger's approval never grants authority to a dependent"),
        (reconcile, "Deduplicate scopes by parent identity or the standalone set before any write"),
        (reconcile, "held non-ready in both parent-backed and standalone scopes"),
        (reconcile, "Do not traverse dependents of discovered or newly promoted issues"),
        (reconcile, "including an empty native result"),
        (reconcile, "dependencies/blocking"),
        (reconcile, "dependencies/blocked_by"),
        (reconcile, "invert each open issue's canonical blocker references"),
        (reconcile, "at most once per issue"),
        (setup, "Direct dependent discovery and the expanded reconciliation contract must migrate together"),
        (setup, "A new discovery paragraph beside an unchanged trigger-only reconciliation contract is still incomplete"),
        (setup, "A parent-only tracker still rejects parentless dependents"),
    ):
        if required not in document:
            fail(f"expanded reconciliation workflow is missing {required!r}")
    for relative in ("docs/agents/issue-tracker.md", "skills/setup-skills/issue-tracker-github.md"):
        document = (ROOT / relative).read_text(encoding="utf-8")
        frontier = next(line for line in document.splitlines() if line.startswith("- **Frontier promotion**"))
        if "non-held" not in frontier or "expanded `/reconcile` contract" not in frontier:
            fail(f"{relative}: frontier promotion conflicts with held states or affected reconciliation scopes")
    for relative in ("skills/setup-skills/issue-tracker-github.md", "skills/setup-skills/issue-tracker-local.md"):
        seed = (ROOT / relative).read_text(encoding="utf-8")
        current_mode = tracker_standalone_authority(seed)
        old_contract = (
            "- **`/reconcile` contract**: uses the resolved issue as trigger. If the trigger is open, stop. "
            "Enumerate every child under its own parent in order. Apply only the label changes needed; "
            "an unchanged issue is a no-op.\n"
        )
        older = re.sub(r"(?m)^- \*\*(?:Direct dependent discovery|Affected reconciliation scopes)\*\*:.*\n", "", seed)
        older = re.sub(r"(?m)^- \*\*`/reconcile` contract\*\*:.*\n", lambda match: old_contract, older)
        older = older.replace("ready-for-agent", "team:agent-ready") + "\n_Team note: preserve custom tracker commands._\n"
        if tracker_is_current(older):
            fail(f"{relative}: an older trigger-only tracker was incorrectly reported current")
        if missing_tracker_capabilities(older) != ["Direct dependent discovery", "Affected reconciliation scopes", "`/reconcile` contract"]:
            fail(f"{relative}: migration did not report discovery and scope contract gaps together")
        additions = "".join(
            line + "\n" for line in seed.splitlines()
            if line.startswith(("- **Direct dependent discovery**", "- **Affected reconciliation scopes**"))
        )
        discovery_only = older.replace(old_contract, additions + old_contract)
        if missing_tracker_capabilities(discovery_only) != ["`/reconcile` contract"]:
            fail("new discovery alongside old trigger-only reconciliation was incorrectly accepted")
        new_contract = next(line + "\n" for line in seed.splitlines() if line.startswith("- **`/reconcile` contract**"))
        migrated = discovery_only.replace(old_contract, new_contract)
        if not tracker_is_current(migrated) or tracker_standalone_authority(migrated) != current_mode:
            fail("expanded reconciliation migration failed validation or changed standalone authority mode")
        if "team:agent-ready" not in migrated or not migrated.endswith("_Team note: preserve custom tracker commands._\n"):
            fail("expanded reconciliation migration lost a custom readiness state or user note")
