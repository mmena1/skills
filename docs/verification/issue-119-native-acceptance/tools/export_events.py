#!/usr/bin/env python3
"""Export a reviewable visible-event subset of a Claude stream-json transcript.

Same field allowlist as the PR's historical bundle: visible assistant text and tool calls,
user tool results, a reduced init record and the final result. Hidden reasoning, usage,
cost, rate-limit telemetry, partial stream events and stderr are omitted. Retained text
is copied without rewriting.
"""
import hashlib
import json
from pathlib import Path
import sys

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
INIT_KEYS = ("type", "subtype", "session_id", "claude_code_version", "model", "cwd", "tools", "agents", "permissionMode", "uuid")
RESULT_KEYS = ("type", "subtype", "is_error", "num_turns", "duration_ms", "session_id", "terminal_reason", "stop_reason", "result", "permission_denials", "uuid")
kept = 0
out = []
for line in src.read_text().splitlines():
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    t = ev.get("type")
    if t == "system" and ev.get("subtype") == "init":
        out.append({k: ev[k] for k in INIT_KEYS if k in ev})
    elif t == "assistant":
        blocks = [b for b in ev["message"].get("content", []) if b.get("type") in ("text", "tool_use")]
        if not blocks:
            continue
        out.append({"type": "assistant", "message": {"id": ev["message"].get("id"), "model": ev["message"].get("model"),
                    "role": "assistant", "content": blocks}, "parent_tool_use_id": ev.get("parent_tool_use_id"),
                    "session_id": ev.get("session_id"), "uuid": ev.get("uuid"), "timestamp": ev.get("timestamp")})
    elif t == "user":
        content = ev.get("message", {}).get("content")
        if isinstance(content, list) and any(b.get("type") == "tool_result" for b in content):
            out.append({"type": "user", "message": {"role": "user", "content": [b for b in content if b.get("type") == "tool_result"]},
                        "parent_tool_use_id": ev.get("parent_tool_use_id"), "session_id": ev.get("session_id"),
                        "uuid": ev.get("uuid"), "timestamp": ev.get("timestamp")})
    elif t == "result":
        out.append({k: ev[k] for k in RESULT_KEYS if k in ev})
dst.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in out))
print(json.dumps({"source": str(src.name), "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                  "retained_event_count": len(out), "exported": str(dst.name)}))
