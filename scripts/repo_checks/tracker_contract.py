"""Tracker contract parsing: capabilities, gates, authority modes, and branch satisfaction.

Models how `/setup-skills` judges a tracker contract (its required capabilities, its
standalone authority mode, and the optional branch-satisfied blockers operation), how
downstream skills gate on those capabilities, and how `/implement` resolves authority.
"""

from __future__ import annotations

import re

from .agent_brief import AGENT_BRIEF_TRACKER_CONTRACT, resolve_agent_brief
from .common import fail


RETIRED_STANDALONE_RECORD = "## Standalone implementation authority"
# A tracker's standalone authority mode. Parent-only trackers state that standalone
# authority is unsupported, or that every implementation ticket has a parent/spec.
STANDALONE_UNSUPPORTED = re.compile(r"\*\*Standalone authority\*\*:\s*unsupported\b", re.IGNORECASE)
STANDALONE_CLAIMED = re.compile(r"\*\*Standalone authority\*\*:(?!\s*unsupported\b)", re.IGNORECASE)
EVERY_TICKET_HAS_PARENT = re.compile(
    r"every implementation (?:issue|ticket) (?:has|requires) a\b[^.\n]*\bparent", re.IGNORECASE,
)
CURRENT_STANDALONE_MODES = {"parent-only", "standalone"}
# The canonical tracker capabilities `/setup-skills` names, each with the evidence a
# tracker's `## Implementation workflow` section must contain (every pattern matches).
TRACKER_CAPABILITY_HEADING = "## Required implementation-workflow capabilities"
TRACKER_CAPABILITIES = {
    "Implementation-ready state": (r"\*\*Implementation-ready state\*\*",),
    "Planned/non-ready state": (r"planned (?:or non-ready )?state",),
    "Direct parent or spec lookup": (r"follow\b[^.\n]*\bparent",),
    "Canonical blocker checks": (r"blocked[ _]by", r"canonical gate"),
    "Direct dependent discovery": (
        r"\*\*Direct dependent discovery\*\*", r"direct open downstream",
        r"native dependency data (?:is authoritative|takes precedence)",
    ),
    "Affected reconciliation scopes": (
        r"\*\*Affected reconciliation scopes\*\*", r"dependent's own", r"deduplicate",
    ),
    "Claim and assignment semantics": (r"\*\*Claim\*\*",),
    "Resolution and resolved-state verification": (
        r"\*\*Resolve\*\*", r"verif(?:y|ies) the trigger is resolved|if the trigger is open",
    ),
    "Deterministic child/sibling enumeration and ordering": (
        r"(?:enumerate|rescans?|selects?) every[^.\n]*\b(?:child|sibling)", r"\border\b",
    ),
    "Idempotent ready-state mutation": (
        r"only (?:the )?(?:statuses|label changes)(?: that differ| needed)", r"no-op",
    ),
    "Frontier promotion": (r"\*\*Frontier promotion\*\*",),
    "`/reconcile` contract": (
        r"\*\*`/reconcile` contract\*\*", r"direct open dependents", r"affected reconciliation scopes",
        r"held", r"at most once per (?:issue|ticket)",
    ),
}
# Every phrase a downstream gate uses to require a tracker capability, mapped to the
# canonical capabilities it names. A gate phrase outside this map is a capability the
# canonical list may omit, so the check fails until it is mapped.
TRACKER_GATE_PHRASES = {
    "implementation-ready and planned states": ("Implementation-ready state", "Planned/non-ready state"),
    "implementation-ready state": ("Implementation-ready state",),
    "ready state": ("Implementation-ready state",),
    "direct parent or spec lookup": ("Direct parent or spec lookup",),
    "direct parent lookup": ("Direct parent or spec lookup",),
    "canonical blocker checks": ("Canonical blocker checks",),
    "canonical blocker lookup": ("Canonical blocker checks",),
    "blocker checks": ("Canonical blocker checks",),
    "direct dependent discovery": ("Direct dependent discovery",),
    "affected reconciliation scopes": ("Affected reconciliation scopes",),
    "claim/assignment state": ("Claim and assignment semantics",),
    "claim": ("Claim and assignment semantics",),
    "resolution state": ("Resolution and resolved-state verification",),
    "resolve": ("Resolution and resolved-state verification",),
    "child enumeration": ("Deterministic child/sibling enumeration and ordering",),
    "ready-state mutation": ("Idempotent ready-state mutation",),
    "frontier promotion": ("Frontier promotion",),
}
TRACKER_GATE = re.compile(
    r"[Rr]equire (?:`docs/agents/issue-tracker\.md`|that configuration) to define "
    r"(?:all \w+ implementation operations: )?(.+?)\.(?:\s|$)"
)
# The optional GitHub tracker operation that lets one /implement run treat an open
# blocker implemented and intact on the current branch as satisfied. It is never a
# required capability, so a tracker without it stays current and keeps the default
# gate: every blocker must be closed.
BRANCH_SATISFIED_OPERATION = "- **Branch-satisfied blockers (optional)**:"
BRANCH_SATISFIED_CONTRACT = (
    "a fact local to that run",
    "it is claimed",
    "trusted implementation record",
    "verified evidence the user explicitly confirms in this run",
    "every one of those commits is an ancestor of the current `HEAD`",
    "Ancestry is necessary evidence, not sufficient.",
    "`This reverts commit <sha>` trailer or by an equivalent inverse patch",
    "a stop or failure record after its latest successful record",
    "when a record names no commits",
    "neither recorded commits of an issue in the same chain on this branch nor confirmed by the user",
    "an open blocker its own record does not name as branch-satisfied",
    "any lookup or permission check fails",
    "Report the failed condition and the commits involved.",
    "substitutes only for the blockers it validates",
    "as `/reconcile` would classify the issue if those blockers were closed",
    "never more broadly",
    "equally to parent-backed and standalone dependents",
    "never closes, resolves, relabels, or otherwise mutates the blocker",
    "never adds the implementation-ready label to the dependent or to any other issue",
    "never invokes or substitutes for `/reconcile`",
    "`/reconcile` never consults branch contents",
    "The dependent's claim is the normal claim.",
    "must not be resolved before those blockers",
    "`/write-pr` re-validates every recorded branch-satisfied relation against the final head",
    "or with an incomplete copy of it missing any condition above, keeps the default blocker gate",
)
# The minimum full operation, judged in a tracker's own vocabulary. A tracker that names
# the operation but misses any element has an incomplete copy: /implement ignores it and
# keeps the default gate, and /setup-skills reports it as a remaining gap.
BRANCH_SATISFIED_ELEMENTS = {
    "claimed blocker": r"\bclaimed\b",
    "trusted implementation record": r"trusted implementation record",
    "explicit user confirmation": r"user explicitly confirms",
    "ancestry": r"ancestor of the current `?HEAD`?",
    "revert detection": r"\brevert",
    "conflicting records": r"records conflict",
    "missing commits": r"not present",
    "later path changes": r"implemented paths",
    "own blockers named": r"own record does not name",
    "failed lookups": r"lookup or permission check fails",
    "substitution only": r"substitutes only for the blockers it validates",
    "reconcile readiness": r"as `/reconcile` would classify",
    "no readiness promotion": r"never adds the implementation-ready label",
    "reconcile ignores branches": r"`/reconcile` never consults branch contents",
    "closeout record": r"closeout lists each branch-satisfied blocker",
    "/write-pr re-validation": r"`/write-pr` re-validates",
}
# The narrow standalone-authority exceptions the operation needs, stated where the
# tracker's authority rules live so they cannot contradict /implement.
STANDALONE_BRANCH_EXCEPTION = (
    "or, for one `/implement` run under a complete branch-satisfied blockers operation below, "
    "in the branch-local readiness that operation defines"
)
FAIL_CLOSED_BRANCH_EXCEPTION = (
    "unless a complete branch-satisfied blockers operation below grants it branch-local readiness for one "
    "`/implement` run. That readiness exists only while every open blocker is branch-satisfied, so a "
    "ready-less issue without such blockers never starts."
)


