"""Implementation workflow groups: review routing, reviewer authorization, the working copy, and branch-satisfied blockers.

Pins the `/implement`, `/write-pr`, and `implementation-review` wording and exercises
the implementation, reconciliation, and PR handoff models through their scenarios.
"""

from __future__ import annotations

import json

from ..agent_brief import AGENT_BRIEF_HEADING
from ..common import ROOT, fail
from ..implementation import (
    branch_satisfied_blocker, implementation_branch_gate, implementation_start_gate, review_cycle_requests,
    reviewer_preflight,
)
from ..layout import parse_frontmatter
from ..pr_handoff import pr_ticket_plan
from ..reconciliation import HELD_TRIAGE_STATES, reconciliation_plan
from ..tracker_contract import (
    BRANCH_SATISFIED_CONTRACT, FAIL_CLOSED_BRANCH_EXCEPTION, STANDALONE_BRANCH_EXCEPTION, branch_satisfied_operation,
    branch_satisfied_operation_state, gated_tracker_capabilities, missing_branch_satisfied_elements,
    missing_tracker_capabilities, tracker_defines_branch_satisfied_blockers, tracker_is_current,
)


def validate_implementation_review_routing_contract() -> None:
    """Keep fixed-baseline conformance routing distinct from explicit deep review."""
    implementation_review = (ROOT / "skills/implementation-review/SKILL.md").read_text(encoding="utf-8")
    implement = (ROOT / "skills/implement/SKILL.md").read_text(encoding="utf-8")
    deep_review = (ROOT / "skills/deep-review/SKILL.md").read_text(encoding="utf-8")
    deep_review_metadata = (ROOT / "skills/deep-review/agents/openai.yaml").read_text(encoding="utf-8")

    description = parse_frontmatter(ROOT / "skills/implementation-review/SKILL.md")[0]["description"]
    for required in (
        "fixed baseline",
        "originating issue/spec requirements",
        "repository standards",
        "implementation-conformance review",
        "generic PR reviews",
        "broad defect-discovery tasks must not select this skill",
        "Deep-review remains explicit-only",
    ):
        if required not in description:
            fail(f"implementation-review description is missing routing purpose {required!r}")
    for required in (
        "explicit implementation-conformance review",
        "Do not select it for generic PR review requests or broad defect-discovery tasks",
        "Use the fixed point supplied by the invoking workflow, if present",
        "Otherwise, use the fixed point explicitly provided by the user",
        "When composed by `/implement`, the fixed point is `BASELINE`",
        "Ask the user for a fixed point only when neither the caller nor the user provided one",
    ):
        if required not in implementation_review:
            fail(f"implementation-review invocation contract is missing {required!r}")

    for required in (
        "Search the repository for standards documents that apply to the changed files",
        "record its path and applicable content",
        "applicable standards-source paths and their contents",
        "When no applicable standards documents were found, say so explicitly",
        "The Standards report is always applicable",
        "mark the Spec axis as skipped with \"no spec available,\"",
        "Wait until every applicable sub-agent returns a report before aggregating",
        "mark the overall review **incomplete**",
        "Never present an incomplete review as a completed aggregate",
    ):
        if required not in implementation_review:
            fail(f"implementation-review report contract is missing {required!r}")

    review_step = implement.partition("## 5. Commit, review, and converge")[2].partition("## 6.")[0]
    native_compose = review_step.find("Compose the `implementation-review` skill natively")
    compatibility_fallback = review_step.find("On a harness that cannot compose installed skills")
    if not 0 <= native_compose < compatibility_fallback:
        fail("/implement must prefer native implementation-review composition and retain only a harness-compatibility fallback")
    if "fixed baseline" not in description or "BASELINE" not in review_step or "originating source bundle" not in review_step:
        fail("/implement post-commit review must pass BASELINE and its originating source bundle to implementation-review")

    deep_fields, _ = parse_frontmatter(ROOT / "skills/deep-review/SKILL.md")
    if deep_fields.get("disable-model-invocation") != "true" or "triggers" not in deep_fields:
        fail("deep-review must remain explicitly user-invoked")
    if "allow_implicit_invocation: false" not in deep_review_metadata:
        fail("deep-review Codex metadata must remain explicit-only")
    if "implementation-review" in deep_review:
        fail("deep-review must not compose implementation-review as part of explicit deep-review routing")


