#!/usr/bin/env python3
"""Blinded structural-scout calibration benchmark: preparation, isolation, execution, scoring.

Everything this program reads or writes outside the reviewer boundary is evaluator-only:
the catalog, definitions, fixtures, depot, evidence directory and receipts. A reviewer or
validator session sees one capsule repository through the jailed capsule service, plus the
prompt text recorded in its session directory. See README.md for the operator procedure.
"""

import argparse
from contextlib import contextmanager
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
        self.attempt_id = None

    def phase_sessions(self, phase):
        root = self.sessions / phase
        return root / "attempts" / self.attempt_id if self.attempt_id else root

    def set_attempt(self, attempt_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", attempt_id) or attempt_id in (".", ".."):
            raise GateError("attempt-id must be a safe 1-64 character identifier")
        self.attempt_id = attempt_id

    def phase_receipts(self, phase):
        root = self.receipts / phase
        return root / "attempts" / self.attempt_id if self.attempt_id else root

    def phase_result(self, phase, name):
        root = self.results / phase
        if self.attempt_id:
            root = root / "attempts" / self.attempt_id
        return root / name

    def phase_receipt_history(self, phase, stem):
        return sorted(self.phase_receipts(phase).glob(f"{stem}-[0-9][0-9][0-9][0-9].json"))

    def latest_phase_receipt(self, phase, stem):
        history = self.phase_receipt_history(phase, stem)
        return history[-1] if history else self.phase_receipts(phase) / f"{stem}.json"

    def next_phase_receipt(self, phase, stem):
        history = self.phase_receipt_history(phase, stem)
        return self.phase_receipts(phase) / f"{stem}-{len(history) + 1:04d}.json"

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


def setup_live_batch(evidence, phase, args):
    evidence.set_attempt(args.attempt_id)
    if args.max_sessions <= 0 or args.max_requests <= 0:
        raise GateError("setup live plan must grant positive total session and request budgets")
    if not args.approved_by.strip() or not args.reason.strip():
        raise GateError("setup live plan must identify its approving operator and reason")
    hashes = {"calibrate": sha256_file(Path(__file__)), "definitions": sha256_file(DEFINITIONS),
              "catalog": sha256_file(CATALOG),
              "broker": sha256_file(HERE / "broker.py"), "capsule_server": sha256_file(HERE / "capsule_server.py"),
              "preparation": sha256_file(evidence.receipt("preparation"))}
    if phase == "adjudicate":
        hashes["isolation"] = sha256_file(evidence.receipt("isolation"))
        hashes["roles"] = {path.name: sha256_file(path) for path in sorted(ROLES.iterdir())}
    approved = {"phase": phase, "attempt_id": args.attempt_id, "model": args.model, "effort": args.effort,
                "claude": args.claude, "cli_version": cli_version(args.claude),
                "approved_by": args.approved_by, "reason": args.reason,
                "total_session_budget": args.max_sessions, "total_request_budget": args.max_requests,
                "hashes": hashes,
                "provider_quota_enforcement": "not exact; provider-side shared limits are not observable or reserved"}
    usage_root = evidence.phase_receipts(phase)
    write_once(usage_root / "live-approval.json", approved)
    return (broker.BatchGuard(max_sessions=args.max_sessions, max_requests=args.max_requests),
            usage_root / "live-usage-0001.json", approved)


def save_live_usage(path, phase, attempt_id, approval, guard):
    dump(path, {"phase": phase, "attempt_id": attempt_id, "at": now(),
                "approved_limits": {"sessions": approval["total_session_budget"],
                                    "requests": approval["total_request_budget"]},
                "actual": guard.snapshot(),
                "provider_quota_enforcement": approval["provider_quota_enforcement"]})


def command_isolation(args):
    evidence = Evidence(args.evidence)
    with live_run_lock(evidence):
        return _command_isolation_locked(args)


def _command_isolation_locked(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    evidence.require("preparation", "run prepare first")
    preparation = load(evidence.receipt("preparation"))
    aliases = {case: row["alias"] for case, row in preparation["capsules"].items()}
    fix_objects = sorted({row["first_fix"] for row in load(evidence.inputs / "preparer/case-catalog.json")["snapshots"]})
    evaluator_paths = {
        "labels": DEFINITIONS, "catalog": CATALOG, "receipt": evidence.preparation(1) / "evaluator-receipt.json",
        "depot": evidence.corpus, "fixture-depot": evidence.fixture_source, "evidence": evidence.receipts,
        "repository": REPOSITORY, "research-raw": RESEARCH_RAW,
    }
    results = {}
    scratch = evidence.root / f"scratch-isolation-{args.attempt_id}"
    for case in sorted(aliases):
        sibling = next(alias for other, alias in sorted(aliases.items()) if other != case)
        results[case] = broker.challenge_capsule(capsule_for(evidence, case), sibling=sibling,
                                                 evaluator_paths=evaluator_paths, fix_objects=fix_objects,
                                                 scratch=scratch)
        print(f"{case}: {'PASS' if results[case]['pass'] else 'FAIL'} "
              f"({sum(c['pass'] for c in results[case]['checks'])}/{len(results[case]['checks'])})")
    guard, usage_path, approval = setup_live_batch(evidence, "isolation", args)
    archive_attempt(evidence, "isolation")
    try:
        live = live_boundary_checks(evidence, args, guard)
    finally:
        save_live_usage(usage_path, "isolation", args.attempt_id, approval, guard)
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


def live_boundary_checks(evidence, args, batch_guard):
    """Real CLI launches: a capsule round trip works; inherited tools, wrong effort and leaked tokens are refused."""
    checks = []
    root = evidence.phase_sessions("isolation") / "live"
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
        if batch_guard.snapshot()["circuit"]:
            checks.append({"check": f"live:{name}", "expected_status": expected, "status": "not_run",
                           "reasons": ["global_limit_reached"], "session": None, "pass": False,
                           "tools_offered": [], "tool_calls": []})
            continue
        claude = argv_wrapper(root / "launchers", args.claude, *override) if override else args.claude
        try:
            meta = broker.run_session(root / name, model=args.model, effort=args.effort, budget=budget,
                                      system_prompt=system, user_prompt=prompt, capsule=capsule,
                                      forbidden=forbidden_tokens(evidence, capsule), claude=claude,
                                      batch_guard=batch_guard)
        except broker.BatchLimitReached:
            checks.append({"check": f"live:{name}", "expected_status": expected, "status": "not_run",
                           "reasons": ["global_limit_reached"], "session": None, "pass": False,
                           "tools_offered": [], "tool_calls": []})
            continue
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


def evaluator_session(directory, kind, *, plan, system, user, capsule, evidence, batch_guard=None):
    """Run an evaluator session with at most one prospective rerun after an execution failure."""
    attempts = []
    for attempt in (1, 2):
        path = Path(directory) / f"attempt-{attempt}"
        if (path / "meta.json").exists():
            meta = load(path / "meta.json")
        else:
            if path.exists():
                raise GateError(f"{path} is an incomplete retained attempt; resume is read-only and will not replace it")
            try:
                meta = broker.run_session(path, model=plan["model"], effort=plan["effort"], budget=BUDGETS[kind],
                                          system_prompt=system, user_prompt=user, capsule=capsule,
                                          forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"],
                                          batch_guard=batch_guard)
            except broker.BatchLimitReached:
                return None, [str(p) for p in attempts]
        attempts.append(path)
        if meta["status"] == "completed":
            value = scoring.extract_json((path / "result.txt").read_text(encoding="utf-8"))
            if value is not None:
                return value, [str(p) for p in attempts]
        if meta["status"] in ("quota_limited", "global_limit_reached"):
            return None, [str(p) for p in attempts]
    return None, [str(p) for p in attempts]


def adjudicator_prompts(evidence, capsule, anchor, concern, claimed_cost):
    standard = (evidence.inputs / "treatments/neutral-standard.txt").read_text(encoding="utf-8").strip()
    system = render("adjudicator-system.md", standard=standard)
    user = render("adjudicator-packet.md", base=capsule["base"], head=capsule["head"], anchor=anchor,
                  concern=concern, claimed_cost=claimed_cost)
    return system, user


def resolve_pair(directory, kind, *, plan, evidence, capsule, instructions, packet, first, second, schema_key,
                 batch_guard=None):
    system = render("resolver-system.md", instructions=instructions)
    user = (packet + "\n\nAssessment 1:\n\n" + fence(json.dumps(first, indent=2), "json") +
            "\n\nAssessment 2:\n\n" + fence(json.dumps(second, indent=2), "json"))
    value, attempts = evaluator_session(directory, kind, plan=plan, system=system, user=user, capsule=capsule,
                                        evidence=evidence, batch_guard=batch_guard)
    return value, attempts


def parallel(items, function, workers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, items))


def evaluator_plan(args):
    return {"model": args.model, "effort": args.effort, "claude": args.claude}


def command_adjudicate(args):
    evidence = Evidence(args.evidence)
    with live_run_lock(evidence):
        return _command_adjudicate_locked(args)


def _command_adjudicate_locked(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    evidence.require("isolation", "isolation must pass before any model session")
    definitions = load(DEFINITIONS)
    plan = evaluator_plan(args)
    if evidence.receipt("labels").exists() or evidence.receipt("controls").exists():
        raise GateError("labels or controls are already frozen")
    root = evidence.phase_sessions("adjudicate")
    guard, usage_path, approval = setup_live_batch(evidence, "adjudicate", args)

    def label_job(label):
        spec = definitions["labels"][label]
        capsule = capsule_for(evidence, spec["case"])
        system, user = adjudicator_prompts(evidence, capsule, spec["anchor"], spec["concern"], spec["claimed_cost"])
        assessments = []
        for index in (1, 2):
            value, attempts = evaluator_session(root / f"label-{label}-{index}", "adjudicator", plan=plan,
                                                system=system, user=user, capsule=capsule, evidence=evidence,
                                                batch_guard=guard)
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
                                           schema_key="decision", batch_guard=guard)
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
                                                system=system, user=user, capsule=capsule, evidence=evidence,
                                                batch_guard=guard)
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
                                           schema_key="expected_outcome", batch_guard=guard)
            record["resolver"] = {"value": value, "sessions": attempts}
            record["expected"] = "negative" if negative(value) else "unestablished"
            record["resolution"] = "disagreement resolved by independent resolver"
        print(f"control {control}: {verdicts} -> {record['expected']}")
        return record

    try:
        labels = parallel(sorted(definitions["labels"]), label_job, args.workers)
        controls = parallel(list(CONTROLS), control_job, args.workers)
    finally:
        save_live_usage(usage_path, "adjudicate", args.attempt_id, approval, guard)
    if guard.snapshot()["circuit"]:
        print(f"INCOMPLETE: adjudication stopped by {guard.snapshot()['circuit']['kind']}; labels and controls remain unfrozen")
        return
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
    pilot_gate_path = None
    if args.phase == "full":
        if not args.pilot_attempt_id:
            raise GateError("the full schedule must name the passing --pilot-attempt-id")
        pilot = Evidence(evidence.root)
        pilot.set_attempt(args.pilot_attempt_id)
        pilot_gate_path = pilot.phase_receipts("pilot") / "gate-pilot.json"
        if not pilot_gate_path.exists() or load(pilot_gate_path).get("verdict") != "PASS":
            raise GateError("the named pilot gate must PASS before the full schedule is frozen")
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
        "live_limits": {"permitted_sessions_by_default": 0, "permitted_requests_by_default": 0},
        "usage_estimate": {"scout_sessions": len(schedule), "validator_sessions_at_cap": cap,
                           "challenge_sessions": len(definitions["challenges"]) if args.phase == "pilot" else 0,
                           "evaluator_sessions_upper_bound": 3 * len({item["case"] for item in schedule}) + 1},
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
        plan["pilot_gate_attempt_id"] = args.pilot_attempt_id
        plan["pilot_gate_sha256"] = sha256_file(pilot_gate_path)
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


