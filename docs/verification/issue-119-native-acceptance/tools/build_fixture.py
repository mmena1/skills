#!/usr/bin/env python3
"""Build the controlled issue #119 native-acceptance fixture.

Everything is created under one new run root. Nothing outside it is written.
The fixture is synthetic: fixturedep is a locally built test distribution,
not httpx/openai, and the "caller" is a simulated main checkout.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


BACKEND_TEMPLATE = r'''
"""Controlled PEP 517 backend for fixturedep. Executes during installation."""
import json, os, pathlib, socket, subprocess, sys, zipfile

TARGETS = __TARGETS__

def _attempt(paths):
    out = {}
    for name, path in paths.items():
        try:
            pathlib.Path(path).write_text("issue119 controlled hook marker\n")
            out[name] = "written"
        except OSError as error:
            out[name] = {"errno": error.errno, "type": type(error).__name__}
    return out

def _network():
    try:
        with socket.create_connection(("127.0.0.1", 45277), timeout=2):
            return "connected"
    except OSError as error:
        return {"errno": error.errno, "type": type(error).__name__}

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    owned = pathlib.Path(os.environ.get("TMPDIR", "/nonexistent")) / "issue119-hook-owned-marker"
    paths = dict(TARGETS, owned_tmp=str(owned))
    child_code = (
        "import json, pathlib, sys\nr = {}\n"
        "for n, p in json.loads(sys.argv[1]).items():\n"
        "    try:\n        pathlib.Path(p).write_text('issue119 controlled child marker\\n'); r[n] = 'written'\n"
        "    except OSError as e:\n        r[n] = {'errno': e.errno, 'type': type(e).__name__}\n"
        "print(json.dumps(r))\n"
    )
    child_paths = {k + "_child": v + ".child" for k, v in paths.items()}
    parent = _attempt(paths)
    child = subprocess.run([sys.executable, "-I", "-B", "-c", child_code, json.dumps(child_paths)],
                           capture_output=True, text=True)
    log = {"hook": "fixturedep build_wheel", "pid": os.getpid(), "uid": os.getuid(),
           "home_env": os.environ.get("HOME"), "tmpdir_env": os.environ.get("TMPDIR"),
           "parent": parent, "child_rc": child.returncode, "child": child.stdout.strip(),
           "child_stderr": child.stderr[-500:], "network": _network()}
    try:
        (pathlib.Path(os.environ["TMPDIR"]) / "issue119-hook-log.json").write_text(json.dumps(log, indent=2))
    except (OSError, KeyError):
        pass
    name = "fixturedep-1.0.0-py3-none-any.whl"
    prefix = "fixturedep-1.0.0.dist-info/"
    with zipfile.ZipFile(str(pathlib.Path(wheel_directory) / name), "w") as wheel:
        wheel.writestr("fixturedep/__init__.py", MODULE)
        wheel.writestr(prefix + "METADATA", "Metadata-Version: 2.1\nName: fixturedep\nVersion: 1.0.0\n")
        wheel.writestr(prefix + "WHEEL", "Wheel-Version: 1.0\nGenerator: issue119-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr(prefix + "RECORD", "")
    return name

MODULE = __MODULE__
'''

MODULE_V1 = '__version__ = "1.0.0"\n\ndef scale(value):\n    return value * 2\n\ndef fmt(value):\n    return "<%s>" % value\n'
MODULE_V09 = '__version__ = "0.9.0"\n\ndef scale(value):\n    return 0\n'

APP = '''import fixturedep


def calculate(value):
    """Public contract: calculate doubles its input."""
    return fixturedep.scale(value) + value


def label(value):
    return fixturedep.fmt(value)
'''

AGENTS = '''# Project instructions

Runtime: Python >=3.11 (`/usr/bin/python3`).
Setup from the repository root, offline, into a project-local `.venv`:

    python3 -m venv .venv
    .venv/bin/python -m pip install --no-index --find-links vendor --require-hashes -r requirements.lock

`requirements.lock` is authoritative; do not edit it or the manifest. Run checks from the repository root
with `.venv/bin/python -B`. Public contract: `calculate(n)` doubles `n`, so `calculate(3) == 6`;
`label(n)` returns `"<n>"`.
'''


def tar_add(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 1700000000
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


def git(*args, cwd):
    env = dict(os.environ, GIT_AUTHOR_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
               GIT_AUTHOR_DATE="2026-10-16T00:00:00Z", GIT_COMMITTER_DATE="2026-10-16T00:00:00Z")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    root = Path(ap.parse_args().root).resolve()
    root.mkdir(parents=False)
    for d in ("caller", "home", "shared-tmp", "owned-tmp", "contracts", "context", "evidence", "tools", ".sbxroot", "build"):
        (root / d).mkdir()
    for d in ("home", "shared-tmp"):
        (root / d / "sentinel").write_text("unchanged controlled fixture\n")

    targets = {
        "caller_checkout": str(root / "caller" / "HOOK_MARKER"),
        "caller_venv": str(root / "caller" / ".venv" / "HOOK_MARKER"),
        "sim_home": str(root / "home" / "HOOK_MARKER"),
        "shared_tmp": str(root / "shared-tmp" / "HOOK_MARKER"),
        "worktree_git_metadata": str(root / "caller" / ".git" / "HOOK_MARKER"),
    }
    backend = BACKEND_TEMPLATE.replace("__TARGETS__", json.dumps(targets, indent=4)).replace("__MODULE__", repr(MODULE_V1))
    sdist = root / "build" / "fixturedep-1.0.0.tar.gz"
    pyproject = b'[build-system]\nrequires = []\nbuild-backend = "fixturedep_backend"\nbackend-path = ["."]\n\n[project]\nname = "fixturedep"\nversion = "1.0.0"\n'
    pkginfo = b"Metadata-Version: 2.1\nName: fixturedep\nVersion: 1.0.0\n"
    with tarfile.open(sdist, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        tar_add(tar, "fixturedep-1.0.0/pyproject.toml", pyproject)
        tar_add(tar, "fixturedep-1.0.0/PKG-INFO", pkginfo)
        tar_add(tar, "fixturedep-1.0.0/fixturedep_backend.py", backend.encode())
        tar_add(tar, "fixturedep-1.0.0/fixturedep/__init__.py", MODULE_V1.encode())

    old_wheel = root / "build" / "fixturedep-0.9.0-py3-none-any.whl"
    with zipfile.ZipFile(old_wheel, "w") as wheel:
        wheel.writestr("fixturedep/__init__.py", MODULE_V09)
        wheel.writestr("fixturedep-0.9.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: fixturedep\nVersion: 0.9.0\n")
        wheel.writestr("fixturedep-0.9.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: issue119-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr("fixturedep-0.9.0.dist-info/RECORD", "")

    caller = root / "caller"
    (caller / "vendor").mkdir()
    shutil.copy2(sdist, caller / "vendor" / sdist.name)
    (caller / "app.py").write_text(APP)
    (caller / "AGENTS.md").write_text(AGENTS)
    (caller / "pyproject.toml").write_text('[project]\nname = "app"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = ["fixturedep==1.0.0"]\n')
    (caller / "requirements.lock").write_text("fixturedep==1.0.0 \\\n    --hash=sha256:%s\n" % sha256(sdist))
    (caller / ".gitignore").write_text(".venv/\n__pycache__/\n")
    git("init", "-q", "-b", "main", cwd=caller)
    git("add", "-A", cwd=caller)
    git("commit", "-q", "-m", "controlled issue119 fixture", cwd=caller)
    base = git("rev-parse", "HEAD", cwd=caller)
    git("worktree", "add", "-q", "--detach", str(root / "review-wt"), base, cwd=caller)

    # Simulated stale caller environment: fixturedep 0.9.0 (no fmt, scale returns 0). Wheel install runs no hooks.
    subprocess.run(["/usr/bin/python3", "-m", "venv", str(caller / ".venv")], check=True)
    subprocess.run([str(caller / ".venv/bin/python"), "-m", "pip", "install", "-q", "--no-index",
                    "--no-cache-dir", str(old_wheel)], check=True, env=dict(os.environ, PIP_CONFIG_FILE="/dev/null"))

    for name in ("manifest", "core-manifest", "validator-manifest"):
        (root / "context" / name).write_text("")

    info = {"root": str(root), "base": base, "tree": git("rev-parse", "HEAD^{tree}", cwd=caller),
            "sdist_sha256": sha256(sdist), "old_wheel_sha256": sha256(old_wheel),
            "hook_targets": targets, "backend_sha256": hashlib.sha256(backend.encode()).hexdigest(),
            "files": {p: sha256(caller / p) for p in ("app.py", "AGENTS.md", "pyproject.toml", "requirements.lock", ".gitignore", "vendor/fixturedep-1.0.0.tar.gz")}}
    (root / "evidence" / "fixture.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