def tracker_defines_retired_record(tracker: str) -> bool:
    """A tracker contract that still defines the old record must be migrated by /setup-skills."""
    return RETIRED_STANDALONE_RECORD.lower() in tracker.lower()


def tracker_standalone_authority(tracker: str) -> str:
    """Classify a tracker's standalone authority mode as `/setup-skills` does.

    "parent-only" and "standalone" are current. "retired", "incomplete" (claims
    standalone support without the complete Agent Brief rule), "undeclared", and
    "ambiguous" (states both modes) are stale and fail closed for parentless work.
    """
    if tracker_defines_retired_record(tracker):
        return "retired"
    claims_standalone = bool(STANDALONE_CLAIMED.search(tracker)) or any(
        text in tracker for text in AGENT_BRIEF_TRACKER_CONTRACT
    )
    parent_only = bool(STANDALONE_UNSUPPORTED.search(tracker) or EVERY_TICKET_HAS_PARENT.search(tracker))
    if parent_only:
        return "ambiguous" if claims_standalone else "parent-only"
    if not claims_standalone:
        return "undeclared"
    return "standalone" if all(text in tracker for text in AGENT_BRIEF_TRACKER_CONTRACT) else "incomplete"


def tracker_is_current(tracker: str) -> bool:
    """Model the `/setup-skills` up-to-date verdict: every capability, a current mode, and no
    incomplete optional branch-satisfied operation."""
    return (
        not missing_tracker_capabilities(tracker)
        and tracker_standalone_authority(tracker) in CURRENT_STANDALONE_MODES
        and branch_satisfied_operation_state(tracker) != "incomplete"
    )


