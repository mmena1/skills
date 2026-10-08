#!/usr/bin/env python3
"""Installer and distribution integration tests for install.sh and install.ps1."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import generate_agents
from check import DEEP_REVIEW_ROLES, RENAMED_SKILLS, ROOT, SKILLS, CheckFailure, fail


def find_bash() -> str:
    if os.name != "nt":
        bash = shutil.which("bash")
        if bash:
            return bash
        fail("bash is required for install.sh distribution tests")

    candidates: list[Path] = []
    try:
        exec_path = Path(subprocess.check_output(["git", "--exec-path"], text=True).strip())
        candidates.append(exec_path.parents[2] / "bin" / "bash.exe")
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    candidates.append(Path(r"C:\Program Files\Git\bin\bash.exe"))
    candidates.append(Path(r"C:\Program Files (x86)\Git\bin\bash.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    bash = shutil.which("bash")
    if bash:
        return bash
    fail("Git Bash is required for install.sh distribution tests on Windows")


def write_agent_skill(skill: Path, body: str, roles: tuple[str, ...] = ("probe",)) -> None:
    """Give a fixture skill native reviewer agent roles on every harness; the installer generates them."""
    (skill / "reviewers").mkdir(parents=True, exist_ok=True)
    (skill / "harnesses").mkdir(exist_ok=True)
    (skill / "reviewers" / "probe.md").write_text(body + "\n", encoding="utf-8")
    (skill / "harnesses" / "roles.toml").write_text(
        "".join(
            f"[roles.{role}]\n"
            f'description = "Fixture {role}."\n'
            'body = ["reviewers/probe.md"]\n'
            f'[roles.{role}.codex]\nmodel = "gpt-6-luna"\nmodel_reasoning_effort = "high"\nsandbox_mode = "read-only"\n'
            f'[roles.{role}.devin]\nmodel = "gpt-5-6-luna-high"\nallowed-tools = ["read"]\n'
            f'[roles.{role}.claude]\nmodel = "inherit"\ntools = ["Read"]\neffort = "high"\n'
            for role in roles
        ),
        encoding="utf-8",
    )


IGNORE_GENERATED_AGENTS = shutil.ignore_patterns(*generate_agents.HARNESSES)


def copy_skill_source(source: Path, destination: Path) -> None:
    """Copy a skill as a fresh clone holds it: manifest and bodies, no generated agents."""
    shutil.copytree(source, destination, ignore=IGNORE_GENERATED_AGENTS)


def copy_installers(repository: Path) -> None:
    """The committed files an installer run needs besides the skills themselves."""
    for installer in ("install.sh", "install.ps1"):
        shutil.copy2(ROOT / installer, repository / installer)
    (repository / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "generate_agents.py", repository / "scripts" / "generate_agents.py")


def write_fixture(root: Path) -> None:
    copy_installers(root)
    stable = root / "skills" / "stable-skill"
    experimental = root / "skills" / "experimental" / "lab-skill"
    stable.mkdir(parents=True)
    experimental.mkdir(parents=True)
    (stable / "SKILL.md").write_text("---\nname: stable-skill\ndescription: Stable fixture.\n---\n", encoding="utf-8")
    (experimental / "SKILL.md").write_text("---\nname: lab-skill\ndescription: Experimental fixture.\n---\n", encoding="utf-8")
    copy_skill_source(ROOT / "tests" / "fixtures" / "agent-skill", root / "skills" / "agent-skill")
    write_agent_skill(experimental, "Experimental reviewer.")
    if os.name != "nt":
        (root / "install.sh").chmod(0o755)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        fail(f"command failed ({' '.join(command)}):\n{result.stdout}{result.stderr}")
    return result


def assert_skill(path: Path, expected_text: str = "Stable fixture.") -> None:
    skill = path / "SKILL.md"
    if not skill.is_file() or expected_text not in skill.read_text(encoding="utf-8"):
        fail(f"missing or stale installed skill: {skill}")


def create_directory_link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        powershell = find_powershell()
        env = os.environ.copy()
        env["SKILLS_TEST_LINK"] = str(link)
        env["SKILLS_TEST_TARGET"] = str(target)
        run(
            [powershell, "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:SKILLS_TEST_LINK -Target $env:SKILLS_TEST_TARGET | Out-Null"],
            cwd=link.parent,
            env=env,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def create_broken_directory_link(link: Path, target: Path) -> None:
    target.mkdir(parents=True)
    create_directory_link(link, target)
    target.rmdir()


def isolated_environment(home: Path, extra_env: dict[str, str] | None) -> dict[str, str]:
    """Keep Windows Devin agent installs inside the test home."""
    env = os.environ.copy()
    env.pop("SKILLS_INSTALLER_FORCE_COPY", None)
    env["APPDATA"] = str(home / "AppData" / "Roaming")
    env.update(extra_env or {})
    return env


AGENT_FILES = {"codex": "{name}.toml", "devin": "{name}/AGENT.md", "claude": "{name}.md"}
AGENT_HARNESSES = generate_agents.HARNESSES
MANAGED_MARKER = ".skills-repo-managed"


def agent_destinations(home: Path) -> dict[str, Path]:
    devin = home / "AppData" / "Roaming" / "devin" / "agents" if os.name == "nt" else home / ".config" / "devin" / "agents"
    return {"codex": home / ".codex" / "agents", "devin": devin, "claude": home / ".claude" / "agents"}


def installed_agent(home: Path, harness: str, name: str) -> Path:
    return agent_destinations(home)[harness] / AGENT_FILES[harness].format(name=name)


def installed_agent_entry(home: Path, harness: str, name: str) -> Path:
    """The linked destination: the agent directory for Devin, the agent file elsewhere."""
    installed = installed_agent(home, harness, name)
    return installed.parent if harness == "devin" else installed


def assert_agent(home: Path, harness: str, name: str, skill: Path) -> None:
    """The installed agent is exactly what the generator renders from the skill's committed sources."""
    installed = installed_agent(home, harness, name)
    expected = generate_agents.render_agents(skill).get(f"harnesses/{harness}/" + AGENT_FILES[harness].format(name=name))
    if expected is None:
        fail(f"{skill.name} does not declare the {harness} agent {name}")
    if not installed.is_file() or installed.read_bytes() != expected.encode("utf-8"):
        fail(f"missing or stale installed agent: {installed}")


def agent_marker(entry: Path, harness: str) -> Path:
    return entry / MANAGED_MARKER if harness == "devin" else Path(str(entry) + MANAGED_MARKER)


def assert_agent_linked(home: Path, harness: str, name: str, context: str) -> None:
    """A normal install links every agent; only a Windows file agent may fall back to a marked copy."""
    entry = installed_agent_entry(home, harness, name)
    if entry.is_symlink() or (os.name == "nt" and os.path.isjunction(entry)):
        if harness != "devin" and agent_marker(entry, harness).exists():
            fail(f"{context}: linked {harness} agent kept a copy marker")
        return
    if os.name == "nt" and harness != "devin" and agent_marker(entry, harness).is_file():
        return
    fail(f"{context}: {harness} agent is neither linked nor a marked Windows copy: {entry}")


