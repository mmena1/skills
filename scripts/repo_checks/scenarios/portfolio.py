"""The portfolio group: the `/portfolio` boundary of read-only, registry-only, and GitHub-tracker-only."""

from __future__ import annotations

import re

from ..common import SKILLS, fail


PORTFOLIO = SKILLS / "experimental" / "portfolio"
PINNED_SENTENCES = (
    "A GitHub Project is only a **repository registry** here",
    "`/portfolio` supports only repositories whose configured issue tracker is GitHub.",
    "Enumerate the Project's **linked repositories** with a GraphQL query on the ProjectV2 `repositories` connection, "
    "paginated until `pageInfo.hasNextPage` is false and checked against its `totalCount`",
    "Do not fetch Project items, drafts, statuses, fields, issue or PR membership, or history",
    "A Project whose linked repositories are completely read and empty supplies no repository registry",
    "state that this is a registry configuration gap",
    "not an empty portfolio, and do not fall back to repositories referenced by its items",
    "This is an intentional scope override for that request: it does not widen the Project's membership, "
    "and the repository passes the same eligibility gate below.",
    "Positively verify that the contract selects GitHub Issues as the issue tracker. "
    "Do not infer eligibility because the GitHub Issues feature is enabled or issues exist.",
    "is **unsupported** when its contract selects another tracker",
    "is missing, is ambiguous or contradictory, or cannot be read so that the selection is unverifiable",
    "refuse that repository's portfolio analysis with a clear message that `/portfolio` requires a GitHub tracker",
    "skip each unsupported repository, list which were skipped and why, and continue analyzing the eligible ones",
    "Keep unsupported tracker selection separate from coverage limitations.",
    "Include work that was never added to any Project.",
    "Never add, remove, or edit GitHub Project items or fields",
)
# Project reads that would turn the Project back into a source of work state, and any Project write surface.
FORBIDDEN = (
    (r"gh\s+project\s+(?:item-list|field-list|item-add|item-edit|item-create|item-archive|item-delete|edit|link|unlink)",
     "must not read or change Project items, fields, or settings"),
    (r"addProjectV2ItemById|updateProjectV2|deleteProjectV2|archiveProjectV2|linkProjectV2|unlinkProjectV2",
     "must not send Project mutations"),
)


def validate_portfolio_contract() -> None:
    """Pin the `/portfolio` boundary. The removed synchronization skill is guarded by the references group."""
    skill = (PORTFOLIO / "SKILL.md").read_text(encoding="utf-8")
    for required in PINNED_SENTENCES:
        if required not in skill:
            fail(f"portfolio: SKILL.md must state {required!r}")
    for pattern, reason in FORBIDDEN:
        match = re.search(pattern, skill)
        if match:
            fail(f"portfolio: SKILL.md {reason}, found {match.group(0)!r}")
