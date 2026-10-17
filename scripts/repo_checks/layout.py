"""Repository structure and skill invocation metadata.

Owns the flat stable and experimental skill layout, SKILL.md frontmatter parsing, and
the reviewed user-invoked and model-invoked roster that each skill's Claude, Devin, and
Codex controls must agree with.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import ROOT, SKILLS, fail


RETIRED_BUCKETS = {"engineering", "productivity", "misc", "deprecated", "in-progress"}
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
