"""Deterministic parsing and scoring. Nothing here calls a model.

Every number the report publishes is recomputed by `score` from retained raw evidence:
session statuses, raw scout and validator text, frozen labels, and recorded assessor,
resolver, novelty-audit and reason decisions.
"""

import itertools
import json
import random
import re

SCORER_VERSION = "1"
FIELDS = ("Origin", "Title", "File/line", "Potential severity", "Source evidence", "Expected impact",
          "Falsification condition", "Suggested validation", "Context references")
HEADING = re.compile(r"^#{2,4}[ \t]*Hypothesis[ \t]+(\S+)[ \t]*$", re.MULTILINE)
FIELD = re.compile(r"^[ \t]*[-*][ \t]*\*\*(?P<name>[^*]+?):?\*\*:?[ \t]*(?P<value>.*)$")
ZERO = re.compile(r"[*_`\s]*No hypotheses\.?[*_`\s]*", re.IGNORECASE)
OUTCOMES = ("Finding", "Disproved", "Unresolved", "Needs probe")
OUTCOME_HEADING = re.compile(r"^(?:#{1,4}[ \t]*|\*\*)(Finding|Disproved|Unresolved|Needs probe)(?:\*\*)?[ \t]*$",
                             re.MULTILINE)
REASONS = ("absent_task_or_cost", "unchanged_or_legacy_scope", "essential_structure", "behavior_change",
           "relocated_or_equal_burden", "preference", "insufficient_evidence", "other")


def parse_scout(text):
    """Classify raw scout output as a clean zero, hypotheses, or unusable output."""
    stripped = (text or "").strip()
    headings = list(HEADING.finditer(stripped))
    if not headings:
        if ZERO.fullmatch(stripped):
            return {"kind": "zero", "hypotheses": [], "schema_violations": []}
        if re.search(r"\bNo hypotheses\b", stripped, re.IGNORECASE) and "### " not in stripped:
            return {"kind": "zero", "hypotheses": [], "schema_violations": ["prose around No hypotheses"]}
        return {"kind": "unusable", "hypotheses": [], "schema_violations": ["no hypothesis blocks and no clean zero"]}
    violations = []
    if stripped[:headings[0].start()].strip():
        violations.append("prose before the first hypothesis")
    hypotheses = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(stripped)
        block = stripped[match.start():end].strip()
        fields = {}
        current = None
        for line in block.splitlines()[1:]:
            field = FIELD.match(line)
            name = field.group("name").strip() if field else None
            if name in FIELDS:
                current = name
                fields[current] = field.group("value")
            elif current is not None:
                fields[current] += "\n" + line
        fields = {key: value.strip() for key, value in fields.items()}
        missing = [name for name in FIELDS if not fields.get(name)]
        if missing:
            violations.append(f"{match.group(1)}: missing {', '.join(missing)}")
        hypotheses.append({"local_id": match.group(1), "fields": fields, "missing": missing, "raw": block})
    return {"kind": "hypotheses", "hypotheses": hypotheses, "schema_violations": violations}


def replay_text(hypothesis, opaque_id):
    """The emitted block with only its reviewer-local heading replaced by an opaque ID."""
    body = hypothesis["raw"].split("\n", 1)
    return f"### Hypothesis {opaque_id}\n" + (body[1] if len(body) > 1 else "")


def replay_key(hypothesis):
    body = hypothesis["raw"].split("\n", 1)
    return " ".join((body[1] if len(body) > 1 else "").split())


def parse_validator(text):
    found = {match.group(1) for match in OUTCOME_HEADING.finditer(text or "")}
    if len(found) == 1:
        return found.pop()
    return None


def extract_json(text):
    blocks = re.findall(r"```json\s*(.*?)```", text or "", re.DOTALL)
    candidates = list(reversed(blocks))
    if not candidates:
        start = (text or "").rfind("\n{")
        candidates = [(text or "")[start + 1:]] if start >= 0 else [text or ""]
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def label_sets(definitions, frozen_labels):
    """Primary eligible, provisional and auxiliary label IDs per case from frozen decisions."""
    classes = definitions["label_classes"]
    result = {}
    for label, spec in definitions["labels"].items():
        case = result.setdefault(spec["case"], {"eligible": [], "provisional": [], "auxiliary": [], "excluded": []})
        decision = frozen_labels[label]["decision"]
        if label in classes["auxiliary"]:
            case["auxiliary"].append(label)
        elif decision == "eligible" and label in classes["fixed"]:
            case["eligible"].append(label)
        elif decision == "eligible" and label in classes["provisional"]:
            case["provisional"].append(label)
        elif decision == "provisional":
            case["provisional"].append(label)
        else:
            case["excluded"].append(label)
    for case in result.values():
        for key in case:
            case[key].sort()
    return result


