"""Deterministic synthetic deep-review run-state records for the issue #121 benchmark.

Research only. The records follow the contents `skills/deep-review/protocol.md`
enumerates for the consolidated run state. Field names and nesting are this
research's assumptions; the protocol fixes the contents, not a schema. Each record
is built from an empty skeleton by an ordered list of update steps, one step per
moment the protocol requires the coordinator to persist state.
"""

import copy
import json
import random

LENSES = ("bugs", "structural", "conventions", "history", "docs")
ROWS = (
    "zero hypotheses", "surviving hypotheses", "capacity-bounded static validation",
    "multiple selected scouts", "insufficient scout capacity", "validator probes",
    "scout failure", "validator partial failure", "PR-review-overlap", "PR head change",
    "cleanup",
)
WORDS = (
    "coordinator worktree baseline validator scout hypothesis evidence caller guard "
    "invariant contract branch merge snapshot manifest restoration probe finding "
    "disproved unresolved receipt overlap publication payload cleanup status context "
    "path line commit reachability severity remedy outcome question static writable"
).split()

# Two profiles sized to the retrospective's reported 72 KB and 30 KB records.
PROFILES = {
    "large": {"lenses": 5, "hypotheses": 14, "probes": 3, "dispositions": 10, "comments": 6, "words": 65},
    "medium": {"lenses": 2, "hypotheses": 6, "probes": 1, "dispositions": 4, "comments": 3, "words": 56},
}


def skeleton() -> dict:
    """The empty record a run starts from; every contract component has a slot."""
    return {
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


def _sha(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(40))


def _prose(rng: random.Random, words: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(words)).capitalize() + "."


def steps(profile: str, seed: int = 121) -> list[list[dict]]:
    """Ordered update steps; each step is the op list one persistence moment applies."""
    shape = PROFILES[profile]
    rng = random.Random(f"{profile}-{seed}")
    words = shape["words"]
    base, head = _sha(rng), _sha(rng)
    out: list[list[dict]] = []

    out.append([{"op": "set", "path": "/baseline/identity", "value": {
        "repository": "example/repository", "pr": 42, "base_sha": base, "head_sha": head,
        "merge_ref": "refs/pull/42/merge", "tree": _sha(rng),
        "worktree": "/tmp/deep-review-run/worktree", "context_root": "/tmp/deep-review-run/context",
    }}])
    lenses = LENSES[: shape["lenses"]]
    for lens in lenses:
        out.append([{"op": "set", "path": f"/scouts/{lens}", "value": {
            "agent": f"deep-review-scout-{lens}", "status": "completed",
            "manifest": f"reviewers/{lens}-manifest", "started_at": "2026-10-15T10:00:00Z",
            "finished_at": "2026-10-15T10:04:00Z", "hypothesis_count": 0, "provenance": _prose(rng, words // 2),
        }}])
    hypotheses = []
    for number in range(1, shape["hypotheses"] + 1):
        lens = lenses[number % len(lenses)]
        hypotheses.append({
            "id": f"H{number}", "original_ids": [f"{lens}-H{number}"], "origin": lens,
            "title": _prose(rng, 8), "file_line": f"src/module_{number}.py:{10 * number}",
            "potential_severity": rng.choice(("high", "medium", "low")),
            "concern": _prose(rng, words), "evidence": _prose(rng, words),
            "deduplication": _prose(rng, words // 3), "context_references": [f"core-manifest#{number}"],
        })
    out.append([{"op": "append", "path": "/hypotheses", "value": item} for item in hypotheses])
    needs_probe = set(range(1, shape["probes"] + 1))
    for number in range(1, shape["hypotheses"] + 1):
        outcome = "needs probe" if number in needs_probe else rng.choice(("finding", "disproved", "unresolved"))
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": f"H{number}", "phase": "static", "agent": "deep-review-validator-static",
            "outcome": outcome, "evidence": _prose(rng, words * 2), "recommendation": _prose(rng, words // 2),
        }}])
    for number in sorted(needs_probe):
        out.append([{"op": "append", "path": "/baseline/restorations", "value": {
            "before": f"H{number}", "head": head, "tree_verified": True, "status_clean": True,
        }}])
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": f"H{number}", "phase": "writable", "agent": "deep-review-validator-probe",
            "outcome": rng.choice(("finding", "disproved")), "question": _prose(rng, words // 3),
            "check": _prose(rng, words // 3), "evidence": _prose(rng, words * 2),
        }}])
    out.append([
        {"op": "set", "path": "/pr_discussion/retrieval_complete", "value": True},
        {"op": "set", "path": "/pr_discussion/retrieved_at", "value": "2026-10-15T10:40:00Z"},
    ] + [{"op": "append", "path": "/pr_discussion/dispositions", "value": {
        "hypothesis": f"H{1 + index % shape['hypotheses']}", "disposition": rng.choice(("new", "already reported")),
        "reason": _prose(rng, words // 2), "link": f"https://github.com/example/repository/pull/42#discussion_r{index}",
    }} for index in range(shape["dispositions"])])
    out.append([{"op": "set", "path": "/runtime_acceptance_receipt", "value": {
        "harness": "Example CLI 1.0", "skill_commit": base[:7],
        "lenses": {lens: f"deep-review-scout-{lens}" for lens in lenses},
        "validators": ["deep-review-validator-static", "deep-review-validator-probe"],
        "rows": {row: {"status": rng.choice(("PASS", "NOT EXERCISED")), "evidence": _prose(rng, words // 4)} for row in ROWS},
    }}])
    out.append([{"op": "set", "path": "/final_report", "value": {
        "hypotheses_discovered": shape["hypotheses"], "hypotheses_after_dedupe": shape["hypotheses"],
        "summary": _prose(rng, words * 3),
        "actions": [{"hypothesis": f"H{n}", "action": rng.choice(("fix-now", "follow-up", "discuss"))}
                    for n in range(1, shape["hypotheses"] + 1)],
    }}])
    comments = [{"path": f"src/module_{n}.py", "line": 10 * n, "body": _prose(rng, words * 2)}
                for n in range(1, shape["comments"] + 1)]
    payload = json.dumps({"event": "COMMENT", "body": _prose(rng, words), "comments": comments}, indent=2)
    out.append([{"op": "set", "path": "/publication/payload", "value": payload}])
    out.append([{"op": "set", "path": "/cleanup/status", "value": "worktree removed; snapshot and run directory pending preservation checks"}])
    return out


def apply_op(record: dict, op: dict) -> None:
    """Reference semantics for one op; the prototype helper validates before applying."""
    *parents, leaf = op["path"].split("/")[1:]
    target = record
    for part in parents:
        target = target[int(part)] if isinstance(target, list) else target[part]
    if op["op"] == "append":
        target[leaf].append(copy.deepcopy(op["value"]))
    else:
        target[leaf] = copy.deepcopy(op["value"])


def build(profile: str) -> dict:
    record = skeleton()
    for step in steps(profile):
        for op in step:
            apply_op(record, op)
    return record


def serialize(record: dict) -> str:
    """The one canonical layout every candidate writes: two-space indentation, insertion order."""
    return json.dumps(record, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    for name in PROFILES:
        print(name, len(serialize(build(name)).encode()), "bytes", len(steps(name)), "steps")
