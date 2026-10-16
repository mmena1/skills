"""Coordinator-authored canary for the sbx-run process boundary (not target code).

Attempts the same classes of writes as the fixture install hook, from a parent and a
child process, plus network, capability, remount and visibility observations.
"""
import json, os, pathlib, socket, subprocess, sys

fix = pathlib.Path(sys.argv[1])
targets = {
    "owned_worktree": fix / "review-wt" / "CANARY_MARKER",
    "owned_tmp": fix / "owned-tmp" / "CANARY_MARKER",
    "caller_checkout": fix / "caller" / "CANARY_MARKER",
    "caller_venv": fix / "caller" / ".venv" / "CANARY_MARKER",
    "caller_git_metadata": fix / "caller" / ".git" / "CANARY_MARKER",
    "worktree_git_link": fix / "review-wt" / ".git",
    "sim_home": fix / "home" / "CANARY_MARKER",
    "shared_tmp": fix / "shared-tmp" / "CANARY_MARKER",
    "evidence": fix / "evidence" / "CANARY_MARKER",
    "contracts": fix / "contracts" / "CANARY_MARKER",
    "usr": pathlib.Path("/usr/CANARY_MARKER"),
    "etc": pathlib.Path("/etc/CANARY_MARKER"),
    "root_fs": pathlib.Path("/CANARY_MARKER"),
    "real_home_root": pathlib.Path("/root/CANARY_MARKER"),
}


def attempt(paths, suffix):
    out = {}
    for name, path in paths.items():
        path = pathlib.Path(str(path) + suffix) if name != "worktree_git_link" else pathlib.Path(path)
        try:
            with open(path, "a") as handle:
                if name != "worktree_git_link":
                    handle.write("canary\n")
            out[name] = "written" if name != "worktree_git_link" else "opened-for-append"
        except OSError as error:
            out[name] = {"errno": error.errno, "type": type(error).__name__}
    return out


def network():
    res = {}
    for host, port in (("127.0.0.1", 45277), ("8.8.8.8", 53)):
        try:
            with socket.create_connection((host, port), timeout=2):
                res[f"{host}:{port}"] = "connected"
        except OSError as error:
            res[f"{host}:{port}"] = {"errno": error.errno, "type": type(error).__name__}
    try:
        socket.getaddrinfo("api.anthropic.com", 443)
        res["dns"] = "resolved"
    except OSError as error:
        res["dns"] = {"errno": getattr(error, "errno", None), "type": type(error).__name__}
    return res


if len(sys.argv) > 2 and sys.argv[2] == "child":
    print(json.dumps(attempt(targets, ".child")))
    sys.exit(0)

status = {k: v.strip() for k, v in (l.split(":", 1) for l in open("/proc/self/status")) if k in
          ("Uid", "CapEff", "CapPrm", "CapBnd", "CapAmb", "CapInh", "NoNewPrivs", "Seccomp")}
child = subprocess.run([sys.executable, "-I", "-B", __file__, str(fix), "child"], capture_output=True, text=True)
remount = subprocess.run(["/usr/bin/mount", "-o", "remount,rw", "/"], capture_output=True, text=True)
unshare = subprocess.run(["/usr/bin/unshare", "--mount", "--map-root-user", "true"], capture_output=True, text=True)
visible = {p: os.path.exists(p) for p in ("/root", "/home", "/opt", "/mnt", "/run", "/var", "/tmp/claude-0", str(fix))}
report = {
    "pid": os.getpid(), "status": status, "env_keys": sorted(os.environ),
    "parent_writes": attempt(targets, ""),
    "child_rc": child.returncode, "child_writes": json.loads(child.stdout or "{}"), "child_stderr": child.stderr[-300:],
    "network": network(),
    "remount_rw_root": {"rc": remount.returncode, "stderr": remount.stderr.strip()},
    "unshare_userns_attempt": {"rc": unshare.returncode, "stderr": unshare.stderr.strip()},
    "visible_paths": visible,
    "mounts": open("/proc/self/mounts").read().splitlines(),
}
print(json.dumps(report, indent=2))
