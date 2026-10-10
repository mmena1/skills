#!/usr/bin/env python3
"""Blinded structural-scout calibration benchmark: preparation, isolation, execution, scoring.

Everything this program reads or writes outside the reviewer boundary is evaluator-only:
the catalog, definitions, fixtures, depot, evidence directory and receipts. A reviewer or
validator session sees one capsule repository through the jailed capsule service, plus the
prompt text recorded in its session directory. See README.md for the operator procedure.
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import broker  # noqa: E402
import scoring  # noqa: E402

RESEARCH = HERE.parent
REPOSITORY = RESEARCH.parents[2]
CATALOG = RESEARCH / "case-catalog.json"
PREPARER = RESEARCH / "prepare-capsules.py"
DEFINITIONS = HERE / "definitions.json"
FIXTURES = HERE / "fixtures"
ROLES = HERE / "roles"
RESEARCH_RAW = Path.home() / ".local/share/skills-research/structural-calibration-20261009"
CONTROLS = ("N1", "N2", "N3", "N4", "N5")
CHALLENGE_FIXTURE = "C1"
PHASES = {
    "pilot": {"cases": ["M91", "M94", "N1", "N2"], "repetitions": 1, "validator_cap": 12},
    "full": {"cases": ["M72", "M91", "M94", "M102", "M108", "N1", "N2", "N3", "N4", "N5"], "repetitions": 3},
}
# Preregistered identical budgets. The research's 24,000-token scout ceiling cannot hold the
# complete original diff each scout must receive (about 17,000 to 25,000 tokens on its own),
# so these are the supported, enforced equivalents; see README.md.
BUDGETS = {
    "scout": {"timeout_seconds": 1500, "max_requests": 80, "max_context_tokens": 250000,
              "max_output_tokens": 64000},
    "validator": {"timeout_seconds": 900, "max_requests": 50, "max_context_tokens": 200000,
                  "max_output_tokens": 32000},
    "adjudicator": {"timeout_seconds": 900, "max_requests": 50, "max_context_tokens": 200000,
                    "max_output_tokens": 32000},
    "assessor": {"timeout_seconds": 900, "max_requests": 4, "max_context_tokens": 200000,
                 "max_output_tokens": 32000},
}
FIXED_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+00:00",
}


class GateError(SystemExit):
    def __init__(self, message):
        super().__init__(f"STOP: {message}")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_once(path, value):
    if Path(path).exists():
        raise GateError(f"{path} is frozen and already exists; record a prospective revision instead")
    dump(path, value)


def git(*arguments, cwd=None, env=None, data=None, check=True):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(env or {})
    return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, *arguments], cwd=cwd, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, check=check)


def render(template_name, **values):
    text = (ROLES / template_name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def fence(text, language=""):
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(4, longest + 1)
    return f"{ticks}{language}\n{text.rstrip(chr(10))}\n{ticks}"


class Evidence:
    """Paths inside the durable evaluator evidence directory."""

    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        if self.root == REPOSITORY or REPOSITORY in self.root.parents:
            raise GateError("evidence must live outside the repository; the repository check scans ignored files")
        self.inputs = self.root / "inputs"
        self.receipts = self.root / "receipts"
        self.sessions = self.root / "sessions"
        self.results = self.root / "results"
        self.corpus = self.inputs / "corpus.git"
        self.fixture_source = self.inputs / "fixture-source.git"

    def preparation(self, number=1):
        return self.inputs / f"preparation-{number}"

    def receipt(self, name):
        return self.receipts / f"{name}.json"

    def require(self, name, message):
        path = self.receipt(name)
        if not path.exists():
            raise GateError(message)
        value = load(path)
        if value.get("verdict") != "PASS":
            raise GateError(f"{name} receipt verdict is {value.get('verdict')}: {message}")
        return value


# ---------------------------------------------------------------- preparation


def build_fixture_source(evidence, definitions):
    """Deterministic base, head and decoy-future commits for each fixture."""
    repository = evidence.fixture_source
    if repository.exists():
        shutil.rmtree(repository)
    git("init", "--bare", "--quiet", "--template=", str(repository))
    records = {}
    for fixture in sorted(path.name for path in FIXTURES.iterdir() if path.is_dir()):
        commits = {}
        files = {}
        parent = []
        for stage in ("base", "head", "future"):
            source = FIXTURES / fixture / ("head" if stage == "future" else stage)
            with tempfile.TemporaryDirectory() as scratch:
                work = Path(scratch) / "tree"
                shutil.copytree(source, work)
                for cache in work.rglob("__pycache__"):
                    shutil.rmtree(cache)
                if stage == "future":
                    # Evaluator-only future object: a capsule must never contain it.
                    note = definitions["controls"].get(fixture, {"design": "validator challenge fixture"})
                    (work / "EVALUATOR_EXPECTATION.txt").write_text(json.dumps(note) + "\n", encoding="utf-8")
                environment = dict(FIXED_ENV, GIT_INDEX_FILE=str(Path(scratch) / "index"),
                                   GIT_DIR=str(repository), GIT_WORK_TREE=str(work))
                git("add", "--all", "--force", env=environment)
                tree = git("write-tree", env=environment).stdout.decode().strip()
                commit = git("commit-tree", tree, *parent, env=environment,
                             data=f"Fixture {stage}\n".encode()).stdout.decode().strip()
                if stage != "future":
                    files[stage] = {path.relative_to(work).as_posix(): sha256_file(path)
                                    for path in sorted(work.rglob("*")) if path.is_file()}
            git("--git-dir", str(repository), "update-ref", f"refs/fixtures/{fixture}/{stage}", commit)
            commits[stage] = commit
            parent = ["-p", commit]
        records[fixture] = {"commits": commits, "file_sha256": files}
    return records


def export_treatments(evidence, definitions):
    target = evidence.inputs / "treatments"
    if target.exists():
        shutil.rmtree(target)
    exported = {}
    wanted = []
    for arm, spec in definitions["treatments"].items():
        wanted += [(spec["commit"], path) for path in spec["scout_bundle"]]
    wanted += [(definitions["validator"]["commit"], path) for path in definitions["validator"]["bundle"]]
    wanted += [(definitions["treatments"]["B"]["commit"], path) for path in definitions["evaluator_records"]]
    wanted += [(definitions["treatments"]["A"]["commit"], path) for path in definitions["evaluator_records"]]
    for commit, path in sorted(set(wanted)):
        data = git("show", f"{commit}:{path}", cwd=REPOSITORY).stdout
        destination = target / commit / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        exported[f"{commit}:{path}"] = {"sha256": sha256_bytes(data), "bytes": len(data)}
    standard_spec = definitions["neutral_standard"]
    protocol = (target / standard_spec["commit"] / standard_spec["path"]).read_text(encoding="utf-8")
    paragraphs = [line for line in protocol.splitlines() if line.startswith(standard_spec["paragraph_prefix"])]
    if len(paragraphs) != 1:
        raise GateError("could not extract exactly one neutral standard paragraph from B protocol")
    (target / "neutral-standard.txt").write_text(paragraphs[0] + "\n", encoding="utf-8")
    exported["neutral-standard.txt"] = {"sha256": sha256_bytes(paragraphs[0].encode() + b"\n")}
    return exported


def treatment_text(evidence, commit, path):
    return (evidence.inputs / "treatments" / commit / path).read_text(encoding="utf-8")


def contracts_block(evidence, commit, paths):
    blocks = []
    for path in paths:
        label = path.replace("skills/", "", 1)
        blocks.append(f'<contract path="{label}">\n{treatment_text(evidence, commit, path).rstrip()}\n</contract>')
    return "\n\n".join(blocks)


def prepare(evidence, repositories, seed, snapshots=None):
    """Build fixture sources, run the pinned preparer twice into new directories, and export treatments."""
    definitions = load(DEFINITIONS)
    for number in (1, 2):
        if evidence.preparation(number).exists():
            raise GateError(f"{evidence.preparation(number)} exists; preparation output directories must be new")
    evidence.inputs.mkdir(parents=True, exist_ok=True)
    fixtures = build_fixture_source(evidence, definitions)
    combined = {"snapshots": list(load(CATALOG)["snapshots"] if snapshots is None else snapshots)}
    for fixture, record in fixtures.items():
        combined["snapshots"].append({"id": fixture, "base": record["commits"]["base"],
                                      "head": record["commits"]["head"], "first_fix": record["commits"]["future"]})
    runner = evidence.inputs / "preparer"
    if runner.exists():
        shutil.rmtree(runner)
    runner.mkdir()
    shutil.copyfile(PREPARER, runner / PREPARER.name)
    dump(runner / "case-catalog.json", combined)
    receipts = []
    for number in (1, 2):
        command = [sys.executable, str(runner / PREPARER.name)]
        for repository in [*repositories, str(evidence.fixture_source)]:
            command += ["--repository", str(repository)]
        command += ["--output", str(evidence.preparation(number)), "--seed", seed]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            dump(evidence.receipt("preparation"), {"verdict": "FAIL", "stderr": result.stderr, "at": now()})
            raise GateError("preparer failed: " + result.stderr.strip())
        receipts.append(load(evidence.preparation(number) / "evaluator-receipt.json"))
    capsules = {}
    for row in receipts[0]:
        repository = evidence.preparation(1) / "capsules" / row["alias"] / "repository"
        extra = {
            "worktree_links_absent": not (repository / ".git/worktrees").exists()
                                     and not (repository / ".git/commondir").exists(),
            "reflog_only_synthetic": set(git("-C", str(repository), "reflog", "--all", "--format=%H")
                                         .stdout.decode().split()) <= {row["synthetic_base"], row["synthetic_head"]},
            "shallow_absent": not (repository / ".git/shallow").exists(),
        }
        capsules[row["case"]] = dict(row, **extra)
    identical = receipts[0] == receipts[1]
    extras_pass = all(capsule[key] for capsule in capsules.values()
                      for key in ("worktree_links_absent", "reflog_only_synthetic", "shallow_absent"))
    verdict = "PASS" if identical and extras_pass else "FAIL"
    dump(evidence.receipt("preparation"), {
        "verdict": verdict, "at": now(), "seed": seed, "repositories": [str(r) for r in repositories],
        "preparer_sha256": sha256_file(PREPARER), "preparer_copy_sha256": sha256_file(runner / PREPARER.name),
        "combined_catalog_sha256": sha256_file(runner / "case-catalog.json"),
        "catalog_sha256": sha256_file(CATALOG), "two_runs_identical": identical, "capsules": capsules,
        "fixtures": fixtures, "note": "Preparer receipts mark model review and confinement NOT EXERCISED; "
                                      "see the isolation receipt for exercised confinement.",
    })
    exported = export_treatments(evidence, definitions)
    dump(evidence.receipt("treatments"), {"verdict": "PASS", "at": now(), "files": exported,
                                          "definitions_sha256": sha256_file(DEFINITIONS)})
    return verdict, capsules, identical


def command_prepare(args):
    verdict, capsules, identical = prepare(Evidence(args.evidence), args.repository, args.seed)
    print(f"{verdict}: {len(capsules)} capsules prepared twice; identical={identical}")
    if verdict != "PASS":
        raise GateError("preparation receipt failed")


def capsule_for(evidence, case):
    receipt = load(evidence.receipt("preparation"))["capsules"][case]
    return {"repository": evidence.preparation(1) / "capsules" / receipt["alias"] / "repository",
            "base": receipt["synthetic_base"], "head": receipt["synthetic_head"]}


def forbidden_tokens(evidence, capsule):
    """Evaluator-only tokens that must never appear in a session, unless the capsule itself holds them."""
    preparation = load(evidence.receipt("preparation"))
    definitions = load(DEFINITIONS)
    tokens = set()
    for snapshot in load(CATALOG)["snapshots"]:
        for key in ("base", "head", "first_fix"):
            tokens.update({snapshot[key], snapshot[key][:12]})
    for record in preparation["fixtures"].values():
        for commit in record["commits"].values():
            tokens.update({commit, commit[:12]})
    for spec in definitions["treatments"].values():
        tokens.update({spec["commit"], spec["commit"][:12]})
    tokens.update({str(evidence.root), str(REPOSITORY), str(RESEARCH_RAW), "case-catalog.json",
                   "evaluator-receipt.json", "EVALUATOR_EXPECTATION", "definitions.json",
                   "skills-research", "structural-calibration"})
    present = set()
    if capsule:
        for token in tokens:
            for revision in (capsule["base"], capsule["head"]):
                found = git("-C", str(capsule["repository"]), "grep", "-q", "-F", "-e", token, revision,
                            check=False).returncode == 0
                if found:
                    present.add(token)
    return sorted(tokens - present)


# ---------------------------------------------------------------- isolation


def archive_attempt(evidence, name):
    """Keep a superseded, unfrozen receipt as a recorded attempt instead of overwriting it."""
    path = evidence.receipt(name)
    if path.exists():
        target = evidence.receipts / "attempts" / f"{name}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)


def command_note(args):
    evidence = Evidence(args.evidence)
    evidence.receipts.mkdir(parents=True, exist_ok=True)
    with open(evidence.receipts / "corrections.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps({"at": now(), "note": args.text}) + "\n")
    print("recorded")


def command_isolation(args):
    evidence = Evidence(args.evidence)
    evidence.require("preparation", "run prepare first")
    archive_attempt(evidence, "isolation")
    preparation = load(evidence.receipt("preparation"))
    aliases = {case: row["alias"] for case, row in preparation["capsules"].items()}
    fix_objects = sorted({row["first_fix"] for row in load(evidence.inputs / "preparer/case-catalog.json")["snapshots"]})
    evaluator_paths = {
        "labels": DEFINITIONS, "catalog": CATALOG, "receipt": evidence.preparation(1) / "evaluator-receipt.json",
        "depot": evidence.corpus, "fixture-depot": evidence.fixture_source, "evidence": evidence.receipts,
        "repository": REPOSITORY, "research-raw": RESEARCH_RAW,
    }
    results = {}
    scratch = evidence.root / "scratch-isolation"
    for case in sorted(aliases):
        sibling = next(alias for other, alias in sorted(aliases.items()) if other != case)
        results[case] = broker.challenge_capsule(capsule_for(evidence, case), sibling=sibling,
                                                 evaluator_paths=evaluator_paths, fix_objects=fix_objects,
                                                 scratch=scratch)
        print(f"{case}: {'PASS' if results[case]['pass'] else 'FAIL'} "
              f"({sum(c['pass'] for c in results[case]['checks'])}/{len(results[case]['checks'])})")
    live = live_boundary_checks(evidence, args)
    shutil.rmtree(scratch, ignore_errors=True)
    verdict = "PASS" if all(r["pass"] for r in results.values()) and all(c["pass"] for c in live) else "FAIL"
    dump(evidence.receipt("isolation"), {
        "verdict": verdict, "at": now(), "capsules": results, "live": live,
        "interface": "capsule MCP service in bubblewrap (actual reviewer and validator launch); proxy-enforced tool surface",
        "cli_version": cli_version(args.claude),
    })
    print(f"isolation {verdict}")
    if verdict != "PASS":
        raise GateError("isolation challenges failed; no model session may run")


def live_boundary_checks(evidence, args):
    """Real CLI launches: a capsule round trip works; inherited tools, wrong effort and leaked tokens are refused."""
    checks = []
    root = evidence.sessions / "isolation" / datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    capsule = capsule_for(evidence, CHALLENGE_FIXTURE)
    budget = dict(BUDGETS["validator"], timeout_seconds=300)
    system = "You verify tool connectivity for a repository service."
    user = ("Call list_files with path '.', then read_file on the first listed file, then the git tool with "
            f"args ['diff', '--stat', '{capsule['base']}', '{capsule['head']}']. "
            "Reply with one line: the number of files listed.")
    cases = [
        ("capsule-roundtrip", None, user, "completed"),
        ("inherited-tool-refused", ("--tools", "Read"), user, "confinement_failure"),
        ("effort-mismatch-refused", ("--effort", "low" if args.effort != "low" else "high"), user, "effort_mismatch"),
        ("leaked-token-refused", None, user + " " + str(evidence.root), "leaked_context"),
    ]
    for name, override, prompt, expected in cases:
        claude = argv_wrapper(root / "launchers", args.claude, *override) if override else args.claude
        meta = broker.run_session(root / name, model=args.model, effort=args.effort, budget=budget,
                                  system_prompt=system, user_prompt=prompt, capsule=capsule,
                                  forbidden=forbidden_tokens(evidence, capsule), claude=claude)
        passed = meta["status"] == expected
        if name == "capsule-roundtrip":
            calls = [call["status"] for call in meta["tool_calls"]]
            passed = passed and calls.count("ok") >= 3 and meta["observed_settings"]["tools"] == [
                sorted(broker.ALLOWED_TOOLS)]
        checks.append({"check": f"live:{name}", "expected_status": expected, "status": meta["status"],
                       "reasons": meta["failure_reasons"], "session": str(root / name), "pass": passed,
                       "tools_offered": meta["observed_settings"]["tools"], "tool_calls": meta["tool_calls"]})
        print(f"live:{name}: {meta['status']} ({'PASS' if passed else 'FAIL'})")
    return checks


def argv_wrapper(directory, claude, flag, value):
    """A launcher that changes one CLI flag, simulating a mis-launched session the broker must refuse."""
    directory.mkdir(parents=True, exist_ok=True)
    real = shutil.which(claude) or claude
    wrapper = directory / f"launch{flag.replace('-', '_')}_{value}.py"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "# Changes one flag value, simulating a mis-launched session that the broker must refuse.\n"
        "import os, sys\n"
        f"args = sys.argv[1:]\nargs[args.index({flag!r}) + 1] = {value!r}\n"
        f"os.execv({real!r}, [{real!r}] + args)\n", encoding="utf-8")
    wrapper.chmod(0o755)
    return str(wrapper)


def cli_version(claude):
    try:
        return subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL).stdout.strip()
    except OSError as error:
        return f"unavailable: {error}"


# ---------------------------------------------------------------- evaluator sessions


def evaluator_session(directory, kind, *, plan, system, user, capsule, evidence):
    """Run an evaluator session with at most one prospective rerun after an execution failure."""
    attempts = []
    for attempt in (1, 2):
        path = Path(directory) / f"attempt-{attempt}"
        if (path / "meta.json").exists():
            meta = load(path / "meta.json")
        else:
            if path.exists():
                shutil.rmtree(path)
            meta = broker.run_session(path, model=plan["model"], effort=plan["effort"], budget=BUDGETS[kind],
                                      system_prompt=system, user_prompt=user, capsule=capsule,
                                      forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"])
        attempts.append(path)
        if meta["status"] == "completed":
            value = scoring.extract_json((path / "result.txt").read_text(encoding="utf-8"))
            if value is not None:
                return value, [str(p) for p in attempts]
    return None, [str(p) for p in attempts]


def adjudicator_prompts(evidence, capsule, anchor, concern, claimed_cost):
    standard = (evidence.inputs / "treatments/neutral-standard.txt").read_text(encoding="utf-8").strip()
    system = render("adjudicator-system.md", standard=standard)
    user = render("adjudicator-packet.md", base=capsule["base"], head=capsule["head"], anchor=anchor,
                  concern=concern, claimed_cost=claimed_cost)
    return system, user


def resolve_pair(directory, kind, *, plan, evidence, capsule, instructions, packet, first, second, schema_key):
    system = render("resolver-system.md", instructions=instructions)
    user = (packet + "\n\nAssessment 1:\n\n" + fence(json.dumps(first, indent=2), "json") +
            "\n\nAssessment 2:\n\n" + fence(json.dumps(second, indent=2), "json"))
    value, attempts = evaluator_session(directory, kind, plan=plan, system=system, user=user, capsule=capsule,
                                        evidence=evidence)
    return value, attempts


def parallel(items, function, workers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, items))


def evaluator_plan(args):
    return {"model": args.model, "effort": args.effort, "claude": args.claude}


def command_adjudicate(args):
    evidence = Evidence(args.evidence)
    evidence.require("isolation", "isolation must pass before any model session")
    definitions = load(DEFINITIONS)
    plan = evaluator_plan(args)
    if evidence.receipt("labels").exists() or evidence.receipt("controls").exists():
        raise GateError("labels or controls are already frozen")
    root = evidence.sessions / "adjudication"

    def label_job(label):
        spec = definitions["labels"][label]
        capsule = capsule_for(evidence, spec["case"])
        system, user = adjudicator_prompts(evidence, capsule, spec["anchor"], spec["concern"], spec["claimed_cost"])
        assessments = []
        for index in (1, 2):
            value, attempts = evaluator_session(root / f"label-{label}-{index}", "adjudicator", plan=plan,
                                                system=system, user=user, capsule=capsule, evidence=evidence)
            assessments.append({"value": value, "sessions": attempts})
        decisions = [a["value"]["decision"] if a["value"] else "failed" for a in assessments]
        record = {"label": label, "case": spec["case"], "assessments": assessments, "independent_decisions": decisions}
        if decisions[0] == decisions[1] and decisions[0] in ("eligible", "excluded"):
            record["decision"] = decisions[0]
            record["resolution"] = "independent agreement"
        elif "failed" in decisions:
            record["decision"] = "excluded"
            record["resolution"] = "evaluator execution failure; unresolved and excluded"
        else:
            value, attempts = resolve_pair(root / f"label-{label}-resolver", "adjudicator", plan=plan,
                                           evidence=evidence, capsule=capsule, instructions=system, packet=user,
                                           first=assessments[0]["value"], second=assessments[1]["value"],
                                           schema_key="decision")
            resolved = value.get("decision") if value else "failed"
            record["resolver"] = {"value": value, "sessions": attempts}
            if resolved == "eligible":
                record["decision"] = "eligible"
                record["resolution"] = "disagreement resolved eligible by independent resolver"
            elif resolved == "excluded":
                record["decision"] = "excluded"
                record["resolution"] = "disagreement resolved excluded by independent resolver"
            else:
                record["decision"] = "provisional"
                record["resolution"] = "disagreement unresolved; provisional, outside primary recall"
        print(f"label {label}: {decisions} -> {record['decision']}")
        return record

    def control_job(control):
        spec = definitions["controls"][control]
        capsule = capsule_for(evidence, control)
        standard = (evidence.inputs / "treatments/neutral-standard.txt").read_text(encoding="utf-8").strip()
        system = render("control-system.md", standard=standard)
        user = render("control-packet.md", base=capsule["base"], head=capsule["head"], design=spec["design"],
                      must_not=spec["must_not_become_a_finding"])
        assessments = []
        for index in (1, 2):
            value, attempts = evaluator_session(root / f"control-{control}-{index}", "adjudicator", plan=plan,
                                                system=system, user=user, capsule=capsule, evidence=evidence)
            assessments.append({"value": value, "sessions": attempts})

        def negative(value):
            return bool(value) and not value.get("named_design_meets_standard") and not value.get("other_qualifying_concerns")

        verdicts = [negative(a["value"]) if a["value"] else None for a in assessments]
        record = {"control": control, "assessments": assessments, "independent_negative": verdicts}
        if verdicts == [True, True]:
            record["expected"] = "negative"
            record["resolution"] = "independent agreement"
        elif None in verdicts:
            record["expected"] = "unestablished"
            record["resolution"] = "evaluator execution failure"
        else:
            value, attempts = resolve_pair(root / f"control-{control}-resolver", "adjudicator", plan=plan,
                                           evidence=evidence, capsule=capsule, instructions=system, packet=user,
                                           first=assessments[0]["value"], second=assessments[1]["value"],
                                           schema_key="expected_outcome")
            record["resolver"] = {"value": value, "sessions": attempts}
            record["expected"] = "negative" if negative(value) else "unestablished"
            record["resolution"] = "disagreement resolved by independent resolver"
        print(f"control {control}: {verdicts} -> {record['expected']}")
        return record

    labels = parallel(sorted(definitions["labels"]), label_job, args.workers)
    controls = parallel(list(CONTROLS), control_job, args.workers)
    label_verdict = "PASS" if all(r["decision"] in ("eligible", "excluded", "provisional") for r in labels) else "FAIL"
    control_verdict = "PASS" if all(r["expected"] == "negative" for r in controls) else "FAIL"
    write_once(evidence.receipt("labels"), {
        "verdict": label_verdict, "frozen_at": now(), "definitions_sha256": sha256_file(DEFINITIONS),
        "labels": {r["label"]: r for r in labels},
        "rule": "eligible only on independent agreement or independent resolution; unresolved disagreement is provisional",
        "prompts": {name: sha256_file(ROLES / name) for name in ("adjudicator-system.md", "adjudicator-packet.md",
                                                                 "resolver-system.md")},
    })
    write_once(evidence.receipt("controls"), {
        "verdict": control_verdict, "frozen_at": now(), "controls": {r["control"]: r for r in controls},
        "prompts": {name: sha256_file(ROLES / name) for name in ("control-system.md", "control-packet.md")},
    })
    print(f"labels {label_verdict}; controls {control_verdict}")


# ---------------------------------------------------------------- plan


def make_schedule(phase, seed):
    """Seeded random launch order of every case, repetition and arm; fresh sessions throughout."""
    spec = PHASES[phase]
    schedule = [{"case": case, "arm": arm, "repetition": repetition}
                for case in spec["cases"] for repetition in range(1, spec["repetitions"] + 1) for arm in ("A", "B")]
    random.Random(f"{seed}:{phase}").shuffle(schedule)
    first_arm = {}
    for index, item in enumerate(schedule, 1):
        item["order"] = index
        item["run"] = f"{phase}-{item['case']}-r{item['repetition']}-{item['arm']}"
        first_arm.setdefault(f"{item['case']}-r{item['repetition']}", item["arm"])
    return schedule, first_arm


def command_freeze(args):
    evidence = Evidence(args.evidence)
    for name, message in [("preparation", "prepare"), ("treatments", "prepare"), ("isolation", "isolation"),
                          ("labels", "adjudicate"), ("controls", "adjudicate")]:
        evidence.require(name, f"run {message} before freezing")
    if args.phase == "full":
        evidence.require("gate-pilot", "the pilot gate must PASS before the full schedule is frozen")
    phase = PHASES[args.phase]
    cap = args.validator_cap if args.validator_cap is not None else phase.get("validator_cap")
    if cap is None:
        raise GateError("the full phase needs an explicit --validator-cap")
    schedule, first_arm = make_schedule(args.phase, args.seed)
    definitions = load(DEFINITIONS)
    plan = {
        "phase": args.phase, "frozen_at": now(), "seed": args.seed, "model": args.model, "effort": args.effort,
        "claude": args.claude, "cli_version": cli_version(args.claude), "workers": args.workers,
        "schedule": schedule, "first_arm_by_pair": first_arm, "budgets": BUDGETS, "validator_cap": cap,
        "challenge_budget": {"sessions": len(definitions["challenges"]), "per_session": BUDGETS["validator"]},
        "benchmark_revision": git("rev-parse", "HEAD", cwd=REPOSITORY).stdout.decode().strip(),
        "benchmark_dirty": bool(git("status", "--porcelain", "--", str(HERE), cwd=REPOSITORY).stdout.strip()),
        "hashes": {
            "definitions": sha256_file(DEFINITIONS), "catalog": sha256_file(CATALOG),
            "calibrate": sha256_file(Path(__file__)), "broker": sha256_file(HERE / "broker.py"),
            "scoring": sha256_file(HERE / "scoring.py"), "capsule_server": sha256_file(HERE / "capsule_server.py"),
            "roles": {path.name: sha256_file(path) for path in sorted(ROLES.iterdir())},
            "labels_receipt": sha256_file(evidence.receipt("labels")),
            "controls_receipt": sha256_file(evidence.receipt("controls")),
            "preparation_receipt": sha256_file(evidence.receipt("preparation")),
            "treatments_receipt": sha256_file(evidence.receipt("treatments")),
            "isolation_receipt": sha256_file(evidence.receipt("isolation")),
        },
        "matching_rules": "same task, structural cost and causal mechanism; titles, lines and refactors ignored; "
                          "duplicates count once; multiple credits need independent statements",
        "rerun_policy": "no scout or validator rerun; evaluator sessions get one prospective rerun after an execution failure",
        "probe_policy": "static validation only; Needs probe is recorded as a transition and never executed",
    }
    if args.phase == "full":
        plan["pilot_gate_sha256"] = sha256_file(evidence.receipt("gate-pilot"))
    write_once(evidence.receipt(f"plan-{args.phase}"), plan)
    print(f"frozen {args.phase}: {len(schedule)} scouts, validator cap {cap}")


# ---------------------------------------------------------------- execution


def scout_prompts(evidence, plan, case, arm):
    definitions = load(DEFINITIONS)
    capsule = capsule_for(evidence, case)
    spec = definitions["treatments"][arm]
    system = render("scout-system.md", contracts=contracts_block(evidence, spec["commit"], spec["scout_bundle"]))
    diff = git("-C", str(capsule["repository"]), "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
               capsule["base"], capsule["head"]).stdout
    expected = load(evidence.receipt("preparation"))["capsules"][case]["diff_sha256"]
    if sha256_bytes(diff) != expected:
        raise GateError(f"{case}: capsule diff no longer matches the preparation receipt")
    user = render("scout-packet.md", base=capsule["base"], head=capsule["head"],
                  diff=fence(diff.decode("utf-8", errors="replace"), "diff"))
    return capsule, system, user


def validator_prompts(evidence, case, hypothesis_text, opaque):
    definitions = load(DEFINITIONS)
    capsule = capsule_for(evidence, case)
    spec = definitions["validator"]
    system = render("validator-system.md", contracts=contracts_block(evidence, spec["commit"], spec["bundle"]))
    user = render("validator-packet.md", hypothesis_id=opaque, origin_id=f"structural-{opaque}",
                  base=capsule["base"], head=capsule["head"], hypothesis=hypothesis_text)
    return capsule, system, user


def run_scouts(evidence, plan, phase):
    root = evidence.sessions / phase / "scouts"

    def job(item):
        directory = root / item["run"]
        if (directory / "meta.json").exists():
            return load(directory / "meta.json")
        if directory.exists():
            raise GateError(f"{directory} exists without meta.json: an interrupted attempt; record it, do not rerun")
        capsule, system, user = scout_prompts(evidence, plan, item["case"], item["arm"])
        meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"], budget=plan["budgets"]["scout"],
                                  system_prompt=system, user_prompt=user, capsule=capsule,
                                  forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"])
        print(f"scout {item['run']}: {meta['status']} {meta['duration_seconds']}s")
        return meta

    ordered = sorted(plan["schedule"], key=lambda item: item["order"])
    parallel(ordered, job, plan["workers"])


def collect_runs(evidence, plan, phase):
    runs = []
    for item in sorted(plan["schedule"], key=lambda item: item["order"]):
        directory = evidence.sessions / phase / "scouts" / item["run"]
        meta = load(directory / "meta.json") if (directory / "meta.json").exists() else None
        status = meta["status"] if meta else "not_run"
        parsed = {"kind": None, "hypotheses": [], "schema_violations": []}
        if status == "completed":
            parsed = scoring.parse_scout((directory / "result.txt").read_text(encoding="utf-8"))
            if parsed["kind"] == "unusable":
                status = "unusable_output"
        runs.append({"run": item["run"], "case": item["case"], "arm": item["arm"], "repetition": item["repetition"],
                     "status": status, "parse_kind": parsed["kind"], "schema_violations": parsed["schema_violations"],
                     "hypotheses": parsed["hypotheses"], "session": str(directory)})
    return runs


def build_pool(evidence, plan, phase, runs):
    """Opaque, treatment-blind hypothesis pool. The mapping stays evaluator-side."""
    path = evidence.receipts / phase / "pool.json"
    if path.exists():
        return load(path)
    generator = random.Random(f"{plan['seed']}:{phase}:pool")
    entries = []
    for run in runs:
        if run["status"] != "completed":
            continue
        for hypothesis in run["hypotheses"]:
            entries.append((run, hypothesis))
    generator.shuffle(entries)
    pool, replays = {}, {}
    used = set()

    def opaque(prefix):
        while True:
            value = f"{prefix}{generator.getrandbits(32):08x}"
            if value not in used:
                used.add(value)
                return value

    for run, hypothesis in entries:
        key = (run["case"], scoring.replay_key(hypothesis))
        if key not in replays:
            replay_id = opaque("R-")
            replays[key] = {"replay": replay_id, "case": run["case"],
                            "text": scoring.replay_text(hypothesis, replay_id)}
        pid = opaque("H-")
        pool[pid] = {"run": run["run"], "case": run["case"], "local_id": hypothesis["local_id"],
                     "missing": hypothesis["missing"], "replay": replays[key]["replay"],
                     "text": scoring.replay_text(hypothesis, pid)}
    value = {"created_at": now(), "pool": pool,
             "replays": {entry["replay"]: entry for entry in replays.values()},
             "replay_order": sorted(entry["replay"] for entry in replays.values())}
    dump(path, value)
    return value


def run_replay(evidence, plan, phase, pool):
    cap = current_cap(evidence, plan, phase)
    order = pool["replay_order"]
    root = evidence.sessions / phase / "validators"
    selected = order[:cap]

    def job(replay_id):
        entry = pool["replays"][replay_id]
        directory = root / replay_id
        if (directory / "meta.json").exists():
            return
        capsule, system, user = validator_prompts(evidence, entry["case"], entry["text"], replay_id)
        meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"],
                                  budget=plan["budgets"]["validator"], system_prompt=system, user_prompt=user,
                                  capsule=capsule, forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"])
        print(f"validator {replay_id}: {meta['status']} {meta['duration_seconds']}s")

    parallel(selected, job, plan["workers"])
    status = {"cap": cap, "unique_hypotheses": len(order), "replayed": len(selected),
              "unreplayed": order[cap:], "complete": len(order) <= cap, "at": now()}
    dump(evidence.receipts / phase / "replay-status.json", status)
    return status


def current_cap(evidence, plan, phase):
    cap = plan["validator_cap"]
    revisions = evidence.receipts / phase / "budget-revisions.json"
    if revisions.exists():
        for revision in load(revisions):
            cap = revision["validator_cap"]
    return cap


def collect_validations(evidence, phase, pool):
    validations = {}
    for replay_id in pool["replay_order"]:
        directory = evidence.sessions / phase / "validators" / replay_id
        if not (directory / "meta.json").exists():
            continue
        meta = load(directory / "meta.json")
        disposition = None
        status = meta["status"]
        if status == "completed":
            disposition = scoring.parse_validator((directory / "result.txt").read_text(encoding="utf-8"))
            if disposition is None:
                status = "unusable_output"
        validations[replay_id] = {"status": status, "disposition": disposition, "session": str(directory)}
    return validations


def run_challenges(evidence, plan):
    path = evidence.receipt("challenges")
    if path.exists():
        return load(path)
    definitions = load(DEFINITIONS)
    root = evidence.sessions / "challenges"
    generator = random.Random(f"{plan['seed']}:challenges")
    opaques = {challenge["id"]: f"R-{generator.getrandbits(32):08x}" for challenge in definitions["challenges"]}

    def job(challenge):
        opaque = opaques[challenge["id"]]
        fields = dict(challenge["hypothesis"], Origin="structural")
        text = f"### Hypothesis {opaque}\n" + "\n".join(f"- **{name}:** {fields[name]}" for name in scoring.FIELDS)
        directory = root / challenge["id"]
        capsule, system, user = validator_prompts(evidence, challenge["fixture"], text, opaque)
        if (directory / "meta.json").exists():
            meta = load(directory / "meta.json")
        else:
            meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"],
                                      budget=plan["challenge_budget"]["per_session"], system_prompt=system,
                                      user_prompt=user, capsule=capsule, forbidden=forbidden_tokens(evidence, capsule),
                                      claude=plan["claude"])
        disposition = scoring.parse_validator((directory / "result.txt").read_text(encoding="utf-8")) \
            if meta["status"] == "completed" else None
        expected = challenge["expected"]
        if disposition is None:
            outcome = "execution failure"
        elif expected == "not Finding":
            outcome = "pass" if disposition != "Finding" else "validator false positive"
        else:
            outcome = "pass" if disposition == expected else "deviation"
        print(f"challenge {challenge['id']}: {disposition} ({outcome})")
        return {"id": challenge["id"], "kind": challenge["kind"], "fixture": challenge["fixture"],
                "expected": expected, "gating": challenge.get("gating", True), "status": meta["status"],
                "disposition": disposition, "outcome": outcome, "session": str(directory)}

    results = parallel(definitions["challenges"], job, plan["workers"])
    gating = [r for r in results if r["gating"]]
    verdict = "PASS" if all(r["outcome"] == "pass" for r in gating) else "FAIL"
    value = {"verdict": verdict, "at": now(), "results": results,
             "rule": "preference and equal-burden challenges fail conformance on Finding; the indirection challenge "
                     "must be Disproved without substitution; Z1 is supplementary and does not gate"}
    dump(path, value)
    return value


def run_assessments(evidence, plan, phase, pool):
    path = evidence.receipts / phase / "assessments.json"
    if path.exists():
        return load(path)
    definitions = load(DEFINITIONS)
    instructions = (ROLES / "assessor-system.md").read_text(encoding="utf-8")
    root = evidence.sessions / phase / "assessors"
    cases = sorted({entry["case"] for entry in pool["pool"].values()})

    def job(case):
        labels = [(label, spec) for label, spec in sorted(definitions["labels"].items()) if spec["case"] == case]
        label_text = "\n".join(f"- {label} (anchor {spec['anchor']}): {spec['concern']} Claimed cost: "
                               f"{spec['claimed_cost']}" for label, spec in labels) or "(none)"
        ids = sorted(pid for pid, entry in pool["pool"].items() if entry["case"] == case)
        hypotheses = "\n\n".join(fence(pool["pool"][pid]["text"], "markdown") for pid in ids)
        user = render("assessor-packet.md", labels=label_text, hypotheses=hypotheses)
        results = []
        for index in (1, 2):
            value, attempts = evaluator_session(root / f"{case}-{index}", "assessor", plan=plan,
                                                system=instructions, user=user, capsule=None, evidence=evidence)
            results.append({"value": value, "sessions": attempts})
        by_id = [{a["id"]: a for a in (r["value"] or {}).get("assessments", [])} for r in results]
        final, disputed = {}, []
        for pid in ids:
            first, second = by_id[0].get(pid), by_id[1].get(pid)
            if first and second and comparable(first) == comparable(second):
                final[pid] = dict(first, resolution="independent agreement")
            else:
                disputed.append(pid)
        resolver = None
        if disputed:
            subset = "\n\n".join(fence(pool["pool"][pid]["text"], "markdown") for pid in disputed)
            packet = render("assessor-packet.md", labels=label_text, hypotheses=subset)
            value, attempts = resolve_pair(root / f"{case}-resolver", "assessor", plan=plan, evidence=evidence,
                                           capsule=None, instructions=instructions, packet=packet,
                                           first=[by_id[0].get(pid) for pid in disputed],
                                           second=[by_id[1].get(pid) for pid in disputed], schema_key="assessments")
            resolver = {"value": value, "sessions": attempts, "disputed": disputed}
            resolved = {a["id"]: a for a in (value or {}).get("assessments", [])}
            for pid in disputed:
                if pid in resolved:
                    final[pid] = dict(resolved[pid], resolution="resolved by independent resolver")
        print(f"assessors {case}: {len(ids)} hypotheses, {len(disputed)} disputed, {len(final)} decided")
        return case, {"independent": results, "resolver": resolver, "final": final, "ids": ids}

    by_case = dict(parallel(cases, job, plan["workers"]))
    final = {}
    for record in by_case.values():
        final.update(record["final"])
    value = {"at": now(), "cases": by_case, "final": final,
             "complete": all(pid in final for pid in pool["pool"])}
    dump(path, value)
    return value


def comparable(assessment):
    return (bool(assessment.get("admission_qualified")),
            sorted((m.get("label"), bool(m.get("independent_statement"))) for m in assessment.get("matches", [])))


def run_novelty(evidence, plan, phase, pool, validations, assessments):
    path = evidence.receipts / phase / "novelty.json"
    if path.exists():
        return load(path)
    root = evidence.sessions / phase / "novelty"
    targets = {}
    for pid, entry in pool["pool"].items():
        validation = validations.get(entry["replay"])
        matched = assessments["final"].get(pid, {}).get("matches", [])
        if validation and validation["disposition"] == "Finding" and not matched:
            targets.setdefault(entry["replay"], entry)

    def job(replay_id):
        entry = pool["replays"][replay_id]
        hypothesis = scoring.parse_scout(entry["text"])["hypotheses"][0]["fields"]
        capsule = capsule_for(evidence, entry["case"])
        system, user = adjudicator_prompts(
            evidence, capsule, hypothesis.get("File/line", "unstated"),
            hypothesis.get("Title", "") + " " + hypothesis.get("Source evidence", ""),
            hypothesis.get("Expected impact", ""))
        value, attempts = evaluator_session(root / replay_id, "adjudicator", plan=plan, system=system, user=user,
                                            capsule=capsule, evidence=evidence)
        print(f"novelty {replay_id}: {(value or {}).get('decision')}")
        return replay_id, {"decision": (value or {}).get("decision", "failed"), "value": value, "sessions": attempts,
                           "case": entry["case"]}

    value = dict(parallel(sorted(targets), job, plan["workers"]))
    dump(path, value)
    return value


def run_reasons(evidence, plan, phase, pool, validations):
    path = evidence.receipts / phase / "reasons.json"
    if path.exists():
        return load(path)
    items = [(replay_id, v) for replay_id, v in sorted(validations.items())
             if v["status"] == "completed" and v["disposition"] != "Finding"]
    if not items:
        dump(path, {})
        return {}
    texts = "\n\n".join(f"Outcome {replay_id}:\n\n" + fence(
        (Path(v["session"]) / "result.txt").read_text(encoding="utf-8"), "markdown") for replay_id, v in items)
    value, attempts = evaluator_session(evidence.sessions / phase / "reasons", "assessor", plan=plan,
                                        system=(ROLES / "reason-system.md").read_text(encoding="utf-8"),
                                        user=texts, capsule=None, evidence=evidence)
    result = {c["id"]: dict(c, sessions=attempts) for c in (value or {}).get("classifications", [])}
    dump(path, result)
    return result


def command_run(args):
    evidence = Evidence(args.evidence)
    plan = load(evidence.receipt(f"plan-{args.phase}"))
    evidence.require("isolation", "isolation must pass")
    if args.phase == "full":
        evidence.require("gate-pilot", "the pilot gate must PASS")
    revisions = evidence.receipts / args.phase / "budget-revisions.json"
    replay_path = evidence.receipts / args.phase / "replay-status.json"
    if replay_path.exists() and not load(replay_path)["complete"]:
        cap = current_cap(evidence, plan, args.phase)
        if not revisions.exists() or cap <= load(replay_path)["cap"]:
            raise GateError("replay is incomplete at the cap; record a prospective budget revision first")
    run_scouts(evidence, plan, args.phase)
    runs = collect_runs(evidence, plan, args.phase)
    pool = build_pool(evidence, plan, args.phase, runs)
    status = run_replay(evidence, plan, args.phase, pool)
    if args.phase == "pilot":
        run_challenges(evidence, plan)
    if not status["complete"]:
        print(f"INCOMPLETE: {len(status['unreplayed'])} unique hypotheses exceed the validator cap {status['cap']}. "
              "Record a prospective budget revision before any further execution.")
        return
    validations = collect_validations(evidence, args.phase, pool)
    assessments = run_assessments(evidence, plan, args.phase, pool)
    run_novelty(evidence, plan, args.phase, pool, validations, assessments)
    run_reasons(evidence, plan, args.phase, pool, validations)
    command_score(args)


def command_revise_budget(args):
    evidence = Evidence(args.evidence)
    path = evidence.receipts / args.phase / "budget-revisions.json"
    revisions = load(path) if path.exists() else []
    replay = evidence.receipts / args.phase / "replay-status.json"
    revisions.append({"at": now(), "validator_cap": args.validator_cap, "reason": args.reason,
                      "replay_status_before": load(replay) if replay.exists() else None})
    dump(path, revisions)
    print(f"recorded prospective validator cap {args.validator_cap} for {args.phase}")


# ---------------------------------------------------------------- scoring and gates


def phase_data(evidence, phase):
    plan = load(evidence.receipt(f"plan-{phase}"))
    runs = collect_runs(evidence, plan, phase)
    pool = load(evidence.receipts / phase / "pool.json")
    validations = collect_validations(evidence, phase, pool)
    assessments = load(evidence.receipts / phase / "assessments.json")
    labels = load(evidence.receipt("labels"))["labels"]
    return {
        "definitions": load(DEFINITIONS), "frozen_labels": labels, "controls": list(CONTROLS),
        "runs": [{k: v for k, v in run.items() if k != "hypotheses"} for run in runs],
        "pool": pool["pool"], "validations": validations, "assessments": assessments["final"],
        "novelty": load(evidence.receipts / phase / "novelty.json"),
        "reasons": load(evidence.receipts / phase / "reasons.json"), "seed": plan["seed"],
    }


def command_score(args):
    evidence = Evidence(args.evidence)
    result = scoring.score(phase_data(evidence, args.phase))
    result["scorer"] = {"version": scoring.SCORER_VERSION, "sha256": sha256_file(HERE / "scoring.py")}
    dump(evidence.results / f"{args.phase}-scores.json", result)
    print(f"scored {args.phase}: macro {result['macro']}")


def settings_signature(meta):
    observed = meta["observed_settings"]
    return {key: observed[key] for key in ("model", "effort", "tools", "max_tokens", "thinking", "context_management",
                                           "cli")} | {"budget": meta["budget"]}


def all_session_metas(evidence):
    return [(path.parent, load(path)) for path in sorted(evidence.sessions.rglob("meta.json"))]


def command_gate(args):
    evidence = Evidence(args.evidence)
    phase = args.phase
    plan = load(evidence.receipt(f"plan-{phase}"))
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "pass": bool(passed), "detail": detail})

    for name in ("preparation", "treatments", "isolation", "labels", "controls"):
        value = load(evidence.receipt(name)) if evidence.receipt(name).exists() else {}
        check(f"receipt:{name}", value.get("verdict") == "PASS", value.get("verdict", "missing"))
    preparation = load(evidence.receipt("preparation"))
    check("capsule-fidelity", preparation.get("two_runs_identical") and all(
        c["tree_and_diff_equality"] == "PASS" and c["fix_object_absence"] == "PASS" for c in
        preparation["capsules"].values()), "two identical preparations; exact trees and diffs; fix objects absent")
    isolation = load(evidence.receipt("isolation"))
    needed = set(plan_cases(plan)) | ({CHALLENGE_FIXTURE} if phase == "pilot" else set())
    check("access-denials-exercised", all(isolation["capsules"].get(case, {}).get("pass") for case in needed)
          and all(c["pass"] for c in isolation["live"]), sorted(needed))
    scouts = [load(evidence.sessions / phase / "scouts" / item["run"] / "meta.json")
              if (evidence.sessions / phase / "scouts" / item["run"] / "meta.json").exists() else None
              for item in plan["schedule"]]
    started = min((m["started"] for m in scouts if m), default=None)
    frozen = [datetime.datetime.fromisoformat(load(evidence.receipt(n))["frozen_at"]).timestamp()
              for n in ("labels", "controls", f"plan-{phase}")]
    check("frozen-before-execution", started is not None and max(frozen) < started,
          "labels, controls and plan frozen before the first scout started")
    runs = collect_runs(evidence, plan, phase)
    check("complete-outputs", all(r["status"] == "completed" for r in runs),
          {r["run"]: r["status"] for r in runs})
    mismatched = []
    by_pair = {}
    for item, meta in zip(plan["schedule"], scouts):
        if meta:
            by_pair.setdefault((item["case"], item["repetition"]), []).append(settings_signature(meta))
    for pair, signatures in by_pair.items():
        if len(signatures) != 2 or signatures[0] != signatures[1] or signatures[0]["model"] != [plan["model"]] \
                or signatures[0]["effort"] != [plan["effort"]]:
            mismatched.append(list(pair))
    check("resolved-paired-settings", not mismatched and len(by_pair) == len(plan["schedule"]) // 2,
          {"mismatched_pairs": mismatched, "signature_example": next(iter(by_pair.values()), [None])[0]})
    # Sessions whose results feed frozen decisions or this phase. Superseded attempts, shakedowns and the
    # deliberate isolation refusals feed nothing; they are retained and listed, not scanned as leaks.
    scoped = [evidence.sessions / "adjudication", evidence.sessions / phase] + (
        [evidence.sessions / "challenges"] if phase == "pilot" else [])
    refused = [(str(path), meta["status"]) for path, meta in all_session_metas(evidence)
               if meta["status"] in ("leaked_context", "confinement_failure", "unexpected_context")]
    leaks = [path for path, _ in refused if any(Path(path).is_relative_to(root) for root in scoped)]
    check("no-leakage", not leaks, {"leaks": leaks, "retained_unscoped_refusals": [
        item for item in refused if item[0] not in leaks]})
    replay = load(evidence.receipts / phase / "replay-status.json")
    pool = load(evidence.receipts / phase / "pool.json")
    validations = collect_validations(evidence, phase, pool)
    check("disposition-accounting-within-cap", replay["complete"] and replay["unique_hypotheses"] <= replay["cap"]
          and all(validations.get(r, {}).get("disposition") for r in pool["replay_order"]),
          {"cap": replay["cap"], "unique": replay["unique_hypotheses"],
           "dispositions": {r: validations.get(r, {}).get("disposition") for r in pool["replay_order"]}})
    if phase == "pilot":
        challenges = load(evidence.receipt("challenges"))
        check("validator-conformance", challenges["verdict"] == "PASS",
              {r["id"]: r["outcome"] for r in challenges["results"]})
    assessments = load(evidence.receipts / phase / "assessments.json")
    check("assessments-complete", assessments["complete"], f"{len(assessments['final'])}/{len(pool['pool'])}")
    stored = load(evidence.results / f"{phase}-scores.json")
    recomputed = scoring.score(phase_data(evidence, phase))
    recomputed["scorer"] = stored.get("scorer")
    emitted = sum(len(r["hypotheses"]) for r in runs if r["status"] == "completed")
    check("scorer-reconciles-to-raw-evidence", recomputed == stored and emitted == len(pool["pool"]),
          {"emitted_in_raw_outputs": emitted, "pooled": len(pool["pool"])})
    verdict = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    name = f"gate-{phase}" if phase == "pilot" else "completion-full"
    receipt = {"verdict": verdict, "at": now(), "phase": phase, "checks": checks,
               "note": "Low recall or scout false positives do not fail this operational gate."}
    dump(evidence.receipt(name), receipt)
    for item in checks:
        print(f"{'PASS' if item['pass'] else 'FAIL'} {item['check']}")
    print(f"{name}: {verdict}")


def plan_cases(plan):
    return sorted({item["case"] for item in plan["schedule"]})


def command_manifest(args):
    evidence = Evidence(args.evidence)
    lines = []
    for path in sorted(evidence.root.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.sha256":
            lines.append(f"{sha256_file(path)}  {path.relative_to(evidence.root).as_posix()}")
    (evidence.root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"manifest: {len(lines)} files")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command, model=False):
        command.add_argument("--evidence", required=True, help="durable evaluator evidence directory")
        if model:
            command.add_argument("--model", required=True, help="exact model identifier; never substituted")
            command.add_argument("--effort", required=True, choices=["low", "medium", "high", "xhigh", "max"])
            command.add_argument("--claude", default="claude", help="Claude CLI executable")
            command.add_argument("--workers", type=int, default=3)
        return command

    prepare = common(sub.add_parser("prepare", help="build fixtures, prepare capsules twice, export treatments"))
    prepare.add_argument("--repository", action="append", required=True)
    prepare.add_argument("--seed", required=True)
    common(sub.add_parser("isolation", help="exercise access challenges and broker refusals"), model=True)
    common(sub.add_parser("adjudicate", help="independent label and control adjudication, then freeze"), model=True)
    freeze = common(sub.add_parser("freeze", help="freeze the schedule, budgets and hashes for a phase"), model=True)
    freeze.add_argument("--phase", choices=sorted(PHASES), required=True)
    freeze.add_argument("--seed", required=True)
    freeze.add_argument("--validator-cap", type=int)
    for name in ("run", "score", "gate"):
        command = common(sub.add_parser(name))
        command.add_argument("--phase", choices=sorted(PHASES), required=True)
    revise = common(sub.add_parser("revise-budget", help="record a prospective validator cap revision"))
    revise.add_argument("--phase", choices=sorted(PHASES), required=True)
    revise.add_argument("--validator-cap", type=int, required=True)
    revise.add_argument("--reason", required=True)
    common(sub.add_parser("manifest", help="write the evidence integrity manifest"))
    note = common(sub.add_parser("note", help="record a failed attempt or prospective correction"))
    note.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    handlers = {"prepare": command_prepare, "isolation": command_isolation, "adjudicate": command_adjudicate,
                "freeze": command_freeze, "run": command_run, "score": command_score, "gate": command_gate,
                "revise-budget": command_revise_budget, "manifest": command_manifest,
                "note": command_note}
    handlers[args.command](args)


if __name__ == "__main__":
    main()
