"""Session broker: the reviewer boundary, the recording API proxy, and session launch.

A model session sees exactly what the Claude CLI sends to the API. The CLI runs with
no built-in tools and one MCP server, `capsule`, launched inside a bubblewrap jail that
mounts a single capsule repository read-only, without network, home or evaluator
storage. The CLI talks to the API only through `Proxy`, which records every request,
refuses any request that offers other tools, the wrong model or effort, leaked evaluator
tokens or an exhausted budget, and so fails the session closed. Provider credentials
and network stay in the CLI and proxy processes, outside the model-accessible boundary.
"""

import http.client
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
SERVER = HERE / "capsule_server.py"
JAIL_REPOSITORY = "/capsule/repository"
TOOL_NAMES = ("list_files", "read_file", "search", "git")
ALLOWED_TOOLS = tuple(f"mcp__capsule__{name}" for name in TOOL_NAMES)
UPSTREAM = ("https", "api.anthropic.com", 443)
REDACTED_HEADERS = {"authorization", "x-api-key", "cookie", "proxy-authorization"}
# Context the CLI itself injects. Anything else in a request that is not ours, the
# model's own turns or capsule tool results fails the session as unexpected context.
CLI_SYSTEM_BLOCKS = (
    re.compile(r"^x-anthropic-billing-header: [^\n]*$"),
    re.compile(r"^You are a Claude agent, built on Anthropic's Claude Agent SDK\.$"),
    re.compile(r"^You are Claude Code, Anthropic's official CLI for Claude[^\n]*$"),
)
CLI_REMINDERS = (
    re.compile(r"^<system-reminder>\nAs you answer the user's questions, you can use the following context:\n"
               r"# userEmail\n[^\n]*\n\nClaude Code attached this context automatically;[^\n]*\n</system-reminder>\n?$"),
)
CLI_ENVIRONMENT = re.compile(
    r"^# Environment\nYou have been invoked in the following environment: \n - Primary working directory: /tmp/review-[a-z0-9_]+\n"
    r"(?:[^\n]*\n)*?.*Today's date is \d{4}-\d{2}-\d{2}\.$", re.DOTALL)
CLI_TOKEN_NOTICE = re.compile(r"^<total_tokens>\d+ tokens left</total_tokens>$")


def jail_command(repository, log_dir, command, extra_binds=()):
    """bubblewrap invocation exposing exactly one capsule repository, read-only."""
    arguments = [
        shutil.which("bwrap") or "/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
        "--clearenv", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--ro-bind", str(repository), JAIL_REPOSITORY,
        "--ro-bind", str(SERVER), "/broker/capsule_server.py",
        "--bind", str(log_dir), "/log",
    ]
    for source, target in extra_binds:
        arguments += ["--ro-bind", str(source), target]
    arguments += ["--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/nonexistent",
                  "--setenv", "LC_ALL", "C.UTF-8", "--chdir", JAIL_REPOSITORY, *command]
    return arguments


def server_command(repository, log_dir, base, head):
    return jail_command(repository, log_dir, [
        "/usr/bin/python3", "-I", "/broker/capsule_server.py", "--root", JAIL_REPOSITORY,
        "--base", base, "--head", head, "--log", "/log/access.jsonl"])


class McpClient:
    """Minimal MCP stdio client, used by the isolation challenges against the real server launch."""

    def __init__(self, command):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "challenge", "version": "1"}})
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.next_id += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                                             "params": params}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("capsule server exited: " + self.process.stderr.read())
        return json.loads(line)

    def tools(self):
        return [tool["name"] for tool in self.request("tools/list", {})["result"]["tools"]]

    def call(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})["result"]
        return result["content"][0]["text"], result["isError"]

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)


