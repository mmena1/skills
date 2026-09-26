#!/usr/bin/env python3
"""Generate native reviewer agent files from each skill's role manifest.

A skill that ships native reviewer agents declares them in
`harnesses/roles.toml`. This generator writes every harness's complete agent
file under `harnesses/<harness>/`. Generated files are committed and never
hand-edited; `python scripts/check.py` fails when they are stale.

Usage: python scripts/generate_agents.py [skill-directory ...]
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("harnesses") / "roles.toml"
HARNESSES = ("codex", "devin", "claude")
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PLAIN_SCALAR = re.compile(r"[A-Za-z][A-Za-z0-9._/-]*")
YAML_KEYWORDS = {"true", "false", "null", "yes", "no", "on", "off", "y", "n"}
HEADER = "Generated from harnesses/roles.toml by scripts/generate_agents.py. Do not edit."
HARNESS_FIELDS = {
    "codex": {"model": str, "model_reasoning_effort": str, "sandbox_mode": str},
    "devin": {"model": str, "allowed-tools": list},
    "claude": {"model": str, "tools": list, "effort": str},
}
CODEX_SANDBOX_MODES = {"read-only", "workspace-write", "danger-full-access"}
CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


class AgentManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Role:
    name: str
    agent_name: str
    description: str
    body: str
    harnesses: dict[str, dict[str, object]]


def agent_skill_directories(root: Path = ROOT) -> list[Path]:
    """Every skill or fixture skill that ships native agents or harness files."""
    candidates = [
        *(root / "skills").glob("*/harnesses"),
        *(root / "skills" / "experimental").glob("*/harnesses"),
        *(root / "tests" / "fixtures").glob("*/harnesses"),
    ]
    return sorted({path.parent for path in candidates if path.is_dir()}, key=lambda path: path.as_posix())


def _require_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise AgentManifestError(f"{where} must be a non-empty single-line string")
    return value


def _read_body(skill: Path, paths: object, where: str) -> str:
    if not isinstance(paths, list) or not paths:
        raise AgentManifestError(f"{where} must be a non-empty list of skill-relative paths")
    parts = []
    skill_root = skill.resolve()
    for entry in paths:
        relative = _require_string(entry, where)
        source = (skill / relative).resolve()
        if not source.is_relative_to(skill_root) or source.is_relative_to(skill_root / "harnesses"):
            raise AgentManifestError(f"{where}: {relative!r} must name a reviewer body inside the skill, outside harnesses/")
        if not source.is_file():
            raise AgentManifestError(f"{where}: reviewer body {relative!r} does not exist")
        text = source.read_text(encoding="utf-8").replace("\r\n", "\n")
        if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", text):
            raise AgentManifestError(f"{where}: reviewer body {relative!r} contains control characters")
        parts.append(text.strip("\n"))
    return "\n\n".join(parts) + "\n"


def _validate_harness(harness: str, table: object, where: str) -> dict[str, object]:
    if not isinstance(table, dict):
        raise AgentManifestError(f"{where} must be a table")
    allowed = HARNESS_FIELDS[harness]
    unknown = sorted(set(table) - set(allowed))
    if unknown:
        raise AgentManifestError(f"{where}: unsupported fields {', '.join(unknown)}")
    if "model" not in table:
        raise AgentManifestError(f"{where}: missing required 'model'")
    fields: dict[str, object] = {}
    for key, kind in allowed.items():
        if key not in table:
            continue
        value = table[key]
        if kind is str:
            fields[key] = _require_string(value, f"{where}.{key}")
        else:
            if not isinstance(value, list) or not value:
                raise AgentManifestError(f"{where}.{key} must be a non-empty list of strings")
            fields[key] = [_require_string(item, f"{where}.{key}") for item in value]
    if harness == "codex" and fields.get("sandbox_mode", "read-only") not in CODEX_SANDBOX_MODES:
        raise AgentManifestError(f"{where}.sandbox_mode must be one of {', '.join(sorted(CODEX_SANDBOX_MODES))}")
    if harness == "claude" and fields.get("effort", "low") not in CLAUDE_EFFORTS:
        raise AgentManifestError(f"{where}.effort must be one of {', '.join(sorted(CLAUDE_EFFORTS))}")
    return fields


def load_roles(skill: Path) -> list[Role]:
    manifest = skill / MANIFEST
    label = f"{skill.name}/{MANIFEST.as_posix()}"
    if not manifest.is_file():
        raise AgentManifestError(f"{label} is missing")
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise AgentManifestError(f"{label}: {error}") from error
    if set(data) != {"roles"} or not isinstance(data["roles"], dict) or not data["roles"]:
        raise AgentManifestError(f"{label} must contain only a non-empty [roles] table")

    roles = []
    for role_name, entry in data["roles"].items():
        where = f"{label}: roles.{role_name}"
        if not NAME_PATTERN.fullmatch(role_name):
            raise AgentManifestError(f"{where}: role names must be lowercase words joined by hyphens")
        if not isinstance(entry, dict):
            raise AgentManifestError(f"{where} must be a table")
        unknown = sorted(set(entry) - {"description", "body", *HARNESSES})
        if unknown:
            raise AgentManifestError(f"{where}: unsupported fields {', '.join(unknown)}")
        harnesses = {
            harness: _validate_harness(harness, entry[harness], f"{where}.{harness}")
            for harness in HARNESSES
            if harness in entry
        }
        if not harnesses:
            raise AgentManifestError(f"{where} must declare at least one harness")
        roles.append(Role(
            name=role_name,
            agent_name=f"{skill.name}-{role_name}",
            description=_require_string(entry.get("description"), f"{where}.description"),
            body=_read_body(skill, entry.get("body"), f"{where}.body"),
            harnesses=harnesses,
        ))
    return sorted(roles, key=lambda role: role.name)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_multiline(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"""', '""\\"')
    return f'"""\n{escaped}"""'


