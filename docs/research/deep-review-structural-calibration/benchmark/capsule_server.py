#!/usr/bin/env python3
"""Read-only capsule service for one review session, spoken over MCP stdio.

The runner starts this program inside a bubblewrap jail that mounts only one
capsule repository, read-only, with no network. The path and Git checks below
are a second layer: the jail, not this code, is the boundary that hides
evaluator storage, sibling capsules, credentials and the network.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PROTOCOL = "2025-06-18"
OUTPUT_LIMIT = 60_000
SEARCH_LIMIT = 200
GIT_COMMANDS = {"diff", "show", "log", "status", "ls-files", "grep"}
# Options that reach other refs, write files, run programs or read other repositories.
GIT_DENIED = re.compile(
    r"^--?(all|branches|tags|remotes|glob|exclude|reflog|walk-reflogs|output|ext-diff|textconv|"
    r"exec|upload-pack|git-dir|work-tree|namespace|alternate-refs|bisect|stdin|open-files-in-pager|"
    r"no-index|ignored|others|recurse-submodules|contents|threads|config|c|C|O|g)(=.*)?$"
)
GIT_OPTION = re.compile(r"^-[-A-Za-z0-9=,.:%<>|{}\[\] ]*$")

TOOLS = [
    {
        "name": "list_files",
        "description": "List tracked files of the reviewed head under a repository-relative directory.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}},
    },
    {
        "name": "read_file",
        "description": "Read a reviewed-head file by repository-relative path, with 1-based line numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 1, "default": 1},
                "limit": {"type": "integer", "minimum": 1, "default": 600},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search",
        "description": "Search reviewed-head files with a Python regular expression; returns path:line:text.",
        "inputSchema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}},
            "required": ["pattern"],
        },
    },
    {
        "name": "git",
        "description": (
            "Run one read-only Git inspection command (diff, show, log, status, ls-files, grep) in the "
            "review repository. Name revisions only by the supplied base and head SHAs; put paths after --."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"args": {"type": "array", "items": {"type": "string"}}},
            "required": ["args"],
        },
    },
]


class Denied(Exception):
    pass


class Capsule:
    def __init__(self, root, base, head, log):
        self.root = Path(root).resolve()
        self.base = base
        self.head = head
        self.log = log

    def resolve(self, relative):
        if not isinstance(relative, str) or "\0" in relative:
            raise Denied("path must be a string")
        if relative.startswith("/") or relative.startswith("~"):
            raise Denied("absolute and home paths are outside the review repository")
        parts = Path(relative).parts
        if ".." in parts:
            raise Denied("parent-path traversal is outside the review repository")
        if ".git" in parts:
            raise Denied("Git metadata is available only through the git tool")
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise Denied("path resolves outside the review repository")
        return candidate

    def tracked(self):
        listed = self.run_git(["ls-files", "-z"], validate=False)
        return [name for name in listed.split("\0") if name]

    def list_files(self, path="."):
        target = self.resolve(path)
        prefix = "" if target == self.root else target.relative_to(self.root).as_posix() + "/"
        names = [name for name in self.tracked() if name.startswith(prefix)]
        if not names:
            raise Denied(f"no tracked files under {path}")
        return "\n".join(names)

    def read_file(self, path, offset=1, limit=600):
        target = self.resolve(path)
        relative = target.relative_to(self.root).as_posix()
        if relative not in set(self.tracked()) or not target.is_file():
            raise Denied(f"{path} is not a tracked file")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(offset))
        chosen = lines[start - 1:start - 1 + max(1, int(limit))]
        body = "\n".join(f"{number:6d}\t{text}" for number, text in enumerate(chosen, start))
        return f"{relative}: lines {start}-{start + len(chosen) - 1} of {len(lines)}\n{body}"

    def search(self, pattern, path="."):
        target = self.resolve(path)
        prefix = "" if target == self.root else target.relative_to(self.root).as_posix()
        try:
            expression = re.compile(pattern)
        except re.error as error:
            raise Denied(f"invalid pattern: {error}")
        matches = []
        for name in self.tracked():
            if prefix and name != prefix and not name.startswith(prefix + "/"):
                continue
            text = (self.root / name).read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                if expression.search(line):
                    matches.append(f"{name}:{number}:{line}")
                    if len(matches) >= SEARCH_LIMIT:
                        return "\n".join(matches) + f"\n[search stopped at {SEARCH_LIMIT} matches]"
        return "\n".join(matches) or "no matches"

    def check_git(self, args):
        if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
            raise Denied("args must be a non-empty list of strings")
        if args[0] not in GIT_COMMANDS:
            raise Denied(f"git {args[0]} is not a permitted read-only inspection command")
        pathspec = False
        for argument in args[1:]:
            if pathspec:
                if argument.startswith("/") or ".." in Path(argument).parts or ".git" in Path(argument).parts:
                    raise Denied(f"pathspec outside the review repository: {argument}")
                continue
            if argument == "--":
                pathspec = True
            elif argument.startswith("-"):
                if GIT_DENIED.match(argument) or not GIT_OPTION.match(argument):
                    raise Denied(f"git option {argument} is not permitted")
            elif argument.isdigit():
                continue  # a separate option value such as -n 5 or -U 3
            elif not self.permitted_revision(argument):
                raise Denied(
                    f"revision {argument} is not permitted; name only the supplied base and head SHAs "
                    "and put paths after --"
                )

    def permitted_revision(self, argument):
        # base, head, base..head, base...head, head:path, head^, base~0 and so on.
        revision = argument.split(":", 1)[0]
        for piece in re.split(r"\.\.\.?", revision):
            core = re.sub(r"(\^[0-9]*|~[0-9]*|\^\{[a-z]*\})+$", "", piece)
            if len(core) < 7 or not (self.base.startswith(core) or self.head.startswith(core)):
                return False
        if ":" in argument:
            self.resolve(argument.split(":", 1)[1] or ".")
        return True

    def run_git(self, args, validate=True):
        if validate:
            self.check_git(args)
        environment = {
            "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_PAGER": "cat", "PAGER": "cat",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1", "LC_ALL": "C.UTF-8",
        }
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
             "-C", str(self.root), "--no-pager", *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, timeout=60,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        if result.returncode != 0:
            raise Denied("git failed: " + result.stderr.decode("utf-8", errors="replace").strip())
        return output

    def git(self, args):
        return self.run_git(args)

    def call(self, name, arguments):
        handlers = {"list_files": self.list_files, "read_file": self.read_file,
                    "search": self.search, "git": self.git}
        record = {"tool": name, "arguments": arguments}
        try:
            if name not in handlers:
                raise Denied(f"unknown tool {name}")
            text = handlers[name](**arguments)
            truncated = len(text) > OUTPUT_LIMIT
            if truncated:
                text = text[:OUTPUT_LIMIT] + f"\n[output truncated at {OUTPUT_LIMIT} characters]"
            record.update(status="ok", characters=len(text), truncated=truncated)
            return text, False, record
        except (Denied, TypeError, ValueError) as error:
            record.update(status="denied", reason=str(error))
            return f"denied: {error}", True, record
        except subprocess.TimeoutExpired:
            record.update(status="denied", reason="timeout")
            return "denied: command timed out", True, record


def serve(capsule, stdin, stdout):
    for line in stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        method = message.get("method")
        if "id" not in message:
            continue
        if method == "initialize":
            result = {"protocolVersion": message.get("params", {}).get("protocolVersion", PROTOCOL),
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "capsule", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params", {})
            text, error, record = capsule.call(params.get("name"), params.get("arguments") or {})
            if capsule.log:
                with open(capsule.log, "a", encoding="utf-8") as log:
                    log.write(json.dumps(record, sort_keys=True) + "\n")
            result = {"content": [{"type": "text", "text": text}], "isError": error}
        elif method == "ping":
            result = {}
        else:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                     "error": {"code": -32601, "message": "method not found"}}) + "\n")
            stdout.flush()
            continue
        stdout.write(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}) + "\n")
        stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--log")
    args = parser.parse_args()
    serve(Capsule(args.root, args.base, args.head, args.log), sys.stdin, sys.stdout)


if __name__ == "__main__":
    os.umask(0o077)
    main()