class Proxy:
    """Recording, budget-enforcing pass-through to the Anthropic API for one session."""

    def __init__(self, log_path, *, model, effort, budget, allowed_tools, forbidden=(),
                 upstream=("https", "api.anthropic.com", 443)):
        self.log_path = Path(log_path)
        self.model = model
        self.effort = effort
        self.budget = budget
        self.allowed_tools = set(allowed_tools)
        self.forbidden = [token for token in forbidden if token]
        self.upstream = upstream
        self.lock = threading.Lock()
        self.state = {"requests": 0, "output_tokens": 0, "peak_context_tokens": 0, "input_tokens": 0,
                      "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                      "violations": [], "observed": [], "endpoints": [], "refused": 0}
        self.expected_texts = []
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_HEAD(self):
                proxy.handle(self)

            def do_GET(self):
                proxy.handle(self)

            def do_POST(self):
                proxy.handle(self)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def violate(self, kind, detail):
        with self.lock:
            self.state["violations"].append({"kind": kind, "detail": detail})

    def check(self, body):
        """Return a refusal reason for a /v1/messages request, or None."""
        problems = []
        tools = body.get("tools") or []
        names = [tool.get("name") for tool in tools]
        for tool in tools:
            if tool.get("name") not in self.allowed_tools or tool.get("type") not in (None, "custom"):
                problems.append(("confinement", f"tool offered to model: {tool.get('name')} {tool.get('type')}"))
        for key in ("mcp_servers", "container"):
            if key in body:
                problems.append(("confinement", f"request carries {key}"))
        if body.get("model") != self.model:
            problems.append(("model_mismatch", f"requested {body.get('model')}"))
        effort = (body.get("output_config") or {}).get("effort")
        if effort != self.effort:
            problems.append(("effort_mismatch", f"requested effort {effort}"))
        problems += self.context_problems(body)
        serialized = json.dumps(body)
        for token in self.forbidden:
            if token in serialized:
                problems.append(("leaked_context", f"forbidden evaluator token present: {token[:12]}"))
        with self.lock:
            state = self.state
            if state["requests"] >= self.budget["max_requests"]:
                problems.append(("budget_exhausted", "request limit"))
            if state["output_tokens"] >= self.budget["max_output_tokens"]:
                problems.append(("budget_exhausted", "cumulative output token limit"))
            if state["peak_context_tokens"] > self.budget["max_context_tokens"]:
                problems.append(("budget_exhausted", "context token limit"))
            state["observed"].append({"model": body.get("model"), "effort": effort, "tools": names,
                                      "max_tokens": body.get("max_tokens"), "thinking": body.get("thinking"),
                                      "context_management": body.get("context_management")})
        return problems

    def context_problems(self, body):
        """Fail closed on context the session did not intend: memory, skills, agents, instructions."""
        problems = []
        for block in body.get("system") or []:
            text = block.get("text", "") if isinstance(block, dict) else str(block)
            if text not in self.expected_texts and not any(p.match(text) for p in CLI_SYSTEM_BLOCKS):
                problems.append(("unexpected_context", "system block: " + text[:80]))
        for message in body.get("messages") or []:
            content = message.get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []
            for block in blocks:
                if block.get("type") != "text":
                    continue
                text = block["text"]
                if message.get("role") == "assistant" or text in self.expected_texts:
                    continue
                if message.get("role") == "system" and (CLI_ENVIRONMENT.match(text) or CLI_TOKEN_NOTICE.match(text)):
                    continue
                if any(p.match(text) for p in CLI_REMINDERS):
                    continue
                problems.append(("unexpected_context", f"{message.get('role')} block: " + text[:80]))
        return problems

    def handle(self, handler):
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length) if length else b""
        path = handler.path
        record = {"time": time.time(), "method": handler.command, "path": path,
                  "headers": {k: ("<redacted>" if k.lower() in REDACTED_HEADERS else v)
                              for k, v in handler.headers.items()}}
        problems = []
        is_message = handler.command == "POST" and path.split("?")[0] == "/v1/messages"
        permitted = is_message or path.split("?")[0] in ("/api/hello", "/v1/messages/count_tokens")
        body = None
        if raw:
            try:
                body = json.loads(raw)
            except ValueError:
                record["body_unparsed_bytes"] = len(raw)
        record["body"] = body
        if not permitted:
            problems.append(("unexpected_endpoint", f"{handler.command} {path}"))
        elif is_message:
            problems = self.check(body or {})
        with self.lock:
            self.state["endpoints"].append(f"{handler.command} {path.split('?')[0]}")
        if problems:
            for kind, detail in problems:
                if kind != "unexpected_endpoint":
                    self.violate(kind, detail)
            with self.lock:
                self.state["refused"] += 1
            message = "; ".join(detail for _, detail in problems)
            payload = json.dumps({"type": "error", "error": {"type": "permission_error",
                                  "message": "calibration broker refused request: " + message}}).encode()
            handler.send_response(403)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
            record.update(status=403, refused=[list(p) for p in problems])
            self.write(record)
            return
        if is_message:
            with self.lock:
                self.state["requests"] += 1
        scheme, host, port = self.upstream
        connection = (http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection)(
            host, port, timeout=900)
        headers = {k: v for k, v in handler.headers.items()
                   if k.lower() not in ("host", "accept-encoding", "content-length", "connection")}
        headers["Accept-Encoding"] = "identity"
        try:
            connection.request(handler.command, path, body=raw or None, headers=headers)
            response = connection.getresponse()
        except OSError as error:
            self.violate("api_error", f"upstream connection failed: {error}")
            handler.send_response(502)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            record.update(status=502, error=str(error))
            self.write(record)
            return
        handler.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in ("transfer-encoding", "connection", "content-length", "content-encoding"):
                handler.send_header(key, value)
        chunked = handler.command != "HEAD"
        if chunked:
            handler.send_header("Transfer-Encoding", "chunked")
        else:
            handler.send_header("Content-Length", "0")
        handler.end_headers()
        captured = bytearray()
        while chunked:
            chunk = response.read1(65536)
            if not chunk:
                break
            captured += chunk
            try:
                handler.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                handler.wfile.flush()
            except OSError:
                break
        if chunked:
            try:
                handler.wfile.write(b"0\r\n\r\n")
                handler.wfile.flush()
            except OSError:
                pass
        text = captured.decode("utf-8", errors="replace")
        record.update(status=response.status, response_headers=dict(response.getheaders()), response=text)
        if is_message:
            record["usage"] = self.account(text, response.status)
        self.write(record)

    def account(self, text, status):
        usage = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                 "output_tokens": 0, "model": None, "stop_reason": None}
        events = []
        if text.lstrip().startswith("{"):
            try:
                events = [{"type": "message_start", "message": json.loads(text)}]
            except ValueError:
                events = []
        else:
            for line in text.splitlines():
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except ValueError:
                        continue
        for event in events:
            if event.get("type") == "message_start":
                message = event.get("message") or {}
                usage["model"] = message.get("model")
                for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
                    usage[key] = max(usage[key], (message.get("usage") or {}).get(key) or 0)
                usage["stop_reason"] = message.get("stop_reason") or usage["stop_reason"]
            elif event.get("type") == "message_delta":
                usage["output_tokens"] = max(usage["output_tokens"], (event.get("usage") or {}).get("output_tokens") or 0)
                usage["stop_reason"] = (event.get("delta") or {}).get("stop_reason") or usage["stop_reason"]
            elif event.get("type") == "error":
                self.violate("api_error", json.dumps(event.get("error"))[:300])
        if status >= 400 and status != 403:
            self.violate("api_error", f"upstream status {status}")
        context = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
        with self.lock:
            state = self.state
            state["output_tokens"] += usage["output_tokens"]
            for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                state[key] += usage[key]
            state["peak_context_tokens"] = max(state["peak_context_tokens"], context + usage["output_tokens"])
            state.setdefault("response_models", []).append(usage["model"])
            state.setdefault("stop_reasons", []).append(usage["stop_reason"])
        if usage["model"] is not None and usage["model"] != self.model:
            self.violate("model_mismatch", f"response model {usage['model']}")
        if context + usage["output_tokens"] > self.budget["max_context_tokens"]:
            self.violate("budget_exhausted", "context token limit")
        if self.state["output_tokens"] > self.budget["max_output_tokens"]:
            self.violate("budget_exhausted", "cumulative output token limit")
        return usage

    def write(self, record):
        with self.lock, open(self.log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")


FAILURE_ORDER = ("confinement_failure", "leaked_context", "unexpected_context", "model_mismatch", "effort_mismatch",
                 "budget_exhausted", "timeout", "api_error", "launch_failure", "truncation", "missing_output")
VIOLATION_STATUS = {"confinement": "confinement_failure", "leaked_context": "leaked_context",
                    "unexpected_context": "unexpected_context", "model_mismatch": "model_mismatch",
                    "effort_mismatch": "effort_mismatch", "budget_exhausted": "budget_exhausted",
                    "api_error": "api_error"}


def classify(*, timed_out, launch_error, violations, result, init, capsule, final_stop_reason):
    """Map raw session evidence to one execution status. Only `completed` is a usable session."""
    reasons = []
    if launch_error:
        reasons.append("launch_failure")
    if timed_out:
        reasons.append("timeout")
    for violation in violations:
        reasons.append(VIOLATION_STATUS.get(violation["kind"], "confinement_failure"))
    if init is not None:
        tools = sorted(init.get("tools") or [])
        if tools != sorted(ALLOWED_TOOLS if capsule else []):
            reasons.append("confinement_failure")
        servers = {server.get("name"): server.get("status") for server in init.get("mcp_servers") or []}
        if capsule and servers.get("capsule") != "connected":
            reasons.append("launch_failure")
        if set(servers) - ({"capsule"} if capsule else set()):
            reasons.append("confinement_failure")
    if result is None:
        reasons.append("missing_output")
    else:
        subtype = result.get("subtype")
        if subtype == "error_max_budget_usd":
            reasons.append("budget_exhausted")
        elif result.get("is_error") or subtype != "success":
            reasons.append("api_error")
        if final_stop_reason == "max_tokens" or result.get("stop_reason") == "max_tokens":
            reasons.append("truncation")
        if not (result.get("result") or "").strip():
            reasons.append("missing_output")
    if init is None and not launch_error:
        reasons.append("launch_failure" if result is None else "missing_output")
    for status in FAILURE_ORDER:
        if status in reasons:
            return status, sorted(set(reasons))
    return "completed", []


def run_session(session_dir, *, model, effort, budget, system_prompt, user_prompt, capsule=None,
                forbidden=(), claude="claude", upstream=None, extra_env=None):
    """Run one fresh, isolated CLI session. Writes raw evidence to session_dir; returns meta."""
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=False)
    session_id = str(uuid.uuid4())
    (session_dir / "system.txt").write_text(system_prompt, encoding="utf-8")
    (session_dir / "user.txt").write_text(user_prompt, encoding="utf-8")
    access_dir = session_dir / "access"
    access_dir.mkdir()
    (access_dir / "access.jsonl").touch()
    command = [claude, "-p", "--model", model, "--effort", effort, "--tools", "", "--strict-mcp-config",
               "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
               "--system-prompt-file", str(session_dir / "system.txt"), "--output-format", "stream-json",
               "--verbose", "--session-id", session_id, "--permission-mode", "dontAsk"]
    if capsule:
        config = {"mcpServers": {"capsule": {"type": "stdio", "command": server_command(
            capsule["repository"], access_dir, capsule["base"], capsule["head"])[0],
            "args": server_command(capsule["repository"], access_dir, capsule["base"], capsule["head"])[1:]}}}
        (session_dir / "mcp.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        command += ["--mcp-config", str(session_dir / "mcp.json"), "--allowedTools", " ".join(ALLOWED_TOOLS)]
    workdir = Path(tempfile.mkdtemp(prefix="review-", dir="/tmp"))
    started = time.time()
    timed_out = False
    launch_error = None
    with Proxy(session_dir / "api.jsonl", model=model, effort=effort, budget=budget,
               allowed_tools=ALLOWED_TOOLS if capsule else (), forbidden=forbidden,
               upstream=upstream or UPSTREAM) as proxy:
        proxy.expected_texts = [system_prompt, user_prompt, user_prompt.rstrip("\n")]
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", ""),
            "LANG": "C.UTF-8", "ANTHROPIC_BASE_URL": proxy.url, "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1", "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "MCP_TIMEOUT": "60000",
            # The CLI otherwise injects a "user hasn't heard from you" nudge after silent tool turns.
            "CLAUDE_CODE_SILENT_TURN_REMINDER": "0",
        }
        environment.update(extra_env or {})
        with open(session_dir / "stdout.jsonl", "wb") as stdout, open(session_dir / "stderr.txt", "wb") as stderr:
            try:
                process = subprocess.Popen(command, cwd=workdir, env=environment, stdin=subprocess.PIPE,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    process.communicate(user_prompt.encode("utf-8"), timeout=budget["timeout_seconds"])
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                exit_code = process.returncode
            except OSError as error:
                launch_error = str(error)
                exit_code = None
        state = json.loads(json.dumps(proxy.state))
    finished = time.time()
    leftovers = sorted(path.name for path in workdir.iterdir())
    shutil.rmtree(workdir, ignore_errors=True)
    init = None
    result = None
    final_stop = None
    for line in (session_dir / "stdout.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        elif event.get("type") == "result":
            result = event
        elif event.get("type") == "assistant":
            final_stop = (event.get("message") or {}).get("stop_reason") or final_stop
    status, reasons = classify(timed_out=timed_out, launch_error=launch_error, violations=state["violations"],
                               result=result, init=init, capsule=capsule, final_stop_reason=final_stop)
    observed = state["observed"]
    settings = {
        "model": sorted({o["model"] for o in observed} | set(filter(None, state.get("response_models", [])))),
        "effort": sorted({str(o["effort"]) for o in observed}),
        "tools": sorted({tuple(o["tools"]) for o in observed}),
        "max_tokens": sorted({o["max_tokens"] for o in observed if o["max_tokens"] is not None}),
        "thinking": sorted({json.dumps(o["thinking"], sort_keys=True) for o in observed}),
        "context_management": sorted({json.dumps(o["context_management"], sort_keys=True) for o in observed}),
        "cli": sorted({h.get("User-Agent", "") for h in [r.get("headers", {}) for r in read_jsonl(session_dir / "api.jsonl")]
                       if h.get("User-Agent")}),
    }
    settings["tools"] = [list(t) for t in settings["tools"]]
    meta = {
        "session_id": session_id, "status": status, "failure_reasons": reasons, "started": started,
        "finished": finished, "duration_seconds": round(finished - started, 3), "exit_code": exit_code,
        "timed_out": timed_out, "launch_error": launch_error, "budget": budget, "requested_model": model,
        "requested_effort": effort, "observed_settings": settings, "usage": {k: state[k] for k in (
            "requests", "output_tokens", "peak_context_tokens", "input_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens")},
        "cost_usd_reported": (result or {}).get("total_cost_usd"), "violations": state["violations"],
        "refused_requests": state["refused"], "endpoints": sorted(set(state["endpoints"])),
        "cli_reported_tools": (init or {}).get("tools"), "cli_mcp_servers": (init or {}).get("mcp_servers"),
        "cli_model": (init or {}).get("model"), "cli_version": (init or {}).get("claude_code_version"),
        "result_subtype": (result or {}).get("subtype"), "stop_reason": (result or {}).get("stop_reason") or final_stop,
        "num_turns": (result or {}).get("num_turns"), "workdir_leftovers": leftovers,
        "tool_calls": read_jsonl(access_dir / "access.jsonl"),
        "capsule": None if not capsule else {k: str(v) for k, v in capsule.items()},
    }
    (session_dir / "result.txt").write_text((result or {}).get("result") or "", encoding="utf-8")
    (session_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


PROBE = r'''
import json, os, socket, subprocess, sys
spec = json.loads(sys.argv[1])
results = {}
def attempt(name, action):
    try:
        value = action()
        results[name] = {"denied": False, "detail": str(value)[:200]}
    except Exception as error:
        results[name] = {"denied": True, "detail": type(error).__name__ + ": " + str(error)[:160]}
for name, path in spec["paths"].items():
    attempt("read:" + name, lambda path=path: (open(path, "rb").read(64) if os.path.isfile(path) else os.listdir(path)))
attempt("network:tcp", lambda: socket.create_connection((spec["ip"], 443), timeout=5))
attempt("network:dns", lambda: socket.getaddrinfo(spec["host"], 443))
def git(*args):
    out = subprocess.run(["git", "-C", "/capsule/repository", *args], capture_output=True, text=True,
                         env={"PATH": "/usr/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1"})
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[:160])
    return out.stdout
def absent(value, why):
    if value:
        return value
    raise LookupError(why)
for sha in spec["fix_objects"]:
    attempt("git:object:" + sha[:12], lambda sha=sha: git("cat-file", "-e", sha))
attempt("git:other-refs", lambda: absent([r for r in git("for-each-ref", "--format=%(refname)").split()
                                          if r != "refs/heads/review"], "only refs/heads/review"))
attempt("git:alternates", lambda: open("/capsule/repository/.git/objects/info/alternates").read())
attempt("git:remotes", lambda: absent(git("remote").strip(), "no remotes"))
attempt("git:reflog-history", lambda: absent([s for s in git("reflog", "--all", "--format=%H").split()
                                              if s not in spec["synthetic"]], "reflog names only the two snapshots"))
attempt("git:extra-history", lambda: absent(len(git("rev-list", "--all").split()) != 2, "exactly two commits"))
secret_like = [k for k in os.environ if any(s in k.upper() for s in ("TOKEN", "KEY", "SECRET", "AUTH", "ANTHROPIC", "CLAUDE", "GH_", "GITHUB"))]
results["environment:credentials"] = {"denied": not secret_like, "detail": ",".join(sorted(os.environ)) }
results["filesystem:root"] = {"denied": True, "detail": ",".join(sorted(os.listdir("/")))}
print(json.dumps(results))
'''


def challenge_capsule(capsule, *, sibling, evaluator_paths, fix_objects, scratch):
    """Exercise the real capsule-service launch: permitted reads succeed and every leak path is denied."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    log_dir = Path(tempfile.mkdtemp(dir=scratch))
    repository = Path(capsule["repository"])
    base, head = capsule["base"], capsule["head"]
    checks = []

    def record(name, expectation, denied, detail):
        passed = denied if expectation == "deny" else not denied
        checks.append({"check": name, "expect": expectation, "denied": denied, "pass": passed,
                       "detail": detail[:300]})

    client = McpClient(server_command(repository, log_dir, base, head))
    try:
        tools = client.tools()
        record("interface:tool-list", "allow", sorted(tools) != sorted(TOOL_NAMES), ",".join(tools))
        tracked = client.call("list_files", {"path": "."})
        record("allow:list_files", "allow", tracked[1], tracked[0][:120])
        first = tracked[0].splitlines()[0] if not tracked[1] and tracked[0] else "README.md"
        for name, arguments in [
            ("allow:read_file", ("read_file", {"path": first})),
            ("allow:search", ("search", {"pattern": "def |class |import ", "path": "."})),
            ("allow:diff", ("git", {"args": ["diff", "--stat", base, head]})),
            ("allow:show-head-file", ("git", {"args": ["show", f"{head}:{first}"]})),
            ("allow:log-range", ("git", {"args": ["log", "--oneline", f"{base}..{head}"]})),
        ]:
            text, error = client.call(*arguments)
            record(name, "allow", error, text[:120])
        denials = [
            ("deny:label-file-absolute", ("read_file", {"path": str(evaluator_paths["labels"])})),
            ("deny:receipt-traversal", ("read_file", {"path": "../../../evaluator-receipt.json"})),
            ("deny:sibling-capsule", ("read_file", {"path": f"../../{sibling}/repository/README.md"})),
            ("deny:parent-traversal-list", ("list_files", {"path": ".."})),
            ("deny:parent-traversal-search", ("search", {"pattern": ".", "path": "../.."})),
            ("deny:host-home", ("read_file", {"path": "~/.claude/.credentials.json"})),
            ("deny:credentials-absolute", ("read_file", {"path": str(Path.home() / ".claude/.credentials.json")})),
            ("deny:git-metadata", ("read_file", {"path": ".git/config"})),
            ("deny:original-fix-show", ("git", {"args": ["show", fix_objects[0]]})),
            ("deny:all-refs", ("git", {"args": ["log", "--all"]})),
            ("deny:alternate-ref", ("git", {"args": ["show", "refs/remotes/origin/main"]})),
            ("deny:reflog", ("git", {"args": ["log", "--walk-reflogs"]})),
            ("deny:other-repository", ("git", {"args": ["--git-dir", str(evaluator_paths["depot"]), "log"]})),
            ("deny:no-index-host-file", ("git", {"args": ["diff", "--no-index", "/etc/hostname", "README.md"]})),
            ("deny:git-pathspec-escape", ("git", {"args": ["show", head, "--", "../../x"]})),
            ("deny:network-command", ("git", {"args": ["fetch", "https://github.com/mmena1/mtg-copilot.git"]})),
            ("deny:unknown-tool", ("web_fetch", {"url": "https://github.com"})),
        ]
        for name, arguments in denials:
            text, error = client.call(*arguments)
            record(name, "deny", error, text[:200])
    finally:
        client.close()
    probe_file = scratch / "probe.py"
    probe_file.write_text(PROBE, encoding="utf-8")
    paths = {key: str(value) for key, value in evaluator_paths.items()}
    paths["sibling"] = str(Path(capsule["repository"]).parents[1] / sibling)
    paths["host-home"] = str(Path.home())
    paths["credentials"] = str(Path.home() / ".claude/.credentials.json")
    spec = {"paths": paths, "ip": "140.82.112.3", "host": "github.com", "fix_objects": fix_objects,
            "synthetic": [base, head]}
    probe = subprocess.run(jail_command(repository, log_dir, ["/usr/bin/python3", "-I", "/broker/probe.py",
                                                                json.dumps(spec)],
                                        extra_binds=[(probe_file, "/broker/probe.py")]),
                           capture_output=True, text=True, timeout=120)
    try:
        results = json.loads(probe.stdout)
    except ValueError:
        results = {"probe:launch": {"denied": False, "detail": probe.stderr[:300]}}
    for name, outcome in results.items():
        record("jail:" + name, "deny", outcome["denied"], outcome["detail"])
    access = read_jsonl(log_dir / "access.jsonl")
    shutil.rmtree(log_dir, ignore_errors=True)
    return {"capsule": str(repository), "checks": checks, "access_log": access,
            "pass": all(check["pass"] for check in checks) and len(checks) > 0}