def validate_reviewer_authorization_preflight() -> None:
    """Pin the reviewer authorization preflight wording and run its simulated instruction scenarios.

    The scenarios model what the instructions require. They are not observations of native
    harness authorization behavior, and nothing here reports one as observed.
    """
    review = (ROOT / "skills/implementation-review/SKILL.md").read_text(encoding="utf-8")
    implement = (ROOT / "skills/implement/SKILL.md").read_text(encoding="utf-8")
    for required in (
        "## Reviewer authorization preflight",
        "The preflight never launches a reviewer",
        "no dummy, probe, or fabricated reviewer tests a permission",
        "Standards is always required. Spec is required whenever an originating source is available.",
        "may skip Spec as \"no spec available\"",
        "with both Standards and Spec required, because it always supplies a source bundle",
        "- **Established**",
        "Proceed with no added confirmation prompt",
        "- **Known blocked**",
        "Request once the narrowest authorization the harness supports, scoped to this ticket's review",
        "A grant authorizes only the roles it covers",
        "covering the review's fixed-point re-review iterations",
        "On denial, stop and report the affected roles and the consequence",
        "- **Indeterminate**",
        "continue without stating or implying that authorization has been granted",
        "Never infer one role's authorization from another's",
        "Never request a global, broader-than-ticket, or permanent permission",
        "weaken a reviewer's permissions or read-only contract",
        "substitute a coordinator-only check",
        "where the harness itself prompts per invocation, those prompts are the harness's",
        "never a review success",
        "labelled documented, observed (harness, version, date), or inferred",
        "A harness with no documented advance check is indeterminate",
    ):
        if required not in review:
            fail(f"implementation-review reviewer authorization preflight is missing {required!r}")
    for harness in ("Codex", "Devin", "Claude Code"):
        if f"| {harness} |" not in review:
            fail(f"implementation-review harness mechanisms table has no {harness} row")

    gates = implement.partition("## 2. Pass the start gates")[2].partition("## 3.")[0]
    preflight = gates.find("reviewer authorization preflight")
    if not 0 <= gates.find("Verify either that the governing parent/spec") < gates.find("verify it is open") < preflight:
        fail("/implement must apply the reviewer authorization preflight after the authority and ticket-state gates")
    if not 0 <= preflight < gates.find("If HEAD is detached") < gates.find("Claim the ticket"):
        fail("/implement must apply the reviewer authorization preflight before branch creation and the claim")
    for required in (
        "`implementation-review` skill's reviewer authorization preflight by name",
        "with both Standards and Spec required.",
        "stop with no tracker or working-copy write",
        "reviewer authorization preflight outcome",
    ):
        if required not in implement:
            fail(f"/implement reviewer authorization preflight is missing {required!r}")
    if "reviewer-authorization" in implement or "implementation-review/" in gates:
        fail("/implement must apply the preflight by skill name, not by file path")

    both_established = {"Standards": "established", "Spec": "established"}
    scenarios = {
        "simulated: both roles established proceed with no request": (
            dict(context="implement", source_available=True, states=both_established),
            dict(required=["Standards", "Spec"], requests=0, outcome="proceed", writes_allowed=True,
                 authorized=["Standards", "Spec"], disclosed=[]),
        ),
        "simulated: one role denied stops before any write": (
            dict(context="implement", source_available=True, grant=frozenset(),
                 states={"Standards": "established", "Spec": "blocked"}),
            dict(requests=1, request_scope=["Standards", "Spec"], outcome="stop", affected=["Spec"],
                 writes_allowed=False, authorized=[]),
        ),
        "simulated: a grant covering every blocked role proceeds": (
            dict(context="implement", source_available=True, grant=frozenset({"Standards", "Spec"}),
                 states={"Standards": "blocked", "Spec": "blocked"}),
            dict(requests=1, outcome="proceed", writes_allowed=True, authorized=["Standards", "Spec"]),
        ),
        "simulated: missing preflight support is indeterminate and discloses": (
            dict(context="implement", source_available=True, states={}),
            dict(requests=0, outcome="proceed", writes_allowed=True, disclosed=["Standards", "Spec"], authorized=[]),
        ),
        "simulated: a grant for one role leaves an indeterminate role unauthorized and disclosed": (
            dict(context="implement", source_available=True, grant=frozenset({"Standards"}),
                 states={"Standards": "blocked", "Spec": "indeterminate"}),
            dict(requests=1, outcome="proceed", writes_allowed=True, authorized=["Standards"], disclosed=["Spec"],
                 affected=[]),
        ),
        "simulated: a partial grant leaves a blocked role blocked and stops": (
            dict(context="implement", source_available=True, grant=frozenset({"Standards"}),
                 states={"Standards": "blocked", "Spec": "blocked"}),
            dict(requests=1, outcome="stop", writes_allowed=False, affected=["Spec"], authorized=[]),
        ),
        "simulated: a role established does not cover an indeterminate one": (
            dict(context="implement", source_available=True, states={"Standards": "established"}),
            dict(outcome="proceed", disclosed=["Spec"], authorized=["Standards"]),
        ),
        "simulated: a standalone run without a source skips Spec": (
            dict(context="standalone", source_available=False, states={"Standards": "established"}),
            dict(required=["Standards"], skipped=["Spec"], requests=0, outcome="proceed", disclosed=[]),
        ),
        "simulated: a standalone run with a source requires Spec": (
            dict(context="standalone", source_available=True, states=both_established),
            dict(required=["Standards", "Spec"], skipped=[]),
        ),
        "simulated: /implement requires Spec even when the standalone source flag is unset": (
            dict(context="implement", source_available=False, states=both_established),
            dict(required=["Standards", "Spec"], skipped=[]),
        ),
    }
    for label, (arguments, expected) in scenarios.items():
        result = reviewer_preflight(**arguments)
        for key, value in expected.items():
            if result[key] != value:
                fail(f"reviewer authorization preflight: {label} gave {key}={result[key]!r} (expected {value!r})")

    granted = reviewer_preflight(
        context="implement", source_available=True, grant=frozenset({"Standards"}),
        states={"Standards": "blocked", "Spec": "established"},
    )
    mixed = reviewer_preflight(
        context="implement", source_available=True, states={"Standards": "established", "Spec": "indeterminate"},
    )
    cycle_scenarios = {
        "simulated: repeated cycles add no skill request after a grant": (
            dict(preflight=granted, cycles=3, per_invocation=False),
            dict(skill_requests=0, harness_prompts=0, advance_coverage_claimed=True),
        ),
        "simulated: repeated cycles claim no whole-review coverage while a required role is indeterminate": (
            dict(preflight=mixed, cycles=3, per_invocation=False),
            dict(skill_requests=0, harness_prompts=0, advance_coverage_claimed=False),
        ),
        "simulated: repeated cycles under per-invocation prompts claim no advance coverage": (
            dict(preflight=reviewer_preflight(context="implement", source_available=True, states={}), cycles=3,
                 per_invocation=True),
            dict(skill_requests=0, harness_prompts=6, advance_coverage_claimed=False),
        ),
    }
    for label, (arguments, expected) in cycle_scenarios.items():
        result = review_cycle_requests(**arguments)
        if result != expected:
            fail(f"reviewer authorization preflight: {label} gave {result} (expected {expected})")


