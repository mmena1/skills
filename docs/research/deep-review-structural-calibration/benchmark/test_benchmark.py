"""Offline tests of the real benchmark interfaces. No model is called.

A fake upstream stands in for the Anthropic API and a fake CLI stands in for `claude`;
the proxy, jail, capsule service, preparer, scheduler and scorer are the real ones.
"""

import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import broker  # noqa: E402
import calibrate  # noqa: E402
import capsule_server  # noqa: E402
import scoring  # noqa: E402

BUDGET = {"timeout_seconds": 20, "max_requests": 5, "max_context_tokens": 10000, "max_output_tokens": 500}
HAS_BWRAP = shutil.which("bwrap") is not None and subprocess.run(
    ["bwrap", "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64",
     "/lib64", "/usr/bin/true"], capture_output=True).returncode == 0
TREATMENTS_AVAILABLE = all(subprocess.run(["git", "-C", str(calibrate.REPOSITORY), "cat-file", "-e", sha + "^{commit}"],
                                          capture_output=True).returncode == 0
                           for sha in ("b3a568ec926abc17326213dfb3bd00a48feb256a",
                                       "5e61f1a0494701f4844c04351235fa77714d9c4e"))

FAKE_CLI = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time, urllib.error, urllib.request
args = sys.argv[1:]
if args == ["--version"]:
    print("0.0.0 (fake)")
    sys.exit(0)
def option(name):
    return args[args.index(name) + 1] if name in args else None
mode = os.environ.get("FAKE_MODE", "reply")
prompt = sys.stdin.read()
system = open(option("--system-prompt-file")).read()
tools = []
servers = []
if option("--mcp-config"):
    tools = [{"name": "mcp__capsule__" + n, "description": "", "input_schema": {"type": "object"}}
             for n in ("list_files", "read_file", "search", "git")]
    servers = [{"name": "capsule", "status": "connected"}]
    config = json.load(open(option("--mcp-config")))["mcpServers"]["capsule"]
    server = subprocess.Popen([config["command"], *config["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for message in ({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_files", "arguments": {}}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "../x"}}}):
        server.stdin.write(json.dumps(message) + "\n"); server.stdin.flush(); server.stdout.readline()
    server.stdin.close(); server.wait()
if option("--tools"):
    tools.append({"name": option("--tools"), "description": "", "input_schema": {"type": "object"}})
print(json.dumps({"type": "system", "subtype": "init", "tools": [t["name"] for t in tools], "mcp_servers": servers,
                  "model": option("--model"), "claude_code_version": "fake"}), flush=True)
if mode == "timeout":
    time.sleep(120)
model = "substituted-model" if mode == "model" else option("--model")
extra = os.environ.get("FAKE_INJECT")
content = [{"type": "text", "text": prompt}] + ([{"type": "text", "text": extra}] if extra else [])
body = {"model": model, "max_tokens": 1000, "system": [{"type": "text", "text": system}],
        "messages": [{"role": "user", "content": content}], "tools": tools,
        "output_config": {"effort": option("--effort")}, "thinking": {"type": "adaptive"}, "stream": True}
reply = os.environ.get("FAKE_REPLY", "No hypotheses")
if mode == "roles":
    import re
    if system.startswith("You are the structural reviewer"):
        reply = ("### Hypothesis structural-H1\n- **Origin:** structural\n- **Title:** Cost\n- **File/line:** a.py:1\n"
                 "- **Potential severity:** low\n- **Source evidence:** evidence and alternative\n"
                 "- **Expected impact:** task, cost and mechanism\n- **Falsification condition:** f\n"
                 "- **Suggested validation:** v\n- **Context references:** none")
    elif system.startswith("You are the independent validator"):
        reply = "### Disproved\n- **Hypothesis:** H\n- **File/line:** a.py:1\n- **Evidence:** preference only"
    elif system.startswith("You are an independent assessor") or system.startswith("You resolve"):
        ids = sorted(set(re.findall(r"### Hypothesis (H-[0-9a-f]+)", prompt)))
        reply = "```json\n" + json.dumps({"assessments": [{"id": i, "admission_qualified": True, "admission_gaps": [],
                 "schema_problems": [], "structural": True, "matches": []} for i in ids]}) + "\n```"
    elif system.startswith("You classify"):
        ids = sorted(set(re.findall(r"Outcome (R-[0-9a-f]+)", prompt)))
        reply = "```json\n" + json.dumps({"classifications": [{"id": i, "reason": "preference", "explanation": "x"}
                 for i in ids]}) + "\n```"
    else:
        reply = "```json\n" + json.dumps({"decision": "eligible"}) + "\n```"
