#!/usr/bin/env python3
"""Reproduce an offline descriptive report from the sealed original pilot evidence archive."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile


ARCHIVE_SHA256 = "82d329db655a752c0a8fb8a779f390d9cbfb053a7789f5814eb27f92d5cabf51"
GATE_SHA256 = {
    "pilot-1": "470a7b01fa7e31dda2bdb00dbbef3288bf36e550568f29ddff706a07776970ec",
    "pilot-2": "657affb52c44809c81fc80c0de2a7cd3e23269c8130dbde53a3c4faf19c20eb7",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_extract(archive, destination):
    root = Path(destination).resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"unsupported archive member type: {member.name}")
        bundle.extractall(root)


def failed_checks(receipt):
    return [check for check in receipt.get("checks", []) if not check.get("pass")]


def actual_usage(*roots):
    totals = {"sessions": 0, "requests": 0, "input_tokens": 0, "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0, "output_tokens": 0}
    for root in roots:
        for meta_path in sorted(Path(root).rglob("meta.json")):
            meta = load_json(meta_path)
            usage = meta.get("usage") or {}
            totals["sessions"] += 1
            for key in totals.keys() - {"sessions"}:
                totals[key] += usage.get(key, 0) or 0
    return totals


def format_failures(receipt):
    lines = []
    for check in failed_checks(receipt):
        detail = json.dumps(check.get("detail"), sort_keys=True, ensure_ascii=False)
        lines.append(f"- `{check['check']}`: {detail}")
    return "\n".join(lines) or "- None"


def render(evidence):
    original = evidence / "receipts/attempts/pilot-1/gate-pilot.json"
    second = evidence / "receipts/gate-pilot.json"
    if sha256(original) != GATE_SHA256["pilot-1"] or sha256(second) != GATE_SHA256["pilot-2"]:
        raise ValueError("an original gate receipt hash does not match the retained snapshot")
    gate1, gate2 = load_json(original), load_json(second)
    pilot1_sessions = evidence / "sessions/attempts/pilot-1"
    pilot2_sessions = [evidence / "sessions/pilot", evidence / "sessions/challenges"]
    pilot2_validator = evidence / "sessions/challenges/X1/result.txt"
    quota_rows = []
    for log in sorted((evidence / "sessions/pilot").rglob("api.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("status") == 429:
                quota_rows.append(row)
    validator_text = pilot2_validator.read_text(encoding="utf-8").strip().splitlines()[0]
    g1_failures = failed_checks(gate1)
    g2_failures = failed_checks(gate2)
    challenge2 = load_json(evidence / "receipts/challenges.json")
    x1 = next(item for item in challenge2["results"] if item["id"] == "X1")
    validator_excerpt = "> " + validator_text.replace("\n", "\n> ")
    return f"""# Issue 89 original pilot failures, offline report v1

**EXPLORATORY retrospective.** This report describes retained original failure receipts. It does not rescore either pilot, rewrite any result, establish recall, or replace the original FAIL gates.

## Reproduction and integrity

Input archive is retained on the operator host at `/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/takeover-snapshot-b481487ca52ce86f/preexisting-evidence.tar.gz` (SHA-256 `{ARCHIVE_SHA256}`). The reproducer checks this archive hash before extraction and checks the individual original gate receipt hashes. Absolute session paths printed inside gate details are historical strings only; the reproducer never follows them. All inspected files come from the immutable archive. Run it with:

```bash
python3 /path/to/reproduce_pilot_failures.py --snapshot /path/to/preexisting-evidence.tar.gz --output original-pilot-failures-v1.md
```

Pilot 1 gate SHA-256: `{GATE_SHA256['pilot-1']}`. Pilot 2 gate SHA-256: `{GATE_SHA256['pilot-2']}`. Original files are read from archive members and are not modified.

## Pilot 1

Original verdict: **{gate1['verdict']}**, recorded at `{gate1['at']}`. The original gate failed these checks:

{format_failures(gate1)}

The retained receipt records eight completed scout sessions and seven unique hypotheses, all within the validator cap. Six validator dispositions parsed. Replay `R-ca85afb1` returned `{(evidence / 'sessions/attempts/pilot-1/pilot/validators/R-ca85afb1/result.txt').read_text(encoding='utf-8').strip().splitlines()[0]}`; the v1 outcome parser did not recognize that bold label with a colon, so disposition accounting failed. The no-leakage failure listed five retained superseded adjudication sessions and one shakedown refusal outside the evidence used by the pilot. The challenge gate passed. These are descriptions of the original gate and result text, not a new gate computation.

Actual retained session usage: `{json.dumps(actual_usage(pilot1_sessions), sort_keys=True)}`.

## Pilot 2

Original verdict: **{gate2['verdict']}**, recorded at `{gate2['at']}`. The original gate failed these checks:

{format_failures(gate2)}

All eight scouts completed with paired settings. Seven hypotheses were replayed within the cap. The scoped leakage check passed. Challenge X1 had status `{x1['status']}` but no parsed disposition. Its first output line was:

{validator_excerpt}

This supported output form was not recognized by the parser, so the validator conformance gate failed. The pilot gate also recorded only three of seven hypotheses with completed assessments.

The retained pilot API logs contain {len(quota_rows)} HTTP 429 response(s), including provider `rate_limit_error` responses saying the account's rate limit would be exceeded. The original evaluator then created attempt 2 for affected evaluator sessions, which also received quota errors. This left assessments, novelty audits and rejection classifications incomplete. No later sessions can recover the lost quota within this attempt.

Actual retained session usage: `{json.dumps(actual_usage(*pilot2_sessions), sort_keys=True)}`. This is observed per-session request and token accounting. The provider-side quota was not measured exactly.

## Scientific status and acceptance

Both pilot attempts remain operational **FAIL** receipts. The isolated scout outputs and validator evidence are retained, but incomplete matching, novelty auditing, rejection classification and validator disposition accounting prevent a scientifically complete pilot assessment. Neither pilot supports a recall estimate or a treatment comparison. The preregistered full experiment of sixty scout invocations was not run. Issue 89's acceptance requirement for an audited passing pilot and completed full comparison therefore remains incomplete.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = sha256(args.snapshot)
    if digest != ARCHIVE_SHA256:
        raise SystemExit(f"snapshot hash mismatch: expected {ARCHIVE_SHA256}, got {digest}")
    with tempfile.TemporaryDirectory(prefix="issue89-report-") as temporary:
        safe_extract(args.snapshot, temporary)
        evidence = Path(temporary) / "structural-calibration-benchmark-20261009"
        report = render(evidence)
    args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
