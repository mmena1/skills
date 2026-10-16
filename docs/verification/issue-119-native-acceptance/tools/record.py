#!/usr/bin/env python3
"""Append one invocation entry to the consolidated run state (pre-restoration), or attach
its restoration record afterwards.

record.py pre  ROOT ID HYPOTHESIS FP_BEFORE FP_AFTER [ROOT_CHECK_FILE]
record.py post ROOT ID RESTORE_JSON
"""
import hashlib
import json
from pathlib import Path
import sys

mode, root, inv = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
state_path = root / "evidence" / "run-state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {
    "kind": "issue #119 targeted native acceptance; controlled fixture, not a full deep-review run",
    "fixture": json.loads((root / "evidence" / "fixture.json").read_text()),
    "invocations": []}
h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

if mode == "pre":
    hyp, fp_before, fp_after = sys.argv[4], sys.argv[5], sys.argv[6]
    root_check = sys.argv[7] if len(sys.argv) > 7 else None
    insp = json.loads((root / "evidence" / f"{inv}-inspect.json").read_text())
    init = next(s["init"] for s in insp["session"] if "init" in s)
    final = next(s for s in insp["session"] if "init" not in s)
    a, b = json.loads(Path(fp_before).read_text()), json.loads(Path(fp_after).read_text())
    hook_log = root / "owned-tmp" / "issue119-hook-log.json"
    contract = root / "contracts" / f"contract-{inv}.json"
    entry = {
        "invocation": inv, "hypothesis": hyp,
        "harness": {"claude_code_version": init["claude_code_version"], "session_id": init["session_id"],
                    "agent": "deep-review-validator-probe (project-local byte copy of PR-head generated agent)",
                    "models_served": insp["models"], "permission_mode": init["permissionMode"], "tools": init["tools"]},
        "contract_sha256": h(contract), "prompt_sha256": h(root / "evidence" / "prompts" / f"{inv}.txt"),
        "process_gate": json.loads(contract.read_text())["process_gate"],
        "native_tool_calls": [{"id": c["id"], "tool": c["tool"], "uses_sbx_run": c.get("uses_sbx_run"),
                               "sensitive_path_mentions": c["sensitive_path_mentions"], "result_is_error": c["result_is_error"]}
                              for c in insp["calls"]],
        "validator_final": final["result"], "validator_terminal": {k: final.get(k) for k in ("subtype", "is_error", "num_turns", "terminal_reason")},
        "hook_log": json.loads(hook_log.read_text()) if hook_log.exists() else None,
        "fingerprint_comparison": {k: ("unchanged" if a[k] == b[k] else {"before": a[k], "after": b[k]}) for k in a},
        "root_independent_check": Path(root_check).read_text().strip() if root_check else None,
        "pre_restoration_status": sorted(p.name for p in (root / "review-wt").iterdir() if p.name not in (".git",)),
        "owned_tmp_entries": sorted(p.name for p in (root / "owned-tmp").iterdir()),
        "events_sha256": h(root / "evidence" / f"{inv}-events.jsonl"),
    }
    state["invocations"].append(entry)
elif mode == "post":
    entry = next(e for e in state["invocations"] if e["invocation"] == inv)
    entry["restoration"] = json.loads(Path(sys.argv[4]).read_text())
state_path.write_text(json.dumps(state, indent=2) + "\n")
print("recorded", mode, inv)
