"""Repository references: retired files, stale names, prose style, and relative links.

This module holds the stale-reference literals the scanner matches, so it is the one
script the scanner exempts from its own stale-name and upstream-identity rules.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from .common import ROOT, fail
from .layout import skill_directories


TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".sh", ".ps1", ".toml"}
RETIRED_FILES = {
    "CLAUDE.md",
    "CHANGELOG.md",
    "package.json",
    "package-lock.json",
    ".github/workflows/release.yml",
    "scripts/sync-plugin-version.mjs",
    "scripts/link-skills.sh",
    "skills/experimental/portfolio-sync",
    "scripts/repo_checks/scenarios/portfolio_sync.py",
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
    # The artifact `/to-spec` produces is a spec. A file that must name the old terms to migrate them is listed below.
    "legacy PRD terminology": re.compile(r"\bPRDs?\b|to[-_]prd", re.IGNORECASE),
}
# The former names of the spec, as the `setup-skills` migration mode must name them to detect and rewrite them.
LEGACY_SPEC_TERMS = ("PRD", "PRD.md", "to-prd")
# Former stable skill names mapped to their current names. A former name is a stale
# reference; the installer tests seed installations under it to prove reconciliation.
RENAMED_SKILLS = {"code-review": "implementation-review"}
for _former in RENAMED_SKILLS:
    STALE_PATTERNS[f"renamed skill {_former}"] = re.compile(rf"(?<![\w-]){re.escape(_former)}(?![\w-])")
# Removed experimental skills. The installer tests seed installations under these names to prove reconciliation.
RETIRED_EXPERIMENTAL_SKILLS = ("portfolio-sync",)
for _retired in RETIRED_EXPERIMENTAL_SKILLS:
    STALE_PATTERNS[f"retired skill {_retired}"] = re.compile(r"[-_]".join(map(re.escape, _retired.split("-"))))
INTENTIONAL_STALE_REFERENCE_FILES = {
    "install.sh", "install.ps1", "scripts/repo_checks/references.py",
    # Migration mode names the legacy spec terms so it can detect and rewrite them in a target repository.
    "skills/setup-skills/SKILL.md",
    # A historical verification record pinned to an earlier baseline, so it keeps the names it recorded.
    "docs/verification/issue-128.md",
}


def iter_repository_text() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore", ".gitattributes"}:
            paths.append(path)
    return paths


def first_stale_reference(text: str) -> tuple[str, int] | None:
    """The label and 1-based line of the first stale pattern in `text`, or None."""
    for label, pattern in STALE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            return label, text.count("\n", 0, match.start()) + 1
    return None


def validate_stale_pattern_guard() -> None:
    """Prove the scanner rejects each legacy spec term and accepts the spec convention."""
    for stale in ("Create PRD.md under .scratch", "run /to-prd now", "the PRD is approved", "see to_prd", "write the prd", "two PRDs"):
        found = first_stale_reference(stale)
        if found is None or found[0] != "legacy PRD terminology":
            fail(f"stale-pattern guard: {stale!r} must be rejected as legacy PRD terminology, got {found!r}")
    for fine in ("Spec: Billing export", ".scratch/feature/spec.md", "run /to-spec now", "the specification is approved", "a prdigy"):
        found = first_stale_reference(fine)
        if found is not None:
            fail(f"stale-pattern guard: {fine!r} must be accepted, got {found!r}")


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
            stale = first_stale_reference(text)
            if stale:
                label, line = stale
                fail(f"{relative}:{line}: stale {label} reference")
        if relative not in {"README.md", "scripts/repo_checks/references.py"} and re.search(r"mattpocock/skills", text, re.IGNORECASE):
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
