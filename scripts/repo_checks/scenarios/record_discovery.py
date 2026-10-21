"""The preserved-record discovery group: exercises the deep-review discovery script at its public seams.

The script is a skill file, not a repository-check model, so this runner loads it by path, builds
disposable record roots, and asserts the documented discovery rules over scenario tables.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from ..common import ROOT, CheckFailure, fail


SCRIPT = ROOT / "skills/deep-review/scripts/discover_records.py"
REPOSITORY, TARGET_KIND, TARGET_KEY = "mmena1/skills", "pr", "mmena1/skills#7"
SHA = "a" * 40


def load_discovery():
    if not SCRIPT.is_file():
        fail(f"{SCRIPT.relative_to(ROOT)}: the record discovery script is missing")
    spec = importlib.util.spec_from_file_location("deep_review_discover_records", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # keep the skill directory free of bytecode
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def identity(run_id: str, completed_at: object = "2026-10-20T10:00:00Z", **overrides: object) -> dict:
    record = {
        "format_version": 1, "run_id": run_id, "mode": "full", "repository": REPOSITORY,
        "target": {"kind": TARGET_KIND, "key": TARGET_KEY}, "base_sha": SHA, "reviewed_head_sha": "b" * 40,
        "completed_at": completed_at, "completeness": "complete",
    }
    record.update(overrides)
    return record


def follow_up(run_id: str, source: str, completed_at: object, earlier: tuple[str, ...] = ()) -> dict:
    return identity(run_id, completed_at, mode="follow-up",
                    lineage={"source_run_id": source, "follow_up_run_ids": list(earlier)})


def write_record(root: Path, run_id: str, state: object = None, raw: bytes | None = None) -> Path:
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    payload = raw if raw is not None else json.dumps(state).encode("utf-8")
    (directory / "run-state.json").write_bytes(payload)
    return directory


def write_identity(root: Path, record: dict, **extra: object) -> Path:
    return write_record(root, record["run_id"], {"record": record, **extra})


def snapshot(root: Path) -> dict[str, tuple[bytes | None, int]]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes() if path.is_file() else None, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
    }


def run_ids(entries: list[dict]) -> list[str]:
    return [entry["run_id"] for entry in entries]


def discover(module, root: Path, kind: str = TARGET_KIND, key: str = TARGET_KEY, repository: str = REPOSITORY) -> dict:
    return module.discover(root, repository, kind, key)


SCENARIO = ""


def begin(name: str, location: object = "") -> None:
    """Name the scenario group and the record root under test so a failing assertion reports its input."""
    global SCENARIO
    SCENARIO = f"{name} in {location}" if location else name


def problem(message: str) -> None:
    """Report a failed assertion with the scenario group and record root under test."""
    fail(f"record discovery [{SCENARIO}]: {message}")


def expect(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        problem(f"{label}: expected {expected!r}, got {actual!r}")


def validate_failure_reporting() -> None:
    """A failed assertion raises the check failure with the scenario and the expectation, never a recursion."""
    begin("failure_reporting", "a deliberately failing assertion")
    try:
        expect("a deliberate mismatch", 1, 2)
    except CheckFailure as error:
        expect("the failure names the scenario and the expectation",
               str(error), "record discovery [failure_reporting in a deliberately failing assertion]: "
                           "a deliberate mismatch: expected 2, got 1")
    else:
        fail("record discovery: a failed expectation did not raise the check failure")


def validate_timestamps(module) -> None:
    """Instants compare by actual time across offsets and fraction lengths; unsupported values are diagnosed."""
    begin("timestamps")
    parse = module.parse_timestamp
    expect("a UTC and an equivalent offset form are the same instant",
           parse("2026-10-20T12:00:00Z"), parse("2026-10-20T14:00:00+02:00"))
    expect("fraction length does not change the instant", parse("2026-10-20T12:00:00.5Z"), parse("2026-10-20T12:00:00.500000Z"))
    expect("a zero fraction equals no fraction", parse("2026-10-20T12:00:00.000Z"), parse("2026-10-20T12:00:00Z"))
    expect("a negative offset moves the instant later", parse("2026-10-20T04:00:00-06:00") > parse("2026-10-20T11:00:00Z"), False)
    expect("nanosecond precision orders instants", parse("2026-10-20T12:00:00.123456789Z") > parse("2026-10-20T12:00:00.123456788Z"), True)
    expect("a lexicographically larger text can be an earlier instant",
           parse("2026-10-20T11:00:00+02:00") < parse("2026-10-20T10:00:00Z"), True)
    expect("an offset can cross the year boundary", parse("2026-01-01T00:30:00+01:00"), parse("2025-12-31T23:30:00Z"))
    expect("the earliest representable instant stays comparable", parse("0001-01-01T00:00:00+01:00") < parse("0001-01-01T00:00:00Z"), True)

    cases = {
        "2026-10-20T12:00:00": "UTC offset",
        "2026-10-20T12:00:00-00:00": "unknown offset",
        "2026-10-20 12:00:00Z": "unsupported",
        "2026-10-20t12:00:00Z": "unsupported",
        "2026-10-20T12:00:00z": "unsupported",
        "20261020T120000Z": "unsupported",
        "2026-10-20T12:00Z": "unsupported",
        "2026-10-20": "unsupported",
        "2026-10-20T12:00:00+0200": "unsupported",
        "2026-10-20T12:00:00+02": "unsupported",
        "2026-10-20T12:00:00.Z": "unsupported",
        "2026-10-20T12:00:00.1234567890Z": "unsupported",
        "2026-13-20T12:00:00Z": "invalid",
        "2026-02-30T12:00:00Z": "invalid",
        "2026-10-20T24:00:00Z": "invalid",
        "2026-10-20T12:60:00Z": "invalid",
        "2026-10-20T12:00:60Z": "invalid",
        "2026-10-20T12:00:00+24:00": "invalid",
        "2026-10-20T12:00:00+02:60": "invalid",
        "": "unsupported",
        " 2026-10-20T12:00:00Z": "unsupported",
        "2026-10-20T12:00:00Z\n": "unsupported",
    }
    for text, reason in cases.items():
        try:
            parse(text)
        except module.TimestampError as error:
            if reason not in str(error):
                problem(f"timestamp {text!r} diagnostic {str(error)!r} lacks {reason!r}")
        else:
            problem(f"timestamp {text!r} was accepted")
    for value in (None, 12345, 1.5, ["2026-10-20T12:00:00Z"]):
        try:
            parse(value)
        except module.TimestampError as error:
            if "string" not in str(error):
                problem(f"non-string timestamp {value!r} diagnostic {str(error)!r} lacks 'string'")
        else:
            problem(f"non-string timestamp {value!r} was accepted")


def validate_source_selection(module, base: Path) -> None:
    """The latest full review by instant is the source, whatever its textual form, and ties are ambiguous."""
    begin("source_selection", base)
    root = base / "instants"
    write_identity(root, identity("r-utc", "2026-10-20T10:00:00Z"))
    write_identity(root, identity("r-plus", "2026-10-20T11:00:00+02:00"))
    write_identity(root, identity("r-minus", "2026-10-20T04:00:00.5-06:00"))
    result = discover(module, root)
    expect("the source is the latest instant, not the lexicographic maximum", (result["status"], result["source"]["run_id"]), ("source", "r-minus"))
    expect("older matching full-review records are counted", result["older_full_review_count"], 2)
    expect("source completeness is reported", result["source"]["completeness"], "complete")
    expect("nothing is skipped", result["skipped"], [])

    for left, right in (
        ("2026-10-20T12:00:00Z", "2026-10-20T14:00:00+02:00"),
        ("2026-10-20T12:00:00Z", "2026-10-20T12:00:00.000000Z"),
        ("2026-10-20T12:00:00.5Z", "2026-10-20T06:00:00.50-06:00"),
    ):
        tie = base / f"tie-{left[-3:]}-{right[-8:]}"
        write_identity(tie, identity("t-old", "2026-10-19T00:00:00Z"))
        write_identity(tie, identity("t-b", right))
        write_identity(tie, identity("t-a", left, completeness="incomplete"))
        result = discover(module, tie)
        expect(f"equal instants {left} and {right} are ambiguous", (result["status"], result["source"]), ("ambiguous", None))
        expect("the tied records are listed in run ID order", run_ids(result["ambiguous"]), ["t-a", "t-b"])
        expect("a tie reports each candidate's completeness", [entry["completeness"] for entry in result["ambiguous"]], ["incomplete", "complete"])

    nanos = base / "nanos"
    write_identity(nanos, identity("n-low", "2026-10-20T12:00:00.123456788Z"))
    write_identity(nanos, identity("n-high", "2026-10-20T12:00:00.123456789Z"))
    expect("a nanosecond difference selects a source", discover(module, nanos)["source"]["run_id"], "n-high")

    expect("a missing record root has no source", discover(module, base / "absent")["status"], "none")
    empty = base / "empty"
    empty.mkdir()
    expect("an empty record root has no source", discover(module, empty)["status"], "none")


def validate_filtering_and_lineage(module, base: Path) -> None:
    """Repository and target identity filter candidates; a newer follow-up never becomes the source."""
    begin("filtering_and_lineage", base)
    root = base / "filtering"
    write_identity(root, identity("full-1", "2026-10-20T10:00:00Z"))
    write_identity(root, identity("full-other-repo", "2026-10-21T10:00:00Z", repository="someone/else"))
    write_identity(root, identity("full-other-kind", "2026-10-21T11:00:00Z", target={"kind": "branch", "key": TARGET_KEY}))
    write_identity(root, identity("full-other-key", "2026-10-21T12:00:00Z", target={"kind": TARGET_KIND, "key": "mmena1/skills#8"}))
    write_identity(root, identity("full-case", "2026-10-21T13:00:00Z", repository="MMENA1/skills"))
    write_identity(root, follow_up("fu-1", "full-1", "2026-10-22T10:00:00Z"))
    write_identity(root, follow_up("fu-2", "full-1", "2026-10-23T10:00:00+00:00", ("fu-1",)))
    write_identity(root, follow_up("fu-foreign", "full-other-key", "2026-10-24T10:00:00Z"))
    result = discover(module, root)
    expect("only the identity-matching full review is the source", (result["status"], result["source"]["run_id"]), ("source", "full-1"))
    expect("a newer subset-only follow-up never replaces the source", result["older_full_review_count"], 0)
    expect("lineage-named follow-ups supply prior context in completion order", run_ids(result["follow_ups"]), ["fu-1", "fu-2"])
    expect("filtered records are not skipped", result["skipped"], [])

    only_follow_up = base / "follow-up-only"
    write_identity(only_follow_up, follow_up("fu-1", "gone", "2026-10-22T10:00:00Z"))
    result = discover(module, only_follow_up)
    expect("a follow-up alone is never a source", (result["status"], result["source"]), ("none", None))

    branch = base / "branch"
    write_identity(branch, identity("b-1", target={"kind": "branch", "key": "refs/heads/feature"}))
    expect("a branch target matches by kind and key",
           discover(module, branch, "branch", "refs/heads/feature")["source"]["run_id"], "b-1")

    ranges = base / "ranges"
    write_identity(ranges, identity("g-1", target={"kind": "range", "key": f"{SHA}..{'c' * 40}"}))
    result = discover(module, ranges, "range", f"{SHA}..{'c' * 40}")
    expect("a commit-range target requires explicit selection", (result["status"], result["source"]), ("none", None))
    if "explicit selection" not in result.get("reason", ""):
        problem("a commit-range target must say explicit selection is required")


def validate_skipped_records(module, base: Path) -> None:
    """Unusable candidates are reported with specific reasons in deterministic order; the rest still resolve."""
    begin("skipped_records", base)
    root = base / "skipped"
    write_identity(root, identity("good", "2026-10-20T10:00:00Z"))
    (root / "a-empty").mkdir()
    write_record(root, "b-malformed", raw=b'{"record": ')
    write_record(root, "c-binary", raw=b"\xff\xfe\x00")
    write_record(root, "d-array", ["not", "an", "object"])
    write_record(root, "e-legacy", {"hypotheses": []})
    write_record(root, "f-record-scalar", {"record": "oops"})
    (root / "g-directory" / "run-state.json").mkdir(parents=True)
    (root / "stray-file.txt").write_text("not a record", encoding="utf-8")
    invalid = {
        "h-run-id": identity("someone-else"),
        "i-version": identity("i-version", format_version=2),
        "j-mode": identity("j-mode", mode="partial"),
        "k-repository": identity("k-repository", repository=""),
        "l-kind": identity("l-kind", target={"kind": "tag", "key": "v1"}),
        "m-key": identity("m-key", target={"kind": "pr", "key": " "}),
        "n-target": identity("n-target", target="pr"),
        "o-base": identity("o-base", base_sha="zzz"),
        "p-head": identity("p-head", reviewed_head_sha=""),
        "q-completeness": identity("q-completeness", completeness="done"),
        "r-timestamp": identity("r-timestamp", "2026-10-20T10:00:00"),
        "s-full-lineage": identity("s-full-lineage", lineage={"source_run_id": "good", "follow_up_run_ids": []}),
        "t-follow-up-no-lineage": identity("t-follow-up-no-lineage", mode="follow-up"),
        "u-lineage-source": identity("u-lineage-source", mode="follow-up", lineage={"source_run_id": "", "follow_up_run_ids": []}),
        "v-lineage-list": identity("v-lineage-list", mode="follow-up", lineage={"source_run_id": "good", "follow_up_run_ids": "x"}),
    }
    for run_id, record in invalid.items():
        write_record(root, run_id, {"record": record})
    expectations = {
        "a-empty": "run-state.json is unreadable",
        "b-malformed": "malformed JSON",
        "c-binary": "malformed JSON",
        "d-array": "not a JSON object",
        "e-legacy": "no record identity",
        "f-record-scalar": "record identity is not an object",
        "g-directory": "run-state.json is unreadable",
        "h-run-id": "run_id",
        "i-version": "format_version",
        "j-mode": "mode",
        "k-repository": "repository",
        "l-kind": "target kind",
        "m-key": "target key",
        "n-target": "target",
        "o-base": "base_sha",
        "p-head": "reviewed_head_sha",
        "q-completeness": "completeness",
        "r-timestamp": "completed_at",
        "s-full-lineage": "lineage",
        "t-follow-up-no-lineage": "lineage",
        "u-lineage-source": "lineage",
        "v-lineage-list": "lineage",
    }
    result = discover(module, root)
    expect("a valid record still resolves beside skipped ones", (result["status"], result["source"]["run_id"]), ("source", "good"))
    expect("skipped records are listed in run ID order", run_ids(result["skipped"]), sorted(expectations))
    for entry in result["skipped"]:
        if expectations[entry["run_id"]] not in entry["reason"]:
            problem(f"skipped {entry['run_id']} reason {entry['reason']!r} lacks {expectations[entry['run_id']]!r}")
    expect("an unusable record is never counted as a match", result["older_full_review_count"], 0)
    expect("the result is deterministic", json.dumps(discover(module, root)), json.dumps(result))

    shuffled = base / "shuffled"
    for run_id in reversed(sorted(expectations)):
        if run_id in invalid:
            write_record(shuffled, run_id, {"record": invalid[run_id]})
    write_identity(shuffled, identity("good", "2026-10-20T10:00:00Z"))
    expect("creation order does not change the skipped order",
           run_ids(discover(module, shuffled)["skipped"]), sorted(invalid))

    unsupported = base / "unsupported-timestamp"
    write_identity(unsupported, identity("old", "2026-10-19T10:00:00Z"))
    write_identity(unsupported, identity("bad", "2026-10-21 10:00:00Z"))
    result = discover(module, unsupported)
    expect("an unsupported newer timestamp never wins or falls through silently",
           (result["source"]["run_id"], run_ids(result["skipped"])), ("old", ["bad"]))
    if "unsupported" not in result["skipped"][0]["reason"]:
        problem("an unsupported timestamp must be diagnosed in the skipped reason")


def validate_legacy_incomplete_concerns(module, base: Path) -> None:
    """Discovery checks identity, never per-concern evidence, so an incomplete legacy source stays the source."""
    begin("legacy_incomplete_concerns", base)
    root = base / "legacy"
    write_identity(root, identity("older-complete", "2026-10-18T10:00:00Z"), hypotheses=[{"canonical_id": "H1", "title": "t"}])
    write_identity(root, identity("newest-incomplete", "2026-10-19T10:00:00Z", completeness="stale"),
                   hypotheses=[{"canonical_id": "H1"}, {"canonical_id": "H2", "title": ""}], outcomes={})
    write_identity(root, identity("newest-empty", "2026-10-17T10:00:00Z"))
    result = discover(module, root)
    expect("the newest valid source is not replaced for incomplete concerns",
           (result["status"], result["source"]["run_id"]), ("source", "newest-incomplete"))
    expect("the source completeness status is reported", result["source"]["completeness"], "stale")
    expect("older matching full-review records are counted", result["older_full_review_count"], 2)
    expect("incomplete concerns do not skip the record", result["skipped"], [])


def validate_explicit_selection(module, base: Path) -> None:
    """Explicit selection accepts identity-less legacy records and resolves a follow-up to its source."""
    begin("explicit_selection", base)
    root = base / "explicit"
    legacy = write_record(root, "legacy-run", {"hypotheses": [{"canonical_id": "H1"}]})
    write_identity(root, identity("full-run", "2026-10-20T10:00:00Z", target={"kind": "range", "key": f"{SHA}..{'c' * 40}"}))
    write_identity(root, follow_up("fu-1", "full-run", "2026-10-21T10:00:00Z"))
    write_identity(root, follow_up("fu-2", "full-run", "2026-10-22T10:00:00Z", ("fu-1",)))
    write_identity(root, follow_up("fu-orphan", "missing-run", "2026-10-22T10:00:00Z"))
    write_identity(root, follow_up("fu-bad-source", "fu-1", "2026-10-22T10:00:00Z"))
    write_record(root, "fu-unreadable-source", {"record": follow_up("fu-unreadable-source", "broken-run", "2026-10-22T10:00:00Z")})
    write_record(root, "broken-run", raw=b"{")
    write_identity(root, follow_up("legacy-follow-up", "legacy-run", "2026-10-22T10:00:00Z"))

    result = module.select_record(root, "legacy-run")
    expect("a legacy record is selectable by run ID", (result["status"], result["source"]["run_id"]), ("source", "legacy-run"))
    expect("a missing identity is shown for confirmation", result["identity_missing"], True)
    expect("a legacy record has no completeness to report", result["source"]["completeness"], None)
    for form in (str(legacy), str(legacy / "run-state.json")):
        by_path = module.select_record(root, form)
        expect(f"a legacy record is selectable by path {Path(form).name}", (by_path["status"], by_path["source"]["run_id"]), ("source", "legacy-run"))

    result = module.select_record(root, "full-run")
    expect("an identified full review is its own source regardless of target kind", (result["status"], result["source"]["run_id"]), ("source", "full-run"))
    expect("an identified record needs no identity confirmation", result["identity_missing"], False)
    expect("a selected full review lists the follow-ups naming it", run_ids(result["follow_ups"]), ["fu-1", "fu-2"])

    result = module.select_record(root, "fu-2")
    expect("a follow-up resolves through its lineage to the source",
           (result["status"], result["selected"]["run_id"], result["source"]["run_id"]), ("source", "fu-2", "full-run"))
    expect("the lineage follow-ups remain context", run_ids(result["follow_ups"]), ["fu-1", "fu-2"])
    result = module.select_record(root, str(root / "fu-1" / "run-state.json"))
    expect("a follow-up selected by path also resolves to its source", result["source"]["run_id"], "full-run")

    result = module.select_record(root, "legacy-follow-up")
    expect("a follow-up built on a legacy source resolves to it",
           (result["status"], result["source"]["run_id"], result["identity_missing"]), ("source", "legacy-run", True))
    expect("the follow-up naming a legacy source is listed", run_ids(result["follow_ups"]), ["legacy-follow-up"])

    failures = {
        "unknown-run": "no record found",
        "fu-orphan": "source record 'missing-run'",
        "fu-bad-source": "not a full-review",
        "fu-unreadable-source": "source record 'broken-run'",
        "broken-run": "malformed JSON",
        "": "no record found",
        "../outside": "no record found",
    }
    for selection, reason in failures.items():
        result = module.select_record(root, selection)
        if result["status"] != "error" or reason not in result["reason"]:
            problem(f"selection {selection!r} expected an error naming {reason!r}, got {result!r}")
        if result["source"] is not None:
            problem(f"failed selection {selection!r} must not report a source")

    write_record(root, "invalid-run", {"record": identity("invalid-run", completed_at="soon")})
    result = module.select_record(root, "invalid-run")
    expect("an identity-invalid record stays selectable", (result["status"], result["source"]["run_id"]), ("source", "invalid-run"))
    expect("its identity problems are shown for confirmation, not reported as a missing identity",
           (result["identity_missing"], len(result["identity_problems"]), result["source_identity_problems"] == result["identity_problems"]),
           (False, 1, True))
    if "completed_at" not in result["identity_problems"][0]:
        problem(f"the timestamp diagnostic must be shown for confirmation, got {result!r}")
    write_record(root, "renamed-dir", {"record": identity("original-name")})
    result = module.select_record(root, "renamed-dir")
    expect("a record whose run_id disagrees with its directory stays selectable",
           (result["status"], result["source"]["run_id"], "run_id" in result["identity_problems"][0]), ("source", "renamed-dir", True))
    write_identity(root, follow_up("fu-invalid-source", "invalid-run", "2026-10-22T10:00:00Z"))
    result = module.select_record(root, "fu-invalid-source")
    expect("a follow-up resolves to a source whose identity is invalid, with the source's problems apart from its own",
           (result["status"], result["source"]["run_id"], result["identity_problems"], len(result["source_identity_problems"])),
           ("source", "invalid-run", [], 1))
    write_record(root, "fu-invalid-follow-up", {"record": follow_up("fu-invalid-follow-up", "full-run", "later")})
    write_identity(root, follow_up("fu-over-invalid-follow-up", "fu-invalid-follow-up", "2026-10-23T10:00:00Z"))
    result = module.select_record(root, "fu-over-invalid-follow-up")
    if result["status"] != "error" or "not a full-review" not in result["reason"] or result["source"] is not None:
        problem(f"a lineage source that is a follow-up with other identity errors must be rejected, got {result!r}")
    result = module.select_record(root, "fu-invalid-follow-up")
    expect("a selected follow-up with an invalid identity keeps its own problems apart from a valid source's",
           (result["status"], result["source"]["run_id"], result["identity_missing"], result["source_identity_problems"]),
           ("source", "full-run", False, []))
    expect("the selected follow-up's metadata and problems are shown",
           (result["selected"]["run_id"], result["selected"]["mode"], result["selected"]["completed_at"], len(result["identity_problems"])),
           ("fu-invalid-follow-up", "follow-up", "later", 1))
    if "completed_at" not in result["identity_problems"][0]:
        problem(f"the selected follow-up's timestamp diagnostic must be shown, got {result!r}")
    write_record(root, "fu-no-lineage", {"record": identity("fu-no-lineage", mode="follow-up")})
    result = module.select_record(root, "fu-no-lineage")
    if result["status"] != "error" or "lineage source" not in result["reason"]:
        problem(f"a follow-up without a usable lineage source must be an error, got {result!r}")

    cwd_root = base / "cwd"
    write_identity(cwd_root / "records", identity("shared", "2026-10-20T10:00:00Z"))
    unrelated = write_record(cwd_root / "elsewhere", "other", {"hypotheses": []}).parent
    (unrelated / "shared").mkdir()
    selected = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "select", "--record-root", str(cwd_root / "records"), "--selection", "shared"],
        capture_output=True, text=True, cwd=unrelated,
    )
    payload = json.loads(selected.stdout)
    expect("a run ID in the record root resolves there whatever the working directory holds",
           (selected.returncode, payload["status"], payload["source"]["run_id"]), (0, "source", "shared"))

    def select_from(directory: Path, selection: str) -> tuple[int, dict]:
        completed = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "select", "--record-root", str(cwd_root / "records"), "--selection", selection],
            capture_output=True, text=True, cwd=directory,
        )
        return completed.returncode, json.loads(completed.stdout)

    write_identity(cwd_root / "elsewhere", identity("old-run", "2026-10-19T10:00:00Z"))
    code, payload = select_from(cwd_root / "elsewhere", "old-run")
    expect("a bare run ID absent from the record root never resolves against the working directory",
           (code, payload["status"], payload["source"], "./old-run" in payload["reason"]), (1, "error", None, True))
    code, payload = select_from(cwd_root / "elsewhere", "./old-run")
    expect("an explicit path form selects a record outside the record root",
           (code, payload["status"], payload["source"]["run_id"]), (0, "source", "old-run"))


def validate_read_only(module, base: Path) -> None:
    """Discovery and selection never create, modify, or repair anything."""
    begin("read_only", base)
    root = base / "read-only"
    write_identity(root, identity("r-1", "2026-10-20T10:00:00Z"))
    write_identity(root, follow_up("fu-1", "r-1", "2026-10-21T10:00:00Z"))
    write_record(root, "legacy", {"hypotheses": []})
    write_record(root, "broken", raw=b"{")
    (root / "empty").mkdir()
    before = snapshot(root)
    discover(module, root)
    module.select_record(root, "fu-1")
    module.select_record(root, "legacy")
    module.select_record(root, "broken")
    expect("the record root is unchanged", snapshot(root), before)
    missing = base / "never-created"
    discover(module, missing)
    module.select_record(missing, "anything")
    if missing.exists():
        problem("a missing record root must not be created")


def validate_command_line(base: Path) -> None:
    """The script is usable directly: JSON on stdout, exit status 0 only when a source is found."""
    begin("command_line", base)
    root = base / "cli"
    write_identity(root, identity("r-1", "2026-10-20T10:00:00Z"))
    write_identity(root, identity("r-2", "2026-10-20T12:00:00Z"))
    write_identity(root, identity("r-3", "2026-10-20T14:00:00+02:00"))
    write_record(root, "legacy", {"hypotheses": []})
    write_record(root, "broken", raw=b"{")
    common = [sys.executable, "-I", str(SCRIPT)]

    def run(*arguments: str) -> tuple[int, dict]:
        result = subprocess.run([*common, *arguments], capture_output=True, text=True)
        try:
            return result.returncode, json.loads(result.stdout)
        except json.JSONDecodeError:
            problem(f"command line {arguments} did not print JSON: {result.stdout!r} {result.stderr!r}")

    selector = ["--record-root", str(root)]
    target = ["--repository", REPOSITORY, "--target-kind", TARGET_KIND, "--target-key", TARGET_KEY]
    code, payload = run("discover", *selector, *target)
    expect("a tie exits non-zero with the ambiguity", (code, payload["status"], run_ids(payload["ambiguous"])), (1, "ambiguous", ["r-2", "r-3"]))
    expect("the skipped records are printed", run_ids(payload["skipped"]), ["broken", "legacy"])
    code, payload = run("select", *selector, "--selection", "r-1")
    expect("a selection prints its source", (code, payload["status"], payload["source"]["run_id"]), (0, "source", "r-1"))
    code, payload = run("select", *selector, "--selection", "missing")
    expect("a failed selection exits non-zero", (code, payload["status"]), (1, "error"))
    code, payload = run("discover", "--record-root", str(base / "cli-empty"), *target)
    expect("no source exits non-zero", (code, payload["status"]), (1, "none"))
    usage = subprocess.run([*common, "discover", *selector], capture_output=True, text=True)
    expect("missing arguments are a usage error", usage.returncode, 2)
    bad_kind = subprocess.run([*common, "discover", *selector, "--repository", "x", "--target-kind", "tag", "--target-key", "y"],
                              capture_output=True, text=True)
    expect("an unknown target kind is a usage error", bad_kind.returncode, 2)


def validate_record_discovery() -> None:
    module = load_discovery()
    validate_failure_reporting()
    validate_timestamps(module)
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        validate_source_selection(module, base)
        validate_filtering_and_lineage(module, base)
        validate_skipped_records(module, base)
        validate_legacy_incomplete_concerns(module, base)
        validate_explicit_selection(module, base)
        validate_read_only(module, base)
        validate_command_line(base)
