#!/usr/bin/env python3
"""Canonical fast repository validation. Installer tests live in test_installers.py."""

from __future__ import annotations

import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.parse
from pathlib import Path

import generate_agents


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".sh", ".ps1", ".toml"}
RETIRED_BUCKETS = {"engineering", "productivity", "misc", "deprecated", "in-progress"}
RETIRED_FILES = {
    "CLAUDE.md",
    "CHANGELOG.md",
    "package.json",
    "package-lock.json",
    ".github/workflows/release.yml",
    "scripts/sync-plugin-version.mjs",
    "scripts/link-skills.sh",
}
STALE_PATTERNS = {
    "ask-matt": re.compile(r"ask-matt", re.IGNORECASE),
    "old setup skill": re.compile(r"setup-matt-pocock-skills", re.IGNORECASE),
    "bucketed skill path": re.compile(r"skills/(?:engineering|productivity|misc|deprecated|in-progress)/", re.IGNORECASE),
    "mirrored docs path": re.compile(r"docs/(?:engineering|productivity)/", re.IGNORECASE),
    "Claude plugin manifest": re.compile(r"\.claude-plugin|claude plugins? install", re.IGNORECASE),
    "old publishing URL": re.compile(r"aihero\.dev", re.IGNORECASE),
    # Only a line that says "legacy" (a fallback or migration statement) may name the old glossary files.
    "legacy glossary name": re.compile(r"^(?!.*\blegacy\b).*\bCONTEXT(?:-MAP)?\.md", re.MULTILINE),
}
# Former stable skill names mapped to their current names. A former name is a stale
# reference; the installer tests seed installations under it to prove reconciliation.
RENAMED_SKILLS = {"code-review": "implementation-review"}
for _former in RENAMED_SKILLS:
    STALE_PATTERNS[f"renamed skill {_former}"] = re.compile(rf"(?<![\w-]){re.escape(_former)}(?![\w-])")
