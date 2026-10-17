"""Tracker capability and implementation authority groups.

Pins the tracker contract wording and exercises the capability, Agent Brief, authority
mode, and start-gate models against real documents, fixtures, and scenario tables.
"""

from __future__ import annotations

import re

from ..agent_brief import (
    AGENT_BRIEF_COMPLETENESS_RULE, AGENT_BRIEF_HEADING, AGENT_BRIEF_REQUIRED_FIELDS, AGENT_BRIEF_TRACKER_CONTRACT,
    TRIAGE_COMMENT_DISCLAIMER, is_complete_agent_brief, resolve_agent_brief,
)
from ..common import ROOT, CheckFailure, fail
from ..implementation import implementation_start_gate
from ..reconciliation import HELD_TRIAGE_STATES, standalone_frontier_numbers
from ..tracker_contract import (
    RETIRED_STANDALONE_RECORD, TRACKER_CAPABILITIES, canonical_tracker_capabilities, gated_tracker_capabilities,
    missing_tracker_capabilities, resolve_issue_authority, tracker_defines_retired_record, tracker_is_current,
    tracker_standalone_authority,
)


def validate_tracker_capability_contract() -> None:
    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    setup = read("skills/setup-skills/SKILL.md")
    canonical = canonical_tracker_capabilities(setup)
    if canonical != list(TRACKER_CAPABILITIES):
        fail(
            "skills/setup-skills/SKILL.md: the canonical capability list must name exactly "
            f"{list(TRACKER_CAPABILITIES)}, found {canonical}"
        )
    for required in (
        "check it against every entry in the required implementation-workflow capabilities",
        "re-read the file from disk and validate it against every entry",
        "report the setup or migration as incomplete and name each remaining missing capability",
        "Only after validation passes",
        "already up to date",
    ):
        if required not in setup:
            fail(f"skills/setup-skills/SKILL.md: tracker capability validation is missing {required!r}")

    for relative in (
        "skills/setup-skills/issue-tracker-github.md",
        "skills/setup-skills/issue-tracker-local.md",
        "docs/agents/issue-tracker.md",
    ):
        missing = missing_tracker_capabilities(read(relative))
        if missing:
            fail(f"{relative}: tracker contract is missing required capabilities {missing}")

    for relative in ("skills/to-tickets/SKILL.md", "skills/implement/SKILL.md", "skills/reconcile/SKILL.md"):
        required = gated_tracker_capabilities(read(relative))
        if not required:
            fail(f"{relative}: no tracker capability gate found")
        omitted = sorted(required - set(canonical))
        if omitted:
            fail(f"{relative}: gates on capabilities the canonical list omits: {omitted}")
    gate = "Require `docs/agents/issue-tracker.md` to define the ready state and frontier promotion."
    unlisted_gates = {
        "an unlisted capability in the gate sentence": gate.replace("and frontier", "sprint velocity, and frontier"),
        "an unlisted capability in a following sentence": gate + " Also require dependency provenance. Then go.",
        "an unlisted capability in a second gate sentence": (
            gate + "\n\nLater.\n\nRequire that configuration to define dependency provenance. Then go."
        ),
    }
    for label, probe in unlisted_gates.items():
        try:
            gated_tracker_capabilities(probe)
        except CheckFailure:
            continue
        fail(f"a downstream gate with {label} was not detected")

    # Regression: an older Local Markdown tracker that has some of the contract. The
    # check must name every gap at once, and a pass that adds only the first obvious
    # gap must still be reported incomplete.
    partial = read("tests/fixtures/tracker-contract/local-partial.md")
    expected_gaps = [
        "Planned/non-ready state", "Canonical blocker checks", "Direct dependent discovery",
        "Affected reconciliation scopes", "Idempotent ready-state mutation", "`/reconcile` contract",
    ]
    found_gaps = missing_tracker_capabilities(partial)
    if found_gaps != expected_gaps:
        fail(f"partial Local tracker fixture: expected gaps {expected_gaps}, found {found_gaps}")
    planned = "- **Planned state**: `Status: planned`. Every blocked implementation ticket has this explicit non-ready state.\n"
    first_gap_only = partial.replace("- **Parent/spec**", planned + "- **Parent/spec**")
    if missing_tracker_capabilities(first_gap_only) != expected_gaps[1:]:
        fail("a migration that added only the first gap was not reported incomplete with its remaining gaps")
    if missing_tracker_capabilities("# Issue tracker\n\nNo workflow.\n") != list(TRACKER_CAPABILITIES):
        fail("a tracker without an implementation workflow did not miss every capability")