def resolve_issue_authority(*, tracker: str, parent: str | None, issue: dict, ready_for_agent: bool) -> str | None:
    """Model /implement authority; readiness alone never establishes authority.

    Returns "parent" or "standalone" when authority is established, "requires-parent"
    when a parent-only tracker meets a parentless ticket, "stale-tracker" when
    `/setup-skills` must migrate the tracker, and None when the ticket has no authority.
    A parent-backed ticket never depends on the tracker's standalone authority mode,
    even a stale one: the retired record only stops parentless work.
    """
    if parent is not None:
        return "parent" if parent == "approved" else None
    mode = tracker_standalone_authority(tracker)
    if mode == "parent-only":
        return "requires-parent"
    if mode != "standalone":
        return "stale-tracker"
    if ready_for_agent and resolve_agent_brief(issue) is not None:
        return "standalone"
    return None


def branch_satisfied_operation(tracker: str) -> str | None:
    """The optional operation's bullet and its sub-bullets in the implementation workflow, if defined."""
    section = re.search(r"(?ms)^## Implementation workflow\s*$(.*?)(?=^#{1,2}\s|\Z)", tracker)
    operation = re.search(
        rf"(?m)^{re.escape(BRANCH_SATISFIED_OPERATION)}.*\n(?:  - .*\n?)*", section.group(1) if section else "",
    )
    return operation.group() if operation else None


def missing_branch_satisfied_elements(tracker: str) -> list[str]:
    """The minimum-operation elements a present branch-satisfied operation omits."""
    operation = branch_satisfied_operation(tracker) or ""
    return [
        name for name, pattern in BRANCH_SATISFIED_ELEMENTS.items()
        if not re.search(pattern, operation, re.IGNORECASE)
    ]