for turn in range(int(os.environ.get("FAKE_TURNS", "1"))):
    request = urllib.request.Request(os.environ["ANTHROPIC_BASE_URL"] + "/v1/messages", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json", "User-Agent": "fake-cli/1"})
    try:
        urllib.request.urlopen(request).read()
    except urllib.error.HTTPError as error:
        print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": ""}))
        sys.exit(1)
stop = "max_tokens" if mode == "truncate" else "end_turn"
print(json.dumps({"type": "assistant", "message": {"stop_reason": stop, "content": [{"type": "text", "text": reply}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": mode == "error", "result": reply,
                  "stop_reason": stop, "num_turns": 1, "total_cost_usd": 0.0}))
'''


class FakeUpstream:
    """Serves streaming /v1/messages responses that echo the requested model."""

    def __init__(self, output_tokens=50, input_tokens=100, status=200, error_type=None):
        upstream = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if upstream.status != 200:
                    payload = json.dumps({"type": "error", "error": {"type": upstream.error_type or "api_error",
                                                                          "message": "retained fake failure"}}).encode()
                    self.send_response(upstream.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                events = [
                    {"type": "message_start", "message": {"model": body["model"], "usage": {
                        "input_tokens": upstream.input_tokens, "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0, "output_tokens": 1}}},
                    {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                     "usage": {"output_tokens": upstream.output_tokens}},
                ]
                data = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.output_tokens = output_tokens
        self.input_tokens = input_tokens
        self.status = status
        self.error_type = error_type
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.address = ("http", "127.0.0.1", self.server.server_address[1])

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def git(*arguments, cwd=None):
    return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, check=True,
                          env=dict(os.environ, **calibrate.FIXED_ENV)).stdout.decode().strip()


def make_capsule(root, files_base, files_head):
    repository = Path(root) / "capsules" / "alias0001" / "repository"
    repository.mkdir(parents=True)
    git("init", "--quiet", "--template=", cwd=repository)
    shas = []
    for files in (files_base, files_head):
        for path in repository.iterdir():
            if path.name != ".git":
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        for name, text in files.items():
            (repository / name).parent.mkdir(parents=True, exist_ok=True)
            (repository / name).write_text(text)
        git("add", "--all", cwd=repository)
        tree = git("write-tree", cwd=repository)
        commit = subprocess.run(["git", "commit-tree", tree, *(["-p", shas[-1]] if shas else [])], cwd=repository,
                                input=b"Snapshot\n", capture_output=True, check=True,
                                env=dict(os.environ, **calibrate.FIXED_ENV)).stdout.decode().strip()
        shas.append(commit)
    git("update-ref", "refs/heads/review", shas[1], cwd=repository)
    git("symbolic-ref", "HEAD", "refs/heads/review", cwd=repository)
    (Path(root) / "capsules" / "alias0002" / "repository").mkdir(parents=True)
    (Path(root) / "capsules" / "alias0002" / "repository" / "SIBLING.txt").write_text("sibling answer\n")
    return {"repository": repository, "base": shas[0], "head": shas[1]}


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.capsule = make_capsule(self.root, {"README.md": "# demo\n", "app.py": "VALUE = 1\n"},
                                    {"README.md": "# demo\n", "app.py": "VALUE = 2\n", "new.py": "def f():\n    return 1\n"})
        self.evaluator = self.root / "evaluator"
        self.evaluator.mkdir()
        (self.evaluator / "labels.json").write_text('{"S99": "secret label"}\n')
        self.fake = self.root / "fake-claude"
        self.fake.write_text(FAKE_CLI)
        self.fake.chmod(0o755)

    def upstream(self, **settings):
        upstream = FakeUpstream(**settings)
        self.addCleanup(upstream.close)
        return upstream

    def session(self, name="session", mode="reply", reply="No hypotheses", capsule="default", budget=None,
                inject=None, turns=1, forbidden=(), upstream=None):
        upstream = upstream or self.upstream()
        environment = {"FAKE_MODE": mode, "FAKE_REPLY": reply, "FAKE_TURNS": str(turns)}
        if inject:
            environment["FAKE_INJECT"] = inject
        return broker.run_session(self.root / "sessions" / name, model="model-x", effort="high",
                                  budget=budget or BUDGET, system_prompt="contract", user_prompt="packet",
                                  capsule=self.capsule if capsule == "default" else capsule,
                                  forbidden=forbidden, claude=str(self.fake), upstream=upstream.address,
                                  extra_env=environment)


@unittest.skipUnless(HAS_BWRAP, "bubblewrap user namespaces unavailable")
class ConfinementTests(Workspace):
    def challenge(self):
        return broker.challenge_capsule(
            self.capsule, sibling="alias0002",
            evaluator_paths={"labels": self.evaluator / "labels.json", "depot": self.evaluator,
                             "evidence": self.evaluator},
            fix_objects=["d0c3579209615563c826b4acd0651daec7d56b60"], scratch=self.root / "scratch")

    def test_real_launch_permits_capsule_reads_and_denies_every_leak_path(self):
        result = self.challenge()
        failed = [check for check in result["checks"] if not check["pass"]]
        self.assertEqual(failed, [])
        names = {check["check"] for check in result["checks"]}
        for required in ("allow:read_file", "allow:diff", "deny:label-file-absolute", "deny:sibling-capsule",
                         "deny:parent-traversal-list", "deny:credentials-absolute", "deny:original-fix-show",
                         "deny:alternate-ref", "deny:other-repository", "deny:network-command",
                         "jail:read:labels", "jail:read:sibling", "jail:read:credentials", "jail:network:tcp",
                         "jail:network:dns", "jail:git:other-refs", "jail:environment:credentials"):
            self.assertIn(required, names)
        self.assertTrue(result["pass"])

    def test_leaky_mount_fails_closed(self):
        original = broker.jail_command

        def leaky(repository, log_dir, command, extra_binds=()):
            return original(repository, log_dir, command,
                            extra_binds=[*extra_binds, (self.evaluator, str(self.evaluator))])

        with mock.patch.object(broker, "jail_command", leaky):
            result = self.challenge()
        self.assertFalse(result["pass"])
        leaked = {check["check"] for check in result["checks"] if not check["pass"]}
        self.assertIn("jail:read:labels", leaked)

    def test_session_tool_calls_run_inside_the_jail_and_are_logged(self):
        meta = self.session()
        self.assertEqual(meta["status"], "completed")
        statuses = [(call["tool"], call["status"]) for call in meta["tool_calls"]]
        self.assertEqual(statuses, [("list_files", "ok"), ("read_file", "denied")])


class CapsuleServerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        capsule = make_capsule(temporary.name, {"a.py": "x = 1\n"}, {"a.py": "x = 2\n", "pkg/b.py": "y = 1\n"})
        self.capsule = capsule_server.Capsule(capsule["repository"], capsule["base"], capsule["head"], None)
        self.base, self.head = capsule["base"], capsule["head"]

    def call(self, name, **arguments):
        text, error, record = self.capsule.call(name, arguments)
        return text, error

    def test_permitted_reads(self):
        self.assertEqual(self.call("list_files")[0].splitlines(), ["a.py", "pkg/b.py"])
        self.assertIn("x = 2", self.call("read_file", path="a.py")[0])
        self.assertIn("-x = 1", self.call("git", args=["diff", self.base, self.head])[0])
        self.assertIn("x = 1", self.call("git", args=["show", f"{self.base[:12]}:a.py"])[0])
        self.assertFalse(self.call("git", args=["log", "--oneline", "-n", "5", f"{self.base}..{self.head}"])[1])

    def test_denials(self):
        for name, arguments in [
            ("read_file", {"path": "../a.py"}), ("read_file", {"path": "/etc/passwd"}),
            ("read_file", {"path": ".git/HEAD"}), ("list_files", {"path": "../.."}),
            ("git", {"args": ["log", "--all"]}), ("git", {"args": ["show", "main"]}),
            ("git", {"args": ["-C", "/", "log"]}), ("git", {"args": ["diff", "--output=/tmp/x", self.base]}),
            ("git", {"args": ["fetch", "origin"]}), ("git", {"args": ["show", f"{self.head}:../x"]}),
            ("unknown", {}),
        ]:
            with self.subTest(name=name, arguments=arguments):
                self.assertTrue(self.call(name, **arguments)[1])


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.log = Path(temporary.name) / "api.jsonl"

    def proxy(self, **overrides):
        settings = dict(model="model-x", effort="high", budget=BUDGET, allowed_tools=broker.ALLOWED_TOOLS,
                        forbidden=["secret-token"], upstream=self.upstream.address)
        settings.update(overrides)
        proxy = broker.Proxy(self.log, **settings)
        proxy.expected_texts = ["contract", "packet"]
        return proxy

    def post(self, proxy, **changes):
        import urllib.error
        import urllib.request
        body = {"model": "model-x", "output_config": {"effort": "high"}, "system": [{"type": "text", "text": "contract"}],
                "messages": [{"role": "user", "content": [{"type": "text", "text": "packet"}]}],
                "tools": [{"name": name} for name in broker.ALLOWED_TOOLS], "stream": True}
        body.update(changes)
        request = urllib.request.Request(proxy.url + "/v1/messages", data=json.dumps(body).encode(),
                                         headers={"content-type": "application/json", "authorization": "Bearer s3cret"})
        try:
            return urllib.request.urlopen(request).status
        except urllib.error.HTTPError as error:
            return error.code

    def test_permitted_request_is_forwarded_accounted_and_redacted(self):
        with self.proxy() as proxy:
            self.assertEqual(self.post(proxy), 200)
        self.assertEqual(proxy.state["violations"], [])
        self.assertEqual(proxy.state["output_tokens"], 50)
        self.assertEqual(proxy.state["peak_context_tokens"], 150)
        self.assertNotIn("s3cret", self.log.read_text())

    def test_refusals_fail_closed(self):
        cases = {
            "confinement": {"tools": [{"name": "WebFetch"}]},
            "model_mismatch": {"model": "other"},
            "effort_mismatch": {"output_config": {"effort": "low"}},
            "leaked_context": {"messages": [{"role": "user", "content": [{"type": "text", "text": "packet"},
                                                                         {"type": "text", "text": "secret-token"}]}]},
            "unexpected_context": {"system": [{"type": "text", "text": "contract"},
                                              {"type": "text", "text": "# Memory\nremembered answer"}]},
        }
        for kind, change in cases.items():
            with self.subTest(kind=kind), self.proxy() as proxy:
                self.assertEqual(self.post(proxy, **change), 403)
                self.assertIn(kind, [v["kind"] for v in proxy.state["violations"]])
                self.assertEqual(proxy.state["requests"], 0)
        with self.proxy() as proxy:
            self.assertEqual(self.post(proxy, mcp_servers=[{"url": "https://x"}]), 403)

    def test_budget_exhaustion_refuses_further_requests(self):
        with self.proxy(budget=dict(BUDGET, max_output_tokens=60)) as proxy:
            self.assertEqual(self.post(proxy), 200)
            self.assertEqual(self.post(proxy), 200)
            self.assertEqual(self.post(proxy), 403)
        self.assertIn("budget_exhausted", [v["kind"] for v in proxy.state["violations"]])

    def test_http_429_opens_batch_circuit_and_blocks_retry_requests(self):
        limited = FakeUpstream(status=429, error_type="rate_limit_error")
        self.addCleanup(limited.close)
        guard = broker.BatchGuard(max_sessions=4, max_requests=12)
        with self.proxy(upstream=limited.address, batch_guard=guard) as proxy:
            self.assertEqual(self.post(proxy), 429)
            self.assertEqual(self.post(proxy), 403)
        self.assertEqual(proxy.state["requests"], 1)
        self.assertEqual(guard.snapshot()["requests_forwarded"], 1)
        self.assertEqual(guard.snapshot()["circuit"]["kind"], "quota_limited")
        self.assertFalse(guard.start_session())

    def test_account_limit_payload_opens_batch_circuit_without_429(self):
        limited = FakeUpstream(status=200, error_type="usage_limit_reached")
        self.addCleanup(limited.close)
        self.assertEqual(broker.Proxy.quota_error(
            json.dumps({"error": {"type": "usage_limit_reached", "message": "daily quota"}}), 200),
            "usage_limit_reached daily quota")


class ExecutionTests(Workspace):
    def run_case(self, **arguments):
        if not HAS_BWRAP:
            arguments.setdefault("capsule", None)
        return self.session(**arguments)

    def test_clean_zero_is_completed(self):
        meta = self.run_case(name="zero")
        self.assertEqual(meta["status"], "completed")
        self.assertEqual(scoring.parse_scout(Path(self.root / "sessions/zero/result.txt").read_text())["kind"], "zero")
        self.assertEqual(meta["observed_settings"]["model"], ["model-x"])
        self.assertEqual(meta["observed_settings"]["effort"], ["high"])

    def test_execution_failures_are_not_semantic_zero(self):
        expectations = {
            "timeout": dict(mode="timeout", budget=dict(BUDGET, timeout_seconds=3)),
            "api_error": dict(mode="error"),
            "truncation": dict(mode="truncate"),
            "model_mismatch": dict(mode="model"),
            "budget_exhausted": dict(turns=3, budget=dict(BUDGET, max_output_tokens=60)),
            "leaked_context": dict(inject="secret-token", forbidden=["secret-token"]),
            "unexpected_context": dict(inject="<system-reminder>skills are available</system-reminder>"),
        }
        for status, arguments in expectations.items():
            with self.subTest(status=status):
                meta = self.run_case(name=status, **arguments)
                self.assertEqual(meta["status"], status)

    def test_mismatched_resolved_settings_fail_the_pair(self):
        first = self.run_case(name="first")
        second = self.run_case(name="second", budget=dict(BUDGET, max_requests=6))
        self.assertNotEqual(calibrate.settings_signature(first), calibrate.settings_signature(second))
        third = self.run_case(name="third")
        self.assertEqual(calibrate.settings_signature(first), calibrate.settings_signature(third))


class ScheduleTests(unittest.TestCase):
    def test_schedule_is_deterministic_complete_and_seed_dependent(self):
        first, arms = calibrate.make_schedule("full", "seed-1")
        again, _ = calibrate.make_schedule("full", "seed-1")
        other, _ = calibrate.make_schedule("full", "seed-2")
        self.assertEqual(first, again)
        self.assertNotEqual([i["run"] for i in first], [i["run"] for i in other])
        self.assertEqual(len(first), 60)
        self.assertEqual(len({i["run"] for i in first}), 60)
        self.assertEqual(len(arms), 30)
        pilot, _ = calibrate.make_schedule("pilot", "seed-1")
        self.assertEqual(sorted({(i["case"], i["arm"]) for i in pilot}),
                         sorted((c, a) for c in ("M91", "M94", "N1", "N2") for a in "AB"))


class PreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.evidence = calibrate.Evidence(Path(temporary.name) / "evidence")

    def test_fixture_sources_are_deterministic(self):
        definitions = calibrate.load(calibrate.DEFINITIONS)
        first = calibrate.build_fixture_source(self.evidence, definitions)
        second = calibrate.build_fixture_source(self.evidence, definitions)
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), ["C1", "N1", "N2", "N3", "N4", "N5"])

    @unittest.skipUnless(TREATMENTS_AVAILABLE, "treatment commits unavailable in this checkout")
    def test_control_capsules_reproduce_and_exclude_evaluator_objects(self):
        verdict, capsules, identical = calibrate.prepare(self.evidence, [], "test-seed", snapshots=[])
        self.assertEqual(verdict, "PASS")
        self.assertTrue(identical)
        self.assertEqual(sorted(capsules), ["C1", "N1", "N2", "N3", "N4", "N5"])
        definitions = calibrate.load(calibrate.DEFINITIONS)
        secrets = [spec["design"][:40] for spec in definitions["controls"].values()]
        for case, row in capsules.items():
            repository = self.evidence.preparation(1) / "capsules" / row["alias"] / "repository"
            self.assertNotIn(case, row["alias"])
            names = subprocess.run(["git", "-C", str(repository), "ls-tree", "-r", "--name-only", "HEAD"],
                                   capture_output=True, text=True).stdout
            self.assertNotIn("EVALUATOR_EXPECTATION", names)
            text = "".join(p.read_text() for p in repository.rglob("*") if p.is_file() and ".git" not in p.parts)
            for secret in secrets + ["N1", "N2", "control", "negative", "expected outcome"]:
                self.assertNotIn(secret, text)
            capsule = calibrate.capsule_for(self.evidence, case)
            _, system, user = calibrate.scout_prompts(self.evidence, {}, case, "B")
            for leaked in ["N1", "N2", "N3", "N4", "N5", "C1", "negative control", row["alias"]] + secrets:
                self.assertNotIn(leaked, system + user.split("````diff")[0])
            self.assertIn(capsule["head"], user)
        _, system_a, _ = calibrate.scout_prompts(self.evidence, {}, "N1", "A")
        _, system_b, _ = calibrate.scout_prompts(self.evidence, {}, "N1", "B")
        self.assertIn("codebase-design/SKILL.md", system_a)
        self.assertNotIn("codebase-design/SKILL.md", system_b)


@unittest.skipUnless(HAS_BWRAP and TREATMENTS_AVAILABLE, "needs bubblewrap and the treatment commits")
class PilotPipelineTests(unittest.TestCase):
    """The real pilot runner, cap exhaustion, budget revision, scorer and gate, with a role-aware fake model."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.fake = root / "fake-claude"
        self.fake.write_text(FAKE_CLI)
        self.fake.chmod(0o755)
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        self.evidence = calibrate.Evidence(root / "evidence")
        self.attempt_id = "offline-test"
        calibrate.prepare(self.evidence, [], "pipeline-seed", snapshots=[])
        capsules = {case: {"pass": True} for case in ("N1", "N2", "C1")}
        calibrate.dump(self.evidence.receipt("isolation"), {"verdict": "PASS", "capsules": capsules, "live": []})
        definitions = calibrate.load(calibrate.DEFINITIONS)
        labels = {label: {"decision": "eligible"} for label in definitions["labels"]}
        calibrate.dump(self.evidence.receipt("labels"), {"verdict": "PASS", "frozen_at": calibrate.now(), "labels": labels})
        calibrate.dump(self.evidence.receipt("controls"), {"verdict": "PASS", "frozen_at": calibrate.now()})
        patches = [
            mock.patch.dict(calibrate.PHASES, {"pilot": {"cases": ["N1", "N2"], "repetitions": 1, "validator_cap": 1}}),
            mock.patch.object(broker, "UPSTREAM", self.upstream.address),
            mock.patch.dict(os.environ, {"FAKE_MODE": "roles"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def cli(self, *arguments):
        calibrate.main([arguments[0], "--evidence", str(self.evidence.root), *arguments[1:]])

    def test_cap_exhaustion_blocks_until_prospective_revision_then_gate_passes(self):
        original = broker.run_session

        def with_mode(*args, **kwargs):
            kwargs["extra_env"] = {"FAKE_MODE": "roles"}
            return original(*args, **kwargs)

        with mock.patch.object(broker, "run_session", with_mode):
            self.cli("freeze", "--phase", "pilot", "--seed", "s", "--model", "model-x", "--effort", "high",
                     "--claude", str(self.fake), "--workers", "2")
            plan = calibrate.load(self.evidence.receipt("plan-pilot"))
            self.assertEqual(plan["live_limits"], {"permitted_sessions_by_default": 0,
                                                  "permitted_requests_by_default": 0})
            with self.assertRaises(SystemExit):
                self.cli("run", "--phase", "pilot", "--attempt-id", self.attempt_id)
            self.assertFalse((self.evidence.sessions / "pilot/attempts" / self.attempt_id).exists())
            self.cli("approve-live", "--phase", "pilot", "--attempt-id", self.attempt_id,
                     "--max-sessions", "100", "--max-requests", "1000", "--approved-by", "offline-test",
                     "--reason", "fake backend only")
            self.cli("run", "--phase", "pilot", "--attempt-id", self.attempt_id)
            receipt_root = self.evidence.receipts / "pilot/attempts" / self.attempt_id
            session_root = self.evidence.sessions / "pilot/attempts" / self.attempt_id
            replay = calibrate.load(receipt_root / "replay-status-0001.json")
            self.assertFalse(replay["complete"])
            self.assertEqual((replay["unique_hypotheses"], replay["replayed"]), (2, 1))
            self.assertFalse((receipt_root / "assessments.json").exists())
            with self.assertRaises(SystemExit):
                self.cli("run", "--phase", "pilot", "--attempt-id", self.attempt_id)
            self.cli("revise-budget", "--phase", "pilot", "--attempt-id", self.attempt_id,
                     "--validator-cap", "4", "--reason", "prospective test revision")
            self.cli("run", "--phase", "pilot", "--attempt-id", self.attempt_id)
            self.cli("gate", "--phase", "pilot", "--attempt-id", self.attempt_id)
        gate = calibrate.load(receipt_root / "gate-pilot.json")
        self.assertEqual(gate["verdict"], "PASS", [c for c in gate["checks"] if not c["pass"]])
        scores = calibrate.load(self.evidence.results / "pilot/attempts" / self.attempt_id / "pilot-scores.json")
        self.assertEqual(scores["admission"]["A"]["raw_emissions"], 2)
        self.assertEqual(scores["controls"]["B"]["control_admission_rate"], 1.0)
        self.assertEqual(scores["controls"]["B"]["validated_findings"], 0)
        challenges = calibrate.load(receipt_root / "challenges.json")
        usage = calibrate.load(receipt_root / "live-usage-0002.json")
        self.assertIn("actual", usage)
        self.assertIn("estimated", usage)
        self.assertIn("provider-side shared limits are not observable", usage["provider_quota_enforcement"])
        self.assertEqual(challenges["verdict"], "PASS")
        self.assertEqual({r["id"]: r["outcome"] for r in challenges["results"]}["Z1"], "deviation")
        pool = calibrate.load(receipt_root / "pool.json")
        for entry in pool["replays"].values():
            self.assertNotIn("structural-H1", entry["text"])
        for directory in (session_root / "validators").iterdir():
            prompt = (directory / "user.txt").read_text() + (directory / "system.txt").read_text()
            for secret in ("pilot-N", "-A", "-B", "arm", "treatment", "N1", "N2"):
                self.assertNotIn(secret, prompt)


class GateTests(unittest.TestCase):
    def test_full_freeze_requires_a_passing_pilot_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = calibrate.Evidence(Path(temporary) / "evidence")
            for name in ("preparation", "treatments", "isolation", "labels", "controls"):
                calibrate.dump(evidence.receipt(name), {"verdict": "PASS", "frozen_at": calibrate.now()})
            arguments = ["freeze", "--evidence", str(evidence.root), "--phase", "full", "--seed", "s",
                         "--model", "m", "--effort", "high", "--validator-cap", "10",
                         "--pilot-attempt-id", "pilot-a"]
            with self.assertRaises(SystemExit) as stopped:
                calibrate.main(arguments)
            self.assertIn("pilot gate", str(stopped.exception))
            calibrate.dump(evidence.receipt("gate-pilot"), {"verdict": "PASS"})
            pilot = calibrate.Evidence(evidence.root)
            pilot.set_attempt("pilot-a")
            calibrate.dump(pilot.phase_receipts("pilot") / "gate-pilot.json", {"verdict": "FAIL"})
            with self.assertRaises(SystemExit):
                calibrate.main(arguments)
            calibrate.dump(pilot.phase_receipts("pilot") / "gate-pilot.json", {"verdict": "PASS"})
            calibrate.main(arguments)
            plan = calibrate.load(evidence.receipt("plan-full"))
            self.assertEqual(plan["pilot_gate_attempt_id"], "pilot-a")
            calibrate.verify_frozen_hashes(evidence, plan)
            calibrate.dump(pilot.phase_receipts("pilot") / "gate-pilot.json", {"verdict": "FAIL"})
            with self.assertRaisesRegex(calibrate.GateError, "pilot_gate_receipt"):
                calibrate.verify_frozen_hashes(evidence, plan)

    def test_evidence_inside_repository_is_rejected(self):
        with self.assertRaises(SystemExit):
            calibrate.Evidence(calibrate.REPOSITORY / ".scratch" / "evidence")


def hypothesis_block(local, title="Cost"):
    fields = "\n".join(f"- **{name}:** {title} {name}" for name in scoring.FIELDS)
    return f"### Hypothesis {local}\n{fields}"


class ParsingTests(unittest.TestCase):
    def test_scout_output_kinds(self):
        self.assertEqual(scoring.parse_scout("No hypotheses")["kind"], "zero")
        self.assertEqual(scoring.parse_scout("**No hypotheses.**")["kind"], "zero")
        self.assertEqual(scoring.parse_scout("No hypotheses. I could not finish the review.")["kind"], "unusable")
        self.assertEqual(scoring.parse_scout("Interrupted after writing: No hypotheses")["kind"], "unusable")
        self.assertEqual(scoring.parse_scout("I looked around.")["kind"], "unusable")
        self.assertEqual(scoring.parse_scout("")["kind"], "unusable")
        parsed = scoring.parse_scout(hypothesis_block("structural-H1") + "\n\n### Hypothesis structural-H2\n- **Title:** x")
        self.assertEqual(parsed["kind"], "hypotheses")
        self.assertEqual(parsed["hypotheses"][0]["missing"], [])
        self.assertIn("Source evidence", parsed["hypotheses"][1]["missing"])
        schema_only = scoring.parse_scout("### Hypothesis H1\n- **Origin:** structural")
        self.assertEqual(schema_only["kind"], "unusable")
        self.assertIn("no complete hypothesis schema", schema_only["schema_violations"])
        replay = scoring.replay_text(parsed["hypotheses"][0], "R-1")
        self.assertTrue(replay.startswith("### Hypothesis R-1\n"))
        self.assertNotIn("structural-H1", replay)

    def test_validator_outcome(self):
        self.assertEqual(scoring.parse_validator("### Disproved\n- **Evidence:** x"), "Disproved")
        self.assertEqual(scoring.parse_validator("### Needs probe\n- x"), "Needs probe")
        self.assertEqual(scoring.parse_validator("**Finding**\n- **Evidence:** x"), "Finding")
        self.assertEqual(scoring.parse_validator("**Finding: one owner is split, low cost.**\n- x"), "Finding")
        self.assertEqual(scoring.parse_validator("Disproved: the alternative changes behavior.\n- x"), "Disproved")
        self.assertEqual(scoring.parse_validator("**Finding**: evidence supports the concern.\n- x"), "Finding")
        self.assertEqual(scoring.parse_validator("Checked it.\n\n### Disproved\n- x"), "Disproved")
        self.assertIsNone(scoring.parse_validator("**Findings** are below"))
        self.assertIsNone(scoring.parse_validator("**Finding**\n...\n**Disproved**"))
        self.assertIsNone(scoring.parse_validator("### Finding\n...\n### Disproved\n..."))
        self.assertIsNone(scoring.parse_validator("I think it is fine."))
        self.assertIsNone(scoring.parse_validator("The word Finding appears in this explanation."))

    def test_extract_json(self):
        self.assertEqual(scoring.extract_json('text\n```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(scoring.extract_json("no json"))


class ScoringTests(unittest.TestCase):
    def data(self):
        definitions = {
            "label_classes": {"fixed": ["S1", "S2", "S3"], "provisional": ["S4"], "auxiliary": ["S5"]},
            "labels": {"S1": {"case": "M1"}, "S2": {"case": "M1"}, "S3": {"case": "M2"}, "S4": {"case": "M1"},
                       "S5": {"case": "M1"}},
        }
        frozen = {"S1": {"decision": "eligible"}, "S2": {"decision": "eligible"}, "S3": {"decision": "excluded"},
                  "S4": {"decision": "eligible"}, "S5": {"decision": "eligible"}}
        runs = []
        for case in ("M1", "M2", "N1"):
            for arm in ("A", "B"):
                runs.append({"run": f"{case}-{arm}", "case": case, "arm": arm, "repetition": 1,
                             "status": "completed", "parse_kind": "hypotheses", "schema_violations": []})
        runs[1]["status"] = "timeout"  # M1-B failed
        runs[2]["parse_kind"] = "zero"  # M2-A clean zero
        pool = {
            "h1": {"run": "M1-A", "case": "M1", "missing": [], "replay": "r1"},
            "h2": {"run": "M1-A", "case": "M1", "missing": [], "replay": "r2"},
            "h3": {"run": "M1-A", "case": "M1", "missing": ["Title"], "replay": "r3"},
            "h4": {"run": "M2-B", "case": "M2", "missing": [], "replay": "r4"},
            "h5": {"run": "N1-B", "case": "N1", "missing": [], "replay": "r5"},
        }
        validations = {"r1": {"status": "completed", "disposition": "Finding"},
                       "r2": {"status": "completed", "disposition": "Disproved"},
                       "r3": {"status": "completed", "disposition": "Unresolved"},
                       "r4": {"status": "completed", "disposition": "Finding"},
                       "r5": {"status": "completed", "disposition": "Disproved"}}
        assessments = {
            # One broad hypothesis matches two labels without independent statements: one credit.
            "h1": {"admission_qualified": True, "matches": [{"label": "S1", "independent_statement": False},
                                                            {"label": "S2", "independent_statement": False}]},
            # A duplicate of S1 counts once; S4 is provisional and reported separately.
            "h2": {"admission_qualified": True, "matches": [{"label": "S1", "independent_statement": False},
                                                            {"label": "S4", "independent_statement": False}]},
            "h3": {"admission_qualified": False, "matches": []},
            "h4": {"admission_qualified": True, "matches": []},
            "h5": {"admission_qualified": True, "matches": []},
        }
        return {"definitions": definitions, "frozen_labels": frozen, "controls": ["N1"], "runs": runs, "pool": pool,
                "validations": validations, "assessments": assessments, "novelty": {"r4": {"decision": "eligible"}},
                "reasons": {"r5": {"reason": "preference"}}, "seed": "s"}

    def test_denominators_credits_and_failures(self):
        result = scoring.score(self.data())
        rows = {row["run"]: row for row in result["runs"]}
        self.assertEqual(rows["M1-A"]["eligible_scout_matched"], ["S1"])
        self.assertEqual(rows["M1-A"]["eligible_scout_recall"], 0.5)
        self.assertEqual(rows["M1-A"]["provisional_scout_matched"], ["S4"])
        self.assertEqual(rows["M1-A"]["eligible_validated_matched"], ["S1"])
        self.assertIsNone(rows["M1-B"]["eligible_scout_recall"])
        self.assertEqual(rows["M2-A"]["eligible_scout_recall"], "N/A")
        self.assertTrue(rows["M2-A"]["clean_zero"])
        self.assertEqual(rows["M1-A"]["partial_hypotheses"], 1)
        case = {c["case"]: c for c in result["cases"]}
        self.assertEqual(case["M1"]["eligible_scout_recall_A"], 0.5)
        self.assertIsNone(case["M1"]["eligible_scout_recall_B"])
        self.assertIsNone(case["M1"]["paired"][0]["eligible_scout_recall_difference_B_minus_A"])
        self.assertFalse(case["M1"]["paired"][0]["complete_pair"])
        self.assertEqual(case["M2"]["eligible_scout_recall_A"], "N/A")
        self.assertEqual(result["macro"]["eligible_scout_recall_cases_with_eligible_labels"], 1)
        self.assertEqual(result["intention_to_run"]["B"], {"recovered": 0, "opportunities": 2,
                                                           "operational_lower_bound": 0.0})
        self.assertEqual(result["execution_status"]["B"]["timeout"], 1)
        self.assertEqual(result["paired_completion"], {"pairs": 3, "complete": 2})

    def test_grouping_novelty_false_positives_and_controls(self):
        data = self.data()
        data["assessments"]["h1"]["matches"] = [{"label": "S1", "independent_statement": True},
                                                {"label": "S2", "independent_statement": True}]
        result = scoring.score(data)
        rows = {row["run"]: row for row in result["runs"]}
        self.assertEqual(rows["M1-A"]["eligible_scout_matched"], ["S1", "S2"])
        self.assertEqual(rows["M1-A"]["grouped_credits"], [{"hypothesis": "h1", "labels": ["S1", "S2"]}])
        self.assertEqual(len(rows["M1-A"]["one_credit_matched"]), 2)
        self.assertEqual(result["novel_findings"], [{"hypothesis": "h4", "case": "M2", "arm": "B",
                                                     "audit": "eligible", "classification": "confirmed novel"}])
        self.assertEqual(result["false_positives"]["A"]["disproved_unmatched"], 0)
        self.assertEqual(result["controls"]["B"]["runs_with_admission"], 1)
        self.assertEqual(result["controls"]["B"]["validated_findings"], 0)
        self.assertEqual(result["validator_rejections"]["B"]["Disproved"], {"preference": 1})
        self.assertEqual(result["admission"]["A"]["clean_zero_runs"], 1)

    def test_one_credit_sensitivity_is_conservative(self):
        self.assertEqual(len(scoring.one_credit([{"S1", "S2"}])), 1)
        self.assertEqual(len(scoring.one_credit([{"S1", "S2"}, {"S1"}])), 2)

    def test_incomplete_assessment_is_not_scored_as_zero_recall(self):
        data = self.data()
        del data["assessments"]["h1"]
        result = scoring.score(data)
        row = next(row for row in result["runs"] if row["run"] == "M1-A")
        self.assertEqual(row["assessment_status"], "incomplete")
        self.assertIsNone(row["eligible_scout_recall"])
        self.assertIsNone(row["eligible_validated_recall"])
        self.assertIsNone(row["admission_qualified"])


class RecoveryTests(unittest.TestCase):
    def test_incomplete_evaluator_attempt_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "assessment"
            partial = root / "attempt-1"
            partial.mkdir(parents=True)
            marker = partial / "stdout.jsonl"
            marker.write_text("retained interrupted output")
            evidence = calibrate.Evidence(Path(temporary) / "evidence")
            with self.assertRaises(calibrate.GateError):
                calibrate.evaluator_session(root, "assessor", plan={"model": "m", "effort": "high", "claude": "x"},
                                            system="s", user="u", capsule=None, evidence=evidence)
            self.assertEqual(marker.read_text(), "retained interrupted output")

    def test_attempt_ids_cannot_escape_the_evidence_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = calibrate.Evidence(Path(temporary) / "evidence")
            with self.assertRaises(calibrate.GateError):
                evidence.set_attempt("../pilot-2")

    def test_only_one_live_batch_can_use_an_evidence_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = calibrate.Evidence(Path(temporary) / "evidence")
            with calibrate.live_run_lock(evidence):
                with self.assertRaisesRegex(calibrate.GateError, "another live batch"):
                    with calibrate.live_run_lock(evidence):
                        self.fail("concurrent batch acquired the aggregate budget")
            with calibrate.live_run_lock(evidence):
                pass

    def test_existing_deterministic_pool_reconciles_before_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = calibrate.Evidence(Path(temporary) / "evidence")
            evidence.set_attempt("pilot-a")
            hypothesis = scoring.parse_scout(hypothesis_block("H1"))["hypotheses"][0]
            run = {"run": "pilot-M91-r1-A", "case": "M91", "status": "completed",
                   "hypotheses": [hypothesis]}
            plan = {"seed": "stable"}
            first = calibrate.build_pool(evidence, plan, "pilot", [run])
            self.assertEqual(calibrate.build_pool(evidence, plan, "pilot", [run]), first)
            changed = dict(hypothesis, raw=hypothesis["raw"] + "\nextra evidence")
            with self.assertRaises(calibrate.GateError):
                calibrate.build_pool(evidence, plan, "pilot", [dict(run, hypotheses=[changed])])


if __name__ == "__main__":
    unittest.main()
