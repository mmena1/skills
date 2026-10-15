"""Deterministic synthetic deep-review run-state records for the issue #121 benchmark.

Research only. The records follow the contents `skills/deep-review/protocol.md`
enumerates for the consolidated run state, as of `main` at 388a424 (after #125 and
#126): the record identity, the publication payload with separately recorded
submission and read-back verification outcomes and comment identifiers, the
intended record directory for preservation, and the follow-up record. Field names
and nesting below the protocol's record identity are this research's assumptions;
the protocol fixes contents, not a schema. Each record is built from its mode's
skeleton by an ordered list of update steps, one step per moment the protocol
requires the coordinator to persist state.
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
FOLLOW_UP_ROWS = (
    "multiple selected concerns", "follow-up validator capacity", "validator probes",
    "validator partial failure", "PR head change", "cleanup",
)
WORDS = (
    "coordinator worktree baseline validator scout hypothesis evidence caller guard "
    "invariant contract branch merge snapshot manifest restoration probe finding "
    "disproved unresolved receipt overlap publication payload cleanup status context "
    "path line commit reachability severity remedy outcome question static writable"
).split()

# Two full-review profiles sized to the retrospective's reported 72 KB and 30 KB
# records, and one follow-up revalidation of five concerns from the large review.
PROFILES = {
    "large": {"mode": "full", "lenses": 5, "hypotheses": 14, "probes": 3, "dispositions": 10, "comments": 6, "words": 60},
    "medium": {"mode": "full", "lenses": 2, "hypotheses": 6, "probes": 1, "dispositions": 4, "comments": 3, "words": 50},
    "follow-up": {"mode": "follow-up", "source": "large", "selected": 5, "deferred": 1, "probes": 1, "words": 58},
}


def skeleton(mode: str = "full") -> dict:
    """The record a run starts from: its mode is known at creation, every other slot is empty."""
    record = {"format_version": 1, "run_id": None, "mode": mode, "repository": None, "target": None,
              "base_sha": None, "reviewed_head_sha": None, "completed_at": None, "completeness": None}
    if mode == "follow-up":
        record["lineage"] = None
    return {
        "record": record,
        "baseline": {"identity": None, "restorations": []},
        "scouts": {},
        "hypotheses": [],
        "validator_outcomes": [],
        "pr_discussion": {"retrieval_complete": None, "retrieved_at": None, "dispositions": []},
        "run_status": {"incomplete": False, "reasons": [], "unattempted_hypotheses": []},
        "runtime_acceptance_receipt": None,
        "final_report": None,
        "cleanup": {"status": "pending", "leftovers": []},
        "publication": {"payload": None, "pre_submission": None, "submission": None,
                        "verification": None, "comment_identifiers": []},
        "preservation": {"record_directory": None, "failure": None},
        "follow_up": None if mode == "full" else {
            "source": None, "selected_concerns": [], "deferred": [], "thread_states": []},
        "runtime_constraints": [],
    }


def _sha(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(40))


def _prose(rng: random.Random, words: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(words)).capitalize() + "."


def _identity(run_id: str, base: str, head: str) -> list[dict]:
    fields = {"run_id": run_id, "repository": "example/repository",
              "target": {"kind": "pr", "key": "example/repository#42"}, "base_sha": base, "reviewed_head_sha": head}
    return [{"op": "set", "path": f"/record/{name}", "value": value} for name, value in fields.items()]


def _baseline(rng: random.Random, base: str, head: str, run_id: str) -> list[dict]:
    return [{"op": "set", "path": "/baseline/identity", "value": {
        "repository": "example/repository", "pr": 42, "base_sha": base, "head_sha": head,
        "merge_ref": "refs/pull/42/merge", "tree": _sha(rng),
        "worktree": f"/tmp/{run_id}/worktree", "context_root": f"/tmp/{run_id}/context",
    }}]


def _hypothesis(rng: random.Random, number: int, lens: str, words: int) -> dict:
    return {
        "id": f"H{number}", "original_ids": [f"{lens}-H{number}"], "origin": lens,
        "title": _prose(rng, 8), "file_line": f"src/module_{number}.py:{10 * number}",
        "potential_severity": rng.choice(("high", "medium", "low")),
        "concern": _prose(rng, words), "evidence": _prose(rng, words),
        "deduplication": _prose(rng, words // 3), "context_references": [f"core-manifest#{number}"],
    }


def _probe_steps(rng: random.Random, number: int, head: str, words: int, label: str, outcomes) -> list[list[dict]]:
    return [
        [{"op": "append", "path": "/baseline/restorations", "value": {
            "before": f"H{number}", "head": head, "tree_verified": True, "status_clean": True}}],
        [{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": f"H{number}", "phase": "writable", "agent": "deep-review-validator-probe",
            label: rng.choice(outcomes), "question": _prose(rng, words // 3),
            "check": _prose(rng, words // 3), "evidence": _prose(rng, words * 2)}}],
    ]


def _closing_steps(rng: random.Random, run_id: str, words: int, rows, receipt_extra: dict, report: dict) -> list[list[dict]]:
    return [
        [{"op": "set", "path": "/runtime_acceptance_receipt", "value": {
            "harness": "Example CLI 1.0", **receipt_extra,
            "validators": ["deep-review-validator-static", "deep-review-validator-probe"],
            "rows": {row: {"status": rng.choice(("PASS", "NOT EXERCISED")), "evidence": _prose(rng, words // 4)} for row in rows},
        }}],
        [{"op": "set", "path": "/final_report", "value": report}],
    ]


def _publication_steps(rng: random.Random, concerns: list[str], head: str, words: int) -> list[list[dict]]:
    comments = [{"concern_id": concern, "path": f"src/module_{concern[1:]}.py", "side": "RIGHT",
                 "line": 10 * int(concern[1:]), "body": _prose(rng, words * 2)} for concern in concerns]
    payload = json.dumps({"event": "COMMENT", "commit_id": head, "body": "", "comments": comments}, indent=2)
    review_id = rng.randrange(10**9, 10**10)
    identifiers = [{"concern_id": c["concern_id"], "review_id": review_id, "comment_id": rng.randrange(10**9, 10**10),
                    "node_id": "PRRC_" + _sha(rng)[:20],
                    "html_url": f"https://github.com/example/repository/pull/42#discussion_r{index}"}
                   for index, c in enumerate(comments)]
    return [
        [{"op": "set", "path": "/publication/payload", "value": payload},
         {"op": "set", "path": "/publication/pre_submission", "value": {
             "pinned_head_sha": head, "account": "reviewer", "submission_started_at": "2026-10-15T10:45:00Z"}}],
        [{"op": "set", "path": "/publication/submission", "value": {
            "outcome": "submitted", "status": 200, "review_id": review_id, "commit_id": head,
            "requested_at": "2026-10-15T10:45:01Z", "responded_at": "2026-10-15T10:45:02Z"}}],
        [{"op": "set", "path": "/publication/verification", "value": {
            "outcome": "verified", "source": "GET pulls/42/reviews/{review_id}/comments", "pagination_complete": True,
            "read_at": "2026-10-15T10:45:10Z", "matched": [c["concern_id"] for c in comments],
            "missing": [], "conflicting": [], "extra": [], "retrieval_error": None}}]
        + [{"op": "append", "path": "/publication/comment_identifiers", "value": item} for item in identifiers],
    ]


def _ending_steps(run_id: str, completeness: str) -> list[list[dict]]:
    return [
        [{"op": "set", "path": "/cleanup/status", "value": "worktree removed and registration verified gone"}],
        [{"op": "set", "path": "/record/completed_at", "value": "2026-10-15T10:50:00Z"},
         {"op": "set", "path": "/record/completeness", "value": completeness}],
        [{"op": "set", "path": "/preservation/record_directory",
          "value": f"/repo/.git/deep-review/records/{run_id}"}],
    ]


def _full_steps(shape: dict, rng: random.Random, run_id: str) -> list[list[dict]]:
    words = shape["words"]
    base, head = _sha(rng), _sha(rng)
    out = [_identity(run_id, base, head), _baseline(rng, base, head, run_id)]
    lenses = LENSES[: shape["lenses"]]
    for lens in lenses:
        out.append([{"op": "set", "path": f"/scouts/{lens}", "value": {
            "agent": f"deep-review-scout-{lens}", "status": "completed",
            "manifest": f"reviewers/{lens}-manifest", "started_at": "2026-10-15T10:00:00Z",
            "finished_at": "2026-10-15T10:04:00Z", "hypothesis_count": 0, "provenance": _prose(rng, words // 2),
        }}])
    hypotheses = [_hypothesis(rng, n, lenses[n % len(lenses)], words) for n in range(1, shape["hypotheses"] + 1)]
    out.append([{"op": "append", "path": "/hypotheses", "value": item} for item in hypotheses])
    needs_probe = set(range(1, shape["probes"] + 1))
    for number in range(1, shape["hypotheses"] + 1):
        outcome = "needs probe" if number in needs_probe else rng.choice(("finding", "disproved", "unresolved"))
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": f"H{number}", "phase": "static", "agent": "deep-review-validator-static",
            "outcome": outcome, "evidence": _prose(rng, words * 2), "recommendation": _prose(rng, words // 2),
        }}])
    for number in sorted(needs_probe):
        out += _probe_steps(rng, number, head, words, "outcome", ("finding", "disproved"))
    out.append([
        {"op": "set", "path": "/pr_discussion/retrieval_complete", "value": True},
        {"op": "set", "path": "/pr_discussion/retrieved_at", "value": "2026-10-15T10:40:00Z"},
    ] + [{"op": "append", "path": "/pr_discussion/dispositions", "value": {
        "hypothesis": f"H{1 + index % shape['hypotheses']}", "disposition": rng.choice(("new", "already reported")),
        "reason": _prose(rng, words // 2), "link": f"https://github.com/example/repository/pull/42#discussion_r{index}",
    }} for index in range(shape["dispositions"])])
    out += _closing_steps(rng, run_id, words, ROWS, {
        "skill_commit": base[:7], "lenses": {lens: f"deep-review-scout-{lens}" for lens in lenses}}, {
        "hypotheses_discovered": shape["hypotheses"], "hypotheses_after_dedupe": shape["hypotheses"],
        "summary": _prose(rng, words * 3),
        "actions": [{"hypothesis": f"H{n}", "action": rng.choice(("fix-now", "follow-up", "discuss"))}
                    for n in range(1, shape["hypotheses"] + 1)],
    })
    out += _publication_steps(rng, [f"H{n}" for n in range(1, shape["comments"] + 1)], head, words)
    return out + _ending_steps(run_id, "complete")


def _follow_up_steps(shape: dict, rng: random.Random, run_id: str) -> list[list[dict]]:
    """Follow-up revalidation: no scouts or overlap, read-only toward GitHub by default."""
    words = shape["words"]
    source = build(shape["source"])
    base, head = source["record"]["base_sha"], _sha(rng)
    selected = source["hypotheses"][: shape["selected"]]
    deferred = selected[-shape["deferred"]:]
    revalidated = selected[: -shape["deferred"]]
    out = [_identity(run_id, base, head) + [{"op": "set", "path": "/record/lineage", "value": {
        "source_run_id": source["record"]["run_id"], "follow_up_run_ids": []}}],
        _baseline(rng, base, head, run_id)]
    originals = []
    for concern in selected:
        outcome = next(o for o in source["validator_outcomes"] if o["hypothesis"] == concern["id"] and o["phase"] == "static")
        originals.append({"hypothesis": concern, "original_outcome": outcome,
                          "original_reviewed_head_sha": source["record"]["reviewed_head_sha"]})
    out.append([{"op": "set", "path": "/follow_up/source", "value": {
        "run_id": source["record"]["run_id"], "path": f"/repo/.git/deep-review/records/{source['record']['run_id']}",
        "completeness": source["record"]["completeness"], "reviewed_head_sha": source["record"]["reviewed_head_sha"],
        "older_matching_full_records": 0}}]
        + [{"op": "append", "path": "/follow_up/selected_concerns", "value": item} for item in originals]
        + [{"op": "append", "path": "/follow_up/deferred", "value": {"concern": c["id"], "reason": _prose(rng, 8)}}
           for c in deferred])
    needs_probe = {concern["id"] for concern in revalidated[: shape["probes"]]}
    for concern in revalidated:
        status = "needs probe" if concern["id"] in needs_probe else rng.choice(("Addressed", "Not addressed"))
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": concern["id"], "phase": "static", "agent": "deep-review-validator-static",
            "status": status, "evidence": _prose(rng, words * 2)}}])
    for concern_id in sorted(needs_probe):
        out += _probe_steps(rng, int(concern_id[1:]), head, words, "status", ("Addressed", "Not addressed"))
    out.append([{"op": "append", "path": "/follow_up/thread_states", "value": {
        "concern": c["id"], "state": rng.choice(("open", "resolved", "outdated", "not published"))}} for c in selected])
    out += _closing_steps(rng, run_id, words, FOLLOW_UP_ROWS, {"skill_commit": base[:7], "scouts": "not run"}, {
        "label": "Follow-up revalidation: not a full PR review", "summary": _prose(rng, words * 2),
        "statuses": [{"concern": c["id"], "status": "Deferred" if c in deferred else "revalidated"} for c in selected],
    })
    return out + _ending_steps(run_id, "complete")


def steps(profile: str, seed: int = 121) -> list[list[dict]]:
    """Ordered update steps; each step is the op list one persistence moment applies."""
    shape = PROFILES[profile]
    rng = random.Random(f"{profile}-{seed}")
    run_id = f"20261015T100000Z-{profile}"
    return (_full_steps if shape["mode"] == "full" else _follow_up_steps)(shape, rng, run_id)


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
    record = skeleton(PROFILES[profile]["mode"])
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
