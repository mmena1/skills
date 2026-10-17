"""Native reviewer agents: in-memory rendering of every role manifest and generated-file ownership.

Role manifests and reviewer bodies are the only source (ADR-0001); generated agent
files are ignored install artifacts that Git must not track.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import generate_agents

from .common import ROOT, fail


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
