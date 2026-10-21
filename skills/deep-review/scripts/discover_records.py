#!/usr/bin/env python3
"""Read-only discovery of preserved deep-review records.

Applies the follow-up discovery rules of `protocol.md` ("Follow-up revalidation") to a record
root: match records by repository and target identity, choose the latest full-review source by
completion instant, resolve an explicit selection through its lineage, and report every record
that cannot be used. It never writes, repairs, or creates anything, and it judges record
identity only: whether a concern preserves complete original evidence is decided later, per
concern, so an otherwise valid legacy source stays discoverable.

    discover_records.py discover --record-root DIR --repository REPO --target-kind pr|branch|range --target-key KEY
    discover_records.py select --record-root DIR --selection RUN_ID_OR_PATH

Each command prints one JSON object. The exit status is 0 only when a source record was found, 1
when explicit selection or another decision is needed, and 2 for a usage error.

`completed_at` timestamps use one profile: `YYYY-MM-DDThh:mm:ss`, an optional fraction of 1 to 9
digits, then `Z` or a `+hh:mm` / `-hh:mm` offset. They compare as instants with nanosecond
precision, so equivalent instants tie whatever their textual form. A timestamp without an offset,
with the unknown `-00:00` offset, in another form, or out of range is diagnosed and its record is
skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

RECORD_FILE = "run-state.json"
FORMAT_VERSION = 1
MODES = ("full", "follow-up")
TARGET_KINDS = ("pr", "branch", "range")
COMPLETENESS = ("complete", "incomplete", "stale")
SHA = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")
TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,9}))?(Z|[+-][0-9]{2}:[0-9]{2})?"
)


class TimestampError(ValueError):
    """A completion timestamp outside the supported profile, with the specific reason."""


class RecordProblem(Exception):
    """Why one candidate record cannot be used."""


def parse_timestamp(value: object) -> int:
    """Return the instant as integer nanoseconds since 0001-01-01T00:00:00Z, or raise TimestampError."""
    if not isinstance(value, str):
        raise TimestampError(f"timestamp must be a string, not {type(value).__name__}")
    match = TIMESTAMP.fullmatch(value)
    if match is None:
        raise TimestampError(
            f"unsupported timestamp {value!r}; expected YYYY-MM-DDThh:mm:ss[.fraction] followed by Z, +hh:mm, or -hh:mm"
        )
    year, month, day, hour, minute, second, fraction, zone = match.groups()
    if zone is None:
        raise TimestampError(f"timestamp {value!r} has no UTC offset, so its instant is ambiguous; add Z or +hh:mm")
    if zone == "-00:00":
        raise TimestampError(f"timestamp {value!r} uses the unknown offset -00:00, so its instant is ambiguous")
    try:
        ordinal = date(int(year), int(month), int(day)).toordinal()
    except ValueError:
        raise TimestampError(f"invalid calendar date in timestamp {value!r}") from None
    if int(hour) > 23 or int(minute) > 59 or int(second) > 59:
        raise TimestampError(f"invalid time of day in timestamp {value!r}")
    offset = 0
    if zone != "Z":
        offset_hour, offset_minute = int(zone[1:3]), int(zone[4:6])
        if offset_hour > 23 or offset_minute > 59:
            raise TimestampError(f"invalid UTC offset in timestamp {value!r}")
        offset = (1 if zone[0] == "+" else -1) * (offset_hour * 3600 + offset_minute * 60)
    seconds = ordinal * 86400 + int(hour) * 3600 + int(minute) * 60 + int(second) - offset
    return seconds * 10**9 + int((fraction or "").ljust(9, "0"))


def read_state(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise RecordProblem(f"{RECORD_FILE} is unreadable: {error.strerror or type(error).__name__}") from None
    try:
        state = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise RecordProblem(f"malformed JSON: {error}") from None
    if not isinstance(state, dict):
        raise RecordProblem(f"{RECORD_FILE} is not a JSON object")
    return state


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def identity_problems(record: dict, expected_run_id: str | None) -> list[str]:
    """Every way a record identity fails validation, in a fixed order."""
    problems = []
    if record.get("format_version") != FORMAT_VERSION or type(record.get("format_version")) is not int:
        problems.append(f"format_version {record.get('format_version')!r} is unsupported (expected {FORMAT_VERSION})")
    run_id = record.get("run_id")
    if not text(run_id):
        problems.append("run_id is missing or empty")
    elif expected_run_id is not None and run_id != expected_run_id:
        problems.append(f"run_id {run_id!r} does not match the record directory {expected_run_id!r}")
    mode = record.get("mode")
    if mode not in MODES:
        problems.append(f"mode {mode!r} is not one of {', '.join(MODES)}")
    if not text(record.get("repository")):
        problems.append("repository is missing or empty")
    target = record.get("target")
    if not isinstance(target, dict):
        problems.append("target is missing or not an object")
    else:
        if target.get("kind") not in TARGET_KINDS:
            problems.append(f"target kind {target.get('kind')!r} is not one of {', '.join(TARGET_KINDS)}")
        if not text(target.get("key")):
            problems.append("target key is missing or empty")
    for key in ("base_sha", "reviewed_head_sha"):
        if not isinstance(record.get(key), str) or SHA.fullmatch(record[key]) is None:
            problems.append(f"{key} is missing or not a full commit SHA")
    try:
        parse_timestamp(record.get("completed_at"))
    except TimestampError as error:
        problems.append(f"completed_at: {error}")
    if record.get("completeness") not in COMPLETENESS:
        problems.append(f"completeness {record.get('completeness')!r} is not one of {', '.join(COMPLETENESS)}")
    lineage = record.get("lineage")
    if mode == "follow-up":
        earlier = lineage.get("follow_up_run_ids") if isinstance(lineage, dict) else None
        if not isinstance(lineage, dict):
            problems.append("lineage is missing or not an object in a follow-up record")
        else:
            source = lineage.get("source_run_id")
            if not text(source) or "/" in source or "\\" in source or source in (".", ".."):
                problems.append("lineage source_run_id is missing, empty, or not a run ID")
            if not isinstance(earlier, list) or not all(text(item) for item in earlier):
                problems.append("lineage follow_up_run_ids is not a list of run IDs")
    elif mode == "full" and "lineage" in record:
        problems.append("lineage is present only in a follow-up record")
    return problems


def summarize(run_id: str, path: Path, record: dict | None) -> dict:
    """The fields a caller needs to show one record; a record without identity has only its run ID and path."""
    summary = {
        "run_id": run_id, "path": str(path),
        "mode": record["mode"] if record else None,
        "completed_at": record["completed_at"] if record else None,
        "completeness": record["completeness"] if record else None,
        "reviewed_head_sha": record["reviewed_head_sha"] if record else None,
    }
    if record and record["mode"] == "follow-up":
        summary["lineage"] = {
            "source_run_id": record["lineage"]["source_run_id"],
            "follow_up_run_ids": list(record["lineage"]["follow_up_run_ids"]),
        }
    return summary


def load_record(directory: Path, expected_run_id: str | None) -> dict | None:
    """The validated identity of the record in a directory, or None for a legacy record without one."""
    state = read_state(directory / RECORD_FILE)
    if "record" not in state:
        return None
    record = state["record"]
    if not isinstance(record, dict):
        raise RecordProblem("record identity is not an object")
    problems = identity_problems(record, expected_run_id)
    if problems:
        raise RecordProblem("record identity is invalid: " + "; ".join(problems))
    return record


def scan(record_root: Path) -> tuple[list[tuple[dict, int, Path]], list[dict], str | None]:
    """Valid records as (identity, instant, directory), skipped records with reasons, and a root problem."""
    if not record_root.is_dir():
        return [], [], "record root does not exist"
    try:
        names = sorted(entry.name for entry in os.scandir(record_root) if entry.is_dir())
    except OSError as error:
        return [], [], f"record root is unreadable: {error.strerror or type(error).__name__}"
    valid, skipped = [], []
    for name in names:
        directory = record_root / name
        try:
            record = load_record(directory, name)
            if record is None:
                raise RecordProblem("no record identity (a legacy record needs explicit selection)")
        except RecordProblem as problem:
            skipped.append({"run_id": name, "path": str(directory / RECORD_FILE), "reason": str(problem)})
            continue
        valid.append((record, parse_timestamp(record["completed_at"]), directory))
    return valid, skipped, None


def follow_ups_naming(valid: list[tuple[dict, int, Path]], source_run_id: str) -> list[dict]:
    """Follow-up records whose lineage names the source, in completion order. They are context only."""
    named = [item for item in valid if item[0]["mode"] == "follow-up" and item[0]["lineage"]["source_run_id"] == source_run_id]
    return [summarize(record["run_id"], directory / RECORD_FILE, record)
            for record, _, directory in sorted(named, key=lambda item: (item[1], item[0]["run_id"]))]


def discover(record_root: Path | str, repository: str, target_kind: str, target_key: str) -> dict:
    """Find the source record for a resolved target, or report why none can be chosen automatically."""
    root = Path(record_root)
    result = {
        "record_root": str(root), "repository": repository, "target": {"kind": target_kind, "key": target_key},
        "status": "none", "reason": None, "source": None, "older_full_review_count": 0,
        "ambiguous": [], "follow_ups": [], "skipped": [],
    }
    if target_kind == "range":
        result["reason"] = "a commit-range target requires explicit selection of a record"
        return result
    valid, result["skipped"], problem = scan(root)
    if problem:
        result["reason"] = problem
        return result
    full = [item for item in valid if item[0]["mode"] == "full" and item[0]["repository"] == repository
            and item[0]["target"] == {"kind": target_kind, "key": target_key}]
    if not full:
        result["reason"] = "no matching full-review record; explicit selection is required"
        return result
    latest = max(instant for _, instant, _ in full)
    tied = sorted((item for item in full if item[1] == latest), key=lambda item: item[0]["run_id"])
    result["older_full_review_count"] = sum(1 for _, instant, _ in full if instant < latest)
    if len(tied) > 1:
        result["status"] = "ambiguous"
        result["reason"] = "matching full-review records share the latest completion instant; explicit selection is required"
        result["ambiguous"] = [summarize(record["run_id"], directory / RECORD_FILE, record) for record, _, directory in tied]
        return result
    record, _, directory = tied[0]
    result["status"] = "source"
    result["source"] = summarize(record["run_id"], directory / RECORD_FILE, record)
    result["follow_ups"] = follow_ups_naming(valid, record["run_id"])
    return result


def locate(record_root: Path, selection: str) -> Path:
    """The record directory a run ID or record path names; raise RecordProblem when it names none or several."""
    bare = bool(selection) and selection not in (".", "..") and "/" not in selection and "\\" not in selection
    candidates = []
    if bare and (record_root / selection).is_dir():
        candidates.append(record_root / selection)
    if selection and Path(selection).exists():
        path = Path(selection)
        candidates.append(path.parent if path.is_file() else path)
    if len({os.path.realpath(candidate) for candidate in candidates}) > 1:
        raise RecordProblem(f"selection {selection!r} resolves to more than one record: "
                            + ", ".join(sorted(str(candidate) for candidate in candidates)))
    if not candidates:
        raise RecordProblem(f"no record found for selection {selection!r}")
    return candidates[0]


def select_record(record_root: Path | str, selection: str) -> dict:
    """Resolve an explicit run ID or record path to its source full-review record."""
    root = Path(record_root)
    result = {
        "record_root": str(root), "selection": selection, "status": "error", "reason": None,
        "selected": None, "source": None, "identity_missing": False, "follow_ups": [],
    }
    try:
        directory = locate(root, selection)
        in_root = os.path.realpath(directory.parent) == os.path.realpath(root)
        record = load_record(directory, directory.name if in_root else None)
        selected = summarize(directory.name if record is None else record["run_id"], directory / RECORD_FILE, record)
        source, source_record = selected, record
        if record is not None and record["mode"] == "follow-up":
            source_id = record["lineage"]["source_run_id"]
            try:
                source_directory = root / source_id
                source_record = load_record(source_directory, source_id)
            except RecordProblem as problem:
                raise RecordProblem(f"the source record {source_id!r} named by lineage cannot be recovered: {problem}") from None
            if source_record is not None and source_record["mode"] != "full":
                raise RecordProblem(f"the lineage source {source_id!r} is not a full-review record")
            source = summarize(source_id, source_directory / RECORD_FILE, source_record)
    except RecordProblem as problem:
        result["reason"] = str(problem)
        return result
    valid, _, _ = scan(root)
    result.update(status="source", selected=selected, source=source, identity_missing=source_record is None,
                  follow_ups=follow_ups_naming(valid, source["run_id"]))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only discovery of preserved deep-review records.")
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("discover", help="find the source record for a resolved target")
    find.add_argument("--record-root", required=True)
    find.add_argument("--repository", required=True)
    find.add_argument("--target-kind", required=True, choices=TARGET_KINDS)
    find.add_argument("--target-key", required=True)
    choose = commands.add_parser("select", help="resolve an explicit run ID or record path to its source")
    choose.add_argument("--record-root", required=True)
    choose.add_argument("--selection", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "discover":
        result = discover(arguments.record_root, arguments.repository, arguments.target_kind, arguments.target_key)
    else:
        result = select_record(arguments.record_root, arguments.selection)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["status"] == "source" else 1


if __name__ == "__main__":
    raise SystemExit(main())
