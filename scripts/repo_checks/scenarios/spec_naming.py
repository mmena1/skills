"""The spec naming group: one convention for naming the artifact `/to-spec` produces."""

from __future__ import annotations

from ..common import ROOT, SKILLS, fail
from ..references import LEGACY_SPEC_TERMS


REMOTE_TITLE = "`Spec: <name>`"
LOCAL_PATH = "`.scratch/<feature-slug>/spec.md`"
# The tracker-independent skills state both halves of the convention. Each tracker seed states the half for its tracker.
CONVENTION_DOCUMENTS = {
    SKILLS / "to-spec" / "SKILL.md": (REMOTE_TITLE, LOCAL_PATH),
    SKILLS / "design-review" / "SKILL.md": (REMOTE_TITLE, LOCAL_PATH),
    SKILLS / "to-tickets" / "SKILL.md": (REMOTE_TITLE, LOCAL_PATH),
    SKILLS / "setup-skills" / "issue-tracker-github.md": (REMOTE_TITLE,),
    SKILLS / "setup-skills" / "issue-tracker-local.md": (LOCAL_PATH,),
}
LOCAL_SEED = SKILLS / "setup-skills" / "issue-tracker-local.md"
LOCAL_PUBLISH_HEADING = '## When a skill says "publish to the issue tracker"'
SETUP_SKILL = SKILLS / "setup-skills" / "SKILL.md"
MIGRATION_PINS = (
    "legacy spec terminology",
    "spec naming convention",
    "renames nothing in the target repository",
)


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end >= 0 else len(text)]


def validate_spec_naming_contract() -> None:
    for path, pins in CONVENTION_DOCUMENTS.items():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for required in pins:
            if required not in text:
                fail(f"{relative}: must state the spec naming convention {required}")

    publish = _section(LOCAL_SEED.read_text(encoding="utf-8"), LOCAL_PUBLISH_HEADING)
    if "spec.md" not in publish or "issues/<NN>-<slug>.md" not in publish:
        fail(
            f"{LOCAL_SEED.relative_to(ROOT).as_posix()}: the publish operation must distinguish a spec (spec.md) "
            "from an implementation issue (issues/<NN>-<slug>.md)"
        )

    setup = SETUP_SKILL.read_text(encoding="utf-8")
    for term in LEGACY_SPEC_TERMS:
        if f"`{term}`" not in setup:
            fail(f"{SETUP_SKILL.relative_to(ROOT).as_posix()}: migration mode must name the legacy spec term `{term}`")
    for required in MIGRATION_PINS:
        if required not in setup:
            fail(f"{SETUP_SKILL.relative_to(ROOT).as_posix()}: migration mode must state {required!r}")
