#!/usr/bin/env python3
"""Canonical fast repository validation. Installer tests live in test_installers.py."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import io
import json
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
TRIAGE_COMMENT_DISCLAIMER = "> *This was generated by AI during triage.*"
TRUSTED_APPROVAL_PERMISSIONS = {"write", "admin"}
# Explicit non-agent triage states. Reconciliation never overrides them.
HELD_TRIAGE_STATES = {"needs-triage", "needs-info", "ready-for-human", "wontfix"}
USER_INVOKED_SKILLS = {
    "deep-review", "design-review", "evaluate-model", "grill-me",
    "grill-with-docs", "handoff-doc", "implement",
    "improve-codebase-architecture", "reconcile", "setup-skills", "teach",
    "to-questionnaire", "to-spec", "to-tickets", "triage", "wait-what",
    "wayfinder", "write-pr",
}
MODEL_INVOKED_SKILLS = {
    "codebase-design", "diagnosing-bugs", "domain-modeling", "grilling",
    "implementation-review", "prototype", "research", "tdd", "wizard",
    "writing-for-agents",
}
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


def validate_repository_references() -> None:
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
    for directory in skill_directories():
        expected = f"./{directory.relative_to(ROOT).as_posix()}/SKILL.md"
        if expected not in readme:
            fail(f"README.md does not link canonical SKILL.md for {directory.name}")


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


def inverse_patch(patch: str) -> str:
    """The modelled patch that undoes `patch`, standing in for an equal `git patch-id`."""
    return patch[1:] if patch.startswith("-") else "-" + patch


def branch_satisfied_blocker(
    *, blocker: dict, history: list[dict], attributable: frozenset = frozenset(),
    confirmed_later: frozenset = frozenset(),
) -> tuple[str, list[str]]:
    """Model the optional branch-satisfied validation of one open blocker at the current HEAD.

    `history` is every commit reachable from HEAD, oldest first, each with its touched
    paths, `This reverts commit` trailers, and modelled patch. `attributable` holds the
    recorded commits of tickets in the same chain on this branch, and `confirmed_later`
    the later commits the user confirmed. Returns ("satisfied", commits), or the failed
    condition and the commits (or blocker references) involved. Nothing here writes.
    """
    if not blocker["assignees"]:
        return "unclaimed", []
    records = sorted(blocker["records"], key=lambda record: record["created_at"])
    if any(record["author"].get("permission") is None for record in records):
        return "lookup-failed", []
    trusted = [record for record in records if is_trusted_author(record["author"])]
    successes = [record for record in trusted if record["outcome"] == "succeeded"]
    manual = blocker.get("manual") or {}
    confirmed = manual["commits"] if manual.get("verified") and manual.get("confirmed") else None
    if successes:
        latest = successes[-1]
        if any(record["outcome"] != "succeeded" and record["created_at"] > latest["created_at"] for record in trusted):
            return "conflicting-records", list(latest["commits"])
        if len({frozenset(record["commits"]) for record in successes}) > 1 or (
            confirmed is not None and set(confirmed) != set(latest["commits"])
        ):
            return "conflicting-records", sorted({sha for record in successes for sha in record["commits"]})
        commits, named = list(latest["commits"]), latest.get("branch_satisfied", [])
    elif any(record["outcome"] != "succeeded" for record in trusted) and confirmed is not None:
        return "conflicting-records", list(confirmed)
    elif confirmed is not None:
        commits, named = list(confirmed), manual.get("branch_satisfied", [])
    else:
        return "no-evidence", []
    if not commits:
        return "no-evidence", []
    reachable = [entry["sha"] for entry in history]
    missing = [sha for sha in commits if sha not in reachable]
    if missing:
        return "missing-commits", missing
    unnamed = [reference for reference in blocker["open_blockers"] if reference not in named]
    if unnamed:
        return "unrecorded-blocker", [str(reference) for reference in unnamed]
    own = [entry for entry in history if entry["sha"] in commits]
    inverses = {inverse_patch(entry["patch"]) for entry in own}
    reverting = [
        entry["sha"] for entry in history
        if entry["sha"] not in commits and (set(entry["reverts"]) & set(commits) or entry["patch"] in inverses)
    ]
    if reverting:
        return "reverted", reverting
    paths = {path for entry in own for path in entry["paths"]}
    first = reachable.index(own[0]["sha"])
    touching = [
        entry["sha"] for entry in history[first + 1:]
        if entry["sha"] not in commits and paths & set(entry["paths"])
        and entry["sha"] not in attributable and entry["sha"] not in confirmed_later
    ]
    if touching:
        return "later-path-change", touching
    return "satisfied", commits


def implementation_start_gate(
    *, tracker: str, required: set[str], ticket: dict, branch_satisfaction: dict | None = None,
    override: bool = False, held_labels: set = HELD_TRIAGE_STATES,
) -> str:
    """Model /implement's authority and ticket-state start gates: "start" or the stop reason.

    `branch_satisfaction` maps open blockers to their branch-satisfied verdicts. It counts
    only when the tracker defines the optional operation, and substitutes only for the
    blockers it validates. Readiness then follows /reconcile's classification as if those
    blockers were closed, never more broadly. A user override waives only the ticket-state
    gate, never authority or the readiness standalone authority needs.
    """
    if set(missing_tracker_capabilities(tracker)) & required:
        return "stale-tracker"
    satisfied = {
        blocker for blocker, verdict in (branch_satisfaction or {}).items() if verdict == "satisfied"
    } if tracker_defines_branch_satisfied_blockers(tracker) else set()
    remaining = [blocker for blocker in ticket["open_blockers"] if blocker not in satisfied]
    ready = ticket["ready"]
    if ticket["open_blockers"] and not remaining:
        ready = reconcile_ready(ticket, remaining, held_labels)
    authority = resolve_issue_authority(
        tracker=tracker, parent=ticket["parent"], issue=ticket, ready_for_agent=ready,
    )
    if authority not in AUTHORITY_GRANTED:
        return authority or "no-authority"
    if override:
        return "start"
    if ticket["state"] != "OPEN" or remaining or not ready:
        return "not-ready"
    return "start"


def implementation_branch_gate(*, current: str, detached: bool, default: str, created: bool) -> str:
    """Model /implement's branch gate, which runs before the claim: "continue", "branch", or "stop".

    A detached HEAD, such as a harness-provided isolated working copy, branches from the
    current HEAD like the default branch does. An empty name that is not a detached HEAD
    and a failed branch creation stop; no existing branch is ever replaced to make room.
    """
    if detached or current == default:
        return "branch" if created else "stop"
    return "continue" if current else "stop"


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


def pr_ticket_plan(
    *, tracker: str, tickets: dict, commits: list[dict], base: str, default: str,
    auto_close: bool | None, set_confirmed: bool, shared_confirmed: set | None = None,
    rationales: dict | None = None, blocker_overrides: set | None = None,
    branch_relations: dict | None = None,
) -> dict:
    """Model /write-pr's ticket set, commit attribution, and closure handoff over one branch delta.

    Tickets are tracker snapshots keyed by reference (GitHub issue numbers or local
    ticket paths): `record` is a tracker implementation record with its outcome and
    recorded commits, and `manual` holds the observed verification and confirmation.
    Commits are the branch delta in order, with the ticket references their messages carry. A record's
    `branch_satisfied` lists the blockers its run relied on; `branch_relations` maps each such
    (dependent, blocker) relation to its branch-satisfied verdict re-validated at the final head.
    This is a regression model of the prompt workflow, not a tracker adapter.
    """
    shared_confirmed = shared_confirmed or set()
    rationales = rationales or {}
    blocker_overrides = blocker_overrides or set()
    delta = [entry["sha"] for entry in commits]
    plan = {
        "tickets": [], "admission": {}, "attribution": {}, "unresolved": [], "supporting": [], "shared": [],
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
                plan["unresolved"].append(reference)
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
    if not set_confirmed:
        plan["stops"].append(("unconfirmed-ticket-set", None))
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
        settings = {"tracker": "github", "base": "main", "default": "main", "auto_close": True, "set_confirmed": True}
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
    ):
        rejected = plan({101: record}, partial_commits, **rationale_a1)
        if rejected["tickets"] or rejected["unresolved"] != [101] or rejected["close_directives"]:
            fail(f"{label} admitted its ticket or was not listed as an unclear source")
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
        if rejected["supporting"] != ["m1"] or rejected["stops"] or "Closes #103" in rejected["close_directives"]:
            fail(f"the commits of a ticket rejected {label} were not reported as a rationalized supporting change")
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
    if plan(two, two_commits, set_confirmed=False)["stops"] != [("unconfirmed-ticket-set", None)]:
        fail("drafting proceeded before the user confirmed the final ticket set")

    single = plan({101: ticket(("a1",))}, [commit("a1", 101)])
    expected_single = {
        "tickets": [101], "references": ["#101"], "close_directives": ["Closes #101"],
        "handoff": ["verify-closure"], "reconcile": [101], "stops": [],
    }
    if {key: single[key] for key in expected_single} != expected_single:
        fail("a single-ticket branch changed its close directive or handoff shape")
    if plan({101: ticket()}, [commit("a1", 101)], rationales={"a1": "Unclear."})["stops"] != [("no-admitted-ticket", None)]:
        fail("drafting proceeded with no admitted ticket instead of asking for the governing source")

    # Every unresolved blocker of every admitted ticket must be in the set, which validates chains.
    blocked = {101: ticket(("a1",)), 102: ticket(("b1",), blockers=(101, 90)), 90: ticket()}
    blocked_commits = [commit("a1", 101), commit("b1", 102)]
    outside = plan(blocked, blocked_commits)
    if outside["stops"] != [("blocker-outside-set", (102, 90))] or outside["close_directives"]:
        fail("a ticket with an unresolved blocker outside the confirmed set did not stop drafting")
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
            set_confirmed=True, branch_relations=relations(history), **options,
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


def validate_multi_ticket_pr_contract() -> None:
    """Pin the multi-ticket /write-pr, tracker handoff, and sequential /implement wording."""

    def read(relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    write_pr = read("skills/write-pr/SKILL.md")
    for required in (
        "**Ticket set**: the tickets the branch delta implements, confirmed by the user before drafting",
        "(a) a tracker implementation record of a successful closeout, such as a completed `/implement` closeout, "
        "whose complete recorded commit set is present in the branch delta",
        "verification output this workflow observes, and explicit user confirmation",
        "A stop report, a failed or partial record, or a closeout with any recorded commit missing from the branch delta",
        "as does a commit-message reference alone; neither is admissible evidence",
        "without that confirmation, the candidate is not admitted",
        "as an unclear source for the user to resolve, include, or exclude",
        "Report a commit attributed to more than one ticket and ask the user to confirm that attribution explicitly",
        "Report every unattributed commit as a supporting change with a stated rationale",
        "every unresolved blocker must itself be in the ticket set",
        "merging would resolve a dependent before its blocker",
        "report the override in the body",
        "ask the user to confirm the final ticket set before drafting",
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
    for retired in ("required ticket or issue identifier", "list them and ask the user to choose"):
        if retired in write_pr:
            fail(f"/write-pr still assumes one ticket per branch: {retired!r}")

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


def validate_native_agents(root: Path = ROOT) -> None:
    """Every role manifest renders each harness agent in memory, with one owner per agent name."""
    owners: dict[str, str] = {}
    for skill in generate_agents.agent_skill_directories(root):
        harnesses = sorted(path.name for path in (skill / "harnesses").iterdir() if path.is_dir())
        unsupported = sorted(set(harnesses) - set(generate_agents.HARNESSES))
        if unsupported:
            fail(f"{skill.relative_to(root).as_posix()}/harnesses: unsupported harness directories {', '.join(unsupported)}")
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
                if "sandbox_mode" in parsed:
                    fail(f"{skill.name}: generated Codex agent {role.agent_name} contains unsupported sandbox_mode")
                if parsed.get("name") != role.agent_name or parsed.get("developer_instructions") != role.body:
                    fail(f"{skill.name}: generated Codex agent {role.agent_name} does not round-trip its name and body")
        for path in (skill / "harnesses" / "codex").glob("*.toml"):
            if "sandbox_mode" in tomllib.loads(path.read_text(encoding="utf-8")):
                fail(f"{path.relative_to(root).as_posix()}: generated Codex agent contains unsupported sandbox_mode")
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


def validate_deep_review_role_contract(
    catalog: list[str], roles: dict[str, generate_agents.Role], contract: str, lenses: dict[str, str],
) -> None:
    """Prove the role check rejects each way a lens can lose, gain, or share its native scout."""
    def with_body(name: str, body: str) -> dict[str, generate_agents.Role]:
        return {**roles, name: dataclasses.replace(roles[name], body=body)}

    drifted = {**DEEP_REVIEW_ROLES["scout-conventions"]["claude"], "model": "claude-sonnet-5-5"}
    cases = {
        "a catalog lens without a role": (
            [*catalog, "extra"], roles, {**lenses, "extra": "# Extra Lens\n\nUnclaimed."},
        ),
        "a lens embedded by two roles": (
            catalog, with_body("validator-static", roles["validator-static"].body + "\n" + lenses["bugs"]), lenses,
        ),
        "a scout without the common contract": (catalog, with_body("scout-docs", lenses["docs"] + "\n"), lenses),
        "a scout without its lens": (catalog, with_body("scout-docs", contract + "\n"), lenses),
        "a scout with another lens": (
            catalog, with_body("scout-docs", f"{contract}\n\n{lenses['docs']}\n\n{lenses['history']}\n"), lenses,
        ),
        "a structural scout without the structural lens": (catalog, with_body("structural", contract + "\n"), lenses),
        "drifted harness fields": (
            catalog,
            {**roles, "scout-conventions": dataclasses.replace(
                roles["scout-conventions"], harnesses={**roles["scout-conventions"].harnesses, "claude": drifted},
            )},
            lenses,
        ),
        "a leftover generic scout role": (
            catalog, {**roles, "scout": dataclasses.replace(roles["validator-static"], name="scout", body=contract + "\n")}, lenses,
        ),
    }
    for label, (mutated_catalog, mutated_roles, mutated_lenses) in cases.items():
        if not deep_review_role_problems(mutated_catalog, mutated_roles, contract, mutated_lenses):
            fail(f"the deep-review role check accepted {label}")


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


def validate_deep_review_access_contract(skill: Path) -> None:
    """Reject removed or weakened prohibitions, role sandboxes, and missing inheritance guidance."""
    documents = {relative: (skill / relative).read_text(encoding="utf-8") for relative in DEEP_REVIEW_ACCESS_RULES}
    problems = deep_review_access_problems(documents)
    if problems:
        fail(problems[0])
    for relative, rules in DEEP_REVIEW_ACCESS_RULES.items():
        for rule in rules:
            for replacement in ("", rule.replace("no ", "optional ").replace("never ", "sometimes ")):
                if replacement == rule:
                    continue
                mutated = {**documents, relative: documents[relative].replace(rule, replacement)}
                if not deep_review_access_problems(mutated):
                    fail(f"the access check accepted a removed or weakened {relative} contract")
    for mechanism, expected in DEEP_REVIEW_CODEX_ACCESS_CELLS.items():
        for sandbox in ("read-only", "workspace-write"):
            mutated = {**documents, "SKILL.md": documents["SKILL.md"].replace(expected, f"Enforced by the `{sandbox}` sandbox.")}
            if not deep_review_access_problems(mutated):
                fail(f"the access check accepted a role-specific Codex sandbox for {mechanism}")


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


def validate_deep_review_audience_contract(skill: Path) -> None:
    documents = {path.relative_to(skill).as_posix(): path.read_text(encoding="utf-8")
                 for path in (skill / "references").glob("*.md")}
    documents["protocol.md"] = (skill / "protocol.md").read_text(encoding="utf-8")
    problems = deep_review_audience_problems(documents)
    if problems:
        fail(problems[0])
    # Mutation checks make each routing case observable, including explicit human.
    for guide in ("references/review-tone.md", "references/review-tone-agent.md"):
        mutated = {relative: content for relative, content in documents.items() if relative != guide}
        if not deep_review_audience_problems(mutated):
            fail(f"the audience check accepted a missing {guide}")
    for selection, audience, guide in (
        ("unspecified", "human", "review-tone.md"),
        ("`human`", "human", "review-tone.md"),
        ("`agent`", "agent", "review-tone-agent.md"),
    ):
        row = f"| {selection} | `{audience}` | `{guide}` |"
        for replacement in ("", row.replace(f"`{guide}`", "`missing-tone.md`"),
                            row.replace(f"| `{audience}` |", "| `other` |")):
            mutated = {**documents, "references/pr-review-comments.md":
                       documents["references/pr-review-comments.md"].replace(row, replacement)}
            if not deep_review_audience_problems(mutated):
                fail(f"the audience check accepted an invalid {selection} route")
    for relative, rules in DEEP_REVIEW_PUBLICATION_RULES.items():
        for rule in rules:
            mutated = {**documents, relative: documents[relative].replace(rule, "")}
            if not deep_review_audience_problems(mutated):
                fail(f"the audience check accepted a removed {relative} publication rule")


def validate_deep_review() -> None:
    """Deep review keeps one harness-neutral copy of its sources and its pinned role limits."""
    skill = SKILLS / "deep-review"
    validate_deep_review_access_contract(skill)
    validate_deep_review_audience_contract(skill)
    roles = {role.name: role for role in generate_agents.load_roles(skill)}
    catalog = deep_review_catalog((skill / "protocol.md").read_text(encoding="utf-8"))
    contract = reviewer_text(skill / "reviewers" / "SCOUT.md")
    lenses = {path.stem: reviewer_text(path) for path in (skill / "reviewers" / "lenses").glob("*.md")}
    problems = deep_review_role_problems(catalog, roles, contract, lenses)
    if problems:
        fail(problems[0])
    validate_deep_review_role_contract(catalog, roles, contract, lenses)

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


def markdown_agent_fields(text: str) -> dict[str, object]:
    """Read the frontmatter the generator writes for Devin and Claude Code agents."""
    lines = text.split("\n---\n", 1)[0].removeprefix("---\n").splitlines()
    fields: dict[str, object] = {}
    key = None
    for line in lines:
        if line.startswith("#"):
            continue
        if line.startswith("  - "):
            fields[key].append(json.loads(line[4:]) if line[4:].startswith('"') else line[4:])
            continue
        key, _, value = line.partition(": ")
        key = key.removesuffix(":")
        fields[key] = (json.loads(value) if value.startswith('"') else value) if value else []
    return fields


def validate_deep_review_generation() -> None:
    """Every deep-review agent renders with its pinned fields, regenerates idempotently, and replaces the generic scout."""
    obsolete = {
        "harnesses/codex/deep-review-scout.toml",
        "harnesses/devin/deep-review-scout/AGENT.md",
        "harnesses/claude/deep-review-scout.md",
    }
    with tempfile.TemporaryDirectory(prefix="skills-deep-review-agents-") as temp_value:
        skill = Path(temp_value) / "deep-review"
        shutil.copytree(SKILLS / "deep-review", skill, ignore=shutil.ignore_patterns(*generate_agents.HARNESSES))
        for relative in obsolete:
            (skill / relative).parent.mkdir(parents=True, exist_ok=True)
            (skill / relative).write_text("generated by the former generic scout role\n", encoding="utf-8")
        generate_agents.write_agents(skill)
        leftovers = sorted(relative for relative in obsolete if (skill / relative).exists())
        if leftovers:
            fail(f"regenerating deep-review agents kept the obsolete generic scout output: {', '.join(leftovers)}")
        for role, harnesses in DEEP_REVIEW_ROLES.items():
            name = f"deep-review-{role}"
            codex = tomllib.loads((skill / "harnesses" / "codex" / f"{name}.toml").read_text(encoding="utf-8"))
            devin = markdown_agent_fields((skill / "harnesses" / "devin" / name / "AGENT.md").read_text(encoding="utf-8"))
            claude = markdown_agent_fields((skill / "harnesses" / "claude" / f"{name}.md").read_text(encoding="utf-8"))
            for harness, rendered in (("codex", codex), ("devin", devin), ("claude", claude)):
                expected = {"name": name, **harnesses[harness]}
                if {key: rendered.get(key) for key in expected} != expected:
                    fail(f"generated {harness} agent {name} does not render its pinned name, model, effort, and tools")
        generated = snapshot_tree(skill / "harnesses")
        expected_files = {f"{relative.removeprefix('harnesses/')}" for relative in generate_agents.render_agents(skill)}
        if set(generated) != expected_files | {"roles.toml"} or len(expected_files) != 3 * len(DEEP_REVIEW_ROLES):
            fail("deep-review agent generation does not produce exactly one agent per role for every harness")
        if generate_agents.write_agents(skill) or snapshot_tree(skill / "harnesses") != generated:
            fail("regenerating unchanged deep-review sources changed generated agent files")


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
        for relative, content in rendered.items():
            if relative.startswith("harnesses/codex/"):
                parsed = tomllib.loads(content)
                if set(parsed) != {"name", "description", "model", "model_reasoning_effort", "developer_instructions"}:
                    fail("generated Codex agents must contain only identity, model, effort, and reviewer instructions")
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
        generate_agents.write_agents(skill)
        codex_scout = skill / "harnesses" / "codex" / "agent-skill-scout.toml"
        codex_scout.write_text('sandbox_mode = "read-only"\n' + codex_scout.read_text(encoding="utf-8"), encoding="utf-8")
        fixtures = temporary / "tests" / "fixtures"
        fixtures.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, fixtures / "agent-skill")
        try:
            validate_native_agents(temporary)
        except CheckFailure as error:
            if "unsupported sandbox_mode" not in str(error):
                raise
        else:
            fail("the repository check accepted sandbox_mode in a generated Codex agent")

        fresh_copy()
        manifest = (source / "harnesses" / "roles.toml").read_text(encoding="utf-8")
        sandbox_manifest = manifest.replace(
            "[roles.scout.codex]\n", '[roles.scout.codex]\nsandbox_mode = "read-only"\n',
        )
        (skill / "harnesses" / "roles.toml").write_text(sandbox_manifest, encoding="utf-8")
        errors = io.StringIO()
        before = snapshot_tree(temporary)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            status = generate_agents.main([str(healthy), str(skill)])
        if status == 0 or "unsupported fields sandbox_mode" not in errors.getvalue():
            fail("the agent generator must reject Codex sandbox_mode as an unsupported field")
        if snapshot_tree(temporary) != before:
            fail("the agent generator wrote files before rejecting an unsupported Codex sandbox")
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


PORTFOLIO_PROJECT_URL = "https://github.com/users/octo/projects/7"


class FakePortfolio:
    """An in-memory GitHub Project and repositories behind the helper's GraphQL seam."""

    def __init__(self) -> None:
        self.project = {"id": "P7", "title": "Development portfolio", "url": PORTFOLIO_PROJECT_URL,
                        "closed": False, "viewerCanUpdate": True}
        self.repositories = ["octo/app", "octo/lib"]
        self.content: dict[str, dict] = {}
        self.members: list[dict] = []
        self.mutations: list[str] = []
        self.faults: dict[str, object] = {}
        for repository, kind, number, state in (
            ("octo/app", "issues", 1, "OPEN"), ("octo/app", "issues", 2, "OPEN"),
            ("octo/app", "issues", 3, "CLOSED"), ("octo/app", "pull", 4, "OPEN"),
            ("octo/app", "pull", 5, "MERGED"), ("octo/lib", "issues", 1, "OPEN"),
            ("octo/lib", "issues", 2, "OPEN"), ("octo/lib", "issues", 3, "OPEN"),
            ("octo/other", "issues", 9, "OPEN"),
        ):
            url = f"https://github.com/{repository}/{kind}/{number}"
            self.content[url] = {"id": f"C:{repository}:{number}", "number": number, "title": f"Item {number}",
                                 "url": url, "repository": repository, "kind": kind, "state": state}
        for url, archived in (("https://github.com/octo/app/issues/1", False),
                              ("https://github.com/octo/app/issues/3", False),
                              ("https://github.com/octo/lib/issues/3", True),
                              ("https://github.com/octo/other/issues/9", False)):
            self.members.append({"type": "ISSUE", "isArchived": archived, "url": url})
        self.members.append({"type": "DRAFT_ISSUE", "isArchived": False, "url": None})

    def add_opaque_member(self, url: str) -> None:
        """A member whose content the viewer cannot read, so GitHub returns it without content."""
        self.members.append({"type": "REDACTED", "isArchived": False, "url": url, "opaque": True})

    def missing_urls(self) -> list[str]:
        members = {member["url"] for member in self.members}
        return sorted(url for url, item in self.content.items()
                      if item["state"] == "OPEN" and item["repository"] in self.repositories and url not in members)

    @staticmethod
    def page(nodes: list, after: str | None) -> dict:
        start = int(after or 0)
        end = start + 2
        return {"totalCount": len(nodes), "nodes": nodes[start:end],
                "pageInfo": {"hasNextPage": end < len(nodes), "endCursor": str(end) if end < len(nodes) else None}}

    def __call__(self, query: str, variables: dict) -> dict:
        operation = re.match(r"\s*(?:query|mutation) (\w+)", query).group(1)
        fault = self.faults.get(operation)
        if fault is not None:
            response = fault(variables) if callable(fault) else fault
            if response is not None:
                return response
        if operation == "Project":
            found = "user(login" in query and variables == {"login": "octo", "number": 7}
            return {"data": {"owner": {"projectV2": dict(self.project) if found else None}}}
        if operation == "ProjectRepositories":
            nodes = [{"nameWithOwner": name} for name in self.repositories]
            return {"data": {"node": {"connection": self.page(nodes, variables["after"])}}}
        if operation == "ProjectItems":
            nodes = []
            for member in self.members:
                if member["isArchived"] and "ARCHIVED," not in query:
                    continue  # GitHub hides archived items unless archivedStates includes them.
                item = None if member.get("opaque") else self.content.get(member["url"])
                content = {"url": item["url"], "repository": {"nameWithOwner": item["repository"]}} if item else None
                nodes.append({"type": member["type"], "isArchived": member["isArchived"], "content": content})
            return {"data": {"node": {"connection": self.page(nodes, variables["after"])}}}
        if operation in {"OpenIssues", "OpenPullRequests"}:
            repository = f"{variables['owner']}/{variables['name']}"
            if repository not in self.repositories:
                return {"data": {"repository": None}}
            kind = "issues" if operation == "OpenIssues" else "pull"
            nodes = [{key: item[key] for key in ("id", "number", "title", "url")} for item in self.content.values()
                     if item["repository"] == repository and item["kind"] == kind
                     and (item["state"] == "OPEN" or "states: OPEN" not in query)]
            return {"data": {"repository": {"connection": self.page(nodes, variables["after"])}}}
        if operation == "ContentState":
            item = next((item for item in self.content.values() if item["id"] == variables["id"]), None)
            return {"data": {"node": {"state": item["state"], "url": item["url"]} if item else None}}
        if operation == "AddProjectItem" and "addProjectV2ItemById" in query and variables["project"] == "P7":
            self.mutations.append(variables["content"])
            url = next(url for url, item in self.content.items() if item["id"] == variables["content"])
            if all(member["url"] != url for member in self.members):
                self.members.append({"type": "ISSUE", "isArchived": False, "url": url})
            return {"data": {"addProjectV2ItemById": {"item": {"id": f"I:{url}"}}}}
        raise AssertionError(f"unexpected portfolio-sync operation {operation}")