def validate_implementation_authority_contract() -> None:
    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    tracker = read("docs/agents/issue-tracker.md")
    tracker_seed = read("skills/setup-skills/issue-tracker-github.md")
    guide = read("skills/triage/AGENT-BRIEF.md")
    implement = read("skills/implement/SKILL.md")
    reconcile = read("skills/reconcile/SKILL.md")
    triage = read("skills/triage/SKILL.md")
    to_tickets = read("skills/to-tickets/SKILL.md")
    setup = read("skills/setup-skills/SKILL.md")

    required_contract_text = (
        *((tracker, text) for text in AGENT_BRIEF_TRACKER_CONTRACT),
        *((tracker_seed, text) for text in AGENT_BRIEF_TRACKER_CONTRACT),
        (guide, AGENT_BRIEF_COMPLETENESS_RULE),
        (guide, "in the issue body"),
        (implement, "never fall back to standalone authority"),
        (implement, "newest complete trusted brief comment"),
        (implement, "the issue plus its resolved Agent Brief"),
        (implement, RETIRED_STANDALONE_RECORD),
        (implement, "re-run `/setup-skills`"),
        (implement, "Compose the `implementation-review` skill natively"),
        (implement, "read `implementation-review/SKILL.md` from the active skill root"),
        (reconcile, "same Agent Brief resolver as `/implement`"),
        (reconcile, "never creates or edits Agent Brief authority"),
        (reconcile, "every issue in the repository with no direct or native parent"),
        (reconcile, "standalone frontier in ascending issue-number order"),
        (reconcile, RETIRED_STANDALONE_RECORD),
        (reconcile, "re-run `/setup-skills`"),
        (reconcile, "never promotes a held issue to ready and never changes its triage label"),
        (triage, "does not establish standalone implementation authority"),
        (triage, "`/implement` will reject"),
        (triage, "readiness without a complete trusted Agent Brief does not create authority"),
        (to_tickets, "only after the user has approved"),
        (to_tickets, "effective repository permission `write` (including `maintain`) or `admin`"),
        (to_tickets, "standalone authority was not established"),
        (to_tickets, "keep every one of them out of the frontier"),
        (setup, RETIRED_STANDALONE_RECORD),
        (setup, "as a diff"),
        (setup, "already up to date"),
    )
    for document, required in required_contract_text:
        if required not in document:
            fail(f"implementation authority contract is missing {required!r}")
    for relative, document in (
        ("docs/agents/issue-tracker.md", tracker),
        ("skills/setup-skills/issue-tracker-github.md", tracker_seed),
        ("skills/triage/SKILL.md", triage),
        ("skills/to-tickets/SKILL.md", to_tickets),
    ):
        if tracker_defines_retired_record(document):
            fail(f"{relative}: still defines or writes the retired standalone authority record")

    good_guide, _, bad_guide = guide.partition("### Bad agent brief")
    good_examples = [block for block in re.findall(r"```markdown\n(.*?)```", good_guide, re.S) if AGENT_BRIEF_HEADING in block]
    bad_examples = [block for block in re.findall(r"```markdown\n(.*?)```", bad_guide, re.S) if AGENT_BRIEF_HEADING in block]
    if len(good_examples) < 4 or not bad_examples:
        fail("skills/triage/AGENT-BRIEF.md: expected the template, good examples, and a bad example")
    if not all(is_complete_agent_brief(block) for block in good_examples):
        fail("skills/triage/AGENT-BRIEF.md: the template or a good example is not a complete Agent Brief")
    if any(is_complete_agent_brief(block) for block in bad_examples):
        fail("skills/triage/AGENT-BRIEF.md: the bad example passes as a complete Agent Brief")
    parentless_template = re.search(r"<parentless-issue-template>(.*?)</parentless-issue-template>", to_tickets, re.S)
    if parentless_template is None or not is_complete_agent_brief(parentless_template.group(1)) or "## Blocked by" not in parentless_template.group(1):
        fail("skills/to-tickets/SKILL.md: the parentless template must be a complete Agent Brief plus a Blocked by section")

    brief = "\n".join((
        AGENT_BRIEF_HEADING, "", "**Category:** enhancement", "**Summary:** do the thing", "",
        "**Current behavior:**", "It does not.", "", "**Desired behavior:**", "It does.", "",
        "**Key interfaces:**", "- `Thing`", "", "**Acceptance criteria:**", "- [ ] The thing happens", "",
        "**Out of scope:**", "- Other things",
    ))
    without_key_interfaces = brief.replace("**Key interfaces:**\n- `Thing`\n\n", "")
    surrounded = "# Context\n\nPreamble.\n\n" + brief + "\n\n## Blocked by\n\nNone\n\n---\n_Generated by a tool_"
    triage_brief = TRIAGE_COMMENT_DISCLAIMER + "\n\n" + brief
    retired_record = "\n".join((
        RETIRED_STANDALONE_RECORD, "- Parent/spec: intentionally none", "- Authority: this issue",
        "- Upstream approval: explicit user approval in `/to-tickets`",
    ))
    incomplete_briefs = {
        "missing heading": brief.replace(AGENT_BRIEF_HEADING, "## Brief"),
        "empty acceptance criteria": brief.replace("- [ ] The thing happens", "- [ ]"),
        "a field only after the brief section": brief.replace("**Out of scope:**", "## Notes\n\n**Out of scope:**"),
        **{f"missing {field}": brief.replace(f"**{field}:**", "") for field in AGENT_BRIEF_REQUIRED_FIELDS},
    }
    if not (is_complete_agent_brief(brief) and is_complete_agent_brief(without_key_interfaces) and is_complete_agent_brief(surrounded)):
        fail("a complete Agent Brief, one without Key interfaces, or one with surrounding text was rejected")
    for label, text in incomplete_briefs.items():
        if is_complete_agent_brief(text):
            fail(f"an incomplete Agent Brief ({label}) was accepted")

    admin = {"user_type": "User", "permission": "admin", "author_association": "OWNER"}
    maintainer = {"user_type": "User", "permission": "write", "role_name": "maintain", "author_association": "MEMBER"}
    reader = {"user_type": "User", "permission": "read", "author_association": "CONTRIBUTOR"}
    triager = {"user_type": "User", "permission": "read", "role_name": "triage", "author_association": "COLLABORATOR"}
    bot = {"user_type": "Bot", "permission": "admin", "author_association": "OWNER"}
    lookup_failed = {"user_type": "User", "permission": None, "author_association": "OWNER"}

    def comment(body: str, author: dict, created_at: str = "2026-01-02") -> dict:
        return {"body": body, "created_at": created_at, **author}

    def issue(body: str = "Context only.", author: dict = admin, comments: tuple = ()) -> dict:
        return {"body": body, "author": author, "comments": list(comments)}

    def standalone(subject: dict, ready: bool = True) -> bool:
        return resolve_issue_authority(
            tracker=tracker_seed, parent=None, issue=subject, ready_for_agent=ready,
        ) == "standalone"

    accepted = {
        "trusted issue-body brief": issue(brief),
        "trusted issue-body brief with a blocked-by section and footer": issue(surrounded),
        "trusted brief comment": issue(comments=[comment(brief, maintainer)]),
        "trusted brief comment without the triage disclaimer": issue(comments=[comment(brief, admin)]),
        "trusted brief comment with the triage disclaimer": issue(comments=[comment(triage_brief, admin)]),
        "brief without Key interfaces": issue(comments=[comment(without_key_interfaces, admin)]),
    }
    for label, subject in accepted.items():
        if not standalone(subject):
            fail(f"/implement rejected a ready parentless issue with a {label}")
    rejected = {
        "the ready label alone": issue(),
        "an incomplete brief": issue(comments=[comment(incomplete_briefs["empty acceptance criteria"], admin)]),
        "a bot brief comment": issue(comments=[comment(brief, bot)]),
        "a read-only brief comment": issue(comments=[comment(brief, reader)]),
        "a triage-permission brief comment": issue(comments=[comment(brief, triager)]),
        "a brief comment whose permission lookup failed": issue(comments=[comment(brief, lookup_failed)]),
        "a bot issue body": issue(brief, bot),
        "a read-only issue body": issue(brief, reader),
        "an issue body whose permission lookup failed": issue(brief, lookup_failed),
        "a historical standalone authority comment alone": issue(comments=[comment(retired_record, admin)]),
    }
    for label, subject in rejected.items():
        if standalone(subject):
            fail(f"/implement accepted a parentless issue with {label}")
    if standalone(issue(brief), ready=False):
        fail("/implement accepted a trusted brief without the ready state")
    if resolve_issue_authority(tracker=tracker_seed, parent="approved", issue=issue(), ready_for_agent=True) != "parent":
        fail("approved parent-backed issue was not accepted")
    for parent in ("unapproved", "unresolvable", "missing"):
        if resolve_issue_authority(tracker=tracker_seed, parent=parent, issue=issue(brief), ready_for_agent=True) is not None:
            fail(f"issue with a {parent} parent fell back to standalone authority")

    newer = brief.replace("do the thing", "newer thing")
    body_brief = brief.replace("do the thing", "body thing")
    precedence = {
        "a newer trusted comment over an older one": (
            issue(body_brief, comments=[comment(newer, admin, "2026-01-03"), comment(brief, admin, "2026-01-02")]), newer,
        ),
        "a trusted comment over the issue body": (issue(body_brief, comments=[comment(brief, maintainer)]), brief),
        "the issue body over a newer untrusted comment": (
            issue(body_brief, comments=[comment(newer, reader, "2026-01-09")]), body_brief,
        ),
        "the issue body over a newer incomplete comment": (
            issue(body_brief, comments=[comment(incomplete_briefs["missing Out of scope"], admin, "2026-01-09")]), body_brief,
        ),
        "an older trusted comment over a newer untrusted one": (
            issue(comments=[comment(newer, bot, "2026-01-09"), comment(brief, admin, "2026-01-02")]), brief,
        ),
    }
    for label, (subject, expected) in precedence.items():
        if resolve_agent_brief(subject) != expected:
            fail(f"Agent Brief precedence did not prefer {label}")

    def frontier_issue(number: int, subject: dict, **state) -> dict:
        return {"number": number, "parent": None, "state": "OPEN", "assignees": [], "open_blockers": [], **subject, **state}

    before_close = [
        frontier_issue(40, issue(brief)),
        frontier_issue(41, issue(comments=[comment(brief, maintainer)]), open_blockers=[40]),
        {**frontier_issue(42, issue()), "parent": "#approved-map"},
        frontier_issue(43, issue(comments=[comment(brief, reader)])),
        frontier_issue(44, issue(), labels=["ready-for-agent"]),
        frontier_issue(45, issue(comments=[comment(retired_record, admin)])),
        frontier_issue(46, issue(comments=[comment(brief, admin)])),
    ]
    after_close = [{**before_close[0], "state": "CLOSED"}, {**before_close[1], "open_blockers": []}, *before_close[2:]]
    if standalone_frontier_numbers(before_close) != [40, 46]:
        fail("standalone frontier is not exactly the open, unblocked issues with trusted body or comment briefs")
    if standalone_frontier_numbers(after_close) != [41, 46]:
        fail("closing a standalone blocker did not promote its briefed standalone dependent")

    held = [
        frontier_issue(50 + offset, issue(brief), labels=[state])
        for offset, state in enumerate(sorted(HELD_TRIAGE_STATES))
    ]
    if standalone_frontier_numbers(held) != []:
        fail("standalone reconciliation promoted an issue held in an explicit non-agent triage state")
    held_blocked = frontier_issue(60, issue(brief), labels=["ready-for-human"], open_blockers=[40])
    planned_blocked = frontier_issue(61, issue(brief), labels=[], open_blockers=[40])
    if standalone_frontier_numbers([{**held_blocked, "open_blockers": []}, {**planned_blocked, "open_blockers": []}]) != [61]:
        fail("closing a blocker must promote an unlabelled planned issue but not a triage-held one")

    published = [frontier_issue(70, issue(surrounded)), frontier_issue(71, issue(surrounded), open_blockers=[70])]
    untrusted_publisher = [{**ticket, "author": lookup_failed} for ticket in published]
    if standalone_frontier_numbers(published) != [70]:
        fail("/to-tickets initial frontier did not mark the unblocked trusted parentless ticket ready")
    if standalone_frontier_numbers(untrusted_publisher) != []:
        fail("/to-tickets marked a parentless ticket ready although its publisher's permission was not verified")

    retired_tracker = "## Implementation workflow\n\n```markdown\n" + retired_record + "\n```\n"
    if not tracker_defines_retired_record(retired_tracker) or tracker_defines_retired_record(tracker):
        fail("retired standalone record detection disagrees with the tracker contracts")