def run_scouts(evidence, plan, phase, batch_guard=None):
    root = evidence.phase_sessions(phase) / "scouts"

    def job(item):
        directory = root / item["run"]
        if (directory / "meta.json").exists():
            return load(directory / "meta.json")
        if directory.exists():
            raise GateError(f"{directory} exists without meta.json: an interrupted attempt; record it, do not rerun")
        capsule, system, user = scout_prompts(evidence, plan, item["case"], item["arm"])
        try:
            meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"], budget=plan["budgets"]["scout"],
                                      system_prompt=system, user_prompt=user, capsule=capsule,
                                      forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"],
                                      batch_guard=batch_guard)
        except broker.BatchLimitReached:
            return {"status": "not_run", "failure_reasons": ["global_limit_reached"]}
        print(f"scout {item['run']}: {meta['status']} {meta['duration_seconds']}s")
        return meta

    ordered = sorted(plan["schedule"], key=lambda item: item["order"])
    parallel(ordered, job, plan["workers"])


def collect_runs(evidence, plan, phase):
    runs = []
    for item in sorted(plan["schedule"], key=lambda item: item["order"]):
        directory = evidence.phase_sessions(phase) / "scouts" / item["run"]
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
    path = evidence.phase_receipts(phase) / "pool.json"
    retained = load(path) if path.exists() else None
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
    if retained is not None:
        for key in ("pool", "replays", "replay_order"):
            if retained.get(key) != value[key]:
                raise GateError(f"retained {key} does not reconcile with deterministic replay from raw scout outputs")
        return retained
    dump(path, value)
    return value