def assert_no_agent(home: Path, harness: str, name: str, context: str) -> None:
    entry = installed_agent_entry(home, harness, name)
    if os.path.lexists(entry):
        fail(f"{context}: unexpected installed agent {entry}")


def backups_of(path: Path) -> list[Path]:
    return list(path.parent.glob(path.name + ".bak-*"))


def orphaned_markers(root: Path) -> list[Path]:
    return [
        marker for marker in root.glob("*" + MANAGED_MARKER)
        if not os.path.lexists(str(marker)[: -len(MANAGED_MARKER)])
    ]


def test_agent_installation(label: str, fixture: Path, temporary: Path, invoke, option) -> None:
    """Exercise native agent linking, reconciliation, backup, and copy fallback for one installer."""
    stable = fixture / "skills" / "agent-skill"
    experimental = fixture / "skills" / "experimental" / "lab-skill"
    roles = ("agent-skill-scout", "agent-skill-probe")

    all_home = temporary / f"{label}-agents-all"
    invoke(all_home, option("all"))
    for harness in AGENT_HARNESSES:
        for name in roles:
            assert_agent(all_home, harness, name, stable)
            assert_agent_linked(all_home, harness, name, f"{label} install")
        assert_no_agent(all_home, harness, "lab-skill-probe", f"{label} stable install included an experimental agent")

    for selected in AGENT_HARNESSES:
        home = temporary / f"{label}-agents-{selected}"
        invoke(home, option(selected))
        for harness in AGENT_HARNESSES:
            if harness == selected:
                assert_agent(home, harness, "agent-skill-scout", stable)
                assert_agent_linked(home, harness, "agent-skill-scout", f"{label} {selected} install")
            elif os.path.lexists(agent_destinations(home)[harness]):
                fail(f"{label} {selected} install wrote agents for unselected harness {harness}")

    experimental_home = temporary / f"{label}-agents-experimental"
    invoke(experimental_home, option("all"), option("experimental"))
    for harness in AGENT_HARNESSES:
        assert_agent(experimental_home, harness, "lab-skill-probe", experimental)
    invoke(experimental_home, option("all"))
    for harness in AGENT_HARNESSES:
        assert_no_agent(experimental_home, harness, "lab-skill-probe", f"{label} reconciliation retained an experimental agent")
        assert_agent(experimental_home, harness, "agent-skill-scout", stable)
        if orphaned_markers(agent_destinations(experimental_home)[harness]):
            fail(f"{label} reconciliation left a managed marker for a removed agent")

    retired = fixture / "skills" / f"{label}-retired-agents"
    retired.mkdir()
    (retired / "SKILL.md").write_text(f"---\nname: {retired.name}\ndescription: Retired fixture.\n---\n", encoding="utf-8")
    write_agent_skill(retired, "Retired reviewer.")
    removal_home = temporary / f"{label}-agents-removal"
    invoke(removal_home, option("all"))
    for harness in AGENT_HARNESSES:
        assert_agent(removal_home, harness, f"{retired.name}-probe", retired)
    shutil.rmtree(retired)
    invoke(removal_home, option("all"))
    for harness in AGENT_HARNESSES:
        assert_no_agent(removal_home, harness, f"{retired.name}-probe", f"{label} reconciliation retained a removed agent")
        if orphaned_markers(agent_destinations(removal_home)[harness]):
            fail(f"{label} reconciliation left a managed marker for a removed agent")

    backup_home = temporary / f"{label}-agents-backup"
    for harness in AGENT_HARNESSES:
        path = installed_agent(backup_home, harness, "agent-skill-scout")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep me\n", encoding="utf-8")
    foreign = agent_destinations(backup_home)["claude"] / "my-agent.md"
    foreign.write_text("leave me\n", encoding="utf-8")
    for _ in range(2):
        invoke(backup_home, option("all"))
    for harness in AGENT_HARNESSES:
        backups = backups_of(installed_agent_entry(backup_home, harness, "agent-skill-scout"))
        preserved = (backups[0] / "AGENT.md" if harness == "devin" else backups[0]) if len(backups) == 1 else None
        if preserved is None or preserved.read_text(encoding="utf-8") != "keep me\n":
            fail(f"{label} installer did not back up an unrelated same-named {harness} agent exactly once")
        assert_agent(backup_home, harness, "agent-skill-scout", stable)
    if foreign.read_text(encoding="utf-8") != "leave me\n":
        fail(f"{label} installer changed an unrelated agent")

    copy_home = temporary / f"{label}-agents-copy"
    force_copy = {"SKILLS_INSTALLER_FORCE_COPY": "1"}
    result = invoke(copy_home, option("all"), option("experimental"), extra_env=force_copy)
    output = result.stdout + result.stderr
    reported = output.replace("\\", "/")
    copies = re.findall(r"(?m)^Copied ", output)
    warnings = output.lower().count("rerun the installer after repository updates")
    if not copies or warnings != len(copies):
        fail(f"{label} copy fallback printed {warnings} rerun warnings for {len(copies)} copies")
    for harness in AGENT_HARNESSES:
        entry = installed_agent_entry(copy_home, harness, "lab-skill-probe")
        if not re.search(rf"Copied .*{re.escape('/'.join(entry.parts[-3:]))} -> ", reported):
            fail(f"{label} copy fallback did not report copying the {harness} agent")
        if not agent_marker(entry, harness).is_file():
            fail(f"{label} copy fallback did not mark the copied {harness} agent")
        assert_agent(copy_home, harness, "lab-skill-probe", experimental)
    invoke(copy_home, option("all"), extra_env=force_copy)
    invoke(copy_home, option("all"))
    for harness in AGENT_HARNESSES:
        assert_no_agent(copy_home, harness, "lab-skill-probe", f"{label} reconciliation retained a copied experimental agent")
        if backups_of(installed_agent_entry(copy_home, harness, "agent-skill-scout")):
            fail(f"{label} installer backed up a repository-managed {harness} agent copy")
        assert_agent(copy_home, harness, "agent-skill-scout", stable)
        assert_agent_linked(copy_home, harness, "agent-skill-scout", f"{label} relink after copy fallback")
        if orphaned_markers(agent_destinations(copy_home)[harness]):
            fail(f"{label} installer left an orphaned managed marker for a {harness} agent")


