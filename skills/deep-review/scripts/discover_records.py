#!/usr/bin/env python3
"""Read-only discovery of preserved deep-review records.

Implements the follow-up discovery rules of `protocol.md` ("Follow-up revalidation" and the
`completed_at` timestamp profile): the protocol is the authority, this script only applies it. It
never writes, repairs, or creates anything, and it judges record identity only, never whether a
concern preserves complete original evidence.

    discover_records.py discover --record-root DIR --repository REPO --target-kind pr|branch|range --target-key KEY
    discover_records.py select --record-root DIR --selection RUN_ID_OR_PATH

Each command prints one JSON object. The exit status is 0 only when a source record was found, 1
when explicit selection or another decision is needed, and 2 for a usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

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


def nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_run_id(value: object) -> bool:
    """A bare run directory name: non-blank, with no path separator and not a relative-path component."""
    return nonblank(value) and "/" not in value and "\\" not in value and value not in (".", "..")


class Entry(NamedTuple):
    """A validated record with its completion instant and the directory that holds it."""
    record: dict
    instant: int
    directory: Path

    def summary(self) -> dict:
        return summarize(self.record["run_id"], self.directory / RECORD_FILE, self.record)


def identity_problems(record: dict, expected_run_id: str | None) -> list[str]:
    """Every way a record identity fails validation, in a fixed order."""
    problems = []
    if record.get("format_version") != FORMAT_VERSION or type(record.get("format_version")) is not int:
        problems.append(f"format_version {record.get('format_version')!r} is unsupported (expected {FORMAT_VERSION})")
    run_id = record.get("run_id")
    if not nonblank(run_id):
        problems.append("run_id is missing or empty")
    elif expected_run_id is not None and run_id != expected_run_id:
        problems.append(f"run_id {run_id!r} does not match the record directory {expected_run_id!r}")
    mode = record.get("mode")
    if mode not in MODES:
        problems.append(f"mode {mode!r} is not one of {', '.join(MODES)}")
    if not nonblank(record.get("repository")):
        problems.append("repository is missing or empty")
    target = record.get("target")
    if not isinstance(target, dict):
        problems.append("target is missing or not an object")
    else:
        if target.get("kind") not in TARGET_KINDS:
            problems.append(f"target kind {target.get('kind')!r} is not one of {', '.join(TARGET_KINDS)}")
        if not nonblank(target.get("key")):
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
        if not isinstance(lineage, dict):
            problems.append("lineage is missing or not an object in a follow-up record")
        else:
            earlier = lineage.get("follow_up_run_ids")
            source = lineage.get("source_run_id")
            if not is_run_id(source):
                problems.append("lineage source_run_id is missing, empty, or not a run ID")
            if not isinstance(earlier, list) or not all(nonblank(item) for item in earlier):
                problems.append("lineage follow_up_run_ids is not a list of run IDs")
    elif mode == "full" and "lineage" in record:
        problems.append("lineage is present only in a follow-up record")
    return problems


def summarize(run_id: str, path: Path, record: dict | None) -> dict:
    """The fields a caller needs to show one record.

    Fields are read as the record holds them, so an explicitly selected record with an invalid identity
    still shows what it states. A record without identity has only its run ID and path.
    """
    fields = record or {}
    summary = {
        "run_id": run_id, "path": str(path), "mode": fields.get("mode"),
        "completed_at": fields.get("completed_at"), "completeness": fields.get("completeness"),
        "reviewed_head_sha": fields.get("reviewed_head_sha"),
    }
    lineage = fields.get("lineage")
    if fields.get("mode") == "follow-up" and isinstance(lineage, dict):
        summary["lineage"] = {
            "source_run_id": lineage.get("source_run_id"), "follow_up_run_ids": lineage.get("follow_up_run_ids"),
        }
    return summary


def load_record(directory: Path, expected_run_id: str | None) -> tuple[dict | None, list[str]]:
    """A record's identity and its validation problems.

    The identity is None for a legacy record without one. An identity with problems is returned with them
    so a caller decides whether that disqualifies the record. Unreadable, malformed, and non-object state
    raise RecordProblem because no identity can be read at all.
    """
    state = read_state(directory / RECORD_FILE)
    if "record" not in state:
        return None, []
    record = state["record"]
    if not isinstance(record, dict):
        raise RecordProblem("record identity is not an object")
    return record, identity_problems(record, expected_run_id)


def scan(record_root: Path) -> tuple[list[Entry], list[dict], str | None]:
    """Valid records, skipped records with reasons, and a root problem."""
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
            record, problems = load_record(directory, name)
            if record is None:
                raise RecordProblem("no record identity (a legacy record needs explicit selection)")
            if problems:
                raise RecordProblem("record identity is invalid: " + "; ".join(problems))
        except RecordProblem as problem:
            skipped.append({"run_id": name, "path": str(directory / RECORD_FILE), "reason": str(problem)})
            continue
        valid.append(Entry(record, parse_timestamp(record["completed_at"]), directory))
    return valid, skipped, None


def follow_ups_naming(valid: list[Entry], source_run_id: str) -> list[dict]:
    """Follow-up records whose lineage names the source, in completion order. They are context only."""
    named = [entry for entry in valid
             if entry.record["mode"] == "follow-up" and entry.record["lineage"]["source_run_id"] == source_run_id]
    return [entry.summary() for entry in sorted(named, key=lambda entry: (entry.instant, entry.record["run_id"]))]


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
    full = [entry for entry in valid if entry.record["mode"] == "full" and entry.record["repository"] == repository
            and entry.record["target"] == {"kind": target_kind, "key": target_key}]
    if not full:
        result["reason"] = "no matching full-review record; explicit selection is required"
        return result
    latest = max(entry.instant for entry in full)
    tied = sorted((entry for entry in full if entry.instant == latest), key=lambda entry: entry.record["run_id"])
    result["older_full_review_count"] = sum(1 for entry in full if entry.instant < latest)
    if len(tied) > 1:
        result["status"] = "ambiguous"
        result["reason"] = "matching full-review records share the latest completion instant; explicit selection is required"
        result["ambiguous"] = [entry.summary() for entry in tied]
        return result
    source = tied[0]
    result["status"] = "source"
    result["source"] = source.summary()
    result["follow_ups"] = follow_ups_naming(valid, source.record["run_id"])
    return result


def locate(record_root: Path, selection: str) -> Path:
    """The record directory a selection names.

    A bare name is a run ID and resolves only inside the record root, wherever the working directory is.
    A record elsewhere needs a path form: an absolute path, or one with a separator such as `./old-run`.
    """
    if is_run_id(selection):
        if (record_root / selection).is_dir():
            return record_root / selection
        raise RecordProblem(
            f"no record found for run ID {selection!r} in the record root; "
            f"select a record outside it with a path such as ./{selection} or an absolute path"
        )
    if selection and Path(selection).exists():
        path = Path(selection)
        return path.parent if path.is_file() else path
    raise RecordProblem(f"no record found for selection {selection!r}")


def select_record(record_root: Path | str, selection: str) -> dict:
    """Resolve an explicit run ID or record path to its source full-review record.

    Explicit selection keeps its tolerance: a readable record is selectable even when its identity is
    missing or invalid. `identity_missing` is true when the source record has no identity at all, and
    `identity_problems` and `source_identity_problems` list the problems of the selected and the source
    record separately (the same list when they are one record), for the user's confirmation. A follow-up
    whose lineage names no usable source, or whose source cannot be read or is a follow-up record, is an
    error, whatever other identity problems either record has.
    """
    root = Path(record_root)
    result = {
        "record_root": str(root), "selection": selection, "status": "error", "reason": None,
        "selected": None, "source": None, "identity_missing": False,
        "identity_problems": [], "source_identity_problems": [], "follow_ups": [],
    }
    try:
        directory = locate(root, selection)
        in_root = os.path.realpath(directory.parent) == os.path.realpath(root)
        record, problems = load_record(directory, directory.name if in_root else None)
        selected = summarize(directory.name if problems or record is None else record["run_id"],
                             directory / RECORD_FILE, record)
        source, source_record, source_problems = selected, record, problems
        if (record or {}).get("mode") == "follow-up":
            lineage = record.get("lineage")
            source_id = lineage.get("source_run_id") if isinstance(lineage, dict) else None
            if not is_run_id(source_id):
                raise RecordProblem("the follow-up record names no usable lineage source run ID")
            try:
                source_directory = root / source_id
                source_record, source_problems = load_record(source_directory, source_id)
            except RecordProblem as problem:
                raise RecordProblem(f"the source record {source_id!r} named by lineage cannot be recovered: {problem}") from None
            if (source_record or {}).get("mode") == "follow-up":
                raise RecordProblem(f"the lineage source {source_id!r} is not a full-review record")
            source = summarize(source_id, source_directory / RECORD_FILE, source_record)
    except RecordProblem as problem:
        result["reason"] = str(problem)
        return result
    valid, _, _ = scan(root)
    result.update(status="source", selected=selected, source=source, identity_missing=source_record is None,
                  identity_problems=problems, source_identity_problems=source_problems,
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