def run_replay(evidence, plan, phase, pool, batch_guard=None):
    cap = current_cap(evidence, plan, phase)
    order = pool["replay_order"]
    root = evidence.phase_sessions(phase) / "validators"
    selected = order[:cap]

    def job(replay_id):
        entry = pool["replays"][replay_id]
        directory = root / replay_id
        if (directory / "meta.json").exists():
            return
        if directory.exists():
            raise GateError(f"{directory} is an incomplete retained attempt; it will not be replaced")
        capsule, system, user = validator_prompts(evidence, entry["case"], entry["text"], replay_id)
        try:
            meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"],
                                      budget=plan["budgets"]["validator"], system_prompt=system, user_prompt=user,
                                      capsule=capsule, forbidden=forbidden_tokens(evidence, capsule), claude=plan["claude"],
                                      batch_guard=batch_guard)
        except broker.BatchLimitReached:
            return
        print(f"validator {replay_id}: {meta['status']} {meta['duration_seconds']}s")

    parallel(selected, job, plan["workers"])
    validations = collect_validations(evidence, phase, pool)
    dispositions_complete = all(validations.get(replay_id, {}).get("status") == "completed"
                                and validations[replay_id].get("disposition") in scoring.OUTCOMES
                                for replay_id in order)
    completed = sum(1 for replay_id in order if replay_id in validations)
    status = {"cap": cap, "unique_hypotheses": len(order), "replayed": len(selected),
              "replayed_sessions": completed, "unreplayed": order[cap:],
              "complete": len(order) <= cap and completed == len(order) and dispositions_complete, "at": now()}
    dump(evidence.next_phase_receipt(phase, "replay-status"), status)
    return status


