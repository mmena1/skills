"""Deep-review contracts: pinned roles, the lens catalog, and the document rule catalogs.

Each `*_problems` function checks a set of deep-review documents and returns every
problem it finds, so a caller can both validate the real documents and prove that a
mutated copy is rejected.
"""

from __future__ import annotations

import re
from pathlib import Path

import generate_agents


# Current pinned models and limits for the deep-review adapters.
# Claude Code does not confine an agent's Bash to
# the patterns in its tool list, so its read-only roles keep plain Bash.
DEEP_REVIEW_READ_ONLY_TOOLS = ["read", "grep", "glob", "exec"]
DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "Bash"]
DEEP_REVIEW_ROLES = {
    "scout-bugs": {
        "codex": {"model": "gpt-6.1-sol", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-1-sol-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-opus-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "scout-conventions": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-luna-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-haiku-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "scout-history": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-luna-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-sonnet-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "scout-docs": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-luna-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-haiku-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "structural": {
        "codex": {"model": "gpt-6.1-sol", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-1-sol-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-opus-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "validator-static": {
        "codex": {"model": "gpt-6.1-sol", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-1-sol-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-opus-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "validator-probe": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high"},
        "devin": {"model": "gpt-6-luna-high", "allowed-tools": [*DEEP_REVIEW_READ_ONLY_TOOLS, "write", "edit"]},
        "claude": {"model": "claude-sonnet-5-5", "tools": [*DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "Edit", "Write"], "effort": "high"},
    },
}
HARNESS_SPECIFIC_TEXT = re.compile(
    r"Devin|Codex|Claude|run_subagent|spawn_agent|gpt-[0-9]|allowed-tools|sandbox_mode|model_reasoning_effort|\.config/devin|\.codex",
    re.IGNORECASE,
)


def deep_review_shared_sources(skill: Path) -> list[Path]:
    """The harness-neutral protocol, glossary, references, and reviewer contracts."""
    return sorted([
        skill / "protocol.md",
        skill / "GLOSSARY.md",
        *(path for path in (skill / "references").rglob("*") if path.is_file()),
        *(path for path in (skill / "reviewers").rglob("*") if path.is_file()),
    ])


def deep_review_lens_role(lens: str) -> str:
    """The role whose native agent runs one lens: the structural scout, or `scout-<lens>`."""
    return "structural" if lens == "structural" else f"scout-{lens}"


def deep_review_catalog(protocol: str) -> list[str]:
    """The lens slugs in the protocol's reviewer catalog, in catalog order."""
    section = protocol.split("## Select reviewers and preflight the runtime", 1)[-1].split("\n## ", 1)[0]
    return re.findall(r"(?m)^- `([a-z-]+)`: ", section)


def reviewer_text(path: Path) -> str:
    """A reviewer body as the generator embeds it."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip("\n")


def deep_review_role_problems(
    catalog: list[str], roles: dict[str, generate_agents.Role], contract: str, lenses: dict[str, str],
) -> list[str]:
    """Every pinned role exists unchanged, and every catalog lens runs in exactly its own scout role."""
    problems = []
    if set(roles) != set(DEEP_REVIEW_ROLES):
        problems.append(f"deep-review roles must be exactly {', '.join(sorted(DEEP_REVIEW_ROLES))}")
    for name, expected in DEEP_REVIEW_ROLES.items():
        if name in roles and roles[name].harnesses != expected:
            problems.append(f"deep-review role {name!r} drifted from its pinned harness models and limits")
    if not catalog or sorted(catalog) != sorted(lenses):
        problems.append("deep-review reviewer catalog in protocol.md and reviewers/lenses/ must name the same lenses")
    scouts = {name for name in roles if name.startswith("scout-") or name == "structural"}
    if scouts != {deep_review_lens_role(lens) for lens in catalog}:
        problems.append("deep-review scout roles must be exactly one per lens in the protocol's reviewer catalog")
    for lens in catalog:
        text = lenses.get(lens)
        if text is None:
            continue
        name = deep_review_lens_role(lens)
        embedding = sorted(role for role, entry in roles.items() if text in entry.body)
        if len(embedding) != 1:
            found = ", ".join(embedding) or "no role"
            problems.append(f"deep-review lens {lens!r} must run in exactly one role, {name}, but is embedded by {found}")
        role = roles.get(name)
        if role is None:
            problems.append(f"deep-review lens {lens!r} has no {name} role")
            continue
        if contract not in role.body:
            problems.append(f"deep-review role {name!r} lacks the common scout contract")
        if text not in role.body:
            problems.append(f"deep-review role {name!r} lacks its {lens} lens")
        others = [other for other in catalog if other != lens and lenses.get(other, "\0") in role.body]
        if others:
            problems.append(f"deep-review role {name!r} embeds another lens: {', '.join(others)}")
        if role.body != f"{contract}\n\n{text}\n":
            problems.append(f"deep-review role {name!r} must be the common scout contract followed by exactly its {lens} lens")
    return problems


DEEP_REVIEW_ACCESS_RULES = {
    "SKILL.md": (
        "Codex native agents inherit the parent's effective sandbox and approval policy. "
        "This cannot be overridden per role and applies to the writable probe too.",
        "On Codex, reports and runtime acceptance receipts describe the boundary as instruction-enforced plus the inherited session policy. "
        "An inherited sandbox that differs from a role's read-only or writable behavior contract is not a review failure.",
    ),
    "protocol.md": (
        "Scouts and static validators create no files, probes, fixtures, or temporary tests; "
        "run no builds, tests, linters, typecheckers, package-manager commands, scripts, or artifact-producing commands.",
        "Static validators never execute artifact-producing commands.",
    ),
    "reviewers/SCOUT.md": (
        "Create no files, probes, fixtures, or temporary tests; run no builds, tests, linters, typecheckers, "
        "package-manager commands, scripts, or artifact-producing commands.",
    ),
    "reviewers/validator.md": (
        "In the static phase, use repository reads/searches and read-only Git inspection only. "
        "Run no builds, tests, linters, typecheckers, scripts, probes, package-manager commands, or artifact-producing commands.",
        "Create no files, fixtures, or temporary tests in the static phase.",
    ),
}
DEEP_REVIEW_CODEX_ACCESS_CELLS = {
    "Read-only scouts and static validators": (
        "Instruction-enforced. Their no-write and no-probe contract relies on the reviewer instructions "
        "and the coordinator's inherited sandbox and approval policy."
    ),
    "Writable probe": (
        "Runs under the inherited coordinator policy with no probe-specific permission. "
        "It can write only as far as that policy allows."
    ),
}


def deep_review_access_problems(documents: dict[str, str]) -> list[str]:
    """Preserve strict role behavior while describing the actual Codex enforcement mechanism."""
    problems = []
    for relative, rules in DEEP_REVIEW_ACCESS_RULES.items():
        for rule in rules:
            if rule not in documents[relative]:
                problems.append(f"deep-review/{relative}: missing access contract {rule!r}")
    for mechanism, expected in DEEP_REVIEW_CODEX_ACCESS_CELLS.items():
        rows = [line.split("|")[2].strip() for line in documents["SKILL.md"].splitlines()
                if line.startswith(f"| {mechanism} |")]
        if rows != [expected]:
            problems.append(f"deep-review/SKILL.md: incorrect Codex {mechanism.lower()} enforcement mechanism")
    return problems


DEEP_REVIEW_PUBLICATION_RULES = {
    "references/pr-review-comments.md": (
        "Resolve the audience before drafting approval candidates",
        "Use the user's explicit selection",
        "without an extra confirmation step",
        "Never infer the audience from the PR author's identity",
        "Read the selected guide before drafting",
        "Audience changes wording only: preserve outcomes (including Findings and Unresolved), evidence, severity, "
        "action classification, overlap dispositions, publication eligibility, approval requirements, and payload validation.",
        "these publication rules take precedence where they differ",
        "A later audience change requires redrafting and the same validation and per-comment approval",
        "Draft inline comments only for Findings and user-selected Unresolved items",
        "An Unresolved item is posted only after explicit per-item approval and must be a question",
        "Carry the required outcome and the material constraints from the Finding's recommendation",
        "`fix-now`: ask",
        "Require a decision-complete question",
        "`follow-up`: make the future work's required outcome and scope clear",
        "Get per-comment approval with scope and anchor",
        "Validate each payload mechanically against the current head",
        "path, side, changed-line/range eligibility, and complete range fields",
        "Also validate semantic representativeness",
        "re-fetch complete PR discussion and re-check overlap",
        "Remove newly overlapping open concerns",
        "route any changed comment body or anchor through validation and per-comment approval again",
        "Stop if closed, merged, or changed",
        "comment-audience-scenarios.md",
        "Submit it at most once per approved payload",
        "Record the submission outcome independently of read-back verification",
        "Never post the review or any of its comments a second time because verification failed or was incomplete",
        "reconcile with read-only calls only",
        "every review by the authenticated account at the pinned head SHA within the submission window, whether or not its comments match",
        "Accept the review only if there is exactly one candidate and it verifies",
        "stop for explicit human action",
        "the PR-wide endpoint",
        "Pagination must complete",
        "Select only comments whose `pull_request_review_id` equals the returned review ID",
        "`body`, `path`, `side`, `line`, and, for a range, `start_line` and `start_side`",
        "a matching count is never sufficient",
        "`commit_id` set to the pinned head SHA",
        "Never omit `commit_id`",
        "Compare bodies as raw strings",
        "The only allowed transformation is line-ending normalization",
        "is a mismatch recorded as stale, naming the pinned and received SHAs",
        "A missing field is never a mismatch",
        "no pairing is consistent even if every unknown pair were equal",
        "A known `submitted` outcome stays reported as published whatever the verification outcome",
        "publication-verification-scenarios.md",
    ),
    "references/publication-verification-scenarios.md": (
        "Omitted line and side",
        "Valid range comment",
        "Pagination",
        "Other reviews' comments",
        "Page failure",
        "Success without review ID",
        "Timeout",
        "Whitespace drift",
        "Head moved during submission, bound",
        "Review at a different commit",
        "Two candidates",
        "Lone candidate that differs",
        "zero additional review or comment POSTs",
    ),
    "references/pr-review-overlap.md": (
        "Keep the original outcome and action",
        "Suppress any new comment for the item",
        "an Unresolved item keeps its uncertainty",
        "the open overlap controls suppression",
        "newly eligible items and any changed body or anchor return through exact payload validation and per-comment approval",
    ),
    "protocol.md": (
        "Preserve independent outcomes, severity, evidence, and action classification",
        "Take that remedy classification from the validator's Recommendation",
        "Every Unresolved outcome is separate and always `discuss`",
        "include the output template's optional audience note with the findings/publication invitation",
        "Present it as information, not an extra confirmation gate",
    ),
    "references/output-template.md": (
        "**Comment audience:** `human` (default) or `agent`",
        "include `audience: agent` when requesting publication",
        "Omitting audience uses human wording without an extra confirmation step",
    ),
    "references/review-tone-agent.md": (
        "`pr-review-comments.md`", "`pr-review-overlap.md`", "take precedence",
        "State the required outcome and every material constraint from the recommendation",
        "verification expectations when the existing evidence or recommendation establishes them",
        "**`fix-now`**: directly request the required outcome",
        "**`discuss`**: ask a decision-complete question",
        "judgment calls as questions rather than issuing implementation directives",
        "informative, non-blocking tone",
        "uncertainty never becomes an implementation directive",
    ),
}


def deep_review_audience_problems(documents: dict[str, str]) -> list[str]:
    """Check the publication instruction interface, not generated comment wording."""
    publication = documents["references/pr-review-comments.md"]
    rows = re.findall(
        r"(?m)^\| (unspecified|`human`|`agent`) \| `(human|agent)` \| `([^`]+)` \|$",
        publication,
    )
    expected = [
        ("unspecified", "human", "review-tone.md"),
        ("`human`", "human", "review-tone.md"),
        ("`agent`", "agent", "review-tone-agent.md"),
    ]
    problems = []
    if rows != expected:
        problems.append("deep-review publication must route omitted, human, and agent selections to their tone guides")
    selection_position = publication.find("Resolve the audience before drafting approval candidates")
    draft_position = publication.find("Draft inline comments only for Findings")
    if selection_position < 0 or draft_position < 0 or selection_position >= draft_position:
        problems.append("deep-review must resolve audience before drafting comments")
    for guide in {guide for _, _, guide in rows}:
        if f"references/{guide}" not in documents:
            problems.append(f"deep-review publication references a missing tone guide: references/{guide}")
    for relative, rules in DEEP_REVIEW_PUBLICATION_RULES.items():
        for rule in rules:
            if rule not in documents.get(relative, ""):
                problems.append(f"deep-review/{relative}: missing publication contract {rule!r}")
    # Tone guides refer to safeguards; they do not own an alternative policy.
    agent_tone = documents.get("references/review-tone-agent.md", "")
    for operational_rule in ("headRefOid", "gh api", "per-comment approval", "payload validation",
                             "Already reported", "20 changed lines"):
        if operational_rule in agent_tone:
            problems.append(f"agent tone guide duplicates operational policy {operational_rule!r}")
    return problems


def scenario_matrix_names(text: str) -> list[str] | None:
    """Scenario names of the first runtime matrix in text, or None when that table is malformed."""
    lines = text.splitlines()
    header = "| Scenario | Devin expected result | Claude Code expected result | Codex expected result |"
    if header not in lines:
        return []
    names = []
    for line in lines[lines.index(header) + 1:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != 4:
            return None
        names.append(cells[0])
    return names


def deep_review_scenario_problems(documents: dict[str, str]) -> list[str]:
    """Keep the full-review protocol, receipt template, and runtime matrix scenario names aligned."""
    matrix_scenarios = scenario_matrix_names(documents["runtime-acceptance.md"])
    if matrix_scenarios is None:
        return ["skills/deep-review/runtime-acceptance.md: malformed runtime acceptance scenario table"]

    protocol_scenarios = [
        line[2:].split(": whether ", 1)[0]
        for line in markdown_section(documents["protocol.md"], "## Runtime acceptance receipt").splitlines()
        if line.startswith("- ") and ": whether " in line
    ]
    receipt_scenarios = []
    for line in documents["references/output-template.md"].partition(DEEP_REVIEW_FOLLOW_UP_HEADING)[0].splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[1] == "PASS / FAIL / NOT EXERCISED":
            receipt_scenarios.append(cells[0])
    scenario_lists = {
        "protocol.md": protocol_scenarios,
        "references/output-template.md": receipt_scenarios,
        "runtime-acceptance.md": matrix_scenarios,
    }
    scenarios = {
        relative: [name.strip().lower() for name in names]
        for relative, names in scenario_lists.items()
    }
    expected_scenarios = scenarios["references/output-template.md"]
    return [
        f"skills/deep-review/{relative}: runtime acceptance scenarios differ from references/output-template.md"
        for relative, found in scenarios.items()
        if not found or found != expected_scenarios
    ]


DEEP_REVIEW_FOLLOW_UP_RULES = {
    "SKILL.md": (
        "Only a leading literal `follow-up` token selects it; every other invocation is the unchanged full review",
        "skip reviewer selection, the scout capacity check, and the scout wave, and state in the report that no scouts ran",
        "giving each invocation exactly one original concern record and never GitHub discussion",
        "A preservation failure never changes a review's outcomes, report, or publication and never blocks worktree cleanup",
    ),
    "protocol.md": (
        # Entry token.
        "A leading literal `follow-up` token selects follow-up mode. Every invocation without it is the unchanged full review",
        # Canonical absolute record root.
        "`<git-common-dir>/deep-review/records/<run-id>/`",
        "`git rev-parse --path-format=absolute --git-common-dir`",
        "resolve symlinks, normalize separators and case to the platform's native form, and reject a result that is not an existing directory",
        "Never use the coordinator-owned review worktree's own Git directory or a path relative to the session's working directory.",
        "It never removes unpreserved records and is never silent about a preservation failure.",
        "Worktree cleanup never waits on preservation, and a preservation failure never reverses or blocks it.",
        "only when both the worktree cleanup in step 1 and the record preservation in step 3 are verified",
        "it never deletes them outside the Git worktree mechanism",
        "It runs only after worktree cleanup has finished and the run state and final report record the actual cleanup outcome",
        # Full-review source selection.
        "The **source record** is the latest matching record whose mode is `full`, never a newer follow-up record",
        "supply prior status and provenance only",
        # No reconstruction.
        "It is never reconstructed from a comment body, report prose, or memory, and it never widens the run into a full review.",
        "or with ambiguous evidence",
        "mapped to concerns only through recorded comment identifiers: the source record's publication mapping and the mappings of follow-up records whose lineage names the source, each keyed by source run ID plus canonical ID",
        "These mappings are provenance for selection and thread state, never validator evidence.",
        # Scout skip.
        "Follow-up mode skips reviewer selection, the scout capacity check, and the scout wave, and the report states that no scouts ran.",
        # Follow-up validator capacity independent of the scout capacity check.
        "static validator concurrency comes from the **follow-up validator capacity** the active harness declares in `SKILL.md`",
        # Discussion isolation for follow-up validators.
        "Follow-up validators never receive GitHub discussion, thread state, author claims, or prior follow-up statuses.",
        "The original outcome is context, never evidence",
        "Deferred concerns are not revalidated and are reported as deferred, never as addressed.",
        # Separate thread state.
        "GitHub thread state (open, resolved, outdated, not published, or unknown) is a separate column.",
        "a resolved thread never makes a concern addressed",
        # Not-a-full-review label and read-only GitHub.
        'labeled "Follow-up revalidation: not a full PR review"',
        "It never shows PASS or a `No findings` headline",
        "Follow-up never replies to, edits, resolves, or reopens an existing thread.",
    ),
    "reviewers/validator.md": (
        "You receive no GitHub discussion, thread state, author claims, or prior follow-up statuses, and you must not retrieve them.",
        "The original outcome is context, never evidence.",
        "Never fetch it.",
    ),
    "references/output-template.md": (
        "**Follow-up revalidation: not a full PR review.**",
        "code outside the selected concerns was not reviewed",
        "Scouts: none ran (follow-up mode)",
        "| GitHub thread state |",
        "a resolved thread never makes a concern Addressed",
    ),
    "references/pr-review-comments.md": (
        "Each approved payload entry records the canonical concern ID it publishes",
        "whenever the submission response or a read-back provides them",
    ),
}
DEEP_REVIEW_FULL_ONLY_SCENARIOS = (
    "Zero hypotheses", "Surviving hypotheses", "Multiple selected scouts", "Insufficient scout capacity", "Scout failure",
)
DEEP_REVIEW_FOLLOW_UP_HEADING = "\n## Follow-up revalidation variant\n"
DEEP_REVIEW_PROTOCOL_SCENARIO = r"(?m)^- ([^:\n]+): whether "
DEEP_REVIEW_TEMPLATE_SCENARIO = r"(?m)^\| ([^|\n]+?) \| PASS / FAIL / NOT EXERCISED \|"
DEEP_REVIEW_OBSERVATION_SCENARIO = r"(?m)^\| ([^|\n]+?)(?: \| (?:PASS|FAIL|NOT EXERCISED)){3} \|$"


def markdown_section(text: str, heading: str) -> str:
    """The body of one Markdown heading up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    start = text.find(f"\n{heading}\n")
    if start < 0:
        return ""
    body = text[start + len(heading) + 2:]
    end = re.search(rf"(?m)^#{{1,{level}}} ", body)
    return body[:end.start()] if end else body


def deep_review_follow_up_scenario_lists(documents: dict[str, str]) -> dict[str, list[str] | None]:
    """Follow-up receipt scenarios, read from each document's own follow-up section."""
    follow_up_template = documents["references/output-template.md"].partition(DEEP_REVIEW_FOLLOW_UP_HEADING)[2]
    matrix_section = markdown_section(documents["runtime-acceptance.md"], "## Follow-up revalidation matrix")
    lists = {
        "protocol.md": re.findall(DEEP_REVIEW_PROTOCOL_SCENARIO,
                                  markdown_section(documents["protocol.md"], "### Follow-up runtime acceptance")),
        "references/output-template.md": re.findall(DEEP_REVIEW_TEMPLATE_SCENARIO, follow_up_template),
        "runtime-acceptance.md": scenario_matrix_names(matrix_section),
        "runtime-acceptance.md observations": re.findall(DEEP_REVIEW_OBSERVATION_SCENARIO, matrix_section),
    }
    return {relative: None if names is None else [name.strip().lower() for name in names]
            for relative, names in lists.items()}


def deep_review_follow_up_problems(documents: dict[str, str]) -> list[str]:
    """Check the deterministic follow-up clauses and that the follow-up receipt stays separate and consistent."""
    problems = []
    for relative, rules in DEEP_REVIEW_FOLLOW_UP_RULES.items():
        for rule in rules:
            if rule not in documents.get(relative, ""):
                problems.append(f"deep-review/{relative}: missing follow-up contract {rule!r}")
    follow_up_lists = deep_review_follow_up_scenario_lists(documents)
    follow_up = follow_up_lists["references/output-template.md"]
    for relative, found in follow_up_lists.items():
        if not found or found != follow_up:
            problems.append(f"deep-review/{relative}: follow-up runtime acceptance scenarios differ from references/output-template.md")
    full_template, _, follow_up_template = documents["references/output-template.md"].partition(DEEP_REVIEW_FOLLOW_UP_HEADING)
    full = [name.strip().lower() for name in re.findall(DEEP_REVIEW_TEMPLATE_SCENARIO, full_template)]
    if set(full) & set(follow_up or []):
        problems.append("deep-review follow-up receipt rows must not reuse full-review scenario names")
    for scenario in DEEP_REVIEW_FULL_ONLY_SCENARIOS:
        if scenario.lower() not in full or scenario not in follow_up_template:
            problems.append(f"deep-review follow-up receipt must mark full-review-only row {scenario!r} as not run")
    report = follow_up_template.split("```markdown", 1)[-1].split("\n```", 1)[0]
    for forbidden in ("Headline takeaway", "No findings", "| Already reported"):
        if forbidden in report:
            problems.append(f"deep-review follow-up report must not carry the full-review {forbidden!r} presentation")
    capacity = [line.split("|")[2:5] for line in documents["SKILL.md"].splitlines()
                if line.startswith("| Follow-up validator capacity |")]
    if len(capacity) != 1 or len(capacity[0]) != 3 or not all(cell.strip() for cell in capacity[0]) or any(
            "scout capacity check" in cell or "found by the capacity check" in cell for cell in capacity[0]):
        problems.append("deep-review/SKILL.md: every harness must declare a follow-up validator capacity independent of the scout capacity check")
    hint = re.search(r'(?m)^argument-hint: "([^"\n]*)"$', documents["SKILL.md"].split("\n---\n", 1)[0])
    if not hint or not hint.group(1).startswith("[follow-up] "):
        problems.append("deep-review argument-hint must lead with the optional `follow-up` token")
    if "follow-up" not in documents.get("agents/openai.yaml", "").partition("short_description:")[2].split("\n", 1)[0]:
        problems.append("deep-review Codex short_description must name follow-up revalidation like argument-hint")
    return problems


DEEP_REVIEW_PROBE_ENVIRONMENT_RULES = {
    "SKILL.md": ("references/probe-environment.md", "environment contract"),
    "protocol.md": (
        "## Writable probe environment",
        "references/probe-environment.md",
        "environment contract",
        "environment provenance",
    ),
    "reviewers/validator.md": (
        "references/probe-environment.md",
        "environment contract",
        "actual runtime",
        "process execution gate before setup, production imports, or the bounded check",
    ),
    "references/probe-environment.md": (
        "runtime/dependency declarations, applicable lockfile, dependency groups",
        "project-native setup/execution convention",
        "A plain manifest project may use its documented runtime's ordinary isolated installation",
        "missing or ambiguous prerequisites are a specific limitation",
        "Compare the actual runtime and dependencies against the declared requirements and locked versions",
        "installed dependency versions needed by the check",
        "the reviewed code is loaded from the pinned worktree",
        "Establish a run-owned dependency environment within the review's permitted disposable boundary",
        "A venv, lockfile, installation destination, or owned cache path is not a process sandbox",
        "PEP 517/build backends, npm lifecycle scripts",
        "including child processes",
        "explicit user authorization for the pinned target",
        "A general review request, permission to create the worktree",
        "do not execute target-controlled setup, imports, or checks",
        "Authorization is not mechanical isolation",
        "do not inspect or execute that environment to establish staleness",
        "installs into, synchronizes, repairs, or otherwise mutates the caller or main checkout's environment",
        "outside mutable probe state",
        "Never silently replace missing dependencies with mocks, stubs, fake modules, or import bypasses",
        "why the bounded question does not depend on it, and what the result cannot establish",
        "A mock replacing behavior essential to the claim cannot support that claim",
        "Never call the check passed or infer Finding/Disproved",
        "Unresolved with evidence, Remaining question, and Needs confirmation",
        "not validated due to review failure: mark the run incomplete",
        "block PASS, `No findings`, and publication",
        "independently decisive static evidence usable with its actual provenance",
        "An environment removed by restoration must be re-established and verified before reuse",
        "Failure to preserve required evidence or eliminate contamination stops validation",
    ),
    "references/output-template.md": ("environment provenance",),
    "runtime-acceptance.md": ("references/probe-environment-scenarios.md", "environment provenance"),
    "references/probe-environment-scenarios.md": (
        "Stale Python environment",
        "Verified setup",
        "Native manager other than uv",
        "Plain manifest",
        "Unavailable setup",
        "Failed setup",
        "Justified mocking",
        "Claim-invalidating mocking",
        "Restoration removes environment",
        "Retained environment contamination",
        "Missing or ambiguous prerequisites",
        "Wrong code origin or locked version",
        "Owned paths without a process boundary",
        "Executable install hook under a verified sandbox",
        "Explicit authorization with residual access",
        "unchanged caller",
        "not native runtime evidence",
    ),
}


def deep_review_probe_environment_problems(documents: dict[str, str]) -> list[str]:
    """Guard the prompt contract, not execution or dependency provisioning."""
    return [
        f"skills/deep-review/{relative}: missing probe environment rule {rule!r}"
        for relative, rules in DEEP_REVIEW_PROBE_ENVIRONMENT_RULES.items()
        for rule in rules
        if rule not in documents.get(relative, "")
    ]