def test_agent_role_removal(label: str, fixture: Path, temporary: Path, invoke, option) -> None:
    """Removing one role from a skill that stays installed retires only that role's managed agents."""
    skill = fixture / "skills" / f"{label}-shrinking-agents"
    skill.mkdir()
    (skill / "SKILL.md").write_text(f"---\nname: {skill.name}\ndescription: Shrinking fixture.\n---\n", encoding="utf-8")
    kept, retired = f"{skill.name}-kept", f"{skill.name}-retired"
    shapes = {"link": {}, "copy": {"SKILLS_INSTALLER_FORCE_COPY": "1"}}

    owned_home = temporary / f"{label}-role-removal-owned"
    for harness in AGENT_HARNESSES:
        for name, text in ((kept, "keep me\n"), (retired, "leave me\n")):
            path = installed_agent(owned_home, harness, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    try:
        write_agent_skill(skill, "Shrinking reviewer.", ("kept", "retired"))
        for shape, env in shapes.items():
            home = temporary / f"{label}-role-removal-{shape}"
            invoke(home, option("all"), extra_env=env)
            for harness in AGENT_HARNESSES:
                assert_agent(home, harness, retired, skill)

        write_agent_skill(skill, "Shrinking reviewer.", ("kept",))
        for shape, env in shapes.items():
            home = temporary / f"{label}-role-removal-{shape}"
            context = f"{label} {shape} role removal"
            invoke(home, option("all"), extra_env=env)
            for harness in AGENT_HARNESSES:
                assert_no_agent(home, harness, retired, context)
                assert_agent(home, harness, kept, skill)
                for name in (kept, retired):
                    if backups_of(installed_agent_entry(home, harness, name)):
                        fail(f"{context} backed up a repository-managed {harness} agent {name}")
                if orphaned_markers(agent_destinations(home)[harness]):
                    fail(f"{context} left a managed marker for the removed {harness} agent")
            before = snapshot_home(home)
            invoke(home, option("all"), extra_env=env)
            if snapshot_home(home) != before:
                fail(f"{context} changed the home on a repeated install")

        # User-owned agents that merely carry a declared or retired name are never deleted.
        for _ in range(2):
            invoke(owned_home, option("all"))
        for harness in AGENT_HARNESSES:
            backups = backups_of(installed_agent_entry(owned_home, harness, kept))
            preserved = (backups[0] / "AGENT.md" if harness == "devin" else backups[0]) if len(backups) == 1 else None
            if preserved is None or preserved.read_text(encoding="utf-8") != "keep me\n":
                fail(f"{label} installer did not back up a user-owned {harness} agent under a declared name exactly once")
            assert_agent(owned_home, harness, kept, skill)
            untouched = installed_agent(owned_home, harness, retired)
            if not untouched.is_file() or untouched.read_text(encoding="utf-8") != "leave me\n":
                fail(f"{label} installer changed a user-owned {harness} agent under a retired name")
            if backups_of(installed_agent_entry(owned_home, harness, retired)):
                fail(f"{label} installer backed up a user-owned {harness} agent under a retired name")
    finally:
        shutil.rmtree(skill)


def is_link(path: Path) -> bool:
    return path.is_symlink() or (os.name == "nt" and os.path.isjunction(path))


def snapshot_home(home: Path) -> list[tuple[str, str]]:
    """Every entry under a home, with each link's target and each file's bytes."""
    entries = []
    for directory, names, files in os.walk(home):
        for name in sorted([*names, *files]):
            path = Path(directory) / name
            relative = path.relative_to(home).as_posix()
            if is_link(path):
                entries.append((relative, "link:" + os.readlink(path)))
            elif path.is_file():
                entries.append((relative, "file:" + path.read_bytes().hex()))
            else:
                entries.append((relative, "directory"))
        names[:] = [name for name in names if not is_link(Path(directory) / name)]
    return sorted(entries)


def expect_install_failure(label: str, context: str, home: Path, invoke, *arguments: str, extra_env: dict[str, str], mentions: str) -> None:
    """The install fails, says why, and leaves every destination in the home untouched."""
    before = snapshot_home(home)
    result = invoke(home, *arguments, extra_env=extra_env, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0:
        fail(f"{label} install succeeded {context}")
    if mentions not in output or "No destination was changed" not in output:
        fail(f"{label} install {context} did not fail clearly naming {mentions!r}:\n{output}")
    if snapshot_home(home) != before:
        fail(f"{label} install {context} changed a destination before failing")


def test_agent_prerequisites(label: str, fixture: Path, temporary: Path, invoke_from, option, extra_env_without_python: dict[str, str] | None = None) -> None:
    """Native agents are generated before any destination changes; missing Python or bad sources stop the run."""
    invoke = invoke_from(fixture)
    missing_python = {"SKILLS_INSTALLER_PYTHON": str(temporary / "no-such-python")}
    fresh_home = temporary / f"{label}-prerequisites-fresh"
    fresh_home.mkdir()
    expect_install_failure(label, "without a usable Python", fresh_home, invoke, option("all"), extra_env=missing_python, mentions="Python")

    installed_home = temporary / f"{label}-prerequisites-installed"
    invoke(installed_home, option("all"), option("experimental"))
    expect_install_failure(label, "without a usable Python over an existing install", installed_home, invoke, option("all"), extra_env=missing_python, mentions="Python")
    if extra_env_without_python is not None:
        expect_install_failure(label, "with no Python on PATH", installed_home, invoke, option("all"), extra_env=extra_env_without_python, mentions="Python")

    broken = fixture / "skills" / f"{label}-broken-agents"
    broken.mkdir()
    (broken / "SKILL.md").write_text(f"---\nname: {broken.name}\ndescription: Broken fixture.\n---\n", encoding="utf-8")
    (broken / "harnesses").mkdir()
    (broken / "harnesses" / "roles.toml").write_text('[roles.probe]\ndescription = "Broken."\nbody = ["reviewers/missing.md"]\n[roles.probe.claude]\nmodel = "inherit"\ntools = ["Read"]\neffort = "high"\n', encoding="utf-8")
    try:
        expect_install_failure(label, "with a malformed role manifest", installed_home, invoke, option("all"), extra_env={}, mentions="native reviewer agents")
    finally:
        shutil.rmtree(broken)
    for harness in AGENT_HARNESSES:
        assert_agent(installed_home, harness, "lab-skill-probe", fixture / "skills" / "experimental" / "lab-skill")

    plain = temporary / f"{label}-prerequisites-plain-repository"
    (plain / "skills" / "plain-skill").mkdir(parents=True)
    copy_installers(plain)
    (plain / "skills" / "plain-skill" / "SKILL.md").write_text("---\nname: plain-skill\ndescription: Stable fixture.\n---\n", encoding="utf-8")
    plain_home = temporary / f"{label}-prerequisites-plain"
    invoke_from(plain)(plain_home, option("all"), extra_env=missing_python)
    assert_skill(plain_home / ".claude" / "skills" / "plain-skill")


def path_without_python(temporary: Path) -> dict[str, str]:
    """A PATH holding only the tools install.sh uses, so Python discovery finds nothing."""
    tools = temporary / "tools-without-python"
    tools.mkdir()
    for name in ("basename", "cat", "cp", "date", "dirname", "grep", "ln", "mkdir", "mv", "readlink", "rm", "rmdir", "tr", "uname"):
        executable = shutil.which(name)
        if executable is None:
            fail(f"{name} is required for the installer prerequisite test")
        (tools / name).symlink_to(executable)
    return {"PATH": str(tools)}


# The native agents the standalone mmena1/deep-review repository shipped, pinned so that
# renaming a current deep-review role never changes the legacy installations under test.
LEGACY_DEEP_REVIEW_CODEX_AGENTS = (
    "deep-review-scout", "deep-review-structural", "deep-review-validator-static", "deep-review-validator-probe",
)
LEGACY_DEEP_REVIEW_DEVIN_AGENTS = (
    "code-reviewer", "code-reviewer-structural", "code-reviewer-validator-static", "code-reviewer-validator-probe",
)


def write_legacy_deep_review_checkout(checkout: Path) -> None:
    """The layout of a standalone mmena1/deep-review checkout that its installer linked from."""
    files = {
        "skills/deep-review/protocol.md": "old protocol\n",
        "skills/deep-review/GLOSSARY.md": "old glossary\n",
        "skills/deep-review/references/output-template.md": "old template\n",
        "skills/deep-review/reviewers/SCOUT.md": "old scout\n",
        "harnesses/codex/skills/deep-review/SKILL.md": "old codex wrapper\n",
        "harnesses/codex/skills/deep-review/agents/openai.yaml": "old metadata\n",
        "harnesses/devin/skills/deep-review/SKILL.md": "old devin wrapper\n",
        **{f"harnesses/codex/agents/{name}.toml": f"old {name}\n" for name in LEGACY_DEEP_REVIEW_CODEX_AGENTS},
        **{
            f"harnesses/devin/agents/{name}/AGENT.md": (
                f"---\nname: {name}\nmodel: old\n---\n\n<!-- BEGIN GENERATED: shared reviewer body -->\n"
                f"old {name}\n<!-- END GENERATED: shared reviewer body -->\n"
            )
            for name in LEGACY_DEEP_REVIEW_DEVIN_AGENTS
        },
    }
    for relative, text in files.items():
        (checkout / relative).parent.mkdir(parents=True, exist_ok=True)
        (checkout / relative).write_text(text, encoding="utf-8")


def snapshot_files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def create_file_link(link: Path, target: Path) -> None:
    """Link a file the way the old installer did: a symlink on Unix, a hard link on Windows."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.link(target, link)
    else:
        link.symlink_to(target)


def install_legacy_deep_review(home: Path, checkout: Path, *, copies: bool = False) -> None:
    """Recreate what mmena1/deep-review's installer wrote for Codex and Devin.

    With copies, recreate its fallback when links could not be created: copied skill
    root entries and Devin agent directories. Codex agents stay linked either way.
    """
    link_file = (lambda link, target: shutil.copy2(target, link)) if copies else create_file_link
    link_directory = (lambda link, target: shutil.copytree(target, link)) if copies else create_directory_link
    for harness, root in (("codex", home / ".agents" / "skills" / "deep-review"), ("devin", home / ".config" / "devin" / "skills" / "deep-review")):
        root.mkdir(parents=True)
        (root / ".deep-review-managed").write_text(str(checkout) + "\n", encoding="utf-8")
        wrapper = checkout / "harnesses" / harness / "skills" / "deep-review"
        shared = checkout / "skills" / "deep-review"
        link_file(root / "SKILL.md", wrapper / "SKILL.md")
        link_file(root / "protocol.md", shared / "protocol.md")
        link_file(root / "GLOSSARY.md", shared / "GLOSSARY.md")
        link_directory(root / "references", shared / "references")
        link_directory(root / "reviewers", shared / "reviewers")
        if harness == "codex":
            link_directory(root / "agents", wrapper / "agents")
    for name in LEGACY_DEEP_REVIEW_CODEX_AGENTS:
        create_file_link(home / ".codex" / "agents" / f"{name}.toml", checkout / "harnesses" / "codex" / "agents" / f"{name}.toml")
    for name in LEGACY_DEEP_REVIEW_DEVIN_AGENTS:
        (home / ".config" / "devin" / "agents").mkdir(parents=True, exist_ok=True)
        link_directory(home / ".config" / "devin" / "agents" / name, checkout / "harnesses" / "devin" / "agents" / name)


def deep_review_repository(repository: Path) -> Path:
    """A repository holding both installers and the real deep-review skill as its only skill."""
    (repository / "skills" / "experimental").mkdir(parents=True)
    copy_installers(repository)
    copy_skill_source(SKILLS / "deep-review", repository / "skills" / "deep-review")
    return repository


def declared_agents(skill: Path, harness: str) -> set[str]:
    """The agent names a skill currently declares for one harness."""
    return {role.agent_name for role in generate_agents.load_roles(skill) if harness in role.harnesses}


def test_deep_review_claude(label: str, temporary: Path, invoke_from, option) -> None:
    """Selecting Claude Code installs deep-review and links every one of its native reviewer agents."""
    repository = deep_review_repository(temporary / f"{label}-deep-review-claude-repository")
    skill = repository / "skills" / "deep-review"
    home = temporary / f"{label}-deep-review-claude"
    invoke_from(repository)(home, option("claude"))
    assert_skill(home / ".claude" / "skills" / "deep-review", "name: deep-review")
    for role in DEEP_REVIEW_ROLES:
        name = f"deep-review-{role}"
        assert_agent(home, "claude", name, skill)
        assert_agent_linked(home, "claude", name, f"{label} Claude deep-review install")
    for harness in ("codex", "devin"):
        if os.path.lexists(agent_destinations(home)[harness]):
            fail(f"{label} Claude deep-review install wrote agents for unselected harness {harness}")


FORMER_GENERIC_SCOUT_ROLE = """
[roles.scout]
description = "Read-only deep-review scout using one selected review lens."
body = ["reviewers/SCOUT.md"]

[roles.scout.codex]
model = "gpt-6.1-sol"
model_reasoning_effort = "high"
sandbox_mode = "read-only"

[roles.scout.devin]
model = "gpt-6-1-sol-high"
allowed-tools = ["read", "grep", "glob", "exec"]

[roles.scout.claude]
model = "claude-sonnet-5-5"
tools = ["Read", "Grep", "Glob", "Bash"]
effort = "high"
"""


def test_deep_review_scout_upgrade(label: str, temporary: Path, invoke_from, option) -> None:
    """Upgrading from the generic scout retires its managed agent everywhere and installs every lens-specific scout."""
    repository = deep_review_repository(temporary / f"{label}-scout-upgrade-repository")
    skill = repository / "skills" / "deep-review"
    manifest = skill / "harnesses" / "roles.toml"
    current = manifest.read_text(encoding="utf-8")
    invoke = invoke_from(repository)
    shapes = {"link": {}, "copy": {"SKILLS_INSTALLER_FORCE_COPY": "1"}}

    manifest.write_text(current + FORMER_GENERIC_SCOUT_ROLE, encoding="utf-8")
    for shape, env in shapes.items():
        home = temporary / f"{label}-scout-upgrade-{shape}"
        invoke(home, option("all"), extra_env=env)
        for harness in AGENT_HARNESSES:
            assert_agent(home, harness, "deep-review-scout", skill)

    manifest.write_text(current, encoding="utf-8")
    for shape, env in shapes.items():
        home = temporary / f"{label}-scout-upgrade-{shape}"
        context = f"{label} {shape} upgrade from the generic deep-review scout"
        invoke(home, option("all"), extra_env=env)
        for harness in AGENT_HARNESSES:
            assert_no_agent(home, harness, "deep-review-scout", context)
            for role in DEEP_REVIEW_ROLES:
                assert_agent(home, harness, f"deep-review-{role}", skill)
            if backups_of(installed_agent_entry(home, harness, "deep-review-scout")):
                fail(f"{context} backed up the repository-managed {harness} generic scout")
            if orphaned_markers(agent_destinations(home)[harness]):
                fail(f"{context} left a managed marker for the {harness} generic scout")
        before = snapshot_home(home)
        invoke(home, option("all"), extra_env=env)
        if snapshot_home(home) != before:
            fail(f"{context} changed the home on a repeated install")


def test_renamed_skills(label: str, temporary: Path, invoke_from, option) -> None:
    """Reinstalling after a skill rename removes repository-managed installations of the former name."""
    for former, current in RENAMED_SKILLS.items():
        repository = temporary / f"{label}-renamed-{former}-repository"
        (repository / "skills" / "experimental").mkdir(parents=True)
        copy_installers(repository)
        copy_skill_source(SKILLS / current, repository / "skills" / current)
        former_source = repository / "skills" / former
        roots = (Path(".agents") / "skills", Path(".claude") / "skills")

        for case in ("link", "copy"):
            home = temporary / f"{label}-renamed-{former}-{case}"
            for root in roots:
                stale = home / root / former
                if case == "link":
                    create_broken_directory_link(stale, former_source)
                else:
                    stale.mkdir(parents=True)
                    (stale / "SKILL.md").write_text(f"---\nname: {former}\n---\n", encoding="utf-8")
                    (stale / MANAGED_MARKER).write_text(str(former_source) + "\n", encoding="utf-8")
            invoke_from(repository)(home, option("all"))
            for root in roots:
                if os.path.lexists(home / root / former):
                    fail(f"{label} reconciliation retained a repository-managed {case} of renamed skill {former} in {root}")
                if list((home / root).glob(f"{former}.bak-*")):
                    fail(f"{label} installer backed up a repository-managed {case} of renamed skill {former} in {root}")
                assert_skill(home / root / current, f"name: {current}")

        foreign_home = temporary / f"{label}-renamed-{former}-foreign"
        foreign = foreign_home / ".claude" / "skills" / former
        foreign.mkdir(parents=True)
        (foreign / "local.txt").write_text("keep me\n", encoding="utf-8")
        invoke_from(repository)(foreign_home, option("claude"))
        if not foreign.is_dir() or (foreign / "local.txt").read_text(encoding="utf-8") != "keep me\n":
            fail(f"{label} installer changed an unrelated skill named {former}")
        assert_skill(foreign_home / ".claude" / "skills" / current, f"name: {current}")


def test_legacy_deep_review(label: str, temporary: Path, invoke_from, option) -> None:
    """Installations made by the standalone deep-review installer are replaced; anything else is backed up."""
    repository = deep_review_repository(temporary / f"{label}-legacy-repository")
    skill = repository / "skills" / "deep-review"
    invoke = invoke_from(repository)

    checkout = temporary / f"{label}-old-deep-review"
    write_legacy_deep_review_checkout(checkout)
    checkout_files = snapshot_files(checkout)
    # The current deep-review no longer declares the legacy generic scout, so its legacy agent is retired.
    if "deep-review-scout" in declared_agents(skill, "codex"):
        fail("deep-review still declares the legacy generic scout agent")
    for shape, copies in (("linked", False), ("copied", True)):
        home = temporary / f"{label}-legacy-{shape}"
        install_legacy_deep_review(home, checkout, copies=copies)
        invoke(home, option("all"))
        shared_skill = home / ".agents" / "skills" / "deep-review"
        assert_skill(shared_skill, "name: deep-review")
        if not (shared_skill.is_symlink() or (os.name == "nt" and os.path.isjunction(shared_skill))):
            fail(f"{label} installer did not link deep-review over the old {shape} shared skill root")
        if os.path.lexists(home / ".config" / "devin" / "skills" / "deep-review"):
            fail(f"{label} installer retained the old {shape} deep-review Devin skill root")
        for name in LEGACY_DEEP_REVIEW_CODEX_AGENTS:
            if name in declared_agents(skill, "codex"):
                assert_agent(home, "codex", name, skill)
            else:
                assert_no_agent(home, "codex", name, f"{label} replacement of the old {shape} deep-review installation")
        for name in sorted(declared_agents(skill, "devin")):
            assert_agent(home, "devin", name, skill)
        for name in LEGACY_DEEP_REVIEW_DEVIN_AGENTS:
            if os.path.lexists(home / ".config" / "devin" / "agents" / name):
                fail(f"{label} installer retained the old {shape} deep-review Devin agent {name}")
        backups = [path for path in home.rglob("*.bak-*")]
        if backups:
            fail(f"{label} installer backed up an old {shape} deep-review installation instead of replacing it: {backups[0]}")
        if snapshot_files(checkout) != checkout_files:
            fail(f"{label} installer changed the old deep-review checkout while replacing its {shape} installation")
        before = snapshot_home(home)
        invoke(home, option("all"))
        if snapshot_home(home) != before:
            fail(f"{label} replacement of the old {shape} deep-review installation changed the home on a repeated install")

    # Content that only carries a retired or declared legacy name is not recognisably owned.
    owned_home = temporary / f"{label}-legacy-owned"
    retired_link = owned_home / ".codex" / "agents" / "deep-review-scout.toml"
    retired_target = temporary / f"{label}-legacy-retired-foreign.toml"
    retired_target.write_text("leave me\n", encoding="utf-8")
    create_file_link(retired_link, retired_target)
    retired_plain = owned_home / ".claude" / "agents" / "deep-review-scout.md"
    retired_plain.parent.mkdir(parents=True)
    retired_plain.write_text("leave me\n", encoding="utf-8")
    declared_plain = owned_home / ".codex" / "agents" / "deep-review-structural.toml"
    declared_plain.write_text("keep me\n", encoding="utf-8")
    for _ in range(2):
        invoke(owned_home, option("all"))
    for untouched in (retired_link, retired_plain):
        if not untouched.is_file() or untouched.read_text(encoding="utf-8") != "leave me\n" or backups_of(untouched):
            fail(f"{label} installer changed unrecognised content under a retired deep-review agent name: {untouched}")
    found = backups_of(declared_plain)
    if len(found) != 1 or found[0].read_text(encoding="utf-8") != "keep me\n":
        fail(f"{label} installer did not back up unrecognised content under a declared deep-review agent name exactly once")
    assert_agent(owned_home, "codex", "deep-review-structural", skill)

    unrelated_home = temporary / f"{label}-legacy-unrelated"
    marked_root = unrelated_home / ".agents" / "skills" / "deep-review"
    marked_root.mkdir(parents=True)
    (marked_root / ".deep-review-managed").write_text(str(checkout) + "\n", encoding="utf-8")
    (marked_root / "notes.md").write_text("keep me\n", encoding="utf-8")
    foreign_target = temporary / f"{label}-legacy-foreign.toml"
    foreign_target.write_text("keep me\n", encoding="utf-8")
    foreign_link = unrelated_home / ".codex" / "agents" / "deep-review-scout-bugs.toml"
    create_file_link(foreign_link, foreign_target)
    plain_agent = unrelated_home / ".codex" / "agents" / "deep-review-structural.toml"
    plain_agent.write_text("keep me\n", encoding="utf-8")
    devin_root = unrelated_home / ".config" / "devin" / "skills" / "deep-review"
    devin_root.mkdir(parents=True)
    (devin_root / "notes.md").write_text("leave me\n", encoding="utf-8")
    devin_agent = unrelated_home / ".config" / "devin" / "agents" / "code-reviewer"
    devin_agent.mkdir(parents=True)
    (devin_agent / "AGENT.md").write_text("leave me\n", encoding="utf-8")
    for _ in range(2):
        invoke(unrelated_home, option("all"))
    for destination, relative in ((marked_root, "notes.md"), (foreign_link, None), (plain_agent, None)):
        found = backups_of(destination)
        preserved = (found[0] / relative if relative else found[0]) if len(found) == 1 else None
        if preserved is None or preserved.read_text(encoding="utf-8") != "keep me\n":
            fail(f"{label} installer did not back up an unrecognised deep-review destination exactly once: {destination}")
    assert_skill(marked_root, "name: deep-review")
    assert_agent(unrelated_home, "codex", "deep-review-scout-bugs", skill)
    assert_agent(unrelated_home, "codex", "deep-review-structural", skill)
    for kept in (devin_root / "notes.md", devin_agent / "AGENT.md"):
        if not kept.is_file() or kept.read_text(encoding="utf-8") != "leave me\n":
            fail(f"{label} installer changed unrecognised content that it does not replace: {kept}")

    # A marker only counts when it names a deep-review checkout with the old harness layout.
    lookalike = temporary / f"{label}-legacy-lookalike"
    (lookalike / "skills" / "deep-review").mkdir(parents=True)
    (lookalike / "skills" / "deep-review" / "protocol.md").write_text("not a checkout\n", encoding="utf-8")
    for case, recorded in (("missing", temporary / f"{label}-legacy-missing-checkout"), ("lookalike", lookalike)):
        stale_home = temporary / f"{label}-legacy-stale-{case}"
        shared_root = stale_home / ".agents" / "skills" / "deep-review"
        devin_root = stale_home / ".config" / "devin" / "skills" / "deep-review"
        for root in (shared_root, devin_root):
            root.mkdir(parents=True)
            (root / ".deep-review-managed").write_text(f"{recorded}\n", encoding="utf-8")
            (root / "SKILL.md").write_text("keep me\n", encoding="utf-8")
        invoke(stale_home, option("all"))
        found = backups_of(shared_root)
        if len(found) != 1 or (found[0] / "SKILL.md").read_text(encoding="utf-8") != "keep me\n":
            fail(f"{label} installer did not back up a deep-review skill root whose marker names a {case} checkout")
        assert_skill(shared_root, "name: deep-review")
        if (devin_root / "SKILL.md").read_text(encoding="utf-8") != "keep me\n":
            fail(f"{label} installer removed a Devin deep-review skill root whose marker names a {case} checkout")


def test_shell_installer(fixture: Path, temporary: Path) -> None:
    bash = find_bash()

    def invoke_from(repository: Path):
        def invoke(home: Path, *arguments: str, extra_env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
            env = isolated_environment(home, extra_env)
            env["HOME"] = str(home)
            return run([bash, "./install.sh", *arguments], cwd=repository, env=env, check=check)
        return invoke

    invoke = invoke_from(fixture)

    codex_home = temporary / "shell-codex"
    invoke(codex_home, "--codex")
    assert_skill(codex_home / ".agents" / "skills" / "stable-skill")
    if (codex_home / ".agents" / "skills" / "lab-skill").exists():
        fail("stable shell install included experimental skill")

    source_skill = fixture / "skills" / "stable-skill" / "SKILL.md"
    source_skill.write_text(source_skill.read_text(encoding="utf-8") + "updated-shell\n", encoding="utf-8")
    invoke(codex_home, "--codex")
    assert_skill(codex_home / ".agents" / "skills" / "stable-skill", "updated-shell")
    invoke(codex_home, "--codex", "--experimental")
    assert_skill(codex_home / ".agents" / "skills" / "lab-skill", "Experimental fixture.")
    invoke(codex_home, "--codex")
    if os.path.lexists(codex_home / ".agents" / "skills" / "lab-skill"):
        fail("stable shell reconciliation retained an experimental skill")

    devin_home = temporary / "shell-devin"
    invoke(devin_home, "--devin")
    assert_skill(devin_home / ".agents" / "skills" / "stable-skill")
    if os.path.lexists(devin_home / ".config" / "devin" / "skills"):
        fail("--devin shell install retained the legacy destination")

    all_home = temporary / "shell-all"
    all_result = invoke(all_home, "--all")
    assert_skill(all_home / ".agents" / "skills" / "stable-skill")
    assert_skill(all_home / ".claude" / "skills" / "stable-skill")
    if os.path.lexists(all_home / ".agents" / "skills" / "lab-skill") or os.path.lexists(all_home / ".claude" / "skills" / "lab-skill"):
        fail("--all shell install included experimental skills without the experimental option")
    shared_links = [line for line in all_result.stdout.splitlines() if "Linked " in line and ".agents" in line and "stable-skill" in line]
    if len(shared_links) != 1:
        fail("--all shell install did not materialize the shared destination exactly once")
    if os.path.lexists(all_home / ".config" / "devin" / "skills"):
        fail("--all shell install retained the legacy destination")

    claude_home = temporary / "shell-claude"
    invoke(claude_home, "--claude")
    assert_skill(claude_home / ".claude" / "skills" / "stable-skill")
    if os.path.lexists(claude_home / ".agents" / "skills"):
        fail("--claude shell install wrote to the shared Codex and Devin destination")

    all_experimental_home = temporary / "shell-all-experimental"
    invoke(all_experimental_home, "--all", "--experimental")
    assert_skill(all_experimental_home / ".agents" / "skills" / "lab-skill", "Experimental fixture.")
    assert_skill(all_experimental_home / ".claude" / "skills" / "lab-skill", "Experimental fixture.")

    detected_home = temporary / "shell-detected"
    (detected_home / ".agents").mkdir(parents=True)
    invoke(detected_home)
    assert_skill(detected_home / ".agents" / "skills" / "stable-skill")

    detected_claude_home = temporary / "shell-detected-claude"
    (detected_claude_home / ".claude").mkdir(parents=True)
    invoke(detected_claude_home)
    assert_skill(detected_claude_home / ".claude" / "skills" / "stable-skill")

    legacy_home = temporary / "shell-legacy"
    legacy_managed = legacy_home / ".config" / "devin" / "skills" / "stable-skill"
    legacy_managed.parent.mkdir(parents=True)
    create_directory_link(legacy_managed, fixture / "skills" / "stable-skill")
    legacy_unrelated = legacy_home / ".config" / "devin" / "skills" / "local-skill"
    legacy_unrelated.mkdir()
    (legacy_unrelated / "local.txt").write_text("keep me\n", encoding="utf-8")
    invoke(legacy_home)
    assert_skill(legacy_home / ".agents" / "skills" / "stable-skill")
    if os.path.lexists(legacy_managed):
        fail("shell installer retained a repository-managed skill in the legacy Devin destination")
    if (legacy_unrelated / "local.txt").read_text(encoding="utf-8") != "keep me\n":
        fail("shell installer changed unrelated content in the legacy Devin destination")

    backup_home = temporary / "shell-backup"
    unrelated = backup_home / ".agents" / "skills" / "stable-skill"
    unrelated.mkdir(parents=True)
    (unrelated / "local.txt").write_text("keep me\n", encoding="utf-8")
    invoke(backup_home, "--codex")
    backups = list(unrelated.parent.glob("stable-skill.bak-*"))
    if len(backups) != 1 or (backups[0] / "local.txt").read_text(encoding="utf-8") != "keep me\n":
        fail("shell installer did not preserve an unrelated destination backup")

    broken_managed_home = temporary / "shell-broken-managed"
    broken_managed = broken_managed_home / ".agents" / "skills" / "stable-skill"
    create_broken_directory_link(broken_managed, fixture / "skills" / "retired-managed-skill")
    invoke(broken_managed_home, "--codex")
    assert_skill(broken_managed)
    if list(broken_managed.parent.glob("stable-skill.bak-*")):
        fail("shell installer backed up a broken repository-managed link")

    broken_unrelated_home = temporary / "shell-broken-unrelated"
    broken_unrelated = broken_unrelated_home / ".agents" / "skills" / "stable-skill"
    create_broken_directory_link(broken_unrelated, temporary / "unrelated-missing-target")
    invoke(broken_unrelated_home, "--codex")
    assert_skill(broken_unrelated)
    unrelated_backups = list(broken_unrelated.parent.glob("stable-skill.bak-*"))
    if len(unrelated_backups) != 1 or not os.path.lexists(unrelated_backups[0]):
        fail("shell installer did not back up an unrelated broken link")

    lifecycle_home = temporary / "shell-lifecycle"
    old_source = fixture / "skills" / "shell-old-skill"
    old_source.mkdir()
    (old_source / "SKILL.md").write_text("---\nname: shell-old-skill\ndescription: Old fixture.\n---\n", encoding="utf-8")
    invoke(lifecycle_home, "--codex")
    old_destination = lifecycle_home / ".agents" / "skills" / "shell-old-skill"
    assert_skill(old_destination, "Old fixture.")

    new_source = fixture / "skills" / "shell-renamed-skill"
    old_source.rename(new_source)
    (new_source / "SKILL.md").write_text("---\nname: shell-renamed-skill\ndescription: Renamed fixture.\n---\n", encoding="utf-8")
    stale_copy = lifecycle_home / ".agents" / "skills" / "shell-retired-copy"
    stale_copy.mkdir()
    (stale_copy / "SKILL.md").write_text("retired copy\n", encoding="utf-8")
    (stale_copy / ".skills-repo-managed").write_text(str(old_source) + "\n", encoding="utf-8")
    foreign = lifecycle_home / ".agents" / "skills" / "foreign-skill"
    foreign.mkdir()
    (foreign / "local.txt").write_text("leave me\n", encoding="utf-8")

    invoke(lifecycle_home, "--codex")
    if os.path.lexists(old_destination) or os.path.lexists(stale_copy):
        fail("shell reconciliation retained a removed repository-managed skill")
    assert_skill(lifecycle_home / ".agents" / "skills" / "shell-renamed-skill", "Renamed fixture.")
    if (foreign / "local.txt").read_text(encoding="utf-8") != "leave me\n":
        fail("shell reconciliation changed an unrelated destination")

    shell_options = {"all": "--all", "codex": "--codex", "devin": "--devin", "claude": "--claude", "experimental": "--experimental"}
    test_agent_installation("shell", fixture, temporary, invoke, shell_options.__getitem__)
    test_agent_role_removal("shell", fixture, temporary, invoke, shell_options.__getitem__)
    without_python = None if os.name == "nt" else path_without_python(temporary)
    test_agent_prerequisites("shell", fixture, temporary, invoke_from, shell_options.__getitem__, without_python)
    test_legacy_deep_review("shell", temporary, invoke_from, shell_options.__getitem__)
    test_deep_review_claude("shell", temporary, invoke_from, shell_options.__getitem__)
    test_deep_review_scout_upgrade("shell", temporary, invoke_from, shell_options.__getitem__)
    test_renamed_skills("shell", temporary, invoke_from, shell_options.__getitem__)


def find_powershell() -> str:
    for name in ("pwsh", "powershell.exe"):
        executable = shutil.which(name)
        if executable:
            return executable
    fail("PowerShell is required for native Windows installer tests")


def test_powershell_installer(fixture: Path, temporary: Path) -> None:
    if os.name != "nt":
        return
    powershell = find_powershell()

    def invoke_from(repository: Path):
        def invoke(home: Path, *arguments: str, extra_env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
            return run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(repository / "install.ps1"), *arguments, "-HomePath", str(home)],
                cwd=repository,
                env=isolated_environment(home, extra_env),
                check=check,
            )
        return invoke

    invoke = invoke_from(fixture)

    codex_home = temporary / "powershell-codex"
    invoke(codex_home, "-Codex")
    assert_skill(codex_home / ".agents" / "skills" / "stable-skill")
    if (codex_home / ".agents" / "skills" / "lab-skill").exists():
        fail("stable PowerShell install included experimental skill")
    invoke(codex_home, "-Codex", "-Experimental")
    assert_skill(codex_home / ".agents" / "skills" / "lab-skill", "Experimental fixture.")
    invoke(codex_home, "-Codex")
    if os.path.lexists(codex_home / ".agents" / "skills" / "lab-skill"):
        fail("stable PowerShell reconciliation retained an experimental skill")

    devin_home = temporary / "powershell-devin"
    invoke(devin_home, "-Devin")
    assert_skill(devin_home / ".agents" / "skills" / "stable-skill")
    if os.path.lexists(devin_home / ".config" / "devin" / "skills"):
        fail("-Devin PowerShell install retained the legacy destination")

    all_home = temporary / "powershell-all"
    all_result = invoke(all_home, "-All")
    assert_skill(all_home / ".agents" / "skills" / "stable-skill")
    assert_skill(all_home / ".claude" / "skills" / "stable-skill")
    if os.path.lexists(all_home / ".agents" / "skills" / "lab-skill") or os.path.lexists(all_home / ".claude" / "skills" / "lab-skill"):
        fail("-All PowerShell install included experimental skills without the experimental option")
    shared_links = [line for line in all_result.stdout.splitlines() if "Linked " in line and ".agents" in line and "stable-skill" in line]
    if len(shared_links) != 1:
        fail("-All PowerShell install did not materialize the shared destination exactly once")
    if os.path.lexists(all_home / ".config" / "devin" / "skills"):
        fail("-All PowerShell install retained the legacy destination")

    claude_home = temporary / "powershell-claude"
    invoke(claude_home, "-Claude")
    assert_skill(claude_home / ".claude" / "skills" / "stable-skill")
    if os.path.lexists(claude_home / ".agents" / "skills"):
        fail("-Claude PowerShell install wrote to the shared Codex and Devin destination")

    all_experimental_home = temporary / "powershell-all-experimental"
    invoke(all_experimental_home, "-All", "-Experimental")
    assert_skill(all_experimental_home / ".agents" / "skills" / "lab-skill", "Experimental fixture.")
    assert_skill(all_experimental_home / ".claude" / "skills" / "lab-skill", "Experimental fixture.")

    detected_home = temporary / "powershell-detected"
    (detected_home / ".agents").mkdir(parents=True)
    invoke(detected_home)
    assert_skill(detected_home / ".agents" / "skills" / "stable-skill")

    detected_claude_home = temporary / "powershell-detected-claude"
    (detected_claude_home / ".claude").mkdir(parents=True)
    invoke(detected_claude_home)
    assert_skill(detected_claude_home / ".claude" / "skills" / "stable-skill")

    legacy_home = temporary / "powershell-legacy"
    legacy_managed = legacy_home / ".config" / "devin" / "skills" / "stable-skill"
    legacy_managed.mkdir(parents=True)
    (legacy_managed / ".skills-repo-managed").write_text(str(fixture / "skills" / "stable-skill") + "\n", encoding="utf-8")
    legacy_unrelated = legacy_home / ".config" / "devin" / "skills" / "local-skill"
    legacy_unrelated.mkdir()
    (legacy_unrelated / "local.txt").write_text("keep me\n", encoding="utf-8")
    invoke(legacy_home)
    assert_skill(legacy_home / ".agents" / "skills" / "stable-skill")
    if os.path.lexists(legacy_managed):
        fail("PowerShell installer retained a repository-managed skill in the legacy Devin destination")
    if (legacy_unrelated / "local.txt").read_text(encoding="utf-8") != "keep me\n":
        fail("PowerShell installer changed unrelated content in the legacy Devin destination")

    backup_home = temporary / "powershell-backup"
    unrelated = backup_home / ".agents" / "skills" / "stable-skill"
    unrelated.mkdir(parents=True)
    (unrelated / "local.txt").write_text("keep me\n", encoding="utf-8")
    invoke(backup_home, "-Codex")
    backups = list(unrelated.parent.glob("stable-skill.bak-*"))
    if len(backups) != 1 or (backups[0] / "local.txt").read_text(encoding="utf-8") != "keep me\n":
        fail("PowerShell installer did not preserve an unrelated destination backup")

    broken_home = temporary / "powershell-broken-managed"
    broken_destination = broken_home / ".agents" / "skills" / "stable-skill"
    create_broken_directory_link(broken_destination, fixture / "skills" / "retired-powershell-skill")
    invoke(broken_home, "-Codex")
    assert_skill(broken_destination)
    if list(broken_destination.parent.glob("stable-skill.bak-*")):
        fail("PowerShell installer backed up a broken repository-managed link")

    lifecycle_home = temporary / "powershell-lifecycle"
    old_source = fixture / "skills" / "powershell-old-skill"
    old_source.mkdir()
    (old_source / "SKILL.md").write_text("---\nname: powershell-old-skill\ndescription: Old fixture.\n---\n", encoding="utf-8")
    invoke(lifecycle_home, "-Codex")
    old_destination = lifecycle_home / ".agents" / "skills" / "powershell-old-skill"
    assert_skill(old_destination, "Old fixture.")

    new_source = fixture / "skills" / "powershell-renamed-skill"
    old_source.rename(new_source)
    (new_source / "SKILL.md").write_text("---\nname: powershell-renamed-skill\ndescription: Renamed fixture.\n---\n", encoding="utf-8")
    stale_copy = lifecycle_home / ".agents" / "skills" / "powershell-retired-copy"
    stale_copy.mkdir()
    (stale_copy / "SKILL.md").write_text("retired copy\n", encoding="utf-8")
    (stale_copy / ".skills-repo-managed").write_text(str(old_source) + "\n", encoding="utf-8")
    foreign = lifecycle_home / ".agents" / "skills" / "foreign-skill"
    foreign.mkdir()
    (foreign / "local.txt").write_text("leave me\n", encoding="utf-8")

    invoke(lifecycle_home, "-Codex")
    if os.path.lexists(old_destination) or os.path.lexists(stale_copy):
        fail("PowerShell reconciliation retained a removed repository-managed skill")
    assert_skill(lifecycle_home / ".agents" / "skills" / "powershell-renamed-skill", "Renamed fixture.")
    if (foreign / "local.txt").read_text(encoding="utf-8") != "leave me\n":
        fail("PowerShell reconciliation changed an unrelated destination")

    powershell_options = {"all": "-All", "codex": "-Codex", "devin": "-Devin", "claude": "-Claude", "experimental": "-Experimental"}
    test_agent_installation("powershell", fixture, temporary, invoke, powershell_options.__getitem__)
    test_agent_role_removal("powershell", fixture, temporary, invoke, powershell_options.__getitem__)
    test_agent_prerequisites("powershell", fixture, temporary, invoke_from, powershell_options.__getitem__)
    test_legacy_deep_review("powershell", temporary, invoke_from, powershell_options.__getitem__)
    test_deep_review_claude("powershell", temporary, invoke_from, powershell_options.__getitem__)
    test_deep_review_scout_upgrade("powershell", temporary, invoke_from, powershell_options.__getitem__)
    test_renamed_skills("powershell", temporary, invoke_from, powershell_options.__getitem__)


def validate_installers() -> None:
    with tempfile.TemporaryDirectory(prefix="skills-check-") as temp_value:
        temporary = Path(temp_value)
        fixture = temporary / "repository"
        fixture.mkdir()
        write_fixture(fixture)
        test_shell_installer(fixture, temporary)
        test_powershell_installer(fixture, temporary)


def main() -> int:
    try:
        validate_installers()
    except CheckFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("Installer integration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
