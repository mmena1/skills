"""The portfolio-sync group: the helper's write surface and its behavior against a fake GitHub Project."""

from __future__ import annotations

import importlib.util
import io
import re
import sys

from ..common import SKILLS, fail


PORTFOLIO_PROJECT_URL = "https://github.com/users/octo/projects/7"


class FakePortfolio:
    """An in-memory GitHub Project and repositories behind the helper's GraphQL seam."""

    def __init__(self) -> None:
        self.project = {"id": "P7", "title": "Development portfolio", "url": PORTFOLIO_PROJECT_URL,
                        "closed": False, "viewerCanUpdate": True}
        self.repositories = ["octo/app", "octo/lib"]
        self.content: dict[str, dict] = {}
        self.members: list[dict] = []
        self.mutations: list[str] = []
        self.faults: dict[str, object] = {}
        for repository, kind, number, state in (
            ("octo/app", "issues", 1, "OPEN"), ("octo/app", "issues", 2, "OPEN"),
            ("octo/app", "issues", 3, "CLOSED"), ("octo/app", "pull", 4, "OPEN"),
            ("octo/app", "pull", 5, "MERGED"), ("octo/lib", "issues", 1, "OPEN"),
            ("octo/lib", "issues", 2, "OPEN"), ("octo/lib", "issues", 3, "OPEN"),
            ("octo/other", "issues", 9, "OPEN"),
        ):
            url = f"https://github.com/{repository}/{kind}/{number}"
            self.content[url] = {"id": f"C:{repository}:{number}", "number": number, "title": f"Item {number}",
                                 "url": url, "repository": repository, "kind": kind, "state": state}
        for url, archived in (("https://github.com/octo/app/issues/1", False),
                              ("https://github.com/octo/app/issues/3", False),
                              ("https://github.com/octo/lib/issues/3", True),
                              ("https://github.com/octo/other/issues/9", False)):
            self.members.append({"type": "ISSUE", "isArchived": archived, "url": url})
        self.members.append({"type": "DRAFT_ISSUE", "isArchived": False, "url": None})

    def add_opaque_member(self, url: str) -> None:
        """A member whose content the viewer cannot read, so GitHub returns it without content."""
        self.members.append({"type": "REDACTED", "isArchived": False, "url": url, "opaque": True})

    def missing_urls(self) -> list[str]:
        members = {member["url"] for member in self.members}
        return sorted(url for url, item in self.content.items()
                      if item["state"] == "OPEN" and item["repository"] in self.repositories and url not in members)

    @staticmethod
    def page(nodes: list, after: str | None) -> dict:
        start = int(after or 0)
        end = start + 2
        return {"totalCount": len(nodes), "nodes": nodes[start:end],
                "pageInfo": {"hasNextPage": end < len(nodes), "endCursor": str(end) if end < len(nodes) else None}}

    def __call__(self, query: str, variables: dict) -> dict:
        operation = re.match(r"\s*(?:query|mutation) (\w+)", query).group(1)
        fault = self.faults.get(operation)
        if fault is not None:
            response = fault(variables) if callable(fault) else fault
            if response is not None:
                return response
        if operation == "Project":
            found = "user(login" in query and variables == {"login": "octo", "number": 7}
            return {"data": {"owner": {"projectV2": dict(self.project) if found else None}}}
        if operation == "ProjectRepositories":
            nodes = [{"nameWithOwner": name} for name in self.repositories]
            return {"data": {"node": {"connection": self.page(nodes, variables["after"])}}}
        if operation == "ProjectItems":
            nodes = []
            for member in self.members:
                if member["isArchived"] and "ARCHIVED," not in query:
                    continue  # GitHub hides archived items unless archivedStates includes them.
                item = None if member.get("opaque") else self.content.get(member["url"])
                content = {"url": item["url"], "repository": {"nameWithOwner": item["repository"]}} if item else None
                nodes.append({"type": member["type"], "isArchived": member["isArchived"], "content": content})
            return {"data": {"node": {"connection": self.page(nodes, variables["after"])}}}
        if operation in {"OpenIssues", "OpenPullRequests"}:
            repository = f"{variables['owner']}/{variables['name']}"
            if repository not in self.repositories:
                return {"data": {"repository": None}}
            kind = "issues" if operation == "OpenIssues" else "pull"
            nodes = [{key: item[key] for key in ("id", "number", "title", "url")} for item in self.content.values()
                     if item["repository"] == repository and item["kind"] == kind
                     and (item["state"] == "OPEN" or "states: OPEN" not in query)]
            return {"data": {"repository": {"connection": self.page(nodes, variables["after"])}}}
        if operation == "ContentState":
            item = next((item for item in self.content.values() if item["id"] == variables["id"]), None)
            return {"data": {"node": {"state": item["state"], "url": item["url"]} if item else None}}
        if operation == "AddProjectItem" and "addProjectV2ItemById" in query and variables["project"] == "P7":
            self.mutations.append(variables["content"])
            url = next(url for url, item in self.content.items() if item["id"] == variables["content"])
            if all(member["url"] != url for member in self.members):
                self.members.append({"type": "ISSUE", "isArchived": False, "url": url})
            return {"data": {"addProjectV2ItemById": {"item": {"id": f"I:{url}"}}}}
        raise AssertionError(f"unexpected portfolio-sync operation {operation}")