def _yaml_scalar(value: str) -> str:
    if PLAIN_SCALAR.fullmatch(value) and value.lower() not in YAML_KEYWORDS:
        return value
    return json.dumps(value, ensure_ascii=False)


def _markdown_agent(role: Role, fields: list[tuple[str, object]]) -> str:
    lines = ["---", f"# {HEADER}", f"name: {role.agent_name}", f"description: {_yaml_scalar(role.description)}"]
    for key, value in fields:
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {_yaml_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    return "\n".join([*lines, "---", "", role.body.rstrip("\n")]) + "\n"


def render_codex(role: Role) -> str:
    fields = role.harnesses["codex"]
    lines = [f"# {HEADER}", f"name = {_toml_string(role.agent_name)}", f"description = {_toml_string(role.description)}"]
    for key in ("model", "model_reasoning_effort", "sandbox_mode"):
        if key in fields:
            lines.append(f"{key} = {_toml_string(fields[key])}")
    lines.append(f"developer_instructions = {_toml_multiline(role.body)}")
    return "\n".join(lines) + "\n"


def render_devin(role: Role) -> str:
    fields = role.harnesses["devin"]
    return _markdown_agent(role, [(key, fields[key]) for key in ("model", "allowed-tools") if key in fields])


def render_claude(role: Role) -> str:
    fields = role.harnesses["claude"]
    return _markdown_agent(role, [(key, fields[key]) for key in ("tools", "model", "effort") if key in fields])


def render_agents(skill: Path) -> dict[str, str]:
    """Map each generated file's skill-relative POSIX path to its exact content."""
    rendered = {}
    for role in load_roles(skill):
        if "codex" in role.harnesses:
            rendered[f"harnesses/codex/{role.agent_name}.toml"] = render_codex(role)
        if "devin" in role.harnesses:
            rendered[f"harnesses/devin/{role.agent_name}/AGENT.md"] = render_devin(role)
        if "claude" in role.harnesses:
            rendered[f"harnesses/claude/{role.agent_name}.md"] = render_claude(role)
    return rendered


def _existing_generated(skill: Path) -> set[str]:
    harnesses = skill / "harnesses"
    return {
        path.relative_to(skill).as_posix()
        for path in harnesses.rglob("*")
        if path.is_file() and path != skill / MANIFEST
    }


def stale_agents(skill: Path) -> list[str]:
    """Describe every generated file that is missing, stale, hand-edited, or unexpected."""
    label = skill.name
    try:
        expected = render_agents(skill)
    except AgentManifestError as error:
        return [f"malformed role manifest: {error}"]
    problems = []
    for relative, content in sorted(expected.items()):
        path = skill / relative
        if not path.is_file():
            problems.append(f"{label}/{relative}: missing generated agent file")
        elif path.read_bytes() != content.encode("utf-8"):
            problems.append(f"{label}/{relative}: stale or hand-edited generated agent file")
    for relative in sorted(_existing_generated(skill) - set(expected)):
        problems.append(f"{label}/{relative}: unexpected file in generated harnesses directory")
    return problems


def write_agents(skill: Path) -> list[str]:
    """Regenerate a skill's agent files and remove generated files no longer declared."""
    expected = render_agents(skill)
    changed = []
    for relative in sorted(_existing_generated(skill) - set(expected)):
        (skill / relative).unlink()
        changed.append(f"removed {skill.name}/{relative}")
    for relative, content in sorted(expected.items()):
        path = skill / relative
        if path.is_file() and path.read_bytes() == content.encode("utf-8"):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        changed.append(f"wrote {skill.name}/{relative}")
    for directory in sorted((skill / "harnesses").rglob("*"), key=lambda path: len(path.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    return changed


def main(arguments: list[str]) -> int:
    skills = [Path(argument).resolve() for argument in arguments] or agent_skill_directories()
    try:
        for skill in skills:
            for change in write_agents(skill):
                print(change)
    except AgentManifestError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