def credited(matches, allowed):
    """Labels a hypothesis earns: all independently stated matches, otherwise at most one."""
    relevant = [m for m in matches if m["label"] in allowed]
    independent = [m["label"] for m in relevant if m.get("independent_statement")]
    if len(independent) >= 2:
        return sorted(set(independent)), True
    return ([relevant[0]["label"]] if relevant else []), False


def one_credit(hypothesis_labels):
    """Largest label set coverable when each hypothesis may credit at most one label."""
    items = [labels for labels in hypothesis_labels if labels]
    best = set()
    for choice in itertools.product(*[sorted(labels) for labels in items]) if items else []:
        chosen = set(choice)
        if len(chosen) > len(best):
            best = chosen
    return best


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def bootstrap(differences_by_case, seed, rounds=10000):
    """Percentile interval of the mean paired case difference, resampling cases."""
    cases = [value for value in differences_by_case.values() if value is not None]
    if len(cases) < 2:
        return {"cases": len(cases), "interval_95": None, "note": "fewer than two cases with paired data"}
    generator = random.Random(seed)
    means = sorted(sum(generator.choice(cases) for _ in cases) / len(cases) for _ in range(rounds))
    return {"cases": len(cases), "mean": round(sum(cases) / len(cases), 4),
            "interval_95": [round(means[int(0.025 * rounds)], 4), round(means[int(0.975 * rounds) - 1], 4)]}