def validate_implementation_working_copy_contract() -> None:
    """/implement consumes a harness-provided working copy, including a detached HEAD, and never owns its lifecycle."""
    implement = (ROOT / "skills/implement/SKILL.md").read_text(encoding="utf-8")
    for required in (
        "never creates, replaces, switches to, or cleans up worktrees or other working copies",
        "belongs to the harness or orchestrator that launched it",
        "HEAD is detached only if `git symbolic-ref -q HEAD` fails",
        "If HEAD is detached",
        "is a valid starting state",
        "create and switch to a new implementation branch at `BASELINE`",
        "without asking the user for permission",
        "If the current branch is any other non-default branch, continue on it.",
        "Never delete, reset, force, or overwrite an existing branch",
        "never commit implementation work on a default branch",
        "Confirm `git branch --show-current` is non-empty and is not the resolved default branch",
    ):
        if required not in implement:
            fail(f"/implement working-copy contract is missing {required!r}")
    if "If the current branch is detached" in implement:
        fail("/implement still stops on a detached HEAD")
    gates = implement.partition("## 2. Pass the start gates")[2].partition("## 3.")[0]
    if not 0 <= gates.find("If HEAD is detached") < gates.find("Claim the ticket"):
        fail("/implement must create the branch from a detached HEAD in its start gates, before the claim")

    cases = {
        "an existing non-default branch continues": ("feature", False, True, "continue"),
        "an existing non-default branch never needs creation": ("feature", False, False, "continue"),
        "the default branch branches": ("main", False, True, "branch"),
        "the default branch stops when creation fails": ("main", False, False, "stop"),
        "a detached HEAD branches from the current HEAD": ("", True, True, "branch"),
        "a detached HEAD stops when creation fails": ("", True, False, "stop"),
        "an empty name that is not a detached HEAD stops": ("", False, True, "stop"),
    }
    for label, (current, detached, created, outcome) in cases.items():
        if implementation_branch_gate(current=current, detached=detached, default="main", created=created) != outcome:
            fail(f"/implement branch gate: {label} (expected {outcome!r})")


