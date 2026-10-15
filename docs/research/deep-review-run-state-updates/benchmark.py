"""Measure what each update candidate makes the coordinator emit and read. Research only, issue #121.

    python benchmark.py

Replays every synthetic persistence step for both record profiles and prints one
Markdown table per profile. Bytes are UTF-8 bytes of text that passes through the
model's context: text it must emit in a tool call, and text a tool call returns.

A, model-authored whole-record rewrite: each step emits the complete new record
through the write tool; the comparison column adds one full read-back per step,
the reported "editing and comparison" pattern. Finalization emits the receipt,
which embeds the payload again.

B, fixed helper: each step emits the step's ops document plus the command line and
reads the helper's actual stdout, measured by running `run_state_helper.py`.

C, native targeted edit: each step emits, per changed region, the old and new
strings a unique string-replacement edit needs, found by widening line context
until the old string occurs once. The coordinator first writes the empty skeleton,
so it has seen every anchor it later edits and no read is counted; each forced
re-read, for example after context compaction or an external change, adds at most
one full record. Finalization is the same as A.
"""

import difflib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import synthetic_records  # noqa: E402

RECEIPT = {"review_id": 5550001, "comment_ids": [1, 2, 3, 4, 5, 6], "posted_at": "2026-10-15T10:50:00Z"}
# Output of a read-only validity check after an edit, for example `python3 -m json.tool FILE > /dev/null && echo ok`.
CHECK_OUTPUT = "ok\n"
# Command text the coordinator writes for one helper call, excluding the stdin document.
COMMAND = "python3 ~/.agents/skills/deep-review/run_state_helper.py update --run-dir {run} --root {root} --expect-sha256 {sha}"


def utf8(text: str) -> int:
    return len(text.encode("utf-8"))


def unique_edit(before: list[str], after: list[str], i1: int, i2: int, j1: int, j2: int) -> tuple[str, str]:
    """Smallest old/new pair around one changed region whose old string is unique in the file."""
    text = "".join(before)
    lead = trail = 0
    while True:
        old = "".join(before[i1 - lead:i2 + trail])
        new = "".join(before[i1 - lead:i1]) + "".join(after[j1:j2]) + "".join(before[i2:i2 + trail])
        if old and text.count(old) == 1:
            return old, new
        if lead <= trail and i1 - lead > 0:
            lead += 1
        elif i2 + trail < len(before):
            trail += 1
        elif i1 - lead > 0:
            lead += 1
        else:
            return old, new


def targeted_edits(before_text: str, after_text: str) -> list[tuple[str, str]]:
    before = before_text.splitlines(keepends=True)
    after = after_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    return [unique_edit(before, after, i1, i2, j1, j2)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def helper_stdout(run_dir: Path, root: Path, *arguments: str, stdin: str = "") -> str:
    result = subprocess.run(
        [sys.executable, str(HERE / "run_state_helper.py"), *arguments, "--run-dir", str(run_dir), "--root", str(root)],
        input=stdin, text=True, capture_output=True, check=True,
    )
    return result.stdout


def measure(profile: str) -> dict:
    steps = synthetic_records.steps(profile)
    totals = {key: 0 for key in ("a_emit", "a_read", "b_emit", "b_read", "c_emit", "c_read", "c_calls", "c_max_edit")}
    record = synthetic_records.skeleton()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        run_dir = root / "run"
        run_dir.mkdir()
        out = helper_stdout(run_dir, root, "init")
        totals["b_emit"] = utf8(COMMAND.format(run=run_dir, root=root, sha="").replace(" update ", " init ").replace(" --expect-sha256 ", ""))
        totals["b_read"] = utf8(out)
        digest = json.loads(out)["sha256"]
        totals["c_emit"] = utf8(synthetic_records.serialize(record))
        totals["c_calls"] = 1
        for step in steps:
            before = synthetic_records.serialize(record)
            for op in step:
                synthetic_records.apply_op(record, op)
            after = synthetic_records.serialize(record)
            totals["a_emit"] += utf8(after)
            totals["a_read"] += utf8(after)
            document = json.dumps({"ops": step}, ensure_ascii=False)
            out = helper_stdout(run_dir, root, "update", "--expect-sha256", digest, stdin=document)
            totals["b_emit"] += utf8(document) + utf8(COMMAND.format(run=run_dir, root=root, sha=digest))
            totals["b_read"] += utf8(out)
            digest = json.loads(out)["sha256"]
            edits = targeted_edits(before, after)
            totals["c_calls"] += len(edits)
            for old, new in edits:
                totals["c_emit"] += utf8(old) + utf8(new)
                totals["c_max_edit"] = max(totals["c_max_edit"], utf8(old) + utf8(new))
        receipt = synthetic_records.serialize({
            "payload": record["publication"]["payload"], "payload_sha256": "0" * 64, "receipt": RECEIPT,
        })
        out = helper_stdout(run_dir, root, "finalize-receipt", "--expect-sha256", digest, stdin=json.dumps(RECEIPT))
        totals["receipt_model"] = utf8(receipt)
        totals["receipt_helper"] = utf8(json.dumps(RECEIPT)) + utf8(COMMAND.format(run=run_dir, root=root, sha=digest)) + utf8(out)
        totals["final_bytes"] = (run_dir / "run-state.json").stat().st_size
    totals["steps"] = len(steps)
    totals["ops_documents"] = sum(utf8(json.dumps({"ops": step}, ensure_ascii=False)) for step in steps)
    return totals


def kib(value: int) -> str:
    return f"{value / 1024:,.1f} KiB"


def table(profile: str, m: dict) -> str:
    a_total = m["a_emit"] + m["a_read"] + m["receipt_model"]
    rows = [
        ("A, whole-record rewrite, no comparison", m["a_emit"], 0, m["steps"], m["receipt_model"]),
        ("A, whole-record rewrite plus read-back comparison", m["a_emit"], m["a_read"], 2 * m["steps"], m["receipt_model"]),
        ("B, fixed helper", m["b_emit"], m["b_read"], m["steps"] + 1, m["receipt_helper"]),
        ("C, native targeted edit", m["c_emit"], m["c_read"], m["c_calls"], m["receipt_model"]),
        ("C plus one validity check per step", m["c_emit"], m["c_read"] + m["steps"] * len(CHECK_OUTPUT), m["c_calls"] + m["steps"], m["receipt_model"]),
    ]
    lines = [
        f"Profile `{profile}`: final record {m['final_bytes']:,} bytes ({kib(m['final_bytes'])}), {m['steps']} persistence steps.",
        "",
        "| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, emit, read, calls, receipt in rows:
        total = emit + read + receipt
        lines.append(f"| {name} | {kib(emit)} | {kib(read)} | {calls} | {kib(receipt)} | {kib(total)} | {100 * total / a_total:.1f}% |")
    lines.append("")
    lines.append(f"Ops documents alone total {kib(m['ops_documents'])}; the largest single targeted edit is {kib(m['c_max_edit'])}.")
    return "\n".join(lines)


if __name__ == "__main__":
    for name in synthetic_records.PROFILES:
        print(table(name, measure(name)))
        print()
