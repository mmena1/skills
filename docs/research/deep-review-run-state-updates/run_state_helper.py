"""Research prototype for issue #121: deterministic deep-review run-state updates.

Not shipped and not wired into the deep-review skill. It evaluates candidate B, a
fixed helper that applies narrowly scoped updates to the consolidated run-state
record so the coordinator never re-emits the whole record.

    run_state_helper.py init   --run-dir DIR --root ROOT
    run_state_helper.py update --run-dir DIR --root ROOT --expect-sha256 HEX < {"ops": [...]}
    run_state_helper.py finalize-receipt --run-dir DIR --root ROOT --expect-sha256 HEX < {receipt}

Every command prints one JSON object on success and exits non-zero with a reason
on stderr otherwise.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

RECORD = "run-state.json"
RECEIPT = "publication-receipt.json"
LOCK = ".run-state.lock"
MARKER = ".deep-review-run"
SKELETON = {
    "schema_version": 1,
    "baseline": {"identity": None, "restorations": []},
    "scouts": {},
    "hypotheses": [],
    "validator_outcomes": [],
    "pr_discussion": {"retrieval_complete": None, "retrieved_at": None, "dispositions": []},
    "run_status": {"incomplete": False, "reasons": [], "unattempted_hypotheses": []},
    "runtime_acceptance_receipt": None,
    "final_report": None,
    "cleanup": {"status": "pending", "leftovers": []},
    "publication": {"payload": None},
    "runtime_constraints": [],
}


class Refusal(Exception):
    pass


def serialize(record: dict) -> bytes:
    return (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write(directory: Path, name: str, data: bytes, replace: bool = True) -> None:
    """Write a sibling temporary file, flush it to disk, then rename it over the target.

    With replace=False the temporary file is hard-linked into place instead, which
    fails atomically when the target already exists.

    RUN_STATE_HELPER_FAULT injects the two interruptions the tests exercise; a
    shipped helper would not carry it.
    """
    fault = os.environ.get("RUN_STATE_HELPER_FAULT")
    temporary = directory / f".{name}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            if fault == "exit-after-partial-write":
                handle.write(data[: len(data) // 2])
                handle.flush()
                os._exit(70)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if fault == "raise-before-replace":
            raise OSError("injected failure before replace")
        if replace:
            os.replace(temporary, directory / name)
        else:
            try:
                os.link(temporary, directory / name)
            except FileExistsError:
                raise Refusal(f"{name} already exists and is never replaced") from None
            temporary.unlink()
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class RunLock:
    """Exclusive per-run lock; a second concurrent writer is refused, never queued.

    An advisory `flock` is released by the kernel when the holder exits, so a killed
    helper leaves no stale lock. A lock file created with O_EXCL would survive the
    kill and block every later update. POSIX only: Windows would need `msvcrt.locking`.
    """

    def __init__(self, run_dir: Path):
        self.path = run_dir / LOCK

    def __enter__(self):
        import fcntl

        self.descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.descriptor)
            raise Refusal(f"run lock {LOCK} is held by another update") from None
        return self

    def __exit__(self, *exc):
        os.close(self.descriptor)


def confine(run_dir: str, root: str, initializing: bool) -> Path:
    """Resolve the run directory, refusing anything but a coordinator-owned directory below root."""
    given = Path(run_dir)
    if not given.is_absolute() or ".." in given.parts:
        raise Refusal("path traversal: --run-dir must be an absolute path without '..'")
    if given.is_symlink():
        raise Refusal("--run-dir is a symlink")
    if not given.is_dir():
        raise Refusal("--run-dir is not an existing directory")
    real_root = Path(os.path.realpath(root))
    real_run = Path(os.path.realpath(given))
    if real_run == real_root or real_root not in real_run.parents:
        raise Refusal("--run-dir resolves outside the coordinator's run root")
    if initializing:
        if any(real_run.iterdir()):
            raise Refusal("--run-dir is not empty; init requires the freshly created run directory")
    elif not (real_run / MARKER).is_file() or (real_run / MARKER).is_symlink():
        raise Refusal("--run-dir is not a coordinator-owned run directory (no init marker)")
    return real_run


def read_record(run_dir: Path) -> bytes:
    if (run_dir / RECORD).is_symlink():
        raise Refusal(f"{RECORD} is a symlink")
    descriptor = os.open(run_dir / RECORD, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as handle:
        return handle.read()


NULLABLE_OBJECT = (dict, type(None))
# Allowed types per field. Objects listed in FIXED_KEYS keep exactly their skeleton keys.
TYPES = {
    "/schema_version": (int,), "/baseline": (dict,), "/scouts": (dict,), "/hypotheses": (list,),
    "/validator_outcomes": (list,), "/pr_discussion": (dict,), "/run_status": (dict,),
    "/runtime_acceptance_receipt": NULLABLE_OBJECT, "/final_report": NULLABLE_OBJECT,
    "/cleanup": (dict,), "/publication": (dict,), "/runtime_constraints": (list,),
    "/baseline/identity": NULLABLE_OBJECT, "/baseline/restorations": (list,),
    "/pr_discussion/retrieval_complete": (bool, type(None)), "/pr_discussion/retrieved_at": (str, type(None)),
    "/pr_discussion/dispositions": (list,), "/run_status/incomplete": (bool,),
    "/run_status/reasons": (list,), "/run_status/unattempted_hypotheses": (list,),
    "/cleanup/status": (str,), "/cleanup/leftovers": (list,), "/publication/payload": (str, type(None)),
}
FIXED_KEYS = ("", "/baseline", "/pr_discussion", "/run_status", "/cleanup", "/publication")
# Recorded evidence grows by append only; nothing already recorded is rewritten.
APPEND_ONLY = ("/hypotheses", "/validator_outcomes", "/baseline/restorations",
               "/pr_discussion/dispositions", "/runtime_constraints")
# Set once from null, then immutable: the pinned baseline and the exact publication payload.
WRITE_ONCE = ("/baseline/identity", "/publication/payload")


def covers(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def tokens(path) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise Refusal(f"invalid path {path!r}: a JSON Pointer below the record root is required")
    return [token.replace("~1", "/").replace("~0", "~") for token in path.split("/")[1:]]


def resolve(record, parts: list[str], path: str):
    target = record
    for part in parts:
        if isinstance(target, dict) and part in target:
            target = target[part]
        elif isinstance(target, list) and part.isdigit() and int(part) < len(target):
            target = target[int(part)]
        else:
            raise Refusal(f"path {path} does not exist")
    return target


def apply_op(record: dict, op) -> None:
    if not isinstance(op, dict):
        raise Refusal("malformed update: each op is an object")
    if op.get("op") not in ("set", "append"):
        raise Refusal(f"unknown op {op.get('op')!r}: only set and append exist")
    if not {"path", "value"} <= set(op):
        raise Refusal("malformed update: each op needs path and value")
    path = op["path"]
    *parents, leaf = tokens(path)
    if op["op"] == "set":
        for prefix in APPEND_ONLY:
            if covers(prefix, path):
                raise Refusal(f"{prefix} is append-only")
        for prefix in WRITE_ONCE:
            if covers(prefix, path) and resolve(record, tokens(prefix), prefix) is not None:
                raise Refusal(f"{prefix} is write-once and already set")
        target = resolve(record, parents, path)
        if isinstance(target, list):
            if not (leaf.isdigit() and int(leaf) < len(target)):
                raise Refusal(f"path {path} does not exist")
            target[int(leaf)] = op["value"]
        elif isinstance(target, dict):
            target[leaf] = op["value"]
        else:
            raise Refusal(f"path {path} does not exist")
    else:
        target = resolve(record, parents + [leaf], path)
        if not isinstance(target, list):
            raise Refusal(f"path {path} is not an array")
        target.append(op["value"])


def validate(record: dict) -> None:
    for pointer, allowed in TYPES.items():
        value = resolve(record, tokens(pointer) if pointer else [], pointer)
        if not isinstance(value, allowed) or (bool not in allowed and isinstance(value, bool)):
            raise Refusal(f"schema violation: {pointer} has type {type(value).__name__}")
    for pointer in FIXED_KEYS:
        value = resolve(record, tokens(pointer) if pointer else [], pointer)
        expected = resolve(SKELETON, tokens(pointer) if pointer else [], pointer)
        if set(value) != set(expected):
            raise Refusal(f"schema violation: {pointer or '/'} keys differ from the run-state contract")
    if not all(isinstance(scout, dict) for scout in record["scouts"].values()):
        raise Refusal("schema violation: every /scouts entry is an object")


def parse_updates(text: str) -> list:
    try:
        updates = json.loads(text)
    except json.JSONDecodeError as error:
        raise Refusal(f"malformed update document: {error}") from None
    if not isinstance(updates, dict) or not isinstance(updates.get("ops"), list) or not updates["ops"]:
        raise Refusal('malformed update document: expected {"ops": [...]} with at least one op')
    return updates["ops"]


def command_init(run_dir: Path) -> dict:
    data = serialize(SKELETON)
    descriptor = os.open(run_dir / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(descriptor)
    atomic_write(run_dir, RECORD, data)
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def command_update(run_dir: Path, expect: str, text: str) -> dict:
    ops = parse_updates(text)
    with RunLock(run_dir):
        current = read_record(run_dir)
        if hashlib.sha256(current).hexdigest() != expect:
            raise Refusal("stale record: --expect-sha256 does not match the current run state")
        record = json.loads(current)
        for op in ops:
            apply_op(record, op)
        validate(record)
        data = serialize(record)
        atomic_write(run_dir, RECORD, data)
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def command_finalize_receipt(run_dir: Path, expect: str, text: str) -> dict:
    """Write publication-receipt.json from the payload already recorded, never a re-emitted copy."""
    try:
        receipt = json.loads(text)
    except json.JSONDecodeError as error:
        raise Refusal(f"malformed receipt document: {error}") from None
    with RunLock(run_dir):
        current = read_record(run_dir)
        if hashlib.sha256(current).hexdigest() != expect:
            raise Refusal("stale record: --expect-sha256 does not match the current run state")
        payload = json.loads(current)["publication"]["payload"]
        if payload is None:
            raise Refusal("no publication payload is recorded; a receipt exists only when publication occurs")
        payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        data = serialize({"payload": payload, "payload_sha256": payload_sha256, "receipt": receipt})
        atomic_write(run_dir, RECEIPT, data, replace=False)
    return {"payload_sha256": payload_sha256, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "update", "finalize-receipt"):
        command = commands.add_parser(name)
        command.add_argument("--run-dir", required=True)
        command.add_argument("--root", required=True)
        if name != "init":
            command.add_argument("--expect-sha256", required=True)
    arguments = parser.parse_args(argv)
    try:
        run_dir = confine(arguments.run_dir, arguments.root, initializing=arguments.command == "init")
        if arguments.command == "init":
            result = command_init(run_dir)
        elif arguments.command == "update":
            result = command_update(run_dir, arguments.expect_sha256, sys.stdin.read())
        else:
            result = command_finalize_receipt(run_dir, arguments.expect_sha256, sys.stdin.read())
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
