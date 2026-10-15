"""Measure what each update candidate makes the coordinator emit and read. Research only, issue #121.

    python benchmark.py

Replays every synthetic persistence step for each record profile and prints one
Markdown table per profile. Bytes are UTF-8 bytes of text that passes through the
model's context: text it must emit in a tool call, and text a tool call returns.

A, model-authored whole-record rewrite: each step emits the complete new record
through the write tool; the comparison row adds one full read-back per step, the
reported "editing and comparison" pattern. Finalization emits the receipt, which
embeds the payload and both publication outcomes again.

B, fixed helper: each step emits the step's ops document plus the command line and
reads the helper's actual stdout, measured by running `run_state_helper.py`.

C, native targeted edit: the coordinator writes its mode's skeleton once, then a
file-backed replay applies string replacements to a real file in sequence. Each
edit is found against the file as it stands, with the smallest old string that
occurs exactly once there, widened by whole lines until unique. The replay asserts
that each old string is unique when applied and that the file equals the reference
record after every step, so the counted edits are ones a string-replacement tool
can actually apply. The edit oracle still knows the exact current file, so C's
emission is an optimistic bound: it assumes the coordinator holds every anchor it
edits. The read-before-edit row is the pessimistic case for a harness or session
that must read the whole current file before each edit, for example after context
compaction or because the edit tool requires a prior read. Finalization is the
same as A.
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

# A read-only validity check after an edit: the command the coordinator writes and its output.
CHECK_COMMAND = "python3 -m json.tool {run}/run-state.json > /dev/null && echo ok"
CHECK_OUTPUT = "ok\n"
# Command text the coordinator writes for one helper call, excluding the stdin document.
HELPER_PATH = "python3 ~/.agents/skills/deep-review/run_state_helper.py"
INIT_COMMAND = HELPER_PATH + " init --run-dir {run} --root {root} --mode {mode}"
UPDATE_COMMAND = HELPER_PATH + " update --run-dir {run} --root {root} --expect-sha256 {sha}"
RECEIPT_COMMAND = HELPER_PATH + " finalize-receipt --run-dir {run} --root {root} --expect-sha256 {sha}"


def utf8(text: str) -> int:
    return len(text.encode("utf-8"))


def unique_edit(current: list[str], target: list[str], region: tuple[int, int, int, int]) -> tuple[str, str]:
    """Smallest old/new pair around one changed region whose old string is unique in the current file."""
    i1, i2, j1, j2 = region
    text = "".join(current)
    lead = trail = 0
    while True:
        old = "".join(current[i1 - lead:i2 + trail])
        new = "".join(current[i1 - lead:i1]) + "".join(target[j1:j2]) + "".join(current[i2:i2 + trail])
        if old and text.count(old) == 1:
            return old, new
        if lead <= trail and i1 - lead > 0:
            lead += 1
        elif i2 + trail < len(current):
            trail += 1
        elif i1 - lead > 0:
            lead += 1
        else:
            raise AssertionError("no unique anchor exists for this region")


def replay_step(path: Path, after: str) -> list[tuple[str, str, int]]:
    """Apply one step's targeted edits to the file in sequence; return (old, new, file size before the edit)."""
    edits = []
    for _ in range(10_000):
        current = path.read_text(encoding="utf-8")
        if current == after:
            return edits
        lines, target = current.splitlines(keepends=True), after.splitlines(keepends=True)
        matcher = difflib.SequenceMatcher(a=lines, b=target, autojunk=False)
        tag, *region = next(code for code in matcher.get_opcodes() if code[0] != "equal")
        old, new = unique_edit(lines, target, tuple(region))
        if current.count(old) != 1:
            raise AssertionError("an edit's old string is not unique in the file it is applied to")
        path.write_text(current.replace(old, new, 1), encoding="utf-8")
        edits.append((old, new, utf8(current)))
    raise AssertionError("replay did not converge")


def replay_native_edits(profile: str, directory: Path) -> list[list[tuple[str, str, int]]]:
    """File-backed replay of candidate C for every step; asserts the exact record after each step."""
    record = synthetic_records.skeleton(synthetic_records.PROFILES[profile]["mode"])
    path = directory / f"{profile}-run-state.json"
    path.write_text(synthetic_records.serialize(record), encoding="utf-8")
    replayed = []
    for step in synthetic_records.steps(profile):
        for op in step:
            synthetic_records.apply_op(record, op)
        after = synthetic_records.serialize(record)
        replayed.append(replay_step(path, after))
        if path.read_text(encoding="utf-8") != after:
            raise AssertionError("replayed file differs from the reference record")
    return replayed


def helper_stdout(*arguments: str, stdin: str = "") -> str:
    result = subprocess.run([sys.executable, str(HERE / "run_state_helper.py"), *arguments],
                            input=stdin, text=True, capture_output=True, check=True)
    return result.stdout