def branch_satisfied_operation_state(tracker: str) -> str:
    """"absent" and "complete" are current; "incomplete" grants nothing and is a setup gap."""
    if branch_satisfied_operation(tracker) is None:
        return "absent"
    return "incomplete" if missing_branch_satisfied_elements(tracker) else "complete"


def tracker_defines_branch_satisfied_blockers(tracker: str) -> bool:
    """Only a complete operation enables branch satisfaction; an incomplete one is ignored."""
    return branch_satisfied_operation_state(tracker) == "complete"


def canonical_tracker_capabilities(setup: str) -> list[str]:
    """The capability names listed under the `/setup-skills` canonical heading."""
    lines = setup.splitlines()
    if TRACKER_CAPABILITY_HEADING not in lines:
        return []
    names = []
    for line in lines[lines.index(TRACKER_CAPABILITY_HEADING) + 1:]:
        if re.match(r"#{1,2}\s", line):
            break
        match = re.match(r"- \*\*(.+?)\*\*:", line)
        if match:
            names.append(match.group(1))
    return names


def missing_tracker_capabilities(tracker: str) -> list[str]:
    """Model the `/setup-skills` capability check over one tracker contract.

    Only the `## Implementation workflow` section counts, so similar wording in
    other sections, such as wayfinding operations, never satisfies a capability.
    """
    section = re.search(r"(?ms)^## Implementation workflow\s*$(.*?)(?=^#{1,2}\s|\Z)", tracker)
    text = section.group(1) if section else ""
    reconciliation = re.search(r"(?ms)^- \*\*`/reconcile` contract\*\*:.*?(?=^- \*\*|\Z)", text)
    return [
        name for name, patterns in TRACKER_CAPABILITIES.items()
        if not all(re.search(
            pattern, (reconciliation.group() if reconciliation else "") if name == "`/reconcile` contract" else text,
            re.IGNORECASE,
        ) for pattern in patterns)
    ]


def gate_phrase_capabilities(listed: str) -> set[str]:
    """Map one gate sentence's listed requirements to canonical capabilities.

    Fails when the list names anything that no known phrase maps.
    """
    remaining = listed
    required: set[str] = set()
    for phrase in sorted(TRACKER_GATE_PHRASES, key=len, reverse=True):
        pattern = rf"(?<![\w/-]){re.escape(phrase)}(?![\w/-])"
        if re.search(pattern, remaining):
            required.update(TRACKER_GATE_PHRASES[phrase])
            remaining = re.sub(pattern, " ", remaining)
    leftover = re.sub(r"\b(?:and|the)\b|[,;:]", " ", remaining).strip()
    if leftover:
        fail(f"tracker gate requires {leftover!r}, which the canonical capability list does not name")
    return required


def gated_tracker_capabilities(skill: str) -> set[str] | None:
    """The canonical capabilities one downstream skill's tracker gate requires.

    The gate is the paragraph holding the first `Require ... to define ...`
    sentence. Every sentence in that paragraph that states a requirement must be
    such a gate sentence, so a requirement added in any form, such as a trailing
    "Also require ..." sentence, is either enumerated or fails the check. Gate
    sentences elsewhere in the skill are enumerated too. Returns None when the
    skill has no gate.
    """
    first = TRACKER_GATE.search(skill)
    if first is None:
        return None
    paragraph_start = skill.rfind("\n\n", 0, first.start()) + 1
    paragraph_end = skill.find("\n\n", first.start())
    paragraph = skill[paragraph_start:paragraph_end if paragraph_end != -1 else len(skill)]
    for sentence in re.split(r"(?<=\.)\s+", paragraph.strip()):
        if re.search(r"\brequir", sentence, re.IGNORECASE) and not TRACKER_GATE.search(sentence):
            fail(f"tracker gate paragraph states a requirement outside a gate sentence: {sentence!r}")
    required: set[str] = set()
    for match in TRACKER_GATE.finditer(skill):
        required |= gate_phrase_capabilities(match.group(1))
    return required