def validate_portfolio_sync() -> None:
    skill = SKILLS / "experimental" / "portfolio-sync"
    helper_path = skill / "scripts" / "portfolio_sync.py"
    source = helper_path.read_text(encoding="utf-8")
    if re.findall(r"\bmutation (\w+)\(", source) != ["AddProjectItem"]:
        fail("portfolio-sync: the helper must send exactly one named mutation, AddProjectItem")
    project_writes = set(re.findall(r"\b(?:add|update|delete|archive|unarchive|clear|convert|remove)\w*ProjectV2\w*", source))
    if project_writes != {"addProjectV2ItemById"}:
        fail(f"portfolio-sync: the helper may only add Project items, found {sorted(project_writes)}")
    portfolio = (SKILLS / "experimental" / "portfolio" / "SKILL.md").read_text(encoding="utf-8")
    if "`/portfolio-sync`" not in portfolio:
        fail("portfolio: must recommend `/portfolio-sync` for open work absent from the Project")
    if re.search(r"portfolio_sync\.py|--apply|addProjectV2ItemById|item-add", portfolio):
        fail("portfolio: must stay read-only and must not run the synchronization helper")

    spec = importlib.util.spec_from_file_location("portfolio_sync", helper_path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper  # dataclasses resolve annotations through sys.modules
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(helper)
    finally:
        sys.dont_write_bytecode = previous

    def sync(fake: FakePortfolio, apply: bool = False, plan: str | None = None,
             url: str = PORTFOLIO_PROJECT_URL) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = helper.run(url, apply, plan, fake, out, err)
        return code, out.getvalue(), err.getvalue()

    def plan_id(output: str) -> str:
        match = re.search(r"^Plan: ([0-9a-f]{12})$", output, re.MULTILINE)
        if match is None:
            fail("portfolio-sync: a dry run with missing items must print its plan identifier")
        return match.group(1)

    fake = FakePortfolio()
    expected = fake.missing_urls()
    code, output, _ = sync(fake)
    reported = sorted(re.findall(r"^    (https://\S+)$", output, re.MULTILINE))
    if code != 0 or reported != expected or fake.mutations:
        fail(f"portfolio-sync: dry run must report exactly {expected} without changes, got {reported}")
    if "issues/3" in "".join(reported) or "pull/5" in "".join(reported):
        fail("portfolio-sync: closed issues and merged pull requests must not be imported")
    for note in ("1 archived", "1 draft", "0 inaccessible", "octo/other"):
        if note not in output:
            fail(f"portfolio-sync: dry run must report coverage note {note!r}")
    authorized = plan_id(output)

    for stale in (None, "000000000000"):
        code, _, err = sync(fake, apply=True, plan=stale)
        if code != 1 or fake.mutations or "no longer matches" not in err:
            fail("portfolio-sync: applying without the current authorized plan must refuse before any change")

    code, output, _ = sync(fake, apply=True, plan=authorized)
    added = sorted(re.findall(r"^Added (https://\S+)$", output, re.MULTILINE))
    if code != 0 or added != expected or len(fake.mutations) != len(expected) or "Verified in the Project" not in output:
        fail(f"portfolio-sync: apply must add and verify exactly the authorized plan, got {added}")

    for repeat in ({}, {"apply": True, "plan": authorized}):
        code, output, _ = sync(fake, **repeat)
        if code != 0 or "In sync" not in output or len(fake.mutations) != len(expected):
            fail(f"portfolio-sync: a repeated run {repeat or 'dry run'} must be a no-op")

    def failing(name: str, setup, apply: bool = True, status: int = 1, url: str = PORTFOLIO_PROJECT_URL) -> None:
        fake = FakePortfolio()
        _, output, _ = sync(fake)
        setup(fake)
        try:
            code, output, err = sync(fake, apply=apply, plan=plan_id(output), url=url)
        except AssertionError as error:
            fail(f"portfolio-sync: {name} must fail cleanly, got {error}")
        if code != status or fake.mutations or "Plan:" in output or "In sync" in output or not err.startswith("error:"):
            fail(f"portfolio-sync: {name} must fail before any change and without a conclusion")

    def truncated(fake: FakePortfolio) -> None:
        fake.faults["ProjectItems"] = lambda variables: (
            None if variables["after"] else {"data": {"node": {"connection": {
                "totalCount": 9, "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}})

    def unreadable_node(fake: FakePortfolio) -> None:
        fake.faults["ProjectRepositories"] = {"data": {"node": {"connection": {
            "totalCount": 1, "nodes": [None], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}

    failing("an incomplete Project item read", truncated)
    failing("an unreadable linked repository entry", unreadable_node)

    def endless(next_cursor):
        calls = iter(range(20))

        def respond(variables: dict) -> dict:
            if next(calls, None) is None:
                raise AssertionError("pagination never stopped")
            return {"data": {"node": {"connection": {
                "totalCount": 2, "nodes": [{"nameWithOwner": "octo/app"}] if next_cursor(variables) == "same" else [],
                "pageInfo": {"hasNextPage": True, "endCursor": next_cursor(variables)}}}}}
        return respond

    failing("a repeated pagination cursor", lambda fake: fake.faults.update(
        ProjectRepositories=endless(lambda variables: "same")))
    failing("an empty page that claims more pages", lambda fake: fake.faults.update(
        ProjectRepositories=endless(lambda variables: str(int(variables["after"] or 0) + 1))))
    failing("an unavailable repository", lambda fake: fake.faults.update(OpenIssues={"data": {"repository": None}}))
    failing("a GraphQL error", lambda fake: fake.faults.update(
        OpenPullRequests={"data": None, "errors": [{"message": "Resource not accessible by integration"}]}))
    failing("a Project without linked repositories", lambda fake: setattr(fake, "repositories", []))
    failing("a Project that is not found", lambda fake: None, url="https://github.com/users/octo/projects/8")
    failing("an invalid Project URL", lambda fake: None, status=2, url="https://github.com/octo/app")
    for name, state in (("a read-only Project", {"viewerCanUpdate": False}), ("a closed Project", {"closed": True})):
        fake = FakePortfolio()
        _, output, _ = sync(fake)
        fake.project.update(state)
        code, _, err = sync(fake, apply=True, plan=plan_id(output))
        if code != 1 or fake.mutations or "nothing was added" not in err:
            fail(f"portfolio-sync: applying to {name} must refuse before any change")

    fake = FakePortfolio()
    _, output, _ = sync(fake)
    calls = iter(range(len(expected)))
    fake.faults["AddProjectItem"] = lambda variables: (
        {"data": None, "errors": [{"message": "secondary rate limit"}]} if next(calls) == 1 else None)
    code, output, err = sync(fake, apply=True, plan=plan_id(output))
    if code != 1 or len(fake.mutations) != 1 or "Added 1 of" not in output or "rerun the dry run" not in err:
        fail("portfolio-sync: a failed add must stop and report the partial result")
    code, output, _ = sync(fake)
    if code != 0 or len(re.findall(r"^    https://", output, re.MULTILINE)) != len(expected) - 1:
        fail("portfolio-sync: a dry run after a partial apply must plan exactly the remainder")

    # An item can close after the plan was read; the helper rechecks each one just before adding it.
    fake = FakePortfolio()
    _, output, _ = sync(fake)
    closing = fake.missing_urls()[1]

    def close_after_first_add(variables: dict) -> None:
        fake.content[closing]["state"] = "CLOSED"

    fake.faults["AddProjectItem"] = close_after_first_add
    code, output, err = sync(fake, apply=True, plan=plan_id(output))
    if code != 1 or len(fake.mutations) != 1 or "Added 1 of" not in output or "no longer open (CLOSED)" not in err:
        fail("portfolio-sync: an item that closes during application must stop the add before it")
    code, output, _ = sync(fake)
    remaining = sorted(re.findall(r"^    (https://\S+)$", output, re.MULTILINE))
    if code != 0 or closing in remaining or len(remaining) != len(expected) - 2:
        fail("portfolio-sync: a dry run after a closure must plan only the still-open remainder")

    # An inaccessible member could be any open item, so a readable-only comparison proves no absence.
    fake = FakePortfolio()
    fake.add_opaque_member(expected[0])
    for apply in (False, True):
        code, output, err = sync(fake, apply=apply, plan=authorized)
        if (code != 1 or fake.mutations or "Plan:" in output or "In sync" in output
                or "  ? " not in output or "absence is not proven" not in err):
            fail("portfolio-sync: inaccessible Project items must leave candidates unverified and refuse a plan")
    fake = FakePortfolio()
    _, output, _ = sync(fake)
    sync(fake, apply=True, plan=plan_id(output))
    fake.add_opaque_member("https://github.com/octo/private/issues/1")
    code, output, _ = sync(fake)
    if code != 0 or "In sync" not in output or "1 inaccessible" not in output:
        fail("portfolio-sync: every open item matching a readable member is in sync despite inaccessible items")
