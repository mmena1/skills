#!/usr/bin/env python3
"""Controlled PEP 517 hook experiment, separate from native agent acceptance.

Run with an existing Python that supports venv/ensurepip and an existing bwrap.
Only task-created caller/home fixtures are written; no real caller is targeted.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


BACKEND = r'''
import json, os, pathlib, subprocess, sys, zipfile

def attempt(paths):
    result = {}
    for name, path in paths.items():
        try:
            pathlib.Path(path).write_text("controlled hook marker")
            result[name] = "written"
        except OSError as error:
            result[name] = {"errno": error.errno, "type": type(error).__name__}
    return result

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    paths = json.loads(os.environ["ISSUE119_MARKERS"])
    child_code = "import json, pathlib, sys\nr = {}\nfor name, path in json.loads(sys.argv[1]).items():\n try:\n  pathlib.Path(path).write_text('controlled child marker'); r[name] = 'written'\n except OSError as e:\n  r[name] = {'errno': e.errno, 'type': type(e).__name__}\nprint(json.dumps(r))"
    parent = attempt(paths)
    child = subprocess.run([sys.executable, "-I", "-B", "-c", child_code, json.dumps(paths)], capture_output=True, text=True, check=True)
    pathlib.Path(os.environ["ISSUE119_HOOK_LOG"]).write_text(json.dumps({"parent": parent, "child": json.loads(child.stdout)}))
    name = "controlled_hook_fixture-1.0.0-py3-none-any.whl"
    prefix = "controlled_hook_fixture-1.0.0.dist-info/"
    with zipfile.ZipFile(str(pathlib.Path(wheel_directory) / name), "w") as wheel:
        wheel.writestr("controlled_hook_fixture.py", "value = 1\n")
        wheel.writestr(prefix + "METADATA", "Metadata-Version: 2.1\nName: controlled-hook-fixture\nVersion: 1.0.0\n")
        wheel.writestr(prefix + "WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr(prefix + "RECORD", "")
    return name
'''


def run(command, *, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    return {"argv": command, "cwd": str(cwd), "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, help="Existing Python with venv/ensurepip")
    args = parser.parse_args()
    runtime = Path(args.python).resolve()
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SystemExit("bwrap unavailable; process-boundary experiment NOT EXERCISED")
    root = Path(tempfile.mkdtemp(prefix="issue119-install-hook-"))
    report = {"kind": "controlled PEP 517 process-boundary experiment; not native acceptance",
              "runtime": str(runtime), "bwrap": bwrap, "root": str(root), "cases": {}}
    try:
        project = root / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text('[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n')
        (project / "backend.py").write_text(BACKEND)
        report["backend_sha256"] = hashlib.sha256(BACKEND.encode()).hexdigest()
        for isolated in (False, True):
            name = "verified_process_boundary" if isolated else "owned_paths_only"
            area = root / name
            caller, home, owned = (area / part for part in ("caller", "home", "owned"))
            for path in (caller, home, owned, owned / "tmp"):
                path.mkdir(parents=True, exist_ok=True)
            for path in (caller, home):
                (path / "sentinel").write_text("unchanged controlled fixture")
            if isolated:
                markers = {"owned": "/run/.venv/marker", "caller": "/caller/marker", "home": "/home/fixture/marker"}
                command = [bwrap, "--die-with-parent", "--new-session", "--unshare-all",
                           "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                           "--ro-bind", "/lib64", "/lib64", "--symlink", "usr/bin", "/bin",
                           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/home",
                           "--ro-bind", str(home), "/home/fixture", "--ro-bind", str(caller), "/caller",
                           "--bind", str(owned), "/run", "--ro-bind", str(project), "/project",
                           "--ro-bind", str(runtime.parent.parent), "/runtime", "--chdir", "/run", "--clearenv"]
                for key, value in {"PATH": "/runtime/bin:/usr/bin:/bin", "TMPDIR": "/run/tmp",
                                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
                                   "PIP_CONFIG_FILE": "/dev/null", "PIP_NO_INDEX": "1",
                                   "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1",
                                   "ISSUE119_MARKERS": json.dumps(markers),
                                   "ISSUE119_HOOK_LOG": "/run/hook-observed.json"}.items():
                    command += ["--setenv", key, value]
                command += ["--", "/bin/sh", "-c", "/runtime/bin/python3.11 -m venv .venv && .venv/bin/python -m pip install --no-index --no-build-isolation --no-cache-dir /project"]
                commands = [run(command, cwd=owned)]
            else:
                env = dict(os.environ)
                for key in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
                    env.pop(key, None)
                env.update({"TMPDIR": str(owned / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
                            "PYTHONNOUSERSITE": "1", "PIP_CONFIG_FILE": "/dev/null",
                            "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                            "ISSUE119_MARKERS": json.dumps({"owned": str(owned / ".venv/marker"), "caller": str(caller / "marker"), "home": str(home / "marker")}),
                            "ISSUE119_HOOK_LOG": str(owned / "hook-observed.json")})
                commands = [run([str(runtime), "-m", "venv", ".venv"], cwd=owned, env=env)]
                if commands[-1]["returncode"] == 0:
                    commands.append(run([str(owned / ".venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-build-isolation", "--no-cache-dir", str(project)], cwd=owned, env=env))
            log = owned / "hook-observed.json"
            observed = json.loads(log.read_text()) if log.exists() else None
            report["cases"][name] = {"commands": commands, "hook_observation": observed,
                                    "caller_marker_exists": (caller / "marker").exists(),
                                    "home_marker_exists": (home / "marker").exists(),
                                    "sentinels_unchanged": all((path / "sentinel").read_text() == "unchanged controlled fixture" for path in (caller, home))}
            if any(command["returncode"] for command in commands) or observed is None:
                report["cases"][name]["status"] = "NOT EXERCISED: setup/boundary failed"
                continue
            if isolated:
                assert not (caller / "marker").exists() and not (home / "marker").exists()
                assert all(observed[phase]["owned"] == "written" and all(isinstance(observed[phase][key], dict) for key in ("caller", "home")) for phase in ("parent", "child"))
            else:
                assert all(all(value == "written" for value in observed[phase].values()) for phase in ("parent", "child"))
            report["cases"][name]["status"] = "observed expected controlled result"
    finally:
        shutil.rmtree(root)
        report["cleanup"] = {"exact_owned_fixture_root_removed": str(root), "removed": not root.exists()}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
