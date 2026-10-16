#!/usr/bin/env python3
"""Coordinator helpers for the issue #119 controlled native acceptance run.

fingerprint ROOT                 -> JSON fingerprints of simulated caller/home/shared state
restore ROOT                     -> scoped restoration of the exact disposable worktree + owned tmp
inspect ROOT EVENTS.jsonl        -> native tool calls/results summary from a stream-json transcript
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys


def tree_hash(path, exclude=()):
    path = Path(path)
    entries = {}
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        rel_dir = Path(dirpath).relative_to(path)
        dirnames[:] = sorted(d for d in dirnames if str(rel_dir / d) not in exclude)
        for name in sorted(filenames) + sorted(d for d in dirnames if (Path(dirpath) / d).is_symlink()):
            p = Path(dirpath) / name
            rel = str(p.relative_to(path))
            if rel in exclude:
                continue
            st = p.lstat()
            if p.is_symlink():
                entries[rel] = "link:" + os.readlink(p)
            else:
                entries[rel] = hashlib.sha256(p.read_bytes()).hexdigest() + ":%o" % (st.st_mode & 0o7777)
        for d in dirnames:
            entries.setdefault(str(rel_dir / d) + "/", "dir")
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "entries": len(entries)}


def git(root, *args):
    r = subprocess.run(["git", "-C", str(Path(root) / "review-wt"), *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def fingerprint(root):
    root = Path(root)
    markers = sorted(str(p) for p in root.rglob("*") if p.name.startswith(("HOOK_MARKER", "CANARY_MARKER", "issue119-hook")))
    return {
        "caller_checkout_excluding_git_and_venv": tree_hash(root / "caller", exclude={".git", ".venv"}),
        "caller_git_excluding_worktree_admin": tree_hash(root / "caller" / ".git", exclude={"worktrees"}),
        "caller_venv": tree_hash(root / "caller" / ".venv"),
        "sim_home": tree_hash(root / "home"),
        "shared_tmp": tree_hash(root / "shared-tmp"),
        "contracts": tree_hash(root / "contracts"),
        "context": tree_hash(root / "context"),
        "tools": tree_hash(root / "tools"),
        "marker_files_anywhere_in_fixture": markers,
    }


def restore(root):
    root = Path(root)
    fixture = json.loads((root / "evidence" / "fixture.json").read_text())
    base = fixture["base"]
    log = {"base": base, "commands": []}
    pre_status = git(root, "status", "--porcelain", "--ignored", "--untracked-files=all")[1]
    log["pre_restore_status"] = pre_status.splitlines()
    for args in (("reset", "--hard", "--quiet", base), ("clean", "-ffdxq")):
        rc, out, err = git(root, *args)
        log["commands"].append({"argv": ["git", "-C", "<root>/review-wt", *args], "rc": rc, "stderr": err})
    owned = root / "owned-tmp"
    removed = []
    for entry in sorted(owned.iterdir()):
        removed.append(entry.name)
        subprocess.run(["rm", "-rf", "--one-file-system", "--", str(entry)], check=True)
    log["owned_tmp_disposed_entries"] = removed
    log["verify"] = {
        "head": git(root, "rev-parse", "HEAD")[1],
        "tree": git(root, "rev-parse", "HEAD^{tree}")[1],
        "status_porcelain_ignored": git(root, "status", "--porcelain", "--ignored", "--untracked-files=all")[1],
        "owned_tmp_entries": sorted(os.listdir(owned)),
        "venv_present": (root / "review-wt" / ".venv").exists(),
    }
    v = log["verify"]
    log["exact_baseline_verified"] = (v["head"] == base and v["tree"] == fixture["tree"]
                                      and v["status_porcelain_ignored"] == "" and not v["owned_tmp_entries"]
                                      and not v["venv_present"])
    return log


def inspect(root, events_path):
    root = str(Path(root).resolve())
    sensitive = {
        "caller_path": root + "/caller",
        "sim_home": root + "/home",
        "shared_tmp": root + "/shared-tmp",
        "real_home": "/root",
        "repo_checkout": "/home/user",
    }
    calls, results, finals, models = [], {}, [], set()
    for line in Path(events_path).read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            models.add(ev["message"].get("model"))
            for block in ev["message"].get("content", []):
                if block.get("type") == "tool_use":
                    calls.append({"id": block["id"], "name": block["name"], "input": block["input"],
                                  "parent_tool_use_id": ev.get("parent_tool_use_id")})
        elif ev.get("type") == "user":
            content = ev.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    c = block.get("content")
                    if isinstance(c, list):
                        c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
                    results[block["tool_use_id"]] = {"is_error": block.get("is_error", False), "content": c}
        elif ev.get("type") == "result":
            finals.append({k: ev.get(k) for k in ("subtype", "is_error", "num_turns", "session_id", "terminal_reason", "result")})
        elif ev.get("type") == "system" and ev.get("subtype") == "init":
            finals.append({"init": {k: ev.get(k) for k in ("session_id", "claude_code_version", "model", "agents", "tools", "permissionMode", "cwd")}})
    summary = []
    for c in calls:
        text = json.dumps(c["input"])
        hits = sorted(k for k, v in sensitive.items() if re.search(re.escape(v) + r"(?![\w.-])", text))
        entry = {"id": c["id"], "tool": c["name"], "input": c["input"], "sensitive_path_mentions": hits}
        if c["name"] == "Bash":
            cmd = c["input"].get("command", "")
            entry["uses_sbx_run"] = "/tools/sbx-run" in cmd
        r = results.get(c["id"])
        entry["result_is_error"] = r["is_error"] if r else None
        entry["result_excerpt"] = (r["content"] or "")[:1500] if r else None
        summary.append(entry)
    return {"models": sorted(m for m in models if m), "tool_call_count": len(calls),
            "tools_used": sorted({c["name"] for c in calls}), "calls": summary, "session": finals}


if __name__ == "__main__":
    cmd, root = sys.argv[1], sys.argv[2]
    if cmd == "fingerprint":
        out = fingerprint(root)
    elif cmd == "restore":
        out = restore(root)
    elif cmd == "inspect":
        out = inspect(root, sys.argv[3])
    else:
        raise SystemExit("unknown command")
    print(json.dumps(out, indent=2))