def current_cap(evidence, plan, phase):
    cap = plan["validator_cap"]
    revisions = evidence.phase_receipts(phase) / "budget-revisions.jsonl"
    if revisions.exists():
        for line in revisions.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cap = json.loads(line)["validator_cap"]
    return cap


def collect_validations(evidence, phase, pool):
    validations = {}
    for replay_id in pool["replay_order"]:
        directory = evidence.phase_sessions(phase) / "validators" / replay_id
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


def run_challenges(evidence, plan, batch_guard=None):
    path = evidence.phase_receipts("pilot") / "challenges.json"
    if path.exists():
        return load(path)
    definitions = load(DEFINITIONS)
    root = evidence.phase_sessions("pilot") / "challenges"
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
            if directory.exists():
                raise GateError(f"{directory} is an incomplete retained attempt; it will not be replaced")
            try:
                meta = broker.run_session(directory, model=plan["model"], effort=plan["effort"],
                                          budget=plan["challenge_budget"]["per_session"], system_prompt=system,
                                          user_prompt=user, capsule=capsule, forbidden=forbidden_tokens(evidence, capsule),
                                          claude=plan["claude"], batch_guard=batch_guard)
            except broker.BatchLimitReached:
                return {"id": challenge["id"], "kind": challenge["kind"], "fixture": challenge["fixture"],
                        "expected": challenge["expected"], "gating": challenge.get("gating", True),
                        "status": "not_run", "disposition": None, "outcome": "execution failure",
                        "session": str(directory)}
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


def run_assessments(evidence, plan, phase, pool, batch_guard=None):
    path = evidence.phase_receipts(phase) / "assessments.json"
    if path.exists():
        return load(path)
    definitions = load(DEFINITIONS)
    instructions = (ROLES / "assessor-system.md").read_text(encoding="utf-8")
    root = evidence.phase_sessions(phase) / "assessors"
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
                                                system=instructions, user=user, capsule=None, evidence=evidence,
                                                batch_guard=batch_guard)
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
                                           second=[by_id[1].get(pid) for pid in disputed], schema_key="assessments",
                                           batch_guard=batch_guard)
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


def run_novelty(evidence, plan, phase, pool, validations, assessments, batch_guard=None):
    path = evidence.phase_receipts(phase) / "novelty.json"
    if path.exists():
        return load(path)
    root = evidence.phase_sessions(phase) / "novelty"
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
                                            capsule=capsule, evidence=evidence, batch_guard=batch_guard)
        print(f"novelty {replay_id}: {(value or {}).get('decision')}")
        return replay_id, {"decision": (value or {}).get("decision", "failed"), "value": value, "sessions": attempts,
                           "case": entry["case"]}

    value = dict(parallel(sorted(targets), job, plan["workers"]))
    dump(path, value)
    return value