def validate_standalone_authority_modes() -> None:
    """A parent-only tracker is current, and parent-backed work never needs an Agent Brief rule."""

    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    local_seed = read("skills/setup-skills/issue-tracker-local.md")
    github_seed = read("skills/setup-skills/issue-tracker-github.md")
    tracker = read("docs/agents/issue-tracker.md")
    incomplete = read("tests/fixtures/tracker-contract/standalone-incomplete.md")
    implement = read("skills/implement/SKILL.md")
    reconcile = read("skills/reconcile/SKILL.md")
    setup = read("skills/setup-skills/SKILL.md")
    to_tickets = read("skills/to-tickets/SKILL.md")
    triage = read("skills/triage/SKILL.md")

    for document, required in (
        (implement, "this tracker requires a parent/spec and the ticket has none"),
        (implement, "a parent-backed ticket never depends on it, even when that configuration is stale"),
        (implement, "claims standalone support without the complete Agent Brief rule"),
        (reconcile, "this tracker requires a parent/spec and make no mutations"),
        (reconcile, "parent-backed reconciliation never depends on it, even when that configuration is stale"),
        (reconcile, "claims standalone support without the complete Agent Brief rule"),
        (setup, "**Parent-only (current)**"),
        (setup, "It needs no Agent Brief rule; never propose one for it."),
        (setup, "**Incomplete (stale)**"),
        (setup, "**Ambiguous (stale)**"),
        (setup, "a retired, incomplete, undeclared, or ambiguous mode is a remaining gap"),
        (setup, "already states a current standalone authority mode, parent-only or standalone-capable"),
        (to_tickets, "never use the parentless template or add an Agent Brief there"),
        (triage, "a parentless issue needs a governing parent/spec"),
        (triage, "On a parent-only tracker, post no agent brief"),
        (triage, "Do not write an agent brief on such a tracker, neither as authority nor as documentation"),
        (triage, "on a parent-only tracker, do not offer one"),
        (triage, "An approved parent/spec establishes implementation authority, not readiness."),
        (triage, "including its blocker and claim state"),
        (triage, "A parentless issue on a parent-only tracker stays non-ready: do not apply `ready-for-agent`"),
    ):
        if required not in document:
            fail(f"standalone authority mode contract is missing {required!r}")
    # Parent approval is authority, never readiness: a blocked parent-backed issue stays planned.
    if re.search(r"ready-for-agent`? on its parent's approval", triage):
        fail("skills/triage/SKILL.md: parent approval must not by itself make an issue ready-for-agent")
    # The retired-record stop belongs only to the parentless branch, so it can never
    # block parent-backed work.
    for relative, document, parentless_branch in (
        ("skills/implement/SKILL.md", implement, "- If it has no parent/spec"),
        ("skills/reconcile/SKILL.md", reconcile, "3. If the ticket has no parent"),
    ):
        branch = document.find(parentless_branch)
        if branch == -1 or document.find(RETIRED_STANDALONE_RECORD) < branch:
            fail(f"{relative}: the retired standalone record must stop only parentless work, inside its parentless branch")

    # The local seed is parent-only: it must never grow an Agent Brief rule, and its
    # ticket template always carries a Parent line and never an Agent Brief.
    local_template = re.search(r"<local-ticket-template>(.*?)</local-ticket-template>", to_tickets, re.S)
    if local_template is None or "**Parent:**" not in local_template.group(1) or AGENT_BRIEF_HEADING in local_template.group(1):
        fail("skills/to-tickets/SKILL.md: the local ticket template must carry a Parent line and no Agent Brief")
    if AGENT_BRIEF_COMPLETENESS_RULE in local_seed:
        fail("skills/setup-skills/issue-tracker-local.md: a parent-only tracker must not define the Agent Brief rule")

    # A local tracker written from the earlier seed states parent-only only through its
    # Conventions line; it is just as current.
    legacy_local = "\n".join(line for line in local_seed.splitlines() if "**Standalone authority**" not in line)
    retired_github = github_seed + "\n```markdown\n" + RETIRED_STANDALONE_RECORD + "\n```\n"
    undeclared = "\n".join(
        line for line in incomplete.splitlines() if "**Standalone authority**" not in line
    )
    ambiguous = local_seed + "\n" + github_seed
    expected_modes = {
        "the local seed": (local_seed, "parent-only"),
        "a local tracker from the earlier seed": (legacy_local, "parent-only"),
        "the partial local fixture": (read("tests/fixtures/tracker-contract/local-partial.md"), "parent-only"),
        "the GitHub seed": (github_seed, "standalone"),
        "this repository's tracker": (tracker, "standalone"),
        "a tracker claiming standalone support without Agent Brief semantics": (incomplete, "incomplete"),
        "a tracker stating no mode": (undeclared, "undeclared"),
        "a tracker stating both modes": (ambiguous, "ambiguous"),
        "a tracker with the retired record": (retired_github, "retired"),
    }
    for label, (document, expected) in expected_modes.items():
        found = tracker_standalone_authority(document)
        if found != expected:
            fail(f"standalone authority mode of {label}: expected {expected!r}, found {found!r}")
    for label in ("the local seed", "a local tracker from the earlier seed", "the GitHub seed", "this repository's tracker"):
        if not tracker_is_current(expected_modes[label][0]):
            fail(f"/setup-skills would report {label} as outdated")
    for label in (
        "a tracker claiming standalone support without Agent Brief semantics", "a tracker stating no mode",
        "a tracker stating both modes", "a tracker with the retired record",
    ):
        if tracker_is_current(expected_modes[label][0]):
            fail(f"/setup-skills would report {label} as up to date")

    required = gated_tracker_capabilities(implement) or set()
    trusted = {"user_type": "User", "permission": "admin"}
    brief = "\n".join((
        AGENT_BRIEF_HEADING, "**Category:** enhancement", "**Summary:** do the thing",
        "**Current behavior:** It does not.", "**Desired behavior:** It does.",
        "**Acceptance criteria:**", "- [ ] The thing happens", "**Out of scope:** Other things",
    ))

    def ticket(parent: str | None, body: str = "Context only.", **state) -> dict:
        return {
            "parent": parent, "body": body, "author": trusted, "comments": [],
            "state": "OPEN", "ready": True, "open_blockers": [], **state,
        }

    def gate(document: str, subject: dict) -> str:
        return implementation_start_gate(tracker=document, required=required, ticket=subject)

    cases = {
        # A. A local parent-backed ticket starts without any Agent Brief rule.
        "A: local parent-backed ticket": (local_seed, ticket("approved"), "start"),
        "A: parent-backed ticket on a local tracker from the earlier seed": (legacy_local, ticket("approved"), "start"),
        "A: local parent-backed ticket with an open blocker": (local_seed, ticket("approved", open_blockers=["01"]), "not-ready"),
        "A: local ticket with an unapproved parent": (local_seed, ticket("unapproved"), "no-authority"),
        # B. A parentless ticket on a parent-only tracker fails because a parent is required.
        "B: local parentless ticket": (local_seed, ticket(None), "requires-parent"),
        "B: local parentless ticket carrying a trusted Agent Brief": (local_seed, ticket(None, brief), "requires-parent"),
        "B: parentless ticket on a local tracker from the earlier seed": (legacy_local, ticket(None, brief), "requires-parent"),
        # C. A standalone-capable tracker still demands the complete trusted Agent Brief.
        "C: GitHub parentless ticket with a trusted brief": (github_seed, ticket(None, brief), "start"),
        "C: GitHub parentless ticket without a brief": (github_seed, ticket(None), "no-authority"),
        "C: GitHub parentless ticket with an untrusted brief": (
            github_seed, {**ticket(None, brief), "author": {"user_type": "Bot", "permission": "admin"}}, "no-authority",
        ),
        "C: GitHub parentless ticket with a trusted brief but no ready state": (
            github_seed, ticket(None, brief, ready=False), "no-authority",
        ),
        "C: GitHub parent-backed ticket": (github_seed, ticket("approved"), "start"),
        # D. Claimed standalone support without the Agent Brief semantics is stale.
        "D: parentless ticket on an incomplete standalone tracker": (incomplete, ticket(None, brief), "stale-tracker"),
        "D: parentless ticket on a tracker stating no mode": (undeclared, ticket(None, brief), "stale-tracker"),
        "D: parentless ticket on a tracker stating both modes": (ambiguous, ticket(None, brief), "stale-tracker"),
        "D: parentless ticket on a retired tracker": (retired_github, ticket(None, brief), "stale-tracker"),
        # A stale standalone configuration never blocks parent-backed work.
        "D: parent-backed ticket on an incomplete standalone tracker": (incomplete, ticket("approved"), "start"),
        "D: parent-backed ticket on a retired tracker": (retired_github, ticket("approved"), "start"),
        "D: parent-backed ticket on a tracker stating no mode": (undeclared, ticket("approved"), "start"),
        "D: parent-backed ticket on a tracker stating both modes": (ambiguous, ticket("approved"), "start"),
        "D: unapproved parent on a retired tracker": (retired_github, ticket("unapproved"), "no-authority"),
    }
    for label, (document, subject, expected) in cases.items():
        found = gate(document, subject)
        if found != expected:
            fail(f"/implement start gate for {label}: expected {expected!r}, found {found!r}")
