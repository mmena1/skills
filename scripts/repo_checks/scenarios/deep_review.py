"""The deep-review group: validates the real documents and proves each check rejects its mutations."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import generate_agents

from ..common import ROOT, SKILLS, fail
from ..deep_review import (
    CONCERN_TEXT_KEYS, HYPOTHESIS_TEXT_KEYS, MERGED_TEXT_KEYS, PERSISTED_HYPOTHESIS_FIELDS,
    DEEP_REVIEW_ACCESS_RULES, DEEP_REVIEW_CODEX_ACCESS_CELLS, DEEP_REVIEW_FOLLOW_UP_RULES,
    DEEP_REVIEW_PROBE_ENVIRONMENT_RULES, DEEP_REVIEW_PUBLICATION_RULES, DEEP_REVIEW_ROLES, HARNESS_SPECIFIC_TEXT,
    deep_review_access_problems, deep_review_audience_problems, deep_review_catalog, deep_review_follow_up_problems,
    deep_review_probe_environment_problems, deep_review_role_problems, deep_review_scenario_problems,
    deep_review_shared_sources, reviewer_text,
    concern_gaps, follow_up_coverage, merge_hypotheses,
)
from ..references import iter_repository_text


def validate_deep_review_role_contract(
    catalog: list[str], roles: dict[str, generate_agents.Role], contract: str, lenses: dict[str, str],
) -> None:
    """Prove the role check rejects each way a lens can lose, gain, or share its native scout."""
    def with_body(name: str, body: str) -> dict[str, generate_agents.Role]:
        return {**roles, name: dataclasses.replace(roles[name], body=body)}

    drifted = {**DEEP_REVIEW_ROLES["scout-conventions"]["claude"], "model": "claude-sonnet-5-5"}
    cases = {
        "a catalog lens without a role": (
            [*catalog, "extra"], roles, {**lenses, "extra": "# Extra Lens\n\nUnclaimed."},
        ),
        "a lens embedded by two roles": (
            catalog, with_body("validator-static", roles["validator-static"].body + "\n" + lenses["bugs"]), lenses,
        ),
        "a scout without the common contract": (catalog, with_body("scout-docs", lenses["docs"] + "\n"), lenses),
        "a scout without its lens": (catalog, with_body("scout-docs", contract + "\n"), lenses),
        "a scout with another lens": (
            catalog, with_body("scout-docs", f"{contract}\n\n{lenses['docs']}\n\n{lenses['history']}\n"), lenses,
        ),
        "a structural scout without the structural lens": (catalog, with_body("structural", contract + "\n"), lenses),
        "drifted harness fields": (
            catalog,
            {**roles, "scout-conventions": dataclasses.replace(
                roles["scout-conventions"], harnesses={**roles["scout-conventions"].harnesses, "claude": drifted},
            )},
            lenses,
        ),
        "a leftover generic scout role": (
            catalog, {**roles, "scout": dataclasses.replace(roles["validator-static"], name="scout", body=contract + "\n")}, lenses,
        ),
    }
    for label, (mutated_catalog, mutated_roles, mutated_lenses) in cases.items():
        if not deep_review_role_problems(mutated_catalog, mutated_roles, contract, mutated_lenses):
            fail(f"the deep-review role check accepted {label}")


def validate_deep_review_access_contract(skill: Path) -> None:
    """Reject removed or weakened static-analysis rules, role sandboxes, and missing inheritance guidance."""
    documents = {relative: (skill / relative).read_text(encoding="utf-8") for relative in DEEP_REVIEW_ACCESS_RULES}
    problems = deep_review_access_problems(documents)
    if problems:
        fail(problems[0])
    for relative, rules in DEEP_REVIEW_ACCESS_RULES.items():
        for rule in rules:
            for replacement in ("", rule.replace("no ", "optional ").replace("never ", "sometimes ")):
                if replacement == rule:
                    continue
                mutated = {**documents, relative: documents[relative].replace(rule, replacement)}
                if not deep_review_access_problems(mutated):
                    fail(f"the access check accepted a removed or weakened {relative} contract")
    for mechanism, expected in DEEP_REVIEW_CODEX_ACCESS_CELLS.items():
        for sandbox in ("read-only", "workspace-write"):
            mutated = {**documents, "SKILL.md": documents["SKILL.md"].replace(expected, f"Enforced by the `{sandbox}` sandbox.")}
            if not deep_review_access_problems(mutated):
                fail(f"the access check accepted a role-specific Codex sandbox for {mechanism}")


def validate_deep_review_audience_contract(skill: Path) -> None:
    documents = {path.relative_to(skill).as_posix(): path.read_text(encoding="utf-8")
                 for path in (skill / "references").glob("*.md")}
    documents["protocol.md"] = (skill / "protocol.md").read_text(encoding="utf-8")
    problems = deep_review_audience_problems(documents)
    if problems:
        fail(problems[0])
    # Mutation checks make each routing case observable, including explicit human.
    for guide in ("references/review-tone.md", "references/review-tone-agent.md"):
        mutated = {relative: content for relative, content in documents.items() if relative != guide}
        if not deep_review_audience_problems(mutated):
            fail(f"the audience check accepted a missing {guide}")
    for selection, audience, guide in (
        ("unspecified", "human", "review-tone.md"),
        ("`human`", "human", "review-tone.md"),
        ("`agent`", "agent", "review-tone-agent.md"),
    ):
        row = f"| {selection} | `{audience}` | `{guide}` |"
        for replacement in ("", row.replace(f"`{guide}`", "`missing-tone.md`"),
                            row.replace(f"| `{audience}` |", "| `other` |")):
            mutated = {**documents, "references/pr-review-comments.md":
                       documents["references/pr-review-comments.md"].replace(row, replacement)}
            if not deep_review_audience_problems(mutated):
                fail(f"the audience check accepted an invalid {selection} route")
    for relative, rules in DEEP_REVIEW_PUBLICATION_RULES.items():
        for rule in rules:
            mutated = {**documents, relative: documents[relative].replace(rule, "")}
            if not deep_review_audience_problems(mutated):
                fail(f"the audience check accepted a removed {relative} publication rule")


def validate_deep_review_follow_up_contract(skill: Path, roles: dict[str, generate_agents.Role]) -> None:
    documents = {relative: (skill / relative).read_text(encoding="utf-8") for relative in (
        "SKILL.md", "agents/openai.yaml", "protocol.md", "runtime-acceptance.md", "reviewers/validator.md",
        "references/output-template.md", "references/pr-review-comments.md",
    )}
    problems = deep_review_follow_up_problems(documents)
    if problems:
        fail(problems[0])
    # Both validator agents embed the follow-up adjudication, so no new role is needed.
    isolation = DEEP_REVIEW_FOLLOW_UP_RULES["reviewers/validator.md"][0]
    for name in ("validator-static", "validator-probe"):
        if isolation not in roles[name].body:
            fail(f"deep-review role {name!r} does not embed the follow-up adjudication")
    for relative, rules in DEEP_REVIEW_FOLLOW_UP_RULES.items():
        for rule in rules:
            mutated = {**documents, relative: documents[relative].replace(rule, "")}
            if not deep_review_follow_up_problems(mutated):
                fail(f"the follow-up check accepted a removed {relative} follow-up rule")
    mutations = {
        "a follow-up row in the full-review receipt": (
            "references/output-template.md", "| Cleanup | PASS / FAIL / NOT EXERCISED |",
            "| Fixed concern | PASS / FAIL / NOT EXERCISED | x |\n| Cleanup | PASS / FAIL / NOT EXERCISED |",
        ),
        "a malformed follow-up matrix": ("runtime-acceptance.md", "| Partial fix | Not addressed", "| Partial fix | | Not addressed"),
        "a missing follow-up matrix row": ("runtime-acceptance.md", "| Partial fix | Not addressed", "| Partial fixes | Not addressed"),
        "a follow-up row accepted without observation": ("runtime-acceptance.md", "| Partial fix | NOT EXERCISED | NOT EXERCISED |", "| Partial fix | NOT EXERCISED | ACCEPTED |"),
        "a missing protocol follow-up row": ("protocol.md", "- partial fix: whether", "- partial repair: whether"),
        "a PASS headline in the follow-up report": ("references/output-template.md", "**Status counts:**", "**Headline takeaway:** No findings\n**Status counts:**"),
        "a full-review-only row left unmarked": ("references/output-template.md", "Insufficient scout capacity, and Scout failure", "and Scout failure"),
        "a full-review argument-hint": ("SKILL.md", 'argument-hint: "[follow-up] ', 'argument-hint: "'),
        "a missing follow-up validator capacity": ("SKILL.md", "| Follow-up validator capacity |", "| Follow-up validator limit |"),
        "a follow-up validator capacity tied to the scout check": (
            "SKILL.md", "as a validator-only read with no scout selection or admission, and use the maximum safe capacity it finds.",
            "and use the maximum safe capacity found by the capacity check.",
        ),
        "Codex metadata without follow-up": ("agents/openai.yaml", "or follow-up revalidation", ""),
    }
    for label, (relative, old, new) in mutations.items():
        if old not in documents[relative]:
            fail(f"the follow-up check mutation for {label} no longer applies")
        mutated = {**documents, relative: documents[relative].replace(old, new, 1)}
        if not deep_review_follow_up_problems(mutated):
            fail(f"the follow-up check accepted {label}")


def complete_concern(number: int, scout: str = "bugs") -> dict:
    return {
        "hypothesis": {
            "canonical_id": f"H{number}",
            "scouts": [{"id": f"{scout}-H1", "origin": scout}],
            "title": "Guard missing", "source_location": "src/a.py:10", "potential_severity": "high",
            "source_evidence": "src/a.py:10 skips the guard", "expected_impact": "Crash on empty input",
            "falsification_condition": "A caller always validates", "suggested_validation": "Read the callers",
            "context_references": "none",
        },
        "original_outcome": "Finding", "original_evidence": "No caller validates", "reviewed_head_sha": "a" * 40,
    }


def validate_deep_review_concern_completeness() -> None:
    """Complete records, each omitted or empty field, merged provenance, and a mixed legacy source."""
    complete = complete_concern(1)
    if concern_gaps(complete, "H1"):
        fail(f"a complete original concern record was reported incomplete: {concern_gaps(complete, 'H1')}")
    if concern_gaps(None, "H1") != ["no preserved original concern"]:
        fail("a concern with no preserved record must report that reason")
    # Each required field is omitted and emptied in turn, including each scout entry's ID and origin.
    mutations = {
        "hypothesis omitted": lambda c: c.pop("hypothesis"),
        "canonical ID omitted": lambda c: c["hypothesis"].pop("canonical_id"),
        "canonical ID empty": lambda c: c["hypothesis"].update(canonical_id=" "),
        "scout IDs and origins omitted": lambda c: c["hypothesis"].pop("scouts"),
        "scout IDs and origins empty": lambda c: c["hypothesis"].update(scouts=[]),
        "scout ID empty": lambda c: c["hypothesis"]["scouts"][0].update(id=" "),
        "scout origin empty": lambda c: c["hypothesis"]["scouts"][0].update(origin=" "),
        **{f"{key} omitted": (lambda c, key=key: c["hypothesis"].pop(key)) for key in HYPOTHESIS_TEXT_KEYS},
        **{f"{key} empty": (lambda c, key=key: c["hypothesis"].update({key: "  "})) for key in HYPOTHESIS_TEXT_KEYS},
        **{f"{key} omitted": (lambda c, key=key: c.pop(key)) for key in CONCERN_TEXT_KEYS},
        **{f"{key} empty": (lambda c, key=key: c.update({key: ""})) for key in CONCERN_TEXT_KEYS},
    }
    for label, mutate in mutations.items():
        record = complete_concern(1)
        mutate(record)
        if not concern_gaps(record, "H1"):
            fail(f"the concern completeness model accepted a record with {label}")
    if concern_gaps(complete_concern(2), "H1") != ["preserved hypothesis ID H2 does not match requested concern H1"]:
        fail("a preserved hypothesis whose ID differs from the requested concern must be incomplete")
    # The persisted fields are the text keys plus the canonical ID and the scout IDs and origins.
    if len(HYPOTHESIS_TEXT_KEYS) + 2 != len(PERSISTED_HYPOTHESIS_FIELDS):
        fail("the concern completeness model and the persisted hypothesis fields must name the same content")

    first, second = complete_concern(1)["hypothesis"], complete_concern(1, "history")["hypothesis"]
    first["context_references"] = "manifest: docs/a.md"
    second.update({key: f"{key} from history" for key in MERGED_TEXT_KEYS})
    merged = merge_hypotheses(first, second)
    if merged["scouts"] != [*first["scouts"], *second["scouts"]]:
        fail("merging must retain every originating scout ID and origin pair")
    for key in MERGED_TEXT_KEYS:
        if first[key] not in merged[key] or second[key] not in merged[key]:
            fail(f"merging must retain materially distinct {key.replace('_', ' ')}")
    second["context_references"] = "none"
    if merge_hypotheses(first, second)["context_references"] != first["context_references"]:
        fail("merging must not keep the no-references value beside a real context reference")
    if concern_gaps({**complete_concern(1), "hypothesis": merged}, "H1"):
        fail("a merged hypothesis must stay a complete canonical hypothesis record")
    if not concern_gaps({**complete_concern(1), "hypothesis": {"canonical_id": "H1", "title": merged["title"]}}, "H1"):
        fail("a title alone must not stand in for a complete canonical hypothesis")

    legacy = {"H1": complete_concern(1), "H2": complete_concern(2), "H3": complete_concern(3)}
    del legacy["H2"]["hypothesis"]["falsification_condition"]
    legacy["H3"]["original_evidence"] = ""
    eligible, incomplete = follow_up_coverage(legacy, ["H1", "H2", "H3", "H4"])
    if eligible != ["H1"] or sorted(incomplete) != ["H2", "H3", "H4"]:
        fail("a mixed legacy source must keep its complete concern eligible and report the others as incomplete")
    expected = {
        "H2": ["hypothesis falsification condition missing or empty"],
        "H3": ["original evidence missing or empty"],
        "H4": ["no preserved original concern"],
    }
    if incomplete != expected:
        fail(f"incomplete coverage must carry specific reasons, got {incomplete}")
    if follow_up_coverage({"H1": complete_concern(1)}, ["H1"]) != (["H1"], {}):
        fail("a source of complete concerns must have no incomplete coverage")
    if follow_up_coverage({"H1": complete_concern(2)}, ["H1"]) != (
            [], {"H1": ["preserved hypothesis ID H2 does not match requested concern H1"]}):
        fail("a mismatched preserved hypothesis must be reported as incomplete coverage, not validator input")


def validate_deep_review_probe_environment_contract(skill: Path) -> None:
    documents = {
        relative: (skill / relative).read_text(encoding="utf-8") if (skill / relative).exists() else ""
        for relative in DEEP_REVIEW_PROBE_ENVIRONMENT_RULES
    }
    problems = deep_review_probe_environment_problems(documents)
    if problems:
        fail(problems[0])
    for relative, rules in DEEP_REVIEW_PROBE_ENVIRONMENT_RULES.items():
        for rule in rules:
            mutated = {**documents, relative: documents[relative].replace(rule, "")}
            if not deep_review_probe_environment_problems(mutated):
                fail(f"the probe environment check accepted a removed {relative} rule")


def validate_deep_review() -> None:
    """Deep review keeps one harness-neutral copy of its sources and its pinned role limits."""
    skill = SKILLS / "deep-review"
    validate_deep_review_probe_environment_contract(skill)
    validate_deep_review_access_contract(skill)
    validate_deep_review_audience_contract(skill)
    roles = {role.name: role for role in generate_agents.load_roles(skill)}
    catalog = deep_review_catalog((skill / "protocol.md").read_text(encoding="utf-8"))
    contract = reviewer_text(skill / "reviewers" / "SCOUT.md")
    lenses = {path.stem: reviewer_text(path) for path in (skill / "reviewers" / "lenses").glob("*.md")}
    problems = deep_review_role_problems(catalog, roles, contract, lenses)
    if problems:
        fail(problems[0])
    validate_deep_review_role_contract(catalog, roles, contract, lenses)

    shared = deep_review_shared_sources(skill)
    for path in shared:
        match = HARNESS_SPECIFIC_TEXT.search(path.read_text(encoding="utf-8"))
        if match:
            fail(f"{path.relative_to(ROOT).as_posix()}: harness-specific text {match.group(0)!r} in shared deep-review content")
    # Structural review is architecture-neutral: deep-review must not require or defer to codebase-design.
    for path in [skill / "SKILL.md", *shared]:
        if "codebase-design" in path.read_text(encoding="utf-8"):
            fail(f"{path.relative_to(ROOT).as_posix()}: deep-review must not depend on or defer adjudication to codebase-design")
    scenario_sources = ("protocol.md", "references/output-template.md", "runtime-acceptance.md")
    scenario_documents = {
        relative: (skill / relative).read_text(encoding="utf-8")
        for relative in scenario_sources
    }
    problems = deep_review_scenario_problems(scenario_documents)
    if problems:
        fail(problems[0])
    scenario_mutations = {
        "protocol.md": ("- zero hypotheses: whether", "- divergent scenario: whether"),
        "references/output-template.md": ("| Zero hypotheses |", "| Divergent scenario |"),
        "runtime-acceptance.md": ("| Zero hypotheses |", "| Divergent scenario |"),
    }
    for relative, (original, replacement) in scenario_mutations.items():
        mutated_scenarios = dict(scenario_documents)
        mutated_scenarios[relative] = scenario_documents[relative].replace(original, replacement, 1)
        if mutated_scenarios[relative] == scenario_documents[relative]:
            fail(f"the runtime scenario check self-test could not mutate {relative}")
        if not deep_review_scenario_problems(mutated_scenarios):
            fail(f"the runtime scenario check accepted divergent scenario names in {relative}")
    validate_deep_review_follow_up_contract(skill, roles)
    validate_deep_review_concern_completeness()

    contents = {path.read_text(encoding="utf-8"): path for path in shared}
    generated = skill / "harnesses"
    for path in iter_repository_text():
        if path in shared or path.is_relative_to(generated):
            continue
        original = contents.get(path.read_text(encoding="utf-8"))
        if original is not None:
            fail(f"{path.relative_to(ROOT).as_posix()}: duplicate copy of {original.relative_to(ROOT).as_posix()}")