def validate_portfolio_sync() -> None:
    skill = SKILLS / "experimental" / "portfolio-sync"
    helper_path = skill / "scripts" / "portfolio_sync.py"
    source = helper_path.read_text(encoding="utf-8")
    if re.findall(r"\bmutation (\w+)\(", source) != ["AddProjectItem"]:
        fail("portfolio-sync: the helper must send exactly one named mutation, AddProjectItem")
    project_writes = set(re.findall(r"\b(?:add|update|delete|archive|unarchive|clear|convert|remove)\w*ProjectV2\w*", source))
    if project_writes != {"addProjectV2ItemById"}:
        fail(f"portfolio-sync: the helper may only add Project items, found {sorted(project_writes)}")
    portfolio = (SKILLS / "experimental" / "portfolio" / "SKILL.md").read_text(encoding="utf-8")
    if "`/portfolio-sync`" not in portfolio:
        fail("portfolio: must recommend `/portfolio-sync` for open work absent from the Project")
    if re.search(r"portfolio_sync\.py|--apply|addProjectV2ItemById|item-add", portfolio):
        fail("portfolio: must stay read-only and must not run the synchronization helper")

    spec = importlib.util.spec_from_file_location("portfolio_sync", helper_path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper  # dataclasses resolve annotations through sys.modules
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(helper)
    finally:
        sys.dont_write_bytecode = previous

    def sync(fake: FakePortfolio, apply: bool = False, plan: str | None = None,
             url: str = PORTFOLIO_PROJECT_URL) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = helper.run(url, apply, plan, fake, out, err)
        return code, out.getvalue(), err.getvalue()

    def plan_id(output: str) -> str:
        match = re.search(r"^Plan: ([0-9a-f]{12})$", output, re.MULTILINE)
        if match is None:
            fail("portfolio-sync: a dry run with missing items must print its plan identifier")
        return match.group(1)

    fake = FakePortfolio()
    expected = fake.missing_urls()
    code, output, _ = sync(fake)
    reported = sorted(re.findall(r"^    (https://\S+)$", output, re.MULTILINE))
    if code != 0 or reported != expected or fake.mutations:
        fail(f"portfolio-sync: dry run must report exactly {expected} without changes, got {reported}")
    if "issues/3" in "".join(reported) or "pull/5" in "".join(reported):
        fail("portfolio-sync: closed issues and merged pull requests must not be imported")
    for note in ("1 archived", "1 draft", "0 inaccessible", "octo/other"):
        if note not in output:
            fail(f"portfolio-sync: dry run must report coverage note {note!r}")
    authorized = plan_id(output)

    for stale in (None, "000000000000"):
        code, _, err = sync(fake, apply=True, plan=stale)
        if code != 1 or fake.mutations or "no longer matches" not in err:
            fail("portfolio-sync: applying without the current authorized plan must refuse before any change")

    code, output, _ = sync(fake, apply=True, plan=authorized)
    added = sorted(re.findall(r"^Added (https://\S+)$", output, re.MULTILINE))
    if code != 0 or added != expected or len(fake.mutations) != len(expected) or "Verified in the Project" not in output:
        fail(f"portfolio-sync: apply must add and verify exactly the authorized plan, got {added}")

    for repeat in ({}, {"apply": True, "plan": authorized}):
        code, output, _ = sync(fake, **repeat)
        if code != 0 or "In sync" not in output or len(fake.mutations) != len(expected):
            fail(f"portfolio-sync: a repeated run {repeat or 'dry run'} must be a no-op")

    def failing(name: str, setup, apply: bool = True, status: int = 1, url: str = PORTFOLIO_PROJECT_URL) -> None:
        fake = FakePortfolio()
        _, output, _ = sync(fake)
        setup(fake)
        try:
            code, output, err = sync(fake, apply=apply, plan=plan_id(output), url=url)
        except AssertionError as error:
            fail(f"portfolio-sync: {name} must fail cleanly, got {error}")
        if code != status or fake.mutations or "Plan:" in output or "In sync" in output or not err.startswith("error:"):
            fail(f"portfolio-sync: {name} must fail before any change and without a conclusion")

    def truncated(fake: FakePortfolio) -> None:
        fake.faults["ProjectItems"] = lambda variables: (
            None if variables["after"] else {"data": {"node": {"connection": {
                "totalCount": 9, "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}})

    def unreadable_node(fake: FakePortfolio) -> None:
        fake.faults["ProjectRepositories"] = {"data": {"node": {"connection": {
            "totalCount": 1, "nodes": [None], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}

    failing("an incomplete Project item read", truncated)
    failing("an unreadable linked repository entry", unreadable_node)

    def endless(next_cursor):
        calls = iter(range(20))

        def respond(variables: dict) -> dict:
            if next(calls, None) is None:
                raise AssertionError("pagination never stopped")
            return {"data": {"node": {"connection": {
                "totalCount": 2, "nodes": [{"nameWithOwner": "octo/app"}] if next_cursor(variables) == "same" else [],
                "pageInfo": {"hasNextPage": True, "endCursor": next_cursor(variables)}}}}}
        return respond

    failing("a repeated pagination cursor", lambda fake: fake.faults.update(
        ProjectRepositories=endless(lambda variables: "same")))
    failing("an empty page that claims more pages", lambda fake: fake.faults.update(
        ProjectRepositories=endless(lambda variables: str(int(variables["after"] or 0) + 1))))
    failing("an unavailable repository", lambda fake: fake.faults.update(OpenIssues={"data": {"repository": None}}))
    failing("a GraphQL error", lambda fake: fake.faults.update(
        OpenPullRequests={"data": None, "errors": [{"message": "Resource not accessible by integration"}]}))
    failing("a Project without linked repositories", lambda fake: setattr(fake, "repositories", []))
    failing("a Project that is not found", lambda fake: None, url="https://github.com/users/octo/projects/8")
    failing("an invalid Project URL", lambda fake: None, status=2, url="https://github.com/octo/app")
    for name, state in (("a read-only Project", {"viewerCanUpdate": False}), ("a closed Project", {"closed": True})):
        fake = FakePortfolio()
        _, output, _ = sync(fake)
        fake.project.update(state)
        code, _, err = sync(fake, apply=True, plan=plan_id(output))
        if code != 1 or fake.mutations or "nothing was added" not in err:
            fail(f"portfolio-sync: applying to {name} must refuse before any change")

    fake = FakePortfolio()
    _, output, _ = sync(fake)
    calls = iter(range(len(expected)))
    fake.faults["AddProjectItem"] = lambda variables: (
        {"data": None, "errors": [{"message": "secondary rate limit"}]} if next(calls) == 1 else None)
    code, output, err = sync(fake, apply=True, plan=plan_id(output))
    if code != 1 or len(fake.mutations) != 1 or "Added 1 of" not in output or "rerun the dry run" not in err:
        fail("portfolio-sync: a failed add must stop and report the partial result")
    code, output, _ = sync(fake)
    if code != 0 or len(re.findall(r"^    https://", output, re.MULTILINE)) != len(expected) - 1:
        fail("portfolio-sync: a dry run after a partial apply must plan exactly the remainder")

    # An item can close after the plan was read; the helper rechecks each one just before adding it.
    fake = FakePortfolio()
    _, output, _ = sync(fake)
    closing = fake.missing_urls()[1]

    def close_after_first_add(variables: dict) -> None:
        fake.content[closing]["state"] = "CLOSED"

    fake.faults["AddProjectItem"] = close_after_first_add
    code, output, err = sync(fake, apply=True, plan=plan_id(output))
    if code != 1 or len(fake.mutations) != 1 or "Added 1 of" not in output or "no longer open (CLOSED)" not in err:
        fail("portfolio-sync: an item that closes during application must stop the add before it")
    code, output, _ = sync(fake)
    remaining = sorted(re.findall(r"^    (https://\S+)$", output, re.MULTILINE))
    if code != 0 or closing in remaining or len(remaining) != len(expected) - 2:
        fail("portfolio-sync: a dry run after a closure must plan only the still-open remainder")

    # An inaccessible member could be any open item, so a readable-only comparison proves no absence.
    fake = FakePortfolio()
    fake.add_opaque_member(expected[0])
    for apply in (False, True):
        code, output, err = sync(fake, apply=apply, plan=authorized)
        if (code != 1 or fake.mutations or "Plan:" in output or "In sync" in output
                or "  ? " not in output or "absence is not proven" not in err):
            fail("portfolio-sync: inaccessible Project items must leave candidates unverified and refuse a plan")
    fake = FakePortfolio()
    _, output, _ = sync(fake)
    sync(fake, apply=True, plan=plan_id(output))
    fake.add_opaque_member("https://github.com/octo/private/issues/1")
    code, output, _ = sync(fake)
    if code != 0 or "In sync" not in output or "1 inaccessible" not in output:
        fail("portfolio-sync: every open item matching a readable member is in sync despite inaccessible items")


def main() -> int:
    try:
        skill_names = validate_layout_and_skills()
        validate_repository_references()
        validate_implementation_authority_contract()
        validate_implementation_review_routing_contract()
        validate_implementation_working_copy_contract()
        validate_standalone_authority_modes()
        validate_tracker_capability_contract()
        validate_reconciliation()
        validate_reconciliation_contract()
        validate_pr_ticket_plan()
        validate_multi_ticket_pr_contract()
        validate_branch_satisfied_blockers()
        validate_native_agents()
        validate_generated_agents_untracked()
        validate_deep_review()
        validate_deep_review_generation()
        validate_agent_generation_contract()
        validate_portfolio_sync()
    except CheckFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Repository checks passed for {len(skill_names)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