INTENTIONAL_STALE_REFERENCE_FILES = {"install.sh", "install.ps1", "scripts/check.py"}
AGENT_BRIEF_HEADING = "## Agent Brief"
AGENT_BRIEF_REQUIRED_FIELDS = (
    "Category", "Summary", "Current behavior", "Desired behavior", "Acceptance criteria", "Out of scope",
)
AGENT_BRIEF_OPTIONAL_FIELDS = ("Key interfaces",)
# The one completeness rule. The tracker contract, its GitHub seed, and the Agent Brief
# guide must each state it verbatim so the documents and this model cannot drift.
AGENT_BRIEF_COMPLETENESS_RULE = (
    "A complete Agent Brief has the `## Agent Brief` heading and the Category, Summary, "
    "Current behavior, Desired behavior, non-empty Acceptance criteria, and Out of scope fields; "
    "`Key interfaces` is optional and its absence never makes a brief incomplete."
)
# The Agent Brief semantics a tracker that supports parentless standalone tickets must
# state. A tracker that claims standalone support without all of them is stale.
AGENT_BRIEF_TRACKER_CONTRACT = (
    AGENT_BRIEF_COMPLETENESS_RULE,
    "newest complete trusted brief comment",
    "effective repository permission `write` (including `maintain`) or `admin`",
    "does not depend on detecting `/triage`",
    "never falls back to standalone authority",
    "never creates or edits Agent Brief authority",
    "author_association",
    "is held non-ready",
    "when the publishing account's permission cannot be verified, it stays non-ready",
)
RETIRED_STANDALONE_RECORD = "## Standalone implementation authority"
# A tracker's standalone authority mode. Parent-only trackers state that standalone
# authority is unsupported, or that every implementation ticket has a parent/spec.
STANDALONE_UNSUPPORTED = re.compile(r"\*\*Standalone authority\*\*:\s*unsupported\b", re.IGNORECASE)
STANDALONE_CLAIMED = re.compile(r"\*\*Standalone authority\*\*:(?!\s*unsupported\b)", re.IGNORECASE)
EVERY_TICKET_HAS_PARENT = re.compile(
    r"every implementation (?:issue|ticket) (?:has|requires) a\b[^.\n]*\bparent", re.IGNORECASE,
)
CURRENT_STANDALONE_MODES = {"parent-only", "standalone"}
AUTHORITY_GRANTED = {"parent", "standalone"}
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
TRIAGE_COMMENT_DISCLAIMER = "> *This was generated by AI during triage.*"
TRUSTED_APPROVAL_PERMISSIONS = {"write", "admin"}
# Explicit non-agent triage states. Reconciliation never overrides them.
HELD_TRIAGE_STATES = {"needs-triage", "needs-info", "ready-for-human", "wontfix"}
USER_INVOKED_SKILLS = {
    "deep-review", "design-review", "evaluate-model", "grill-me",
    "grill-with-docs", "handoff-doc", "implement", "implementation-review",
    "improve-codebase-architecture", "reconcile", "setup-skills", "teach",
    "to-questionnaire", "to-spec", "to-tickets", "triage", "wait-what",
    "wayfinder", "write-pr",
}
MODEL_INVOKED_SKILLS = {
    "codebase-design", "diagnosing-bugs", "domain-modeling", "grilling",
    "prototype", "research", "tdd", "wizard",
    "writing-for-agents",
}
# Current pinned models and limits for the deep-review adapters.
# Claude Code does not confine an agent's Bash to
# the patterns in its tool list, so its read-only roles keep plain Bash.
DEEP_REVIEW_READ_ONLY_TOOLS = ["read", "grep", "glob", "exec"]
DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "Bash"]
DEEP_REVIEW_ROLES = {
    "scout": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high", "sandbox_mode": "read-only"},
        "devin": {"model": "gpt-6-sol-medium", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-sonnet-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "structural": {
        "codex": {"model": "gpt-6.1-sol", "model_reasoning_effort": "high", "sandbox_mode": "read-only"},
        "devin": {"model": "gpt-6-sol-medium", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-opus-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "validator-static": {
        "codex": {"model": "gpt-6.1-sol", "model_reasoning_effort": "high", "sandbox_mode": "read-only"},
        "devin": {"model": "gpt-6-sol-high", "allowed-tools": DEEP_REVIEW_READ_ONLY_TOOLS},
        "claude": {"model": "claude-opus-5-5", "tools": DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "effort": "high"},
    },
    "validator-probe": {
        "codex": {"model": "gpt-6-luna", "model_reasoning_effort": "high", "sandbox_mode": "workspace-write"},
        "devin": {"model": "gpt-6-sol-high", "allowed-tools": [*DEEP_REVIEW_READ_ONLY_TOOLS, "write", "edit"]},
        "claude": {"model": "claude-sonnet-5-5", "tools": [*DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS, "Edit", "Write"], "effort": "high"},
    },
}
HARNESS_SPECIFIC_TEXT = re.compile(
    r"Devin|Codex|Claude|run_subagent|spawn_agent|gpt-[0-9]|allowed-tools|sandbox_mode|model_reasoning_effort|\.config/devin|\.codex",
    re.IGNORECASE,
)


class CheckFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CheckFailure(message)


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        fail(f"{path.relative_to(ROOT)}: missing opening frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"{path.relative_to(ROOT)}: missing closing frontmatter delimiter")

    fields: dict[str, str] = {}
    current_list: str | None = None
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list is None:
                fail(f"{path.relative_to(ROOT)}:{number}: list item has no key")
            fields[current_list] += "\n" + line[4:].strip()
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            fail(f"{path.relative_to(ROOT)}:{number}: unsupported or invalid frontmatter")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9-]*", key):
            fail(f"{path.relative_to(ROOT)}:{number}: invalid frontmatter key {key!r}")
        if key in fields:
            fail(f"{path.relative_to(ROOT)}:{number}: duplicate frontmatter key {key!r}")
        if value and not (value.startswith(('"', "'")) and value.endswith(('"', "'"))) and ": " in value:
            fail(f"{path.relative_to(ROOT)}:{number}: quote scalar values containing ': '")
        fields[key] = value
        current_list = key if not value else None
    return fields, "\n".join(lines[1:end])


def skill_directories() -> list[Path]:
    stable = [path for path in SKILLS.iterdir() if path.is_dir() and path.name != "experimental"]
    experimental_root = SKILLS / "experimental"
    experimental = [path for path in experimental_root.iterdir() if path.is_dir()]
    return sorted(stable + experimental, key=lambda path: path.as_posix())


def codex_implicit_policy_values(metadata_text: str, metadata: Path) -> list[str]:
    """Read the supported policy field without treating an unrelated key as policy."""
    section = None
    values = []
    for line in metadata_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            section = line.split(":", 1)[0]
        if "allow_implicit_invocation" not in line:
            continue
        match = re.fullmatch(r"  allow_implicit_invocation:\s*(true|false)\s*", line)
        if section != "policy" or match is None:
            fail(f"{metadata.relative_to(ROOT)}: allow_implicit_invocation must be a boolean under policy")
        values.append(match.group(1))
    return values


def validate_layout_and_skills() -> list[str]:
    if not (SKILLS / "experimental").is_dir():
        fail("skills/experimental must exist")
    present_retired = sorted(name for name in RETIRED_BUCKETS if (SKILLS / name).exists())
    if present_retired:
        fail(f"retired skill buckets remain: {', '.join(present_retired)}")

    names: dict[str, Path] = {}
    if USER_INVOKED_SKILLS & MODEL_INVOKED_SKILLS:
        fail("stable skill invocation classifications overlap")
    for directory in skill_directories():
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            fail(f"{directory.relative_to(ROOT)}: skill directory lacks SKILL.md")
        wrappers = sorted(path for path in directory.rglob("SKILL.md") if path != skill_file)
        if wrappers:
            fail(f"{wrappers[0].relative_to(ROOT).as_posix()}: a skill has exactly one authoritative SKILL.md")
        fields, raw_frontmatter = parse_frontmatter(skill_file)
        for required in ("name", "description"):
            if not fields.get(required):
                fail(f"{skill_file.relative_to(ROOT)}: missing required {required!r} frontmatter")
        name = fields["name"].strip('"\'')
        if name != directory.name:
            fail(f"{skill_file.relative_to(ROOT)}: name {name!r} does not match directory {directory.name!r}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            fail(f"{skill_file.relative_to(ROOT)}: invalid skill name {name!r}")
        if name in names:
            fail(f"duplicate skill name {name!r}: {names[name]} and {directory}")
        names[name] = directory

        metadata = directory / "agents" / "openai.yaml"
        if not metadata.is_file():
            fail(f"{directory.relative_to(ROOT)}: missing agents/openai.yaml")
        metadata_text = metadata.read_text(encoding="utf-8")
        for required_metadata in ("display_name", "short_description"):
            if not re.search(rf"(?m)^\s*{required_metadata}:\s*\S", metadata_text):
                fail(f"{metadata.relative_to(ROOT)}: missing {required_metadata}")
        if directory.parent == SKILLS:
            expected = "user" if name in USER_INVOKED_SKILLS else "model" if name in MODEL_INVOKED_SKILLS else None
            if expected is None:
                fail(f"{directory.relative_to(ROOT)}: stable skill has no reviewed invocation classification")
            triggers = [trigger for trigger in fields["triggers"].splitlines() if trigger] if "triggers" in fields else None
            expected_triggers = ["user"] if expected == "user" else None
            if triggers != expected_triggers:
                requirement = "must be ['user']" if expected == "user" else "must be omitted to use the default [user, model]"
                fail(f"{skill_file.relative_to(ROOT)}: Devin triggers {requirement}")
            disabled = fields.get("disable-model-invocation")
            if disabled != ("true" if expected == "user" else None):
                fail(f"{skill_file.relative_to(ROOT)}: Claude model invocation disagrees with {expected} classification")
            if "user-invocable" in fields:
                fail(f"{skill_file.relative_to(ROOT)}: Claude user-invocable must be omitted")
            implicit = codex_implicit_policy_values(metadata_text, metadata)
            expected_implicit = ["false"] if expected == "user" else []
            if implicit != expected_implicit:
                fail(f"{metadata.relative_to(ROOT)}: Codex policy disagrees with {expected} classification")
        else:
            implicit_false = bool(re.search(r"(?m)^\s*allow_implicit_invocation:\s*false\s*$", metadata_text))
            disabled = bool(re.search(r"(?m)^disable-model-invocation:\s*true\s*$", raw_frontmatter))
            if disabled != implicit_false:
                fail(f"{directory.relative_to(ROOT)}: SKILL.md and agents/openai.yaml invocation policies disagree")
    actual_stable = {path.name for path in SKILLS.iterdir() if path.is_dir() and path.name != "experimental"}
    if actual_stable != USER_INVOKED_SKILLS | MODEL_INVOKED_SKILLS:
        fail("reviewed invocation classifications do not match stable skill directories")
    return sorted(names)


def iter_repository_text() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore", ".gitattributes"}:
            paths.append(path)
    return paths


def validate_repository_references(skill_names: list[str]) -> None:
    for relative in RETIRED_FILES:
        if (ROOT / relative).exists():
            fail(f"retired file remains: {relative}")
    for retired_dir in (".claude-plugin", ".changeset"):
        if (ROOT / retired_dir).exists():
            fail(f"retired directory remains: {retired_dir}")

    for path in iter_repository_text():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if chr(0x2014) in text:
            fail(f"{relative}: em dash violates repository style")
        if relative not in INTENTIONAL_STALE_REFERENCE_FILES:
            for label, pattern in STALE_PATTERNS.items():
                match = pattern.search(text)
                if match:
                    line = text.count("\n", 0, match.start()) + 1
                    fail(f"{relative}:{line}: stale {label} reference")
        if relative not in {"README.md", "scripts/check.py"} and re.search(r"mattpocock/skills", text, re.IGNORECASE):
            fail(f"{relative}: stale upstream repository identity")
        validates_links = path.suffix.lower() == ".md" and (
            path.name == "SKILL.md"
            or path.parent == ROOT
            or relative.startswith(".agents/")
            or relative.startswith(".out-of-scope/")
        )
        if validates_links:
            for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
                target = match.group(1).strip().strip("<>").split(maxsplit=1)[0]
                if not target or target.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                    continue
                target = urllib.parse.unquote(target.split("#", 1)[0])
                if not (target.startswith(("./", "../")) or "/" in target or Path(target).suffix):
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    line = text.count("\n", 0, match.start()) + 1
                    fail(f"{relative}:{line}: broken relative link {target!r}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in skill_names:
        expected = f"./skills/{name}/SKILL.md"
        if expected not in readme:
            fail(f"README.md does not link canonical SKILL.md for {name}")


def agent_brief_fields(text: str) -> dict[str, list[str]] | None:
    """Split the first `## Agent Brief` section into its labelled fields.

    The section ends at the next level-one or level-two heading, so text around it,
    such as a heading above it or a generated footer, never changes the brief.
    """
    lines = [line.strip() for line in text.splitlines()]
    if AGENT_BRIEF_HEADING not in lines:
        return None
    labels = (*AGENT_BRIEF_REQUIRED_FIELDS, *AGENT_BRIEF_OPTIONAL_FIELDS)
    fields: dict[str, list[str]] = {}
    current = None
    for line in lines[lines.index(AGENT_BRIEF_HEADING) + 1:]:
        if re.match(r"#{1,2}\s", line):
            break
        match = re.fullmatch(r"\*\*([^*]+):\*\*\s*(.*)", line)
        if match and match.group(1) in labels:
            current = match.group(1)
            fields.setdefault(current, [])
            line = match.group(2)
        if current is not None and line:
            fields[current].append(line)
    return fields


def is_complete_agent_brief(text: str) -> bool:
    """Apply AGENT_BRIEF_COMPLETENESS_RULE to one brief source."""
    fields = agent_brief_fields(text)
    if fields is None or any(field not in fields for field in AGENT_BRIEF_REQUIRED_FIELDS):
        return False
    for line in fields["Acceptance criteria"]:
        item = re.fullmatch(r"(?:[-*]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.*)", line)
        if item and item.group(1).strip():
            return True
    return False


def is_trusted_author(author: dict) -> bool:
    """A human account whose current repository permission is write (including maintain) or admin."""
    return author.get("user_type") == "User" and author.get("permission") in TRUSTED_APPROVAL_PERMISSIONS


def resolve_agent_brief(issue: dict) -> str | None:
    """The one Agent Brief resolver shared by /implement and /reconcile.

    The newest complete trusted brief comment wins; otherwise a complete trusted
    issue-body brief. Recognition never depends on a /triage marker or disclaimer.
    """
    for comment in sorted(issue["comments"], key=lambda comment: comment["created_at"], reverse=True):
        if is_trusted_author(comment) and is_complete_agent_brief(comment["body"]):
            return comment["body"]
    if is_trusted_author(issue["author"]) and is_complete_agent_brief(issue["body"]):
        return issue["body"]
    return None


def standalone_frontier_numbers(issues: list[dict]) -> list[int]:
    """Project readiness across parentless issues that carry a trusted Agent Brief.

    An explicit non-agent triage state holds an issue non-ready; an unlabelled
    planned issue is promoted once its blockers close.
    """
    ready = []
    for issue in issues:
        if issue["parent"] is not None or resolve_agent_brief(issue) is None:
            continue
        if HELD_TRIAGE_STATES & set(issue.get("labels", ())):
            continue
        if issue["state"] != "OPEN" or issue["assignees"] or issue["open_blockers"]:
            continue
        ready.append(issue["number"])
    return sorted(ready)


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
    """Model the `/setup-skills` up-to-date verdict: every capability and a current mode."""
    return not missing_tracker_capabilities(tracker) and tracker_standalone_authority(tracker) in CURRENT_STANDALONE_MODES


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


def implementation_start_gate(*, tracker: str, required: set[str], ticket: dict) -> str:
    """Model /implement's authority and ticket-state start gates: "start" or the stop reason."""
    if set(missing_tracker_capabilities(tracker)) & required:
        return "stale-tracker"
    authority = resolve_issue_authority(
        tracker=tracker, parent=ticket["parent"], issue=ticket, ready_for_agent=ticket["ready"],
    )
    if authority not in AUTHORITY_GRANTED:
        return authority or "no-authority"
    if ticket["state"] != "OPEN" or ticket["open_blockers"] or not ticket["ready"]:
        return "not-ready"
    return "start"


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
        (implement, "Explicitly compose the `implementation-review` workflow"),
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
            ready = (
                subject["state"] == "OPEN" and not subject["assignees"] and not blockers
                and not held_labels.intersection(subject["labels"])
            )
            marked = ready_label in subject["labels"]
            if ready:
                plan["frontiers"][scope].append(number)
            if ready == marked:
                plan["noops"].append(number)
            else:
                plan["promotions" if ready else "removals"].append(number)
                plan["writes"].append((number, "add" if ready else "remove", ready_label))
    return plan


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


def validate_native_agents() -> None:
    """Every role manifest renders each harness agent in memory, with one owner per agent name."""
    owners: dict[str, str] = {}
    for skill in generate_agents.agent_skill_directories(ROOT):
        harnesses = sorted(path.name for path in (skill / "harnesses").iterdir() if path.is_dir())
        unsupported = sorted(set(harnesses) - set(generate_agents.HARNESSES))
        if unsupported:
            fail(f"{skill.relative_to(ROOT).as_posix()}/harnesses: unsupported harness directories {', '.join(unsupported)}")
        try:
            rendered = generate_agents.render_agents(skill)
            roles = generate_agents.load_roles(skill)
        except generate_agents.AgentManifestError as error:
            fail(f"malformed role manifest: {error}")
        for role in roles:
            if role.agent_name in owners:
                fail(f"agent name {role.agent_name!r} is shipped by both {owners[role.agent_name]} and {skill.name}")
            owners[role.agent_name] = skill.name
            codex = rendered.get(f"harnesses/codex/{role.agent_name}.toml")
            if codex is not None:
                parsed = tomllib.loads(codex)
                if parsed.get("name") != role.agent_name or parsed.get("developer_instructions") != role.body:
                    fail(f"{skill.name}: generated Codex agent {role.agent_name} does not round-trip its name and body")
    if "agent-skill" not in owners.values():
        fail("tests/fixtures/agent-skill must ship native reviewer agents")


def git_paths(command: str, *arguments: str, stdin: str | None = None) -> list[str]:
    """Run one read-only Git query in the repository and return its NUL-separated paths."""
    try:
        result = subprocess.run(
            ["git", command, "-z", *arguments], cwd=ROOT, input=stdin, text=True, capture_output=True, encoding="utf-8",
        )
    except OSError as error:
        fail(f"git is required to check generated agent ownership: {error}")
    if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr.strip()):
        fail(f"git {command} failed: {result.stderr.strip()}")
    return [path for path in result.stdout.split("\0") if path]


def validate_generated_agents_untracked() -> None:
    """Generated harness agents are ignored install artifacts; only manifests and bodies are source."""
    for skill in generate_agents.agent_skill_directories(ROOT):
        harnesses = (skill / "harnesses").relative_to(ROOT).as_posix()
        manifest = f"{harnesses}/roles.toml"
        tracked = [path for path in git_paths("ls-files", "--", harnesses) if path != manifest]
        if tracked:
            fail(f"generated agent files are tracked by Git: {', '.join(tracked)}; run git rm --cached on them")
        if manifest in git_paths("check-ignore", "--no-index", "--stdin", stdin=f"{manifest}\0"):
            fail(f"{manifest} is ignored by Git but is native-agent source")
        expected = sorted(f"{skill.relative_to(ROOT).as_posix()}/{relative}" for relative in generate_agents.render_agents(skill))
        ignored = set(git_paths("check-ignore", "--no-index", "--stdin", stdin="".join(f"{path}\0" for path in expected)))
        unignored = [path for path in expected if path not in ignored]
        if unignored:
            fail(f"generated agent files are not ignored by .gitignore: {', '.join(unignored)}")


def deep_review_shared_sources(skill: Path) -> list[Path]:
    """The harness-neutral protocol, glossary, references, and reviewer contracts."""
    return sorted([
        skill / "protocol.md",
        skill / "GLOSSARY.md",
        *(path for path in (skill / "references").rglob("*") if path.is_file()),
        *(path for path in (skill / "reviewers").rglob("*") if path.is_file()),
    ])


def validate_deep_review() -> None:
    """Deep review keeps one harness-neutral copy of its sources and its pinned role limits."""
    skill = SKILLS / "deep-review"
    roles = {role.name: role for role in generate_agents.load_roles(skill)}
    if set(roles) != set(DEEP_REVIEW_ROLES):
        fail(f"deep-review roles must be exactly {', '.join(sorted(DEEP_REVIEW_ROLES))}")
    for name, expected in DEEP_REVIEW_ROLES.items():
        if roles[name].harnesses != expected:
            fail(f"deep-review role {name!r} drifted from its pinned harness models and limits")
    if "# Structural Lens" not in roles["structural"].body or "# Structural Lens" in roles["scout"].body:
        fail("only the deep-review structural scout embeds the structural lens")

    shared = deep_review_shared_sources(skill)
    for path in shared:
        match = HARNESS_SPECIFIC_TEXT.search(path.read_text(encoding="utf-8"))
        if match:
            fail(f"{path.relative_to(ROOT).as_posix()}: harness-specific text {match.group(0)!r} in shared deep-review content")
    # Structural review is architecture-neutral: deep-review must not require or defer to codebase-design.
    for path in [skill / "SKILL.md", *shared]:
        if "codebase-design" in path.read_text(encoding="utf-8"):
            fail(f"{path.relative_to(ROOT).as_posix()}: deep-review must not depend on or defer adjudication to codebase-design")
    scenario_lists = {
        "protocol.md": r"(?m)^- ([^:\n]+): whether ",
        "references/output-template.md": r"(?m)^\| ([^|\n]+?) \| PASS / FAIL / NOT EXERCISED \|",
        "runtime-acceptance.md": r"(?m)^\| ([^|\n]+?) \| [^\n]* \| Same \|$",
    }
    scenarios = {
        relative: [name.strip().lower() for name in re.findall(pattern, (skill / relative).read_text(encoding="utf-8"))]
        for relative, pattern in scenario_lists.items()
    }
    expected_scenarios = scenarios["references/output-template.md"]
    for relative, found in scenarios.items():
        if not found or found != expected_scenarios:
            fail(f"skills/deep-review/{relative}: runtime acceptance scenarios differ from references/output-template.md")

    contents = {path.read_text(encoding="utf-8"): path for path in shared}
    generated = skill / "harnesses"
    for path in iter_repository_text():
        if path in shared or path.is_relative_to(generated):
            continue
        original = contents.get(path.read_text(encoding="utf-8"))
        if original is not None:
            fail(f"{path.relative_to(ROOT).as_posix()}: duplicate copy of {original.relative_to(ROOT).as_posix()}")


def remove_generated_agents(skill: Path) -> None:
    """Return a skill to its fresh-clone shape: the manifest and bodies without generated output."""
    for harness in generate_agents.HARNESSES:
        shutil.rmtree(skill / "harnesses" / harness, ignore_errors=True)


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def validate_agent_generation_contract() -> None:
    """Prove generation is deterministic, repairs local output, and rejects malformed sources."""
    source = ROOT / "tests" / "fixtures" / "agent-skill"
    with tempfile.TemporaryDirectory(prefix="skills-agents-") as temp_value:
        temporary = Path(temp_value)
        skill = temporary / "agent-skill"

        def fresh_copy() -> None:
            shutil.rmtree(skill, ignore_errors=True)
            shutil.copytree(source, skill)
            remove_generated_agents(skill)

        fresh_copy()
        rendered = generate_agents.render_agents(skill)
        expected_files = {
            "harnesses/codex/agent-skill-scout.toml",
            "harnesses/devin/agent-skill-scout/AGENT.md",
            "harnesses/claude/agent-skill-scout.md",
        }
        if not expected_files <= set(rendered):
            fail("agent generation does not produce one shared agent name per role for every harness")
        elsewhere = temporary / "elsewhere" / "agent-skill"
        shutil.copytree(skill, elsewhere)
        if generate_agents.render_agents(skill) != rendered or generate_agents.render_agents(elsewhere) != rendered:
            fail("agent generation is not deterministic")
        if not generate_agents.stale_agents(skill):
            fail("agent freshness check accepted a skill with no generated agent files")
        generate_agents.write_agents(skill)
        if generate_agents.stale_agents(skill):
            fail("generation into a fresh clone did not produce every agent file")
        generated = snapshot_tree(skill / "harnesses")
        if generate_agents.write_agents(skill) or snapshot_tree(skill / "harnesses") != generated:
            fail("regenerating unchanged sources rewrote generated agent files")

        codex_scout = skill / "harnesses" / "codex" / "agent-skill-scout.toml"
        cases = {
            "stale": lambda: (skill / "reviewers" / "reviewer.md").write_text("changed body\n", encoding="utf-8"),
            "missing": lambda: (skill / "harnesses" / "claude" / "agent-skill-probe.md").unlink(),
            "hand-edited": lambda: codex_scout.write_text(codex_scout.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8"),
            "unexpected": lambda: (skill / "harnesses" / "claude" / "agent-skill-extra.md").write_text("extra\n", encoding="utf-8"),
        }
        for label, mutate in cases.items():
            fresh_copy()
            generate_agents.write_agents(skill)
            mutate()
            if not generate_agents.stale_agents(skill):
                fail(f"agent freshness check accepted a {label} generated agent file")
            generate_agents.write_agents(skill)
            if generate_agents.stale_agents(skill):
                fail(f"regeneration did not repair a {label} generated agent file")

        malformed = {
            "malformed": lambda: (skill / "harnesses" / "roles.toml").write_text("[roles.scout]\nbody = 3\n", encoding="utf-8"),
            "missing reviewer body": lambda: (skill / "reviewers" / "probe.md").unlink(),
        }
        healthy = temporary / "healthy-skill"
        shutil.copytree(source, healthy)
        remove_generated_agents(healthy)
        for label, mutate in malformed.items():
            fresh_copy()
            generate_agents.write_agents(skill)
            mutate()
            if not generate_agents.stale_agents(skill):
                fail(f"agent freshness check accepted a {label} role manifest")
            try:
                generate_agents.render_agents(skill)
            except generate_agents.AgentManifestError:
                pass
            else:
                fail(f"agent generation accepted a {label} role manifest")
            before = snapshot_tree(temporary)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = generate_agents.main([str(healthy), str(skill)])
            if status == 0:
                fail(f"the agent generator succeeded with a {label} role manifest")
            if snapshot_tree(temporary) != before:
                fail(f"the agent generator wrote files before rejecting a {label} role manifest")

        fresh_copy()
        manifest = (source / "harnesses" / "roles.toml").read_text(encoding="utf-8")
        for harness, fields in generate_agents.HARNESS_FIELDS.items():
            for field in fields:
                (skill / "harnesses" / "roles.toml").write_text(
                    without_manifest_field(manifest, f"roles.scout.{harness}", field), encoding="utf-8"
                )
                try:
                    generate_agents.load_roles(skill)
                except generate_agents.AgentManifestError:
                    continue
                fail(f"role manifest accepted a {harness} role without {field!r}")


def without_manifest_field(manifest: str, table: str, field: str) -> str:
    """Drop one key from one table of a role manifest, failing if it is absent."""
    kept, section, removed = [], None, False
    for line in manifest.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif section == table and stripped.split("=", 1)[0].strip() == field:
            removed = True
            continue
        kept.append(line)
    if not removed:
        fail(f"test skill manifest has no {field!r} in [{table}]")
    return "".join(kept)


def main() -> int:
    try:
        skill_names = validate_layout_and_skills()
        validate_repository_references(skill_names)
        validate_implementation_authority_contract()
        validate_standalone_authority_modes()
        validate_tracker_capability_contract()
        validate_reconciliation()
        validate_reconciliation_contract()
        validate_native_agents()
        validate_generated_agents_untracked()
        validate_deep_review()
        validate_agent_generation_contract()
    except CheckFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Repository checks passed for {len(skill_names)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
