#!/usr/bin/env python3
"""Add the open issues and PRs of a GitHub Project's linked repositories to that Project.

Dry run by default. `--apply --plan <id>` adds exactly the reviewed missing items and
nothing else: it never removes items, edits fields, or changes issue or PR state.
Requires only Python 3 and an authenticated `gh`.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import subprocess
import sys
from typing import Callable, TextIO

PROJECT_URL = re.compile(
    r"https://(?P<host>[^/\s]+)/(?P<kind>users|orgs)/(?P<login>[^/\s]+)/projects/(?P<number>[0-9]+)/?"
)
PAGE = "first: 100, after: $after"
PAGE_INFO = "totalCount pageInfo { hasNextPage endCursor }"

PROJECT_QUERY = """query Project($login: String!, $number: Int!) {
  owner: %s(login: $login) {
    projectV2(number: $number) { id title url closed viewerCanUpdate }
  }
}"""
REPOSITORIES_QUERY = f"""query ProjectRepositories($id: ID!, $after: String) {{
  node(id: $id) {{ ... on ProjectV2 {{ connection: repositories({PAGE}) {{
    {PAGE_INFO} nodes {{ nameWithOwner }}
  }} }} }}
}}"""
# Archived items are still members; the connection hides them unless asked.
ITEMS_QUERY = f"""query ProjectItems($id: ID!, $after: String) {{
  node(id: $id) {{ ... on ProjectV2 {{ connection: items({PAGE}, archivedStates: [ARCHIVED, NOT_ARCHIVED]) {{
    {PAGE_INFO} nodes {{
      type isArchived
      content {{
        ... on Issue {{ url repository {{ nameWithOwner }} }}
        ... on PullRequest {{ url repository {{ nameWithOwner }} }}
      }}
    }}
  }} }} }}
}}"""
OPEN_QUERY = """query Open%s($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    connection: %s(states: OPEN, %s, orderBy: {field: CREATED_AT, direction: ASC}) {
      %s nodes { id number title url }
    }
  }
}"""
OPEN_ISSUES_QUERY = OPEN_QUERY % ("Issues", "issues", PAGE, PAGE_INFO)
OPEN_PULL_REQUESTS_QUERY = OPEN_QUERY % ("PullRequests", "pullRequests", PAGE, PAGE_INFO)
# Rechecked immediately before each add, because an item can close after the plan was read.
CONTENT_STATE_QUERY = """query ContentState($id: ID!) {
  node(id: $id) { ... on Issue { state url } ... on PullRequest { state url } }
}"""
# The only mutation this helper sends. GitHub returns the existing item when the
# content is already a member, so a repeated add cannot duplicate it.
ADD_ITEM_MUTATION = """mutation AddProjectItem($project: ID!, $content: ID!) {
  addProjectV2ItemById(input: {projectId: $project, contentId: $content}) { item { id } }
}"""

GraphQL = Callable[[str, dict], dict]


class SyncError(RuntimeError):
    pass


class UsageError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class OpenItem:
    repository: str
    kind: str
    number: int
    title: str
    url: str
    content_id: str


@dataclasses.dataclass
class Plan:
    project: dict
    repositories: list[str]
    item_count: int
    archived: int
    drafts: int
    redacted: int
    unlinked: list[str]
    open_items: list[OpenItem]
    missing: list[OpenItem]

    @property
    def id(self) -> str:
        lines = [self.project["id"], *sorted(item.url for item in self.missing)]
        return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]


def gh_graphql(host: str) -> GraphQL:
    def run(query: str, variables: dict) -> dict:
        body = json.dumps({"query": query, "variables": variables})
        try:
            result = subprocess.run(
                ["gh", "api", "graphql", "--hostname", host, "--input", "-"],
                input=body, capture_output=True, text=True, encoding="utf-8",
            )
        except FileNotFoundError:
            raise SyncError("the GitHub CLI `gh` is not installed or not on PATH") from None
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict):
            detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
            raise SyncError(f"gh api graphql failed: {detail}")
        if result.returncode != 0 and not payload.get("errors"):
            payload["errors"] = [{"message": result.stderr.strip() or f"exit status {result.returncode}"}]
        return payload

    return run


def request(graphql: GraphQL, query: str, variables: dict) -> dict:
    payload = graphql(query, variables)
    if payload.get("errors"):
        messages = "; ".join(str(error.get("message", error)) for error in payload["errors"])
        raise SyncError(f"GitHub returned errors: {messages}")
    if not isinstance(payload.get("data"), dict):
        raise SyncError("GitHub returned no data")
    return payload["data"]


def read_all(graphql: GraphQL, query: str, variables: dict, root: str, label: str) -> list[dict]:
    """Read every page of one connection, failing on any gap instead of returning a partial list."""
    nodes: list[dict] = []
    after = None
    seen: set[str] = set()
    while True:
        holder = request(graphql, query, {**variables, "after": after}).get(root)
        if holder is None:
            raise SyncError(f"{label} is unavailable: not found or not readable with the current credentials")
        connection = holder["connection"]
        page = connection["nodes"]
        if any(node is None for node in page):
            raise SyncError(f"{label} contains entries that could not be read")
        nodes.extend(page)
        info = connection["pageInfo"]
        if not info["hasNextPage"]:
            break
        if not info["endCursor"]:
            raise SyncError(f"{label} reported another page without a cursor")
        if not page or info["endCursor"] in seen:
            raise SyncError(f"{label} made no progress: an empty page or a repeated cursor claimed more pages")
        after = info["endCursor"]
        seen.add(after)
    if len(nodes) != connection["totalCount"]:
        raise SyncError(
            f"{label} read {len(nodes)} of {connection['totalCount']} entries; "
            "it may have changed during the read, so rerun"
        )
    return nodes


def resolve_project(graphql: GraphQL, url: str) -> dict:
    match = PROJECT_URL.fullmatch(url.strip())
    if match is None:
        raise UsageError(f"not a GitHub Project URL: {url!r} (expected https://github.com/users|orgs/<login>/projects/<number>)")
    root = "user" if match["kind"] == "users" else "organization"
    data = request(graphql, PROJECT_QUERY % root, {"login": match["login"], "number": int(match["number"])})
    project = (data.get("owner") or {}).get("projectV2")
    if project is None:
        raise SyncError(f"Project {url} was not found or is not readable")
    return project


def build_plan(graphql: GraphQL, project: dict) -> Plan:
    repositories = sorted(
        node["nameWithOwner"]
        for node in read_all(graphql, REPOSITORIES_QUERY, {"id": project["id"]}, "node", "Project repository list")
    )
    if not repositories:
        raise SyncError("the Project has no linked repositories, so there is no synchronization scope")

    items = read_all(graphql, ITEMS_QUERY, {"id": project["id"]}, "node", "Project item list")
    members: dict[str, dict] = {}
    drafts = redacted = 0
    for item in items:
        content = item.get("content") or {}
        if content.get("url"):
            members[content["url"]] = item
        elif item["type"] == "DRAFT_ISSUE":
            drafts += 1
        else:
            redacted += 1
    linked = set(repositories)
    unlinked = sorted({
        item["content"]["repository"]["nameWithOwner"] for item in members.values()
    } - linked)

    open_items: list[OpenItem] = []
    for repository in repositories:
        owner, name = repository.split("/", 1)
        for kind, query in (("issue", OPEN_ISSUES_QUERY), ("pull request", OPEN_PULL_REQUESTS_QUERY)):
            label = f"open {kind}s of {repository}"
            for node in read_all(graphql, query, {"owner": owner, "name": name}, "repository", label):
                open_items.append(OpenItem(repository, kind, node["number"], node["title"], node["url"], node["id"]))
    open_items.sort(key=lambda item: (item.repository, item.kind, item.number))
    missing = [item for item in open_items if item.url not in members]
    archived = sum(1 for item in members.values() if item["isArchived"])
    return Plan(project, repositories, len(items), archived, drafts, redacted, unlinked, open_items, missing)


def count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def report(plan: Plan, out: TextIO) -> None:
    project = plan.project
    print(f"Project: {project['title']} ({project['url']})", file=out)
    if project["closed"]:
        print("  The Project is closed; synchronization is refused until it is reopened.", file=out)
    if not project["viewerCanUpdate"]:
        print("  The current credentials cannot add items to this Project.", file=out)
    print(f"Linked repositories ({len(plan.repositories)}): {', '.join(plan.repositories)}", file=out)
    print(
        f"Project items read: {plan.item_count} "
        f"({plan.archived} archived, {count(plan.drafts, 'draft')}, {plan.redacted} inaccessible)",
        file=out,
    )
    if plan.unlinked:
        print(f"Not synchronized (items present, repository not linked): {', '.join(plan.unlinked)}", file=out)
    print(file=out)
    for repository in plan.repositories:
        open_items = [item for item in plan.open_items if item.repository == repository]
        missing = [item for item in plan.missing if item.repository == repository]
        issues = sum(1 for item in open_items if item.kind == "issue")
        summary = f"{len(missing)} missing" if missing else "in sync"
        counts = f"{count(issues, 'open issue')}, {count(len(open_items) - issues, 'open pull request')}"
        print(f"{repository}: {counts}; {summary}", file=out)
        marker = "?" if plan.redacted else "+"
        for item in missing:
            print(f"  {marker} {item.kind} #{item.number} {item.title}\n    {item.url}", file=out)
    print(file=out)


def run(url: str, apply: bool, plan_id: str | None, graphql: GraphQL, out: TextIO, err: TextIO) -> int:
    try:
        project = resolve_project(graphql, url)
        plan = build_plan(graphql, project)
        report(plan, out)
        if not plan.missing:
            print("In sync: every open issue and pull request of the linked repositories is in the Project.", file=out)
            return 0
        repositories = len({item.repository for item in plan.missing})
        across = "1 repository" if repositories == 1 else f"{repositories} repositories"
        if plan.redacted:
            print(f"Unverified: {count(len(plan.missing), 'open item')} across {across} matched no readable member.", file=out)
            raise SyncError(
                f"{count(plan.redacted, 'inaccessible Project item')} could already represent any of them, so their "
                "absence is not proven and no plan was made; restore read access to that content or remove those "
                "items from the Project yourself, then rerun"
            )
        print(f"Missing: {count(len(plan.missing), 'open item')} across {across}.", file=out)
        print(f"Plan: {plan.id}", file=out)
        if not apply:
            print(f"Dry run: nothing changed. To add exactly these items, rerun with --apply --plan {plan.id}", file=out)
            return 0
        if plan_id != plan.id:
            raise SyncError(f"the authorized plan {plan_id} no longer matches the current plan {plan.id}; review the new dry run")
        if project["closed"] or not project["viewerCanUpdate"]:
            raise SyncError("the Project is closed or not writable with the current credentials; nothing was added")
        added: list[OpenItem] = []
        for item in plan.missing:
            try:
                current = request(graphql, CONTENT_STATE_QUERY, {"id": item.content_id}).get("node") or {}
                if current.get("state") != "OPEN" or current.get("url") != item.url:
                    raise SyncError(f"it is no longer open ({current.get('state', 'unreadable')}), so the plan changed")
                result = request(graphql, ADD_ITEM_MUTATION, {"project": project["id"], "content": item.content_id})
                if not ((result.get("addProjectV2ItemById") or {}).get("item") or {}).get("id"):
                    raise SyncError("GitHub returned no Project item")
            except SyncError as error:
                print(f"Added {len(added)} of {len(plan.missing)} items before a failure.", file=out)
                raise SyncError(f"stopped at {item.url}: {error}; rerun the dry run to continue") from None
            added.append(item)
            print(f"Added {item.url}", file=out)
        verify = build_plan(graphql, project)
        still_missing = {item.url for item in verify.missing} & {item.url for item in added}
        if still_missing:
            raise SyncError(f"added items are not yet visible in the Project: {', '.join(sorted(still_missing))}")
        print(f"Verified in the Project: {count(len(added), 'added item')}.", file=out)
        return 0
    except UsageError as error:
        print(f"error: {error}", file=err)
        return 2
    except SyncError as error:
        print(f"error: {error}", file=err)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", help="exact Project URL, such as https://github.com/users/<login>/projects/<number>")
    parser.add_argument("--apply", action="store_true", help="add the missing items of a reviewed plan")
    parser.add_argument("--plan", help="the plan identifier printed by the reviewed dry run; required with --apply")
    args = parser.parse_args(argv)
    if args.apply and not args.plan:
        parser.error("--apply requires --plan <id> from a reviewed dry run")
    match = PROJECT_URL.fullmatch(args.project.strip())
    graphql = gh_graphql(match["host"] if match else "github.com")
    return run(args.project, args.apply, args.plan, graphql, sys.stdout, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
