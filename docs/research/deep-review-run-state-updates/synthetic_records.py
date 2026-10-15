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
# A follow-up receipt keeps every full-review row, marks these as not run, and adds FOLLOW_UP_ROWS.
FULL_REVIEW_ONLY_ROWS = (
    "zero hypotheses", "surviving hypotheses", "multiple selected scouts", "insufficient scout capacity", "scout failure",
)
FOLLOW_UP_ROWS = (
    "fixed concern", "persisting defect", "partial fix", "missing prior evidence", "explicitly deferred concern",
    "resolved thread with a persisting defect", "head change during revalidation", "multiple selected concerns",
    "follow-up validator capacity", "record discovery in a later session",
    "discovery when the newest record is a narrower follow-up", "record preservation from a linked worktree",
    "record preservation under a write restriction",
)
# Only these final outcomes are concerns: they may be published, compared, and revalidated.
CONCERN_OUTCOMES = ("Finding", "Unresolved")
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


def _receipt_rows(rng: random.Random, words: int, mode: str, observed: set) -> dict:
    """Passive receipt: PASS only for scenarios this record models an observation of, NOT EXERCISED otherwise.

    Cleanup is not observed yet when the receipt is written; the cleanup step records it.
    """
    rows = {}
    for row in ROWS + (FOLLOW_UP_ROWS if mode == "follow-up" else ()):
        if mode == "follow-up" and row in FULL_REVIEW_ONLY_ROWS:
            rows[row] = {"status": "NOT EXERCISED", "evidence": "Not run: full review only"}
        elif row in observed:
            rows[row] = {"status": "PASS", "evidence": _prose(rng, words // 4)}
        else:
            rows[row] = {"status": "NOT EXERCISED", "evidence": "Not observed in this run."}
    return rows


def _closing_steps(rng: random.Random, run_id: str, words: int, mode: str, observed: set,
                   receipt_extra: dict, report: dict) -> list[list[dict]]:
    return [
        [{"op": "set", "path": "/runtime_acceptance_receipt", "value": {
            "harness": "Example CLI 1.0", **receipt_extra,
            "validators": ["deep-review-validator-static", "deep-review-validator-probe"],
            "rows": _receipt_rows(rng, words, mode, observed),
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
            "outcome": "verified", "pagination_complete": True,
            "source": "GET /repos/example/repository/pulls/42/comments?per_page=100 (PR-wide, paginated), "
                      f"filtered by pull_request_review_id {review_id}",
            "read_at": "2026-10-15T10:45:10Z", "matched": [c["concern_id"] for c in comments],
            "missing": [], "conflicting": [], "extra": [], "retrieval_error": None}}]
        + [{"op": "append", "path": "/publication/comment_identifiers", "value": item} for item in identifiers],
    ]


def _ending_steps(run_id: str, completeness: str) -> list[list[dict]]:
    return [
        [{"op": "set", "path": "/cleanup/status", "value": "worktree removed and registration verified gone"},
         {"op": "set", "path": "/runtime_acceptance_receipt/rows/cleanup", "value": {
             "status": "PASS", "evidence": "Only this run's worktree was removed, and its registration is gone."}}],
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
    final = {}
    for number in range(1, shape["hypotheses"] + 1):
        outcome = "Needs probe" if number in needs_probe else rng.choice(("Finding", "Disproved", "Unresolved"))
        final[f"H{number}"] = outcome
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": f"H{number}", "phase": "static", "agent": "deep-review-validator-static",
            "outcome": outcome, "evidence": _prose(rng, words * 2), "recommendation": _prose(rng, words // 2),
        }}])
    for number in sorted(needs_probe):
        probe = _probe_steps(rng, number, head, words, "outcome", ("Finding", "Disproved", "Unresolved"))
        final[f"H{number}"] = probe[1][0]["value"]["outcome"]
        out += probe
    # Only final Finding and Unresolved outcomes are concerns, so only they are compared and published.
    concerns = [concern for concern, outcome in final.items() if outcome in CONCERN_OUTCOMES]
    if len(concerns) < shape["comments"]:
        raise ValueError(f"profile {shape} yields too few concerns to publish")
    out.append([
        {"op": "set", "path": "/pr_discussion/retrieval_complete", "value": True},
        {"op": "set", "path": "/pr_discussion/retrieved_at", "value": "2026-10-15T10:40:00Z"},
    ] + [{"op": "append", "path": "/pr_discussion/dispositions", "value": {
        "hypothesis": concerns[index % len(concerns)], "disposition": rng.choice(("new", "already reported")),
        "reason": _prose(rng, words // 2), "link": f"https://github.com/example/repository/pull/42#discussion_r{index}",
    }} for index in range(shape["dispositions"])])
    observed = {"surviving hypotheses", "PR-review-overlap"}
    observed |= {"multiple selected scouts"} if len(lenses) > 1 else set()
    observed |= {"validator probes"} if needs_probe else set()
    out += _closing_steps(rng, run_id, words, "full", observed, {
        "skill_commit": base[:7], "lenses": {lens: f"deep-review-scout-{lens}" for lens in lenses}}, {
        "hypotheses_discovered": shape["hypotheses"], "hypotheses_after_dedupe": shape["hypotheses"],
        "summary": _prose(rng, words * 3),
        "actions": [{"hypothesis": concern, "action": "discuss" if final[concern] == "Unresolved"
                     else rng.choice(("fix-now", "follow-up", "discuss"))} for concern in concerns],
    })
    out += _publication_steps(rng, concerns[: shape["comments"]], head, words)
    return out + _ending_steps(run_id, "complete")


def _follow_up_steps(shape: dict, rng: random.Random, run_id: str) -> list[list[dict]]:
    """Follow-up revalidation: no scouts or overlap, read-only toward GitHub by default."""
    words = shape["words"]
    source = build(shape["source"])
    base, head = source["record"]["base_sha"], _sha(rng)
    # The concern inventory is the source's final Finding and Unresolved outcomes; a writable
    # adjudication replaces its static "Needs probe" transition, and Disproved is never a concern.
    final = {}
    for outcome in source["validator_outcomes"]:
        final[outcome["hypothesis"]] = outcome
    inventory = [h for h in source["hypotheses"] if final[h["id"]]["outcome"] in CONCERN_OUTCOMES]
    selected = inventory[: shape["selected"]]
    if len(selected) < shape["selected"]:
        raise ValueError("the source review yields too few concerns for this follow-up")
    deferred = selected[-shape["deferred"]:]
    revalidated = selected[: -shape["deferred"]]
    out = [_identity(run_id, base, head) + [{"op": "set", "path": "/record/lineage", "value": {
        "source_run_id": source["record"]["run_id"], "follow_up_run_ids": []}}],
        _baseline(rng, base, head, run_id)]
    originals = []
    for concern in selected:
        originals.append({"hypothesis": concern, "original_outcome": final[concern["id"]],
                          "original_reviewed_head_sha": source["record"]["reviewed_head_sha"]})
    out.append([{"op": "set", "path": "/follow_up/source", "value": {
        "run_id": source["record"]["run_id"], "path": f"/repo/.git/deep-review/records/{source['record']['run_id']}",
        "completeness": source["record"]["completeness"], "reviewed_head_sha": source["record"]["reviewed_head_sha"],
        "older_matching_full_records": 0}}]
        + [{"op": "append", "path": "/follow_up/selected_concerns", "value": item} for item in originals]
        + [{"op": "append", "path": "/follow_up/deferred", "value": {"concern": c["id"], "reason": _prose(rng, 8)}}
           for c in deferred])
    needs_probe = {concern["id"] for concern in revalidated[: shape["probes"]]}
    status = {}
    for concern in revalidated:
        status[concern["id"]] = "needs probe" if concern["id"] in needs_probe else rng.choice(("Addressed", "Not addressed"))
        out.append([{"op": "append", "path": "/validator_outcomes", "value": {
            "hypothesis": concern["id"], "phase": "static", "agent": "deep-review-validator-static",
            "status": status[concern["id"]], "evidence": _prose(rng, words * 2)}}])
    for concern_id in sorted(needs_probe):
        probe = _probe_steps(rng, int(concern_id[1:]), head, words, "status", ("Addressed", "Not addressed"))
        status[concern_id] = probe[1][0]["value"]["status"]
        out += probe
    threads = {c["id"]: rng.choice(("open", "resolved", "outdated", "not published")) for c in selected}
    out.append([{"op": "append", "path": "/follow_up/thread_states", "value": {"concern": concern, "state": state}}
                for concern, state in threads.items()])
    observed = {"explicitly deferred concern"} if deferred else set()
    observed |= {"validator probes"} if needs_probe else set()
    observed |= {"multiple selected concerns"} if len(revalidated) > 1 else set()
    observed |= {"fixed concern"} if "Addressed" in status.values() else set()
    observed |= {"persisting defect"} if "Not addressed" in status.values() else set()
    if any(status[c] == "Not addressed" and threads[c] == "resolved" for c in status):
        observed.add("resolved thread with a persisting defect")
    out += _closing_steps(rng, run_id, words, "follow-up", observed, {"skill_commit": base[:7], "scouts": "not run"}, {
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