def run_reasons(evidence, plan, phase, pool, validations, batch_guard=None):
    path = evidence.phase_receipts(phase) / "reasons.json"
    if path.exists():
        return load(path)
    items = [(replay_id, v) for replay_id, v in sorted(validations.items())
             if v["status"] == "completed" and v["disposition"] != "Finding"]
    if not items:
        dump(path, {})
        return {}
    texts = "\n\n".join(f"Outcome {replay_id}:\n\n" + fence(
        (Path(v["session"]) / "result.txt").read_text(encoding="utf-8"), "markdown") for replay_id, v in items)
    value, attempts = evaluator_session(evidence.phase_sessions(phase) / "reasons", "assessor", plan=plan,
                                        system=(ROLES / "reason-system.md").read_text(encoding="utf-8"),
                                        user=texts, capsule=None, evidence=evidence, batch_guard=batch_guard)
    result = {c["id"]: dict(c, sessions=attempts) for c in (value or {}).get("classifications", [])}
    dump(path, result)
    return result


@contextmanager
def live_run_lock(evidence):
    """Serialize live batches sharing an evidence root across processes."""
    evidence.root.mkdir(parents=True, exist_ok=True)
    path = evidence.root / "live-run.lock"
    handle = path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError as exc:
                raise GateError("another live batch is already using this evidence root") from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError as exc:
                raise GateError("another live batch is already using this evidence root") from exc
        yield
    finally:
        try:
            if locked and os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif locked:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def command_run(args):
    evidence = Evidence(args.evidence)
    with live_run_lock(evidence):
        return _command_run_locked(args)


