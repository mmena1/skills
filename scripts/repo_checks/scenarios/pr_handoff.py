"""PR handoff groups: `/write-pr` ticket-plan scenarios and the multi-ticket handoff wording."""

from __future__ import annotations

import re

from ..common import ROOT, fail
from ..pr_handoff import MULTI_TICKET_HANDOFF, SINGLE_TICKET_HANDOFF, pr_ticket_plan
from ..tracker_contract import missing_tracker_capabilities, tracker_is_current


def validate_pr_ticket_plan() -> None:
    """Exercise multi-ticket /write-pr planning through the PR ticket plan seam."""

    def ticket(
        record: tuple = (), outcome: str = "succeeded", resolved: bool = False, blockers: tuple = (), **manual,
    ) -> dict:
        closeout = {"commits": list(record), "outcome": outcome} if record else None
        return {"record": closeout, "resolved": resolved, "blockers": list(blockers), "manual": manual or None}

    def commit(sha: str, *references) -> dict:
        return {"sha": sha, "references": list(references)}

    def plan(tickets: dict, commits: list, **options) -> dict:
        # No blanket confirmation input: admission and the targeted gates establish the set.
        settings = {"tracker": "github", "base": "main", "default": "main", "auto_close": True}
        return pr_ticket_plan(tickets=tickets, commits=commits, **{**settings, **options})

    two = {101: ticket(("a1",)), 102: ticket(("b1", "b2"))}
    two_commits = [commit("a1", 101), commit("b1", 102), commit("b2")]
    github = plan(two, two_commits)
    if github["stops"] or github["tickets"] != [101, 102] or github["admission"] != {101: "record", 102: "record"}:
        fail("two GitHub tickets with implementation records naming delta commits were not both admitted")
    if github["close_directives"] != ["Closes #101", "Closes #102"] or github["reconcile"] != [101, 102]:
        fail("two GitHub tickets did not get one independent closing keyword and one gated /reconcile each")
    if github["attribution"] != {"a1": [101], "b1": [102], "b2": [102]} or "verify-closure" not in github["handoff"]:
        fail("two GitHub tickets lost commit attribution or closure verification before reconciliation")
    if any(re.search(r"#\d+\s*,\s*#?\d+", directive) for directive in github["close_directives"]):
        fail("a multi-ticket plan emitted a shared closing keyword, which GitHub applies only to the first issue")

    paths = (".scratch/sync/issues/01-cache.md", ".scratch/sync/issues/02-index.md")
    local = plan(
        {paths[0]: ticket(("a1",)), paths[1]: ticket(("b1", "b2"))},
        [commit("a1", paths[0]), commit("b1", paths[1]), commit("b2")], tracker="local",
    )
    if local["stops"] or local["close_directives"] or local["references"] != list(paths):
        fail("a local Markdown tracker emitted a GitHub closing directive or lost a ticket path reference")
    if local["reconcile"] or local["handoff"] != ["tracker-lifecycle"]:
        fail("a local Markdown tracker was given GitHub's post-merge closure and /reconcile lifecycle")

    # Only a successful closeout whose complete recorded commit set is in the delta admits a ticket.
    partial_commits = [commit("a1", 101)]
    rationale_a1 = {"rationales": {"a1": "Unclear."}}
    for label, record in (
        ("a stopped implementation record", ticket(("a1",), outcome="stopped")),
        ("a failed implementation record", ticket(("a1",), outcome="failed")),
        ("a record with a recorded commit missing from the delta", ticket(("a1", "a2"))),
        ("a record naming no commits", {**ticket(), "record": {"commits": [], "outcome": "succeeded"}}),
    ):
        rejected = plan({101: record}, partial_commits, **rationale_a1)
        if rejected["tickets"] or rejected["unresolved"] != [101] or rejected["close_directives"]:
            fail(f"{label} admitted its ticket or was not listed as an unclear source")
        if rejected["stops"] != [("unresolved-ticket-source", 101), ("no-admitted-ticket", None)]:
            fail(f"{label} did not require source resolution and an admitted ticket")
    rewritten = plan({101: ticket(("a1", "a2"), verified=True, confirmed=True)}, partial_commits)
    if rewritten["stops"] or rewritten["admission"] != {101: "manual"} or rewritten["attribution"] != {"a1": [101]}:
        fail("a partially recorded ticket was not admissible through verified, confirmed manual evidence")

    # Manual work without an /implement closeout needs referencing delta commits,
    # observed verification, and explicit confirmation. A reference alone is a candidate.
    manual_commits = [commit("a1", 101), commit("m1", 103)]
    manual = plan({101: ticket(("a1",)), 103: ticket(verified=True, confirmed=True)}, manual_commits)
    if manual["stops"] or manual["tickets"] != [101, 103] or manual["admission"][103] != "manual":
        fail("a manually implemented ticket with observed verification and confirmation was not admitted")
    if manual["attribution"] != {"a1": [101], "m1": [103]}:
        fail("a manually implemented ticket's referencing commits were not attributed to it")
    rationale = {"rationales": {"m1": "Shared fixture refresh."}}
    for label, evidence in (
        ("without confirmation", ticket(verified=True, confirmed=False)),
        ("without observed verification", ticket(verified=False, confirmed=True)),
        ("from commit-message references alone", ticket()),
    ):
        rejected = plan({101: ticket(("a1",)), 103: evidence}, manual_commits, **rationale)
        if rejected["tickets"] != [101] or rejected["unresolved"] != [103]:
            fail(f"a ticket was admitted {label}, or was not listed as an unclear source for the user")
        if rejected["supporting"] != ["m1"] or rejected["stops"] != [("unresolved-ticket-source", 103)]:
            fail(f"a ticket rejected {label} silently became a supporting change without source resolution")
        if rejected["close_directives"] or rejected["reconcile"]:
            fail(f"an unresolved ticket source {label} allowed drafting or reconciliation")
        excluded = plan({101: ticket(("a1",)), 103: evidence}, manual_commits, excluded_sources={103}, **rationale)
        if excluded["stops"] or excluded["tickets"] != [101] or excluded["excluded"] != [103]:
            fail(f"explicitly excluding a ticket {label} required redundant ticket-set confirmation")
        if excluded["supporting"] != ["m1"] or excluded["close_directives"] != ["Closes #101"]:
            fail(f"excluding a ticket {label} admitted it or lost its supporting-change rationale")
    excluded_without_rationale = plan(
        {101: ticket(("a1",)), 103: ticket()}, manual_commits, excluded_sources={103},
    )
    if excluded_without_rationale["stops"] != [("supporting-change-without-rationale", "m1")]:
        fail("explicit source exclusion silently supplied a missing supporting-change rationale")
    unexplained = plan({101: ticket(("a1",))}, manual_commits)
    if unexplained["supporting"] != ["m1"] or unexplained["stops"] != [("supporting-change-without-rationale", "m1")]:
        fail("an unattributed commit without a stated rationale did not stop drafting")
    if unexplained["close_directives"] or unexplained["reconcile"]:
        fail("a stopped plan still drafted closing keywords or reconciliation")

    shared_tickets = {101: ticket(("a1", "s1")), 102: ticket(("s1", "b1"))}
    shared_commits = [commit("a1", 101), commit("s1", 101, 102), commit("b1", 102)]
    unconfirmed = plan(shared_tickets, shared_commits)
    if unconfirmed["shared"] != ["s1"] or unconfirmed["stops"] != [("unconfirmed-shared-commit", "s1")]:
        fail("a commit attributed to two tickets was accepted without explicit confirmation")
    confirmed = plan(shared_tickets, shared_commits, shared_confirmed={"s1"})
    if confirmed["stops"] or confirmed["shared"] != ["s1"] or confirmed["attribution"]["s1"] != [101, 102]:
        fail("a confirmed commit shared by two tickets was not reported against both")

    # Closure is never assumed: keywords are inert off the default branch or without auto-closure.
    stacked = plan(two, two_commits, base="release")
    if stacked["stops"] or "keywords-inert-on-non-default-base" not in stacked["handoff"]:
        fail("a PR targeting a non-default branch did not state that closing keywords will not close its issues")
    for label, auto_close in (("unknown", None), ("disabled", False)):
        unverified = plan(two, two_commits, auto_close=auto_close)
        if unverified["stops"] or "auto-close-unverified" not in unverified["handoff"]:
            fail(f"{label} automatic issue closure was not marked unverified in the handoff")
        if "verify-closure" not in unverified["handoff"] or unverified["reconcile"] != [101, 102]:
            fail(f"{label} automatic issue closure dropped closure verification before reconciliation")
    if {"keywords-inert-on-non-default-base", "auto-close-unverified"} & set(local["handoff"] + github["handoff"]):
        fail("a GitHub-closure caveat appeared where keywords close on merge or no keyword exists")
    if plan(two, two_commits)["stops"]:
        fail("an unambiguous verified ticket set required redundant confirmation before drafting")

    single = plan({101: ticket(("a1",))}, [commit("a1", 101)])
    expected_single = {
        "tickets": [101], "references": ["#101"], "close_directives": ["Closes #101"],
        "handoff": ["verify-closure"], "reconcile": [101], "stops": [],
    }
    if {key: single[key] for key in expected_single} != expected_single:
        fail("a single-ticket branch changed its close directive or handoff shape")
    if plan({101: ticket()}, [commit("a1", 101)], rationales={"a1": "Unclear."})["stops"] != [
        ("unresolved-ticket-source", 101), ("no-admitted-ticket", None),
    ]:
        fail("drafting proceeded with no admitted ticket instead of asking for the governing source")

    # Every unresolved blocker of every admitted ticket must be in the set, which validates chains.
    blocked = {101: ticket(("a1",)), 102: ticket(("b1",), blockers=(101, 90)), 90: ticket()}
    blocked_commits = [commit("a1", 101), commit("b1", 102)]
    outside = plan(blocked, blocked_commits)
    if outside["stops"] != [("blocker-outside-set", (102, 90))] or outside["close_directives"]:
        fail("a ticket with an unresolved blocker outside the established set did not stop drafting")
    overridden = plan(blocked, blocked_commits, blocker_overrides={(102, 90)})
    if overridden["stops"] or overridden["overrides"] != [(102, 90)] or overridden["tickets"] != [101, 102]:
        fail("an explicit blocker override was not honoured and reported")
    blocked[90] = ticket(resolved=True)
    if plan(blocked, blocked_commits)["stops"]:
        fail("a resolved blocker outside the set stopped drafting")
    included = {**blocked, 90: ticket(("z1",))}
    if plan(included, [commit("z1", 90), *blocked_commits])["stops"]:
        fail("including the unresolved blocker in the set did not clear the stop")

    chain = {1: ticket(("c1",)), 2: ticket(("c2",), blockers=(1,)), 3: ticket(("c3",), blockers=(2,))}
    chain_commits = [commit("c1", 1), commit("c2", 2), commit("c3", 3)]
    whole_chain = plan(chain, chain_commits)
    if whole_chain["stops"] or whole_chain["close_directives"] != ["Closes #1", "Closes #2", "Closes #3"]:
        fail("a chain A -> B -> C with all three in the set did not validate")
    without_b = plan({**chain, 2: ticket()}, [commit("c1", 1), commit("c3", 3)])
    if without_b["stops"] != [("blocker-outside-set", (3, 2))]:
        fail("a chain A -> B -> C validated although B is unresolved and outside the set")
    resolved_a = plan({**chain, 1: ticket(resolved=True)}, chain_commits[1:])
    if resolved_a["stops"] or resolved_a["tickets"] != [2, 3]:
        fail("a chain A -> B -> C did not validate when A is already resolved and B and C are in the set")