def score(data):
    """Compute every published measure from one phase's raw evidence.

    `data` keys: definitions, frozen_labels, controls (case IDs that are controls), runs, pool,
    validations, assessments, novelty, reasons, seed.
    """
    definitions = data["definitions"]
    sets = label_sets(definitions, data["frozen_labels"])
    controls = set(data["controls"])
    runs = data["runs"]
    pool = data["pool"]
    validations = data["validations"]
    assessments = data["assessments"]
    novelty = data.get("novelty", {})
    reasons = data.get("reasons", {})

    def disposition(pool_id):
        validation = validations.get(pool[pool_id]["replay"])
        return validation["disposition"] if validation and validation["status"] == "completed" else None

    run_rows = []
    for run in runs:
        case_sets = sets.get(run["case"], {"eligible": [], "provisional": [], "auxiliary": [], "excluded": []})
        row = {key: run[key] for key in ("run", "case", "arm", "repetition", "status")}
        row["control"] = run["case"] in controls
        row.update(eligible=case_sets["eligible"], provisional=case_sets["provisional"])
        completed = run["status"] == "completed"
        hypotheses = [pid for pid in pool if pool[pid]["run"] == run["run"]]
        row["emitted"] = len(hypotheses) if completed else None
        row["clean_zero"] = completed and run["parse_kind"] == "zero"
        row["schema_violations"] = len(run.get("schema_violations", [])) if completed else None
        row["partial_hypotheses"] = sum(1 for pid in hypotheses if pool[pid]["missing"]) if completed else None
        qualified = [pid for pid in hypotheses if assessments.get(pid, {}).get("admission_qualified")]
        row["admission_qualified"] = len(qualified) if completed else None
        for scope in ("eligible", "provisional", "auxiliary"):
            allowed = set(case_sets[scope])
            scout, validated, grouped, single = set(), set(), [], []
            for pid in hypotheses:
                matches = assessments.get(pid, {}).get("matches", [])
                labels, multiple = credited(matches, allowed)
                if multiple:
                    grouped.append({"hypothesis": pid, "labels": labels})
                if pid in qualified:
                    scout.update(labels)
                    single.append(set(labels))
                if labels and disposition(pid) == "Finding":
                    validated.update(labels)
            row[f"{scope}_scout_matched"] = sorted(scout) if completed else None
            row[f"{scope}_validated_matched"] = sorted(validated) if completed else None
            if scope == "eligible":
                row["grouped_credits"] = grouped
                row["one_credit_matched"] = sorted(one_credit(single)) if completed else None
            denominator = len(allowed)
            row[f"{scope}_scout_recall"] = (len(scout) / denominator if denominator else "N/A") if completed else None
            row[f"{scope}_validated_recall"] = (len(validated) / denominator if denominator else "N/A") if completed else None
        row["one_credit_recall"] = (len(row["one_credit_matched"]) / len(case_sets["eligible"])
                                    if completed and case_sets["eligible"] else ("N/A" if completed else None))
        row["dispositions"] = {outcome: sum(1 for pid in hypotheses if disposition(pid) == outcome)
                               for outcome in OUTCOMES} if completed else None
        row["unvalidated"] = sum(1 for pid in hypotheses if disposition(pid) is None) if completed else None
        run_rows.append(row)

    arms = sorted({run["arm"] for run in runs})
    cases = sorted({run["case"] for run in runs})

    def numeric(value):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    case_rows = []
    differences = {"eligible_scout_recall": {}, "eligible_validated_recall": {}}
    for case in cases:
        entry = {"case": case, "control": case in controls,
                 "eligible": sets.get(case, {}).get("eligible", []),
                 "provisional": sets.get(case, {}).get("provisional", [])}
        for measure in ("eligible_scout_recall", "eligible_validated_recall", "provisional_scout_recall",
                        "provisional_validated_recall", "one_credit_recall"):
            for arm in arms:
                values = [numeric(r[measure]) for r in run_rows
                          if r["case"] == case and r["arm"] == arm and r["status"] == "completed"]
                if not entry["eligible" if measure.startswith(("eligible", "one")) else "provisional"]:
                    entry[f"{measure}_{arm}"] = "N/A"
                else:
                    entry[f"{measure}_{arm}"] = mean(values)
        paired = []
        repetitions = sorted({r["repetition"] for r in run_rows if r["case"] == case})
        for repetition in repetitions:
            pair = {r["arm"]: r for r in run_rows if r["case"] == case and r["repetition"] == repetition}
            complete = all(pair.get(arm, {}).get("status") == "completed" for arm in ("A", "B"))
            item = {"repetition": repetition, "complete_pair": complete}
            for measure in ("eligible_scout_recall", "eligible_validated_recall"):
                a = numeric(pair.get("A", {}).get(measure))
                b = numeric(pair.get("B", {}).get(measure))
                item[f"{measure}_difference_B_minus_A"] = round(b - a, 4) if complete and a is not None and b is not None else None
            paired.append(item)
        entry["paired"] = paired
        for measure in differences:
            values = [p[f"{measure}_difference_B_minus_A"] for p in paired]
            differences[measure][case] = mean(values)
            entry[f"{measure}_mean_difference_B_minus_A"] = differences[measure][case]
        case_rows.append(entry)

    concern_rows = []
    for label, spec in sorted(definitions["labels"].items()):
        scope = next((key for key in ("eligible", "provisional", "auxiliary", "excluded")
                      if label in sets.get(spec["case"], {}).get(key, [])), "excluded")
        item = {"label": label, "case": spec["case"], "scope": scope,
                "frozen_decision": data["frozen_labels"][label]["decision"]}
        for arm in arms:
            arm_runs = [r for r in run_rows if r["case"] == spec["case"] and r["arm"] == arm]
            for kind in ("scout", "validated"):
                key = f"{scope}_{kind}_matched" if scope != "excluded" else None
                item[f"{kind}_{arm}"] = [
                    (None if r["status"] != "completed" or key is None else label in (r[key] or []))
                    for r in sorted(arm_runs, key=lambda r: r["repetition"])]
        concern_rows.append(item)

    macro = {}
    for measure in ("eligible_scout_recall", "eligible_validated_recall", "one_credit_recall"):
        for arm in arms:
            values = [numeric(c[f"{measure}_{arm}"]) for c in case_rows if not c["control"]]
            macro[f"{measure}_{arm}"] = mean(values)
        macro[f"{measure}_cases_with_eligible_labels"] = sum(
            1 for c in case_rows if not c["control"] and c["eligible"])
    itt = {}
    for arm in arms:
        recovered = opportunities = 0
        for row in run_rows:
            if row["arm"] != arm or row["control"]:
                continue
            opportunities += len(row["eligible"])
            recovered += len(row["eligible_scout_matched"] or [])
        itt[arm] = {"recovered": recovered, "opportunities": opportunities,
                    "operational_lower_bound": round(recovered / opportunities, 4) if opportunities else "N/A"}

    failures = {}
    for row in run_rows:
        failures.setdefault(row["arm"], {}).setdefault(row["status"], 0)
        failures[row["arm"]][row["status"]] += 1
    pairs = {}
    for row in run_rows:
        pairs.setdefault((row["case"], row["repetition"]), {})[row["arm"]] = row["status"]
    paired_completion = {
        "pairs": len(pairs),
        "complete": sum(1 for p in pairs.values() if all(p.get(a) == "completed" for a in ("A", "B"))),
    }

    admission = {}
    for arm in arms:
        arm_rows = [r for r in run_rows if r["arm"] == arm and r["status"] == "completed"]
        emitted = sum(r["emitted"] for r in arm_rows)
        qualified = sum(r["admission_qualified"] for r in arm_rows)
        admission[arm] = {
            "successful_runs": len(arm_rows), "raw_emissions": emitted, "admission_qualified": qualified,
            "admission_qualified_fraction": round(qualified / emitted, 4) if emitted else "N/A",
            "partial_hypotheses": sum(r["partial_hypotheses"] for r in arm_rows),
            "schema_violations": sum(r["schema_violations"] for r in arm_rows),
            "clean_zero_runs": sum(1 for r in arm_rows if r["clean_zero"]),
            "dispositions": {o: sum(r["dispositions"][o] for r in arm_rows) for o in OUTCOMES},
            "unvalidated": sum(r["unvalidated"] for r in arm_rows),
        }
    rejection = {}
    for pid, entry in pool.items():
        outcome = disposition(pid)
        if outcome in ("Disproved", "Unresolved", "Needs probe"):
            arm = next(r["arm"] for r in runs if r["run"] == entry["run"])
            reason = reasons.get(entry["replay"], {}).get("reason", "unclassified")
            rejection.setdefault(arm, {}).setdefault(outcome, {}).setdefault(reason, 0)
            rejection[arm][outcome][reason] += 1

    novel, false_positive, controls_summary = [], {}, {}
    for pid, entry in pool.items():
        run = next(r for r in runs if r["run"] == entry["run"])
        if run["status"] != "completed":
            continue
        matches = assessments.get(pid, {}).get("matches", [])
        known = {m["label"] for m in matches}
        outcome = disposition(pid)
        if run["case"] in controls:
            continue
        if not known:
            if outcome == "Finding":
                audit = novelty.get(entry["replay"], {}).get("decision")
                novel.append({"hypothesis": pid, "case": run["case"], "arm": run["arm"],
                              "audit": audit or "not audited",
                              "classification": {"eligible": "confirmed novel", "excluded": "contested",
                                                 "uncertain": "uncertain"}.get(audit, "unaudited")})
            elif outcome == "Disproved":
                false_positive.setdefault(run["arm"], 0)
                false_positive[run["arm"]] += 1
    fp_rates = {}
    for arm in arms:
        successful = [r for r in run_rows if r["arm"] == arm and r["status"] == "completed" and not r["control"]]
        emitted = sum(r["emitted"] for r in successful)
        count = false_positive.get(arm, 0)
        fp_rates[arm] = {"disproved_unmatched": count,
                         "per_successful_case_run": round(count / len(successful), 4) if successful else "N/A",
                         "per_emitted_hypothesis": round(count / emitted, 4) if emitted else "N/A"}
    for arm in arms:
        control_rows = [r for r in run_rows if r["arm"] == arm and r["control"] and r["status"] == "completed"]
        emitted = sum(r["emitted"] for r in control_rows)
        qualified = sum(r["admission_qualified"] for r in control_rows)
        findings = sum(r["dispositions"]["Finding"] for r in control_rows)
        audits = [novelty.get(pool[pid]["replay"], {}).get("decision") for pid in pool
                  if any(pool[pid]["run"] == r["run"] for r in control_rows) and disposition(pid) == "Finding"]
        controls_summary[arm] = {
            "successful_control_runs": len(control_rows), "emitted": emitted, "admission_qualified": qualified,
            "runs_with_admission": sum(1 for r in control_rows if r["admission_qualified"]),
            "control_admission_rate": round(sum(1 for r in control_rows if r["admission_qualified"]) /
                                            len(control_rows), 4) if control_rows else "N/A",
            "validated_findings": findings,
            "control_validated_finding_rate": round(sum(1 for r in control_rows if r["dispositions"]["Finding"]) /
                                                    len(control_rows), 4) if control_rows else "N/A",
            "finding_audits": audits,
        }
    return {
        "scorer_version": SCORER_VERSION,
        "runs": run_rows, "cases": case_rows, "concerns": concern_rows, "macro": macro,
        "intention_to_run": itt, "execution_status": failures, "paired_completion": paired_completion,
        "admission": admission, "validator_rejections": rejection, "novel_findings": novel,
        "false_positives": fp_rates, "controls": controls_summary,
        "resampling": {measure: bootstrap({c: v for c, v in values.items() if c not in controls},
                                          f"{data['seed']}:{measure}")
                       for measure, values in differences.items()},
    }