def _command_run_locked(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    plan = load(evidence.receipt(f"plan-{args.phase}"))
    verify_frozen_hashes(evidence, plan)
    approval_path = evidence.phase_receipts(args.phase) / "live-approval.json"
    if not approval_path.exists():
        raise GateError("live calls are disabled by default; create an operator-approved live plan for this attempt")
    approval = load(approval_path)
    if approval.get("plan_sha256") != sha256_file(evidence.receipt(f"plan-{args.phase}")):
        raise GateError("live approval does not match the frozen plan")
    if approval.get("total_session_budget", 0) <= 0 or approval.get("total_request_budget", 0) <= 0:
        raise GateError("live approval has no positive aggregate budget")
    evidence.require("isolation", "isolation must pass")
    if args.phase == "full":
        pilot = Evidence(evidence.root)
        pilot.set_attempt(plan.get("pilot_gate_attempt_id", ""))
        pilot_gate = pilot.phase_receipts("pilot") / "gate-pilot.json"
        if not pilot_gate.exists() or load(pilot_gate).get("verdict") != "PASS":
            raise GateError("the exact pilot attempt frozen into the full plan must still PASS")
    revisions = evidence.phase_receipts(args.phase) / "budget-revisions.jsonl"
    replay_path = evidence.latest_phase_receipt(args.phase, "replay-status")
    if replay_path.exists() and not load(replay_path)["complete"]:
        cap = current_cap(evidence, plan, args.phase)
        if not revisions.exists() or cap <= load(replay_path)["cap"]:
            raise GateError("replay is incomplete at the cap; record a prospective budget revision first")
    usage_root = evidence.phase_receipts(args.phase)
    usage_root.mkdir(parents=True, exist_ok=True)
    prior_usage = sorted(usage_root.glob("live-usage-[0-9][0-9][0-9][0-9].json"))
    previous = load(prior_usage[-1])["actual"] if prior_usage else {}
    guard = broker.BatchGuard(max_sessions=approval["total_session_budget"],
                              max_requests=approval["total_request_budget"],
                              initial_sessions=previous.get("sessions_started", 0),
                              initial_requests=previous.get("requests_forwarded", 0),
                              initial_usage=previous.get("actual_usage", {}))
    usage_path = usage_root / f"live-usage-{len(prior_usage) + 1:04d}.json"
    try:
        run_scouts(evidence, plan, args.phase, guard)
        if guard.snapshot()["circuit"]:
            return
        runs = collect_runs(evidence, plan, args.phase)
        pool = build_pool(evidence, plan, args.phase, runs)
        status = run_replay(evidence, plan, args.phase, pool, guard)
        if args.phase == "pilot":
            run_challenges(evidence, plan, guard)
        if not status["complete"]:
            print(f"INCOMPLETE: validator disposition coverage is incomplete at cap {status['cap']}; "
                  "no scores or gate are written")
            return
        validations = collect_validations(evidence, args.phase, pool)
        assessments = run_assessments(evidence, plan, args.phase, pool, guard)
        if not assessments["complete"] or guard.snapshot()["circuit"]:
            print("INCOMPLETE: assessment or batch execution stopped before completion")
            return
        run_novelty(evidence, plan, args.phase, pool, validations, assessments, guard)
        if guard.snapshot()["circuit"]:
            print("INCOMPLETE: batch circuit stopped execution during novelty auditing")
            return
        run_reasons(evidence, plan, args.phase, pool, validations, guard)
        if guard.snapshot()["circuit"]:
            print("INCOMPLETE: batch circuit stopped execution during rejection classification")
            return
        command_score(args)
    finally:
        snapshot = guard.snapshot()
        dump(usage_path, {"phase": args.phase, "attempt_id": args.attempt_id, "at": now(),
                          "estimated": plan["usage_estimate"], "approved_limits": {
                              "sessions": approval["total_session_budget"],
                              "requests": approval["total_request_budget"]},
                          "actual": snapshot,
                          "provider_quota_enforcement": "not exact; provider-side shared limits are not observable or reserved"})


def command_revise_budget(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    path = evidence.phase_receipts(args.phase) / "budget-revisions.jsonl"
    replay = evidence.latest_phase_receipt(args.phase, "replay-status")
    revision = {"at": now(), "validator_cap": args.validator_cap, "reason": args.reason,
                "replay_status_before": load(replay) if replay.exists() else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(revision, sort_keys=True) + "\n")
    print(f"recorded prospective validator cap {args.validator_cap} for {args.phase}")


# ---------------------------------------------------------------- scoring and gates


def phase_data(evidence, phase):
    plan = load(evidence.receipt(f"plan-{phase}"))
    runs = collect_runs(evidence, plan, phase)
    pool = load(evidence.phase_receipts(phase) / "pool.json")
    validations = collect_validations(evidence, phase, pool)
    assessments = load(evidence.phase_receipts(phase) / "assessments.json")
    labels = load(evidence.receipt("labels"))["labels"]
    return {
        "definitions": load(DEFINITIONS), "frozen_labels": labels, "controls": list(CONTROLS),
        "runs": [{k: v for k, v in run.items() if k != "hypotheses"} for run in runs],
        "pool": pool["pool"], "validations": validations, "assessments": assessments["final"],
        "novelty": load(evidence.phase_receipts(phase) / "novelty.json"),
        "reasons": load(evidence.phase_receipts(phase) / "reasons.json"), "seed": plan["seed"],
    }


def command_score(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    plan = load(evidence.receipt(f"plan-{args.phase}"))
    verify_frozen_hashes(evidence, plan)
    result = scoring.score(phase_data(evidence, args.phase))
    result["scorer"] = {"version": scoring.SCORER_VERSION, "sha256": sha256_file(HERE / "scoring.py")}
    write_once(evidence.phase_result(args.phase, f"{args.phase}-scores.json"), result)
    print(f"scored {args.phase}: macro {result['macro']}")


def settings_signature(meta):
    observed = meta["observed_settings"]
    return {key: observed[key] for key in ("model", "effort", "tools", "max_tokens", "thinking", "context_management",
                                           "cli")} | {"budget": meta["budget"]}


def verify_frozen_hashes(evidence, plan):
    """Fail closed if a frozen plan no longer identifies the code, prompts or frozen inputs."""
    current = {"definitions": sha256_file(DEFINITIONS), "catalog": sha256_file(CATALOG),
               "calibrate": sha256_file(Path(__file__)), "broker": sha256_file(HERE / "broker.py"),
               "scoring": sha256_file(HERE / "scoring.py"),
               "capsule_server": sha256_file(HERE / "capsule_server.py"),
               "roles": {path.name: sha256_file(path) for path in sorted(ROLES.iterdir())}}
    for name in ("labels", "controls", "preparation", "treatments", "isolation"):
        receipt = evidence.receipt(name)
        current[f"{name}_receipt"] = sha256_file(receipt) if receipt.exists() else None
    if plan.get("phase") == "full":
        pilot = Evidence(evidence.root)
        attempt_id = plan.get("pilot_gate_attempt_id")
        if attempt_id:
            pilot.set_attempt(attempt_id)
            receipt = pilot.phase_receipts("pilot") / "gate-pilot.json"
        else:
            receipt = evidence.receipts / "pilot" / "gate-pilot.json"
        current["pilot_gate_receipt"] = sha256_file(receipt) if receipt.exists() else None
    differences = {key: {"frozen": plan.get("hashes", {}).get(key), "current": value}
                   for key, value in current.items()
                   if key in plan.get("hashes", {}) and plan["hashes"].get(key) != value}
    if plan.get("phase") == "full" and plan.get("pilot_gate_sha256") != current.get("pilot_gate_receipt"):
        differences["pilot_gate_receipt"] = {"frozen": plan.get("pilot_gate_sha256"),
                                              "current": current.get("pilot_gate_receipt")}
    if differences:
        raise GateError("frozen input hashes changed; do not process this plan: " + json.dumps(differences, sort_keys=True))


def live_approval_path(evidence, phase, attempt_id):
    return evidence.receipts / phase / "attempts" / attempt_id / "live-approval.json"


def command_approve_live(args):
    evidence = Evidence(args.evidence)
    evidence.set_attempt(args.attempt_id)
    plan = load(evidence.receipt(f"plan-{args.phase}"))
    verify_frozen_hashes(evidence, plan)
    if args.max_sessions <= 0 or args.max_requests <= 0:
        raise GateError("live approval must grant a positive total session and request budget")
    approval = {"phase": args.phase, "attempt_id": args.attempt_id,
                "plan_sha256": sha256_file(evidence.receipt(f"plan-{args.phase}")),
                "approved_by": args.approved_by, "reason": args.reason, "approved_at": now(),
                "total_session_budget": args.max_sessions, "total_request_budget": args.max_requests,
                "usage_estimate": plan["usage_estimate"],
                "provider_quota_enforcement": "not exact; provider-side shared limits are not observable or reserved"}
    write_once(evidence.phase_receipts(args.phase) / "live-approval.json", approval)
    print(f"approved live execution plan for {args.phase}/{args.attempt_id}: "
          f"{args.max_sessions} sessions, {args.max_requests} requests")


def all_session_metas(evidence):
    return [(path.parent, load(path)) for path in sorted(evidence.sessions.rglob("meta.json"))]


def command_gate(args):
    evidence = Evidence(args.evidence)
    phase = args.phase
    evidence.set_attempt(args.attempt_id)
    plan = load(evidence.receipt(f"plan-{phase}"))
    verify_frozen_hashes(evidence, plan)
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
    scouts = [load(evidence.phase_sessions(phase) / "scouts" / item["run"] / "meta.json")
              if (evidence.phase_sessions(phase) / "scouts" / item["run"] / "meta.json").exists() else None
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
    scoped = [evidence.sessions / "adjudication", evidence.phase_sessions(phase)]
    refused = [(str(path), meta["status"]) for path, meta in all_session_metas(evidence)
               if meta["status"] in ("leaked_context", "confinement_failure", "unexpected_context")]
    leaks = [path for path, _ in refused if any(Path(path).is_relative_to(root) for root in scoped)]
    check("no-leakage", not leaks, {"leaks": leaks, "retained_unscoped_refusals": [
        item for item in refused if item[0] not in leaks]})
    replay = load(evidence.latest_phase_receipt(phase, "replay-status"))
    pool = load(evidence.phase_receipts(phase) / "pool.json")
    validations = collect_validations(evidence, phase, pool)
    check("disposition-accounting-within-cap", replay["complete"] and replay["unique_hypotheses"] <= replay["cap"]
          and all(validations.get(r, {}).get("disposition") for r in pool["replay_order"]),
          {"cap": replay["cap"], "unique": replay["unique_hypotheses"],
           "dispositions": {r: validations.get(r, {}).get("disposition") for r in pool["replay_order"]}})
    if phase == "pilot":
        challenges = load(evidence.phase_receipts(phase) / "challenges.json")
        check("validator-conformance", challenges["verdict"] == "PASS",
              {r["id"]: r["outcome"] for r in challenges["results"]})
    assessments = load(evidence.phase_receipts(phase) / "assessments.json")
    expected_hypotheses = set(pool["pool"])
    final_assessments = assessments.get("final", {})
    matching_complete = set(final_assessments) == expected_hypotheses and all(
        isinstance(final_assessments[pid].get("matches"), list)
        and isinstance(final_assessments[pid].get("admission_qualified"), bool)
        for pid in expected_hypotheses if pid in final_assessments)
    check("assessments-complete", assessments.get("complete") and matching_complete,
          {"assessed": len(final_assessments), "expected": len(expected_hypotheses),
           "matching_complete": matching_complete})
    expected_novelty = set()
    expected_reasons = set()
    for replay_id in pool["replay_order"]:
        validation = validations.get(replay_id, {})
        items = [entry for entry in pool["pool"].values() if entry["replay"] == replay_id]
        if validation.get("status") == "completed" and validation.get("disposition") == "Finding":
            if all(not final_assessments.get(pid, {}).get("matches") for pid in
                   (pid for pid, entry in pool["pool"].items() if entry["replay"] == replay_id)):
                expected_novelty.add(replay_id)
        elif validation.get("status") == "completed" and validation.get("disposition") in scoring.OUTCOMES:
            expected_reasons.add(replay_id)
    novelty = load(evidence.phase_receipts(phase) / "novelty.json")
    novelty_complete = set(novelty) == expected_novelty and all(
        novelty[replay_id].get("decision") in ("eligible", "excluded", "uncertain")
        for replay_id in expected_novelty)
    check("novelty-audit-complete", novelty_complete,
          {"audited": sorted(novelty), "expected": sorted(expected_novelty)})
    reasons = load(evidence.phase_receipts(phase) / "reasons.json")
    reasons_complete = set(reasons) == expected_reasons and all(
        reasons[replay_id].get("reason") in scoring.REASONS and reasons[replay_id].get("explanation")
        for replay_id in expected_reasons)
    check("rejection-classification-complete", reasons_complete,
          {"classified": sorted(reasons), "expected": sorted(expected_reasons)})
    stored = load(evidence.phase_result(phase, f"{phase}-scores.json"))
    recomputed = scoring.score(phase_data(evidence, phase))
    recomputed["scorer"] = stored.get("scorer")
    emitted = sum(len(r["hypotheses"]) for r in runs if r["status"] == "completed")
    check("scorer-reconciles-to-raw-evidence", recomputed == stored and emitted == len(pool["pool"]),
          {"emitted_in_raw_outputs": emitted, "pooled": len(pool["pool"])})
    verdict = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    name = f"gate-{phase}" if phase == "pilot" else "completion-full"
    receipt = {"verdict": verdict, "at": now(), "phase": phase, "checks": checks,
               "note": "Low recall or scout false positives do not fail this operational gate."}
    write_once(evidence.phase_receipts(phase) / f"{name}.json", receipt)
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
    for name, help_text in (("isolation", "exercise access challenges and broker refusals"),
                            ("adjudicate", "independent label and control adjudication, then freeze")):
        command = common(sub.add_parser(name, help=help_text), model=True)
        command.add_argument("--attempt-id", required=True, help="unique immutable setup-attempt namespace")
        command.add_argument("--max-sessions", type=int, required=True, help="explicit total session budget")
        command.add_argument("--max-requests", type=int, required=True, help="explicit total forwarded-request budget")
        command.add_argument("--approved-by", required=True, help="operator approving this bounded live plan")
        command.add_argument("--reason", required=True, help="reason for the live setup batch")
    freeze = common(sub.add_parser("freeze", help="freeze the schedule, budgets and hashes for a phase"), model=True)
    freeze.add_argument("--phase", choices=sorted(PHASES), required=True)
    freeze.add_argument("--seed", required=True)
    freeze.add_argument("--validator-cap", type=int)
    freeze.add_argument("--pilot-attempt-id", help="passing pilot attempt required when freezing the full phase")
    for name in ("run", "score", "gate"):
        command = common(sub.add_parser(name))
        command.add_argument("--phase", choices=sorted(PHASES), required=True)
        command.add_argument("--attempt-id", required=True,
                             help="immutable phase-attempt namespace; select the same ID only to read retained outputs")
    approve = common(sub.add_parser("approve-live", help="record an explicit, bounded operator approval for live calls"))
    approve.add_argument("--phase", choices=sorted(PHASES), required=True)
    approve.add_argument("--attempt-id", required=True)
    approve.add_argument("--max-sessions", type=int, required=True)
    approve.add_argument("--max-requests", type=int, required=True)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--reason", required=True)
    revise = common(sub.add_parser("revise-budget", help="record a prospective validator cap revision"))
    revise.add_argument("--phase", choices=sorted(PHASES), required=True)
    revise.add_argument("--attempt-id", required=True)
    revise.add_argument("--validator-cap", type=int, required=True)
    revise.add_argument("--reason", required=True)
    common(sub.add_parser("manifest", help="write the evidence integrity manifest"))
    note = common(sub.add_parser("note", help="record a failed attempt or prospective correction"))
    note.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    handlers = {"prepare": command_prepare, "isolation": command_isolation, "adjudicate": command_adjudicate,
                "freeze": command_freeze, "run": command_run, "score": command_score, "gate": command_gate,
                "approve-live": command_approve_live,
                "revise-budget": command_revise_budget, "manifest": command_manifest,
                "note": command_note}
    handlers[args.command](args)


if __name__ == "__main__":
    main()