def model_receipt(record: dict) -> str:
    publication = record["publication"]
    return synthetic_records.serialize({
        "payload": publication["payload"], "payload_sha256": "0" * 64, "submission": publication["submission"],
        "verification": publication["verification"], "comment_identifiers": publication["comment_identifiers"],
    })


def measure(profile: str) -> dict:
    mode = synthetic_records.PROFILES[profile]["mode"]
    steps = synthetic_records.steps(profile)
    m = {key: 0 for key in ("a_emit", "a_read", "a_max_step", "b_emit", "b_read", "b_max_step",
                            "c_emit", "c_calls", "c_max_step", "c_read_before_edit")}
    record = synthetic_records.skeleton(mode)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        run_dir = root / "run"
        run_dir.mkdir()
        location = {"run": run_dir, "root": root}
        out = helper_stdout("init", "--run-dir", str(run_dir), "--root", str(root), "--mode", mode)
        m["b_emit"], m["b_read"] = utf8(INIT_COMMAND.format(mode=mode, **location)), utf8(out)
        digest = json.loads(out)["sha256"]
        for step in steps:
            for op in step:
                synthetic_records.apply_op(record, op)
            after = utf8(synthetic_records.serialize(record))
            m["a_emit"] += after
            m["a_read"] += after
            m["a_max_step"] = max(m["a_max_step"], after)
            document = json.dumps({"ops": step}, ensure_ascii=False)
            out = helper_stdout("update", "--run-dir", str(run_dir), "--root", str(root),
                                "--expect-sha256", digest, stdin=document)
            b_step = utf8(document) + utf8(UPDATE_COMMAND.format(sha=digest, **location))
            m["b_emit"] += b_step
            m["b_max_step"] = max(m["b_max_step"], b_step)
            m["b_read"] += utf8(out)
            digest = json.loads(out)["sha256"]
        if record["publication"]["payload"] is not None:
            out = helper_stdout("finalize-receipt", "--run-dir", str(run_dir), "--root", str(root), "--expect-sha256", digest)
            m["receipt_model"] = utf8(model_receipt(record))
            m["receipt_helper"] = utf8(RECEIPT_COMMAND.format(sha=digest, **location)) + utf8(out)
        else:
            m["receipt_model"] = m["receipt_helper"] = 0
        m["final_bytes"] = (run_dir / "run-state.json").stat().st_size
        m["check_emit"] = utf8(CHECK_COMMAND.format(run=run_dir))
        m["c_emit"] = utf8(synthetic_records.serialize(synthetic_records.skeleton(mode)))
        m["c_calls"] = 1
        for edits in replay_native_edits(profile, root):
            m["c_calls"] += len(edits)
            c_step = sum(utf8(old) + utf8(new) for old, new, _ in edits)
            m["c_emit"] += c_step
            m["c_max_step"] = max(m["c_max_step"], c_step)
            m["c_read_before_edit"] += sum(size for _, _, size in edits)
    m["steps"] = len(steps)
    m["ops_documents"] = sum(utf8(json.dumps({"ops": step}, ensure_ascii=False)) for step in steps)
    return m


def kib(value: int) -> str:
    return f"{value / 1024:,.1f} KiB"


def table(profile: str, m: dict) -> str:
    a_total = m["a_emit"] + m["a_read"] + m["receipt_model"]
    rows = [
        ("A, whole-record rewrite, no comparison", m["a_emit"], 0, m["steps"], m["receipt_model"]),
        ("A, whole-record rewrite plus read-back comparison", m["a_emit"], m["a_read"], 2 * m["steps"], m["receipt_model"]),
        ("B, fixed helper", m["b_emit"], m["b_read"], m["steps"] + 1, m["receipt_helper"]),
        ("C, native targeted edit, optimistic bound", m["c_emit"], 0, m["c_calls"], m["receipt_model"]),
        ("C plus one validity check per step", m["c_emit"] + m["steps"] * m["check_emit"],
         m["steps"] * len(CHECK_OUTPUT), m["c_calls"] + m["steps"], m["receipt_model"]),
        ("C with a full read before every edit", m["c_emit"], m["c_read_before_edit"],
         2 * m["c_calls"] - 1, m["receipt_model"]),
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
    lines += [
        "",
        f"Ops documents alone total {kib(m['ops_documents'])}.",
        "",
        "| Per update, emitted by the coordinator | Mean | Largest step |",
        "| --- | --- | --- |",
        f"| A, whole-record rewrite (read-back comparison reads the same again) | {kib(m['a_emit'] // m['steps'])} | {kib(m['a_max_step'])} |",
        f"| B, fixed helper (reads back about {m['b_read'] // (m['steps'] + 1)} bytes) | {kib(m['b_emit'] // (m['steps'] + 1))} | {kib(m['b_max_step'])} |",
        f"| C, native targeted edit (reads back a short success message, or the whole file before each edit) | {kib(m['c_emit'] // m['c_calls'])} | {kib(m['c_max_step'])} |",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    for name in synthetic_records.PROFILES:
        print(table(name, measure(name)))
        print()