def validate_multi_ticket_pr_contract() -> None:
    """Pin the multi-ticket /write-pr, tracker handoff, and sequential /implement wording."""

    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    write_pr = read("skills/write-pr/SKILL.md")
    for required in (
        "**Ticket set**: the tickets the branch delta implements, established from admissible evidence",
        "(a) a tracker implementation record of a successful closeout, such as a completed `/implement` closeout, "
        "whose complete recorded commit set is present in the branch delta",
        "verification output this workflow observes, and explicit user confirmation",
        "A stop report, a failed or partial record, or a closeout with any recorded commit missing from the branch delta",
        "as does a commit-message reference alone; neither is admissible evidence",
        "without that confirmation, the candidate is not admitted",
        "as an unclear source for the user to resolve, include, or exclude",
        "Resolve every unclear source before drafting: inclusion requires admissible evidence, and exclusion requires an explicit user decision",
        "excluded commits still need supporting-change rationales",
        "Missing evidence or user silence never admits a candidate",
        "Report a commit attributed to more than one ticket and ask the user to confirm that attribution explicitly",
        "Report every unattributed commit as a supporting change with a stated rationale",
        "every unresolved blocker must itself be in the ticket set",
        "merging would resolve a dependent before its blocker",
        "report the override in the body",
        "Present the established ticket set",
        "proceed without ticket-set confirmation, for both single-ticket and multi-ticket branches",
        "Request targeted input only for unresolved evidence, attribution, or rationale",
        "once resolved, proceed without another acknowledgment of the set",
        "step 6 still requires approval of the exact title and body",
        "**Completion criterion**: the ticket set established from admissible evidence, every unclear source resolved",
        "Stop and warn the user before creating the pull request if the diff contains likely secrets or sensitive material",
        "Create pull request? (ready / draft / edit / abort)",
        "This approves pushing the branch and creating the pull request with the exact displayed title and body",
        "carry one independent closing keyword per issue",
        "GitHub applies a shared keyword such as `Closes #<a>, #<b>` only to the first issue",
        "generate no GitHub closing directive. Reference each ticket by its tracker identifier or path",
        "Closure is never assumed.",
        "closing keywords will not close the issues on merge",
        "mark auto-closure as unverified",
        "invoke `/reconcile <ticket-ref>` once per ticket only after that ticket is verified closed",
        "leave its resolution and frontier refresh to the tracker's configured resolve and frontier rules",
        "The merge carries no closed-state, auto-closure, or post-merge `/reconcile` requirement.",
        "With one admitted GitHub issue, the body keeps its single-ticket shape: one close directive",
    ):
        if required not in write_pr:
            fail(f"/write-pr multi-ticket contract is missing {required!r}")
    for retired in (
        "required ticket or issue identifier", "list them and ask the user to choose",
        "confirmed by the user before drafting", "ask the user to confirm the final ticket set before drafting",
        "the user-confirmed ticket set",
    ):
        if retired in write_pr:
            fail(f"/write-pr retains retired ticket-set wording: {retired!r}")

    for relative in ("skills/setup-skills/issue-tracker-github.md", "docs/agents/issue-tracker.md"):
        tracker = read(relative)
        handoff = next(line for line in tracker.splitlines() if line.startswith("- **PR/merge handoff"))
        if MULTI_TICKET_HANDOFF not in handoff:
            fail(f"{relative}: PR/merge handoff is missing the multi-ticket closing and verification sentence")
        # A clarification, not a new capability: the single-ticket tracker it replaced stays current.
        older = tracker.replace(MULTI_TICKET_HANDOFF, SINGLE_TICKET_HANDOFF)
        if older == tracker or missing_tracker_capabilities(older) or not tracker_is_current(older):
            fail(f"{relative}: a tracker without the multi-ticket handoff sentence was reported stale")
    if "such as the multi-ticket PR/merge handoff, is not a missing capability" not in read("skills/setup-skills/SKILL.md"):
        fail("/setup-skills does not state that the multi-ticket handoff clarification leaves a tracker current")

    implement = read("skills/implement/SKILL.md")
    for required in (
        "Sequential runs for different tickets on one existing non-default branch are supported.",
        "Each run keeps its own `BASELINE`, start gates, claim, review cycle, commits, and closeout",
        "a clean worktree: no uncommitted changes, with this ticket's work committed",
        "Commits from earlier tickets on the branch are allowed; they precede `BASELINE` and stay outside "
        "this run's `<BASELINE>...HEAD` review diff.",
    ):
        if required not in implement:
            fail(f"/implement sequential same-branch contract is missing {required!r}")
    if "a clean worktree containing only committed ticket work" in implement:
        fail("/implement still reads as forbidding earlier tickets' commits on the branch")