def validate_branch_satisfied_blockers() -> None:
    """Exercise the optional branch-satisfied blockers operation and pin its wording."""

    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    github_seed = read("skills/setup-skills/issue-tracker-github.md")
    tracker = read("docs/agents/issue-tracker.md")
    local_seed = read("skills/setup-skills/issue-tracker-local.md")
    implement = read("skills/implement/SKILL.md")
    write_pr = read("skills/write-pr/SKILL.md")
    setup = read("skills/setup-skills/SKILL.md")

    # The optional operation is pinned identically in the GitHub seed and this repository's copy.
    operations = []
    for relative, document in (("skills/setup-skills/issue-tracker-github.md", github_seed), ("docs/agents/issue-tracker.md", tracker)):
        if not tracker_defines_branch_satisfied_blockers(document):
            fail(f"{relative}: does not define the optional branch-satisfied blockers operation")
        operation = branch_satisfied_operation(document)
        for required in BRANCH_SATISFIED_CONTRACT:
            if required not in operation:
                fail(f"{relative}: branch-satisfied blockers operation is missing {required!r}")
        operations.append(operation)
    if operations[0] != operations[1]:
        fail("the branch-satisfied blockers operation differs between the GitHub seed and this repository's tracker")
    # The tracker's own standalone authority rules carry the narrow branch-local exception,
    # so an agent obeying the tracker reaches the same verdict as /implement.
    for relative, document in (("skills/setup-skills/issue-tracker-github.md", github_seed), ("docs/agents/issue-tracker.md", tracker)):
        lines = document.splitlines()
        authority = next(line for line in lines if line.startswith("- **Standalone authority**"))
        fail_closed = next(line for line in lines if line.startswith("  - **Fail closed**: the implementation-ready label"))
        if STANDALONE_BRANCH_EXCEPTION not in authority or FAIL_CLOSED_BRANCH_EXCEPTION not in fail_closed:
            fail(f"{relative}: standalone authority does not state the branch-local readiness exception")
        if "a complete trusted brief without the implementation-ready state is not yet implementable" not in fail_closed:
            fail(f"{relative}: the branch-local exception replaced the ready-state fail-closed rule")
    if tracker_defines_branch_satisfied_blockers(local_seed):
        fail("skills/setup-skills/issue-tracker-local.md: the local tracker must not define branch-satisfied blockers")
    for document, required in (
        (implement, "the optional branch-satisfied blockers operation"),
        (implement, "Validate each direct open blocker"),
        (implement, "Branch satisfaction is a run-local fact"),
        (implement, "never adds the implementation-ready label"),
        (implement, "is evaluated as `/reconcile` would classify the ticket if its branch-satisfied blockers were closed"),
        (implement, "A tracker without the operation keeps the default gate: every blocker must be closed."),
        (implement, "or in the branch-local readiness step 2 defines when every open blocker is branch-satisfied"),
        (implement, "When the file names the operation but omits any of its conditions, ignore it, keep that default gate"),
        (setup, "that incomplete operation is a remaining gap"),
        (implement, "lists each branch-satisfied blocker with its commits and evidence source"),
        (implement, "must not be resolved before those blockers"),
        (write_pr, "Re-validate every branch-satisfied relation in the pull request against the final head"),
        (write_pr, "including ancestry, intactness, and revert detection"),
        (write_pr, "no blocker override applies to it"),
        (setup, "The optional branch-satisfied blockers operation is not a required capability"),
    ):
        if required not in document:
            fail(f"branch-satisfied blockers contract is missing {required!r}")

    # A tracker without the operation, including an existing GitHub configuration, stays current.
    without = {
        relative: document.replace(branch_satisfied_operation(document), "")
        for relative, document in (("the GitHub seed", github_seed), ("this repository's tracker", tracker))
    }
    for label, document in without.items():
        if tracker_defines_branch_satisfied_blockers(document) or not tracker_is_current(document):
            fail(f"{label} without the optional branch-satisfied operation was reported stale")

    # A tracker that names the operation without its full conditions grants nothing.
    operation = branch_satisfied_operation(tracker)
    header_only = tracker.replace(operation, operation.splitlines()[0] + "\n")
    fail_closed_dropped = tracker.replace(
        next(line + "\n" for line in operation.splitlines() if line.startswith("  - **Fail closed**")), "",
    )
    partial = {"a header-only operation": header_only, "an operation missing its fail-closed conditions": fail_closed_dropped}
    for label, document in partial.items():
        if branch_satisfied_operation_state(document) != "incomplete" or tracker_defines_branch_satisfied_blockers(document):
            fail(f"a tracker with {label} enabled branch satisfaction")
        if tracker_is_current(document) or missing_tracker_capabilities(document):
            fail(f"/setup-skills did not report {label} as an optional-operation gap alone")
    if missing_branch_satisfied_elements(fail_closed_dropped) != [
        "revert detection", "conflicting records", "missing commits", "later path changes", "own blockers named", "failed lookups",
    ]:
        fail("an operation missing its fail-closed conditions did not name each missing element")
    for document in (github_seed, tracker, *without.values(), local_seed):
        if branch_satisfied_operation_state(document) == "incomplete":
            fail("a complete or absent branch-satisfied operation was reported incomplete")

    admin = {"user_type": "User", "permission": "admin"}
    writer = {"user_type": "User", "permission": "write"}

    def record(*commits, outcome: str = "succeeded", author: dict = admin, created_at: str = "2026-01-02", relied=()) -> dict:
        return {"outcome": outcome, "commits": list(commits), "author": author, "created_at": created_at, "branch_satisfied": list(relied)}

    def blocker(*records, assignees=("dev",), open_blockers=(), manual: dict | None = None) -> dict:
        return {"assignees": list(assignees), "records": list(records), "open_blockers": list(open_blockers), "manual": manual}

    def commit(sha: str, *paths, reverts=(), patch: str | None = None) -> dict:
        return {"sha": sha, "paths": list(paths), "reverts": list(reverts), "patch": patch or f"patch-{sha}"}

    def verdict(subject: dict, history: list, **options) -> tuple[str, list[str]]:
        return branch_satisfied_blocker(blocker=subject, history=history, **options)

    history = [commit("base", "README.md"), commit("a1", "a.py"), commit("a2", "a_test.py")]
    intact = blocker(record("a1", "a2"))
    later = "2026-01-05"
    verdicts = {
        "an intact, claimed blocker with a trusted record": (intact, history, {}, ("satisfied", ["a1", "a2"])),
        "a writer's record": (blocker(record("a1", "a2", author=writer)), history, {}, ("satisfied", ["a1", "a2"])),
        "a recorded commit implemented on another branch": (
            blocker(record("a1", "a2", "z9")), history, {}, ("missing-commits", ["z9"]),
        ),
        "recorded commits rewritten by a rebase": (
            intact, [history[0], commit("a1'", "a.py"), commit("a2'", "a_test.py")], {}, ("missing-commits", ["a1", "a2"]),
        ),
        "a later commit with a revert trailer": (
            intact, [*history, commit("r1", "a.py", reverts=("a1",))], {}, ("reverted", ["r1"]),
        ),
        "a later inverse patch": (intact, [*history, commit("r2", "a.py", patch="-patch-a1")], {}, ("reverted", ["r2"])),
        "a revert by an in-chain or confirmed commit": (
            intact, [*history, commit("r3", "a.py", reverts=("a2",))],
            {"attributable": frozenset({"r3"}), "confirmed_later": frozenset({"r3"})}, ("reverted", ["r3"]),
        ),
        "two trusted records naming different commits": (
            blocker(record("a1", "a2"), record("a1", created_at=later)), history, {}, ("conflicting-records", ["a1", "a2"]),
        ),
        "a later stop record": (
            blocker(record("a1", "a2"), record(outcome="stopped", created_at=later)), history, {},
            ("conflicting-records", ["a1", "a2"]),
        ),
        "a later failure record": (
            blocker(record("a1", "a2"), record(outcome="failed", created_at=later)), history, {},
            ("conflicting-records", ["a1", "a2"]),
        ),
        "a record disagreeing with the user's confirmation": (
            blocker(record("a1", "a2"), manual={"commits": ["a1"], "verified": True, "confirmed": True}), history, {},
            ("conflicting-records", ["a1", "a2"]),
        ),
        "only an untrusted record author": (
            blocker(record("a1", "a2", author={"user_type": "User", "permission": "read"})), history, {}, ("no-evidence", []),
        ),
        "only a bot record": (
            blocker(record("a1", "a2", author={"user_type": "Bot", "permission": "admin"})), history, {}, ("no-evidence", []),
        ),
        "a failed permission lookup": (
            blocker(record("a1", "a2"), record("a1", "a2", author={"user_type": "User", "permission": None})), history, {},
            ("lookup-failed", []),
        ),
        "manual evidence without user confirmation": (
            blocker(manual={"commits": ["a1", "a2"], "verified": True, "confirmed": False}), history, {}, ("no-evidence", []),
        ),
        "a successful record naming no commits": (blocker(record()), history, {}, ("no-evidence", [])),
        "confirmed manual evidence beside a trusted stop record": (
            blocker(record(outcome="stopped"), manual={"commits": ["a1", "a2"], "verified": True, "confirmed": True}),
            history, {}, ("conflicting-records", ["a1", "a2"]),
        ),
        "manual evidence the user confirms": (
            blocker(manual={"commits": ["a1", "a2"], "verified": True, "confirmed": True}), history, {},
            ("satisfied", ["a1", "a2"]),
        ),
        "an unattributed later change to the blocker's paths": (
            intact, [*history, commit("x1", "a.py", "other.py")], {}, ("later-path-change", ["x1"]),
        ),
        "a later change to the blocker's paths by an in-chain ticket": (
            intact, [*history, commit("x1", "a.py")], {"attributable": frozenset({"x1"})}, ("satisfied", ["a1", "a2"]),
        ),
        "a user-confirmed later change to the blocker's paths": (
            intact, [*history, commit("x1", "a.py")], {"confirmed_later": frozenset({"x1"})}, ("satisfied", ["a1", "a2"]),
        ),
        "a later change elsewhere": (intact, [*history, commit("x2", "other.py")], {}, ("satisfied", ["a1", "a2"])),
        "an unclaimed blocker": (blocker(record("a1", "a2"), assignees=()), history, {}, ("unclaimed", [])),
        "a blocker whose own open blocker its record does not name": (
            blocker(record("a1", "a2"), open_blockers=(7,)), history, {}, ("unrecorded-blocker", ["7"]),
        ),
        "a blocker whose record names its own branch-satisfied blocker": (
            blocker(record("a1", "a2", relied=(7,)), open_blockers=(7,)), history, {}, ("satisfied", ["a1", "a2"]),
        ),
    }
    for label, (subject, commits, options, expected) in verdicts.items():
        found = verdict(subject, commits, **options)
        if found != expected:
            fail(f"branch-satisfied validation of {label}: expected {expected!r}, found {found!r}")

    required = gated_tracker_capabilities(implement) or set()
    brief = "\n".join((
        AGENT_BRIEF_HEADING, "**Category:** enhancement", "**Summary:** build on the blocker",
        "**Current behavior:** It waits.", "**Desired behavior:** It starts.",
        "**Acceptance criteria:**", "- [ ] The dependent starts", "**Out of scope:** Other things",
    ))

    def ticket(parent: str | None, body: str = "Context only.", **state) -> dict:
        return {
            "parent": parent, "body": body, "author": admin, "comments": [], "state": "OPEN",
            "ready": False, "assignees": [], "labels": [], "open_blockers": [10], **state,
        }

    def gate(document: str, subject: dict, satisfaction: dict | None = None, **options) -> str:
        return implementation_start_gate(
            tracker=document, required=required, ticket=subject, branch_satisfaction=satisfaction, **options,
        )

    satisfied = {10: "satisfied"}
    starts = {
        "a parent-backed dependent whose only open blocker is branch-satisfied": ticket("approved"),
        "a standalone dependent with a complete trusted Agent Brief": ticket(None, brief),
        "a standalone dependent with a trusted brief comment": ticket(None, comments=[
            {"body": brief, "created_at": "2026-01-02", **writer},
        ]),
        "a dependent with one closed and one branch-satisfied blocker": ticket("approved", blockers=[9, 10]),
    }
    for label, subject in starts.items():
        before = json.dumps(subject, sort_keys=True)
        if gate(tracker, subject, satisfied) != "start" or gate(github_seed, subject, satisfied) != "start":
            fail(f"/implement did not start {label}")
        if json.dumps(subject, sort_keys=True) != before:
            fail(f"the branch-satisfied start gate changed the snapshot of {label}")
        if gate(tracker, subject) == "start":
            fail(f"/implement started {label} without branch satisfaction")
    unchanged = {
        "a standalone dependent without a complete trusted brief": (ticket(None), satisfied),
        "a standalone dependent whose brief is untrusted": (
            {**ticket(None, brief), "author": {"user_type": "User", "permission": "read"}}, satisfied,
        ),
        "a dependent held by a mapped triage label": (ticket("approved", labels=["ready-for-human"]), satisfied),
        "a standalone dependent held by a mapped triage label": (ticket(None, brief, labels=["needs-info"]), satisfied),
        "a dependent assigned to someone else": (ticket("approved", assignees=["other"]), satisfied),
        "a closed dependent": (ticket("approved", state="CLOSED"), satisfied),
        "a dependent under an unapproved parent": (ticket("unapproved", brief), satisfied),
        "a dependent under an unresolvable parent": (ticket("unresolvable", brief), satisfied),
        "a dependent with a branch-satisfied and an unrelated open blocker": (
            ticket("approved", open_blockers=[10, 90]), satisfied,
        ),
        "a standalone dependent with a branch-satisfied and an unrelated open blocker": (
            ticket(None, brief, open_blockers=[10, 90]), satisfied,
        ),
        **{
            f"a dependent whose blocker failed validation ({failure})": (ticket("approved"), {10: failure})
            for failure in ("missing-commits", "reverted", "conflicting-records", "lookup-failed", "no-evidence",
                            "later-path-change", "unclaimed", "unrecorded-blocker")
        },
    }
    for label, (subject, satisfaction) in unchanged.items():
        found = gate(tracker, subject, satisfaction)
        if found == "start" or found != gate(tracker, subject):
            fail(f"/implement start gate for {label}: expected today's stop, found {found!r}")

    # Held states follow the tracker's triage-label mapping, as reconciliation does.
    mapped = {f"team:{role}" for role in HELD_TRIAGE_STATES}
    if gate(tracker, ticket("approved", labels=["team:wontfix"]), satisfied, held_labels=mapped) == "start":
        fail("/implement started a dependent held by a mapped triage label")
    if gate(tracker, ticket("approved", labels=["wontfix"]), satisfied, held_labels=mapped) != "start":
        fail("/implement treated an unmapped label as a held triage state")

    # Without the optional operation, or with an incomplete copy, the gate is unchanged and never a stale-tracker stop.
    for label, document in (*without.items(), ("the local seed", local_seed), *partial.items()):
        for subject in (ticket("approved"), ticket(None, brief)):
            found = gate(document, subject, satisfied)
            if found != gate(document, subject) or found in ("start", "stale-tracker"):
                fail(f"{label} without the optional operation changed the start gate: {found!r}")
    # The user override of a failed ticket-state gate is unchanged, with or without the operation.
    for document in (tracker, without["this repository's tracker"], local_seed):
        if gate(document, ticket("approved", open_blockers=[90]), override=True) != "start":
            fail("the user override of a failed ticket-state gate no longer starts a parent-backed ticket")
    if gate(tracker, ticket(None, brief, open_blockers=[90]), override=True) != "no-authority":
        fail("the user override waived the implementation-ready state standalone authority requires")

    # Branch contents never reach reconciliation: the blocker stays open, so its dependent stays planned.
    issues = [
        {"number": number, "parent": "P", "body": "", "author": admin, "comments": [], "state": state,
         "assignees": assignees, "labels": [], "native_blockers": blockers, "fallback_blockers": []}
        for number, state, assignees, blockers in ((9, "CLOSED", [], []), (10, "OPEN", ["dev"], []), (11, "OPEN", [], [10]))
    ]
    reconciled = reconciliation_plan(
        tracker=tracker, trigger_number=9, issues=issues, parents={"P": {"approved": True, "children": [9, 10, 11]}},
        native_dependents=[],
    )
    if reconciled["writes"] or reconciled["frontiers"] != {"parent:P": []} or reconciled["unresolved_blockers"] != {11: [10]}:
        fail("reconciliation promoted a dependent whose blocker is only implemented on a branch")

    # Chain A -> B -> C on one branch, each started by /implement, then one PR.
    def chain_ticket(number: int, commits: tuple, relied=(), open_blockers=()) -> dict:
        return blocker(record(*commits, relied=relied), open_blockers=open_blockers) | {"number": number}

    a, b, c = 1, 2, 3
    snapshots = {a: chain_ticket(a, ("a1",)), b: chain_ticket(b, ("b1",), (a,), (a,)), c: chain_ticket(c, ("c1",), (b,), (b,))}
    before_b = [commit("base", "README.md"), commit("a1", "a.py")]
    before_c = [*before_b, commit("b1", "b.py", "a.py")]
    final = [*before_c, commit("c1", "c.py")]
    if verdict(snapshots[a], before_b)[0] != "satisfied" or gate(tracker, ticket("approved", open_blockers=[a]), {a: "satisfied"}) != "start":
        fail("chain A -> B -> C: B did not start with A branch-satisfied")
    if verdict(snapshots[b], before_c)[0] != "satisfied" or gate(tracker, ticket(None, brief, open_blockers=[b]), {b: "satisfied"}) != "start":
        fail("chain A -> B -> C: C did not start with B branch-satisfied")
    if verdict(blocker(record("b1"), open_blockers=(a,)), before_c) != ("unrecorded-blocker", [str(a)]):
        fail("chain A -> B -> C: B was valid although its record does not name its branch-satisfied blocker")
    chain_commits = frozenset({"a1", "b1", "c1"})
    if verdict(snapshots[a], final)[0] != "later-path-change":
        fail("a later chain commit to the blocker's paths was accepted without in-chain attribution")

    def pr_ticket(snapshot: dict, blockers=()) -> dict:
        latest = snapshot["records"][-1]
        return {
            "record": {"commits": latest["commits"], "outcome": latest["outcome"], "branch_satisfied": latest["branch_satisfied"]},
            "resolved": False, "blockers": list(blockers), "manual": None,
        }

    def relations(history: list) -> dict:
        return {
            (dependent, relied): verdict(snapshots[relied], history, attributable=chain_commits)[0]
            for dependent, relied in ((b, a), (c, b))
        }

    def pr_plan(tickets: dict, history: list, **options) -> dict:
        delta = [{"sha": entry["sha"], "references": []} for entry in history[1:]]
        return pr_ticket_plan(
            tracker="github", tickets=tickets, commits=delta, base="main", default="main", auto_close=True,
            branch_relations=relations(history), **options,
        )

    chain = {a: pr_ticket(snapshots[a]), b: pr_ticket(snapshots[b], (a,)), c: pr_ticket(snapshots[c], (b,))}
    whole = pr_plan(chain, final)
    if whole["stops"] or whole["close_directives"] != ["Closes #1", "Closes #2", "Closes #3"]:
        fail(f"/write-pr did not validate the branch-satisfied chain A -> B -> C: {whole['stops']}")
    without_a = pr_plan(
        {**chain, a: {"record": None, "resolved": False, "blockers": [], "manual": None}}, final,
        rationales={"a1": "Unclear."}, blocker_overrides={(b, a)},
    )
    if ("branch-satisfied-blocker-outside-set", (b, a)) not in without_a["stops"] or without_a["overrides"]:
        fail("/write-pr accepted or overrode a branch-satisfied blocker outside its ticket set")
    # A is reverted after C's run, whose direct check of B passed above.
    reverted = [*final, commit("r1", "a.py", reverts=("a1",))]
    after_revert = pr_plan(chain, reverted, rationales={"r1": "Reverted A."})
    if ("branch-satisfied-relation-invalid", (b, a, "reverted")) not in after_revert["stops"] or after_revert["close_directives"]:
        fail("/write-pr did not catch A reverted after C was built on the chain")
    rewritten = pr_plan(chain, [final[0], commit("a1'", "a.py"), *final[2:]], rationales={"a1'": "Rebased A."})
    if not any(stop[0].startswith("branch-satisfied-") for stop in rewritten["stops"]) or rewritten["close_directives"]:
        fail("/write-pr accepted a branch-satisfied relation whose blocker commits were rewritten")
