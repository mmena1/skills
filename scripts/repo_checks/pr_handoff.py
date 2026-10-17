"""The `/write-pr` regression model and the pinned PR/merge handoff sentences.

Models the ticket set, commit attribution, and closure handoff over one branch delta.
"""

from __future__ import annotations


def pr_ticket_plan(
    *, tracker: str, tickets: dict, commits: list[dict], base: str, default: str,
    auto_close: bool | None, shared_confirmed: set | None = None,
    rationales: dict | None = None, blocker_overrides: set | None = None,
    branch_relations: dict | None = None, excluded_sources: set | None = None,
) -> dict:
    """Model /write-pr's ticket set, commit attribution, and closure handoff over one branch delta.

    Tickets are tracker snapshots keyed by reference (GitHub issue numbers or local
    ticket paths): `record` is a tracker implementation record with its outcome and
    recorded commits, and `manual` holds the observed verification and confirmation.
    Commits are the branch delta in order, with the ticket references their messages carry. A record's
    `branch_satisfied` lists the blockers its run relied on; `branch_relations` maps each such
    (dependent, blocker) relation to its branch-satisfied verdict re-validated at the final head.
    `excluded_sources` records explicit user exclusions of candidates lacking admissible evidence;
    their unattributed commits still require supporting-change rationales.
    This is a regression model of the prompt workflow, not a tracker adapter.
    """
    shared_confirmed = shared_confirmed or set()
    rationales = rationales or {}
    blocker_overrides = blocker_overrides or set()
    excluded_sources = excluded_sources or set()
    delta = [entry["sha"] for entry in commits]
    plan = {
        "tickets": [], "admission": {}, "attribution": {}, "unresolved": [], "excluded": [], "supporting": [], "shared": [],
        "overrides": [], "references": [], "close_directives": [], "reconcile": [], "handoff": [], "stops": [],
    }
    attribution: dict = {}
    for reference in sorted(tickets):
        subject = tickets[reference]
        record = subject["record"]
        # Only a successful closeout whose complete recorded commit set is in the delta counts.
        named = record["commits"] if (
            record and record["outcome"] == "succeeded" and record["commits"]
            and all(sha in delta for sha in record["commits"])
        ) else []
        # Commit-message references are candidates; they count only with observed verification and confirmation.
        referencing = [entry["sha"] for entry in commits if reference in entry["references"]]
        manual = subject["manual"] or {}
        confirmed_manual = bool(referencing) and manual.get("verified", False) and manual.get("confirmed", False)
        if not named and not confirmed_manual:
            if referencing or subject["record"] or subject["manual"]:
                if reference in excluded_sources:
                    plan["excluded"].append(reference)
                else:
                    plan["unresolved"].append(reference)
                    plan["stops"].append(("unresolved-ticket-source", reference))
            continue
        plan["tickets"].append(reference)
        plan["admission"][reference] = "record" if named else "manual"
        for sha in set(named) | set(referencing if confirmed_manual else ()):
            attribution.setdefault(sha, []).append(reference)
    plan["attribution"] = {sha: attribution[sha] for sha in delta if sha in attribution}
    for sha in delta:
        owners = attribution.get(sha, [])
        if not owners:
            plan["supporting"].append(sha)
            if not rationales.get(sha):
                plan["stops"].append(("supporting-change-without-rationale", sha))
        elif len(owners) > 1:
            plan["shared"].append(sha)
            if sha not in shared_confirmed:
                plan["stops"].append(("unconfirmed-shared-commit", sha))
    if not plan["tickets"]:
        plan["stops"].append(("no-admitted-ticket", None))
    branch_relations = branch_relations or {}
    # Checking each admitted ticket's own blockers validates whole chains across the set.
    for reference in plan["tickets"]:
        relied_on = (tickets[reference]["record"] or {}).get("branch_satisfied", [])
        for blocker in tickets[reference]["blockers"]:
            if blocker in tickets and tickets[blocker]["resolved"]:
                continue
            if blocker in relied_on:
                # A branch-satisfied relation is never overridden: its blocker ships in this PR,
                # and the relation is re-validated at the final head.
                if blocker not in plan["tickets"]:
                    plan["stops"].append(("branch-satisfied-blocker-outside-set", (reference, blocker)))
                elif branch_relations.get((reference, blocker)) != "satisfied":
                    verdict = branch_relations.get((reference, blocker), "not-validated")
                    plan["stops"].append(("branch-satisfied-relation-invalid", (reference, blocker, verdict)))
                continue
            if blocker in plan["tickets"]:
                continue
            if (reference, blocker) in blocker_overrides:
                plan["overrides"].append((reference, blocker))
            else:
                plan["stops"].append(("blocker-outside-set", (reference, blocker)))
    if plan["stops"]:
        return plan
    if tracker != "github":
        # A local ticket keeps its configured resolve and frontier rules; nothing waits on the merge.
        plan["references"] = list(plan["tickets"])
        plan["handoff"].append("tracker-lifecycle")
        return plan
    plan["references"] = [f"#{reference}" for reference in plan["tickets"]]
    # One independent keyword per issue: GitHub applies a shared keyword only to its first issue.
    plan["close_directives"] = [f"Closes {reference}" for reference in plan["references"]]
    if base != default:
        plan["handoff"].append("keywords-inert-on-non-default-base")
    if auto_close is not True:
        plan["handoff"].append("auto-close-unverified")
    # Every ticket is verified closed after merge, and only a verified-closed ticket is reconciled.
    plan["handoff"].append("verify-closure")
    plan["reconcile"] = list(plan["tickets"])
    return plan


MULTI_TICKET_HANDOFF = (
    "A multi-ticket PR carries one independent closing keyword per issue, such as `Closes #<a>` and "
    "`Closes #<b>` on separate lines, because GitHub applies a shared keyword only to its first issue. "
    "Closing keywords close issues only when the PR targets the default branch and automatic issue closure "
    "is enabled, so after merge the PR/merge owner verifies each issue's closed state, accounting for a "
    "non-default base branch and disabled or unverified auto-closure. For an issue that did not close, report "
    "the missing or ineffective close reference and close it explicitly before reconciling it. Invoke "
    "`/reconcile <ticket-ref>` once per ticket only after that ticket is verified closed, so no dependent is "
    "promoted before its blocker closes. "
)
SINGLE_TICKET_HANDOFF = (
    "If the issue did not auto-close, stop the reconciliation and report the missing or ineffective close "
    "reference rather than promoting dependent tickets. "
)
