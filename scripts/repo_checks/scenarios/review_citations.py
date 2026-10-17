"""The implementation-review citation group: source anchors and commit attribution against real Git objects.

Builds a disposable repository whose history mirrors the reported incident (a 48-line
file, earlier tests, a later removal commit, a pure rename, a rename with an edit, and a
deletion), then exercises
the verification model and pins the implementation-review wording it models.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..common import ROOT, fail
from ..review_citations import (
    BLOB_TYPE_COMMAND, COMMIT_PATCH_COMMAND, LINE_COUNT_COMMAND, anchor_verdict, attribution_verdict, git,
    hunk_coordinates, parse_anchor, review_outcome,
)


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "--all")
    git(repo, "-c", "user.name=Check", "-c", "user.email=check@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "--quiet", "--no-verify", "-m", message)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def build_history(repo: Path) -> dict[str, str]:
    """A baseline and four commits that together implement one reviewed change."""
    git(repo, "init", "--quiet")
    buffer = [f"    // buffer line {number}" for number in range(1, 49)]
    buffer[19] = "    legacyFlush();"
    write_lines(repo / "src/VisitorEventBuffer.java", buffer)
    write_lines(repo / "src/Legacy.java", [f"// legacy line {number}" for number in range(1, 31)])
    write_lines(repo / "src/OldName.java", [f"// named line {number}" for number in range(1, 21)])
    moved = [f"// moved line {number}" for number in range(1, 21)]
    write_lines(repo / "src/Before.java", moved)
    shas = {"base": commit_all(repo, "baseline")}

    buffer[9:9] = ["    void flushOnCapacity() {", "        flush();", "    }"]
    write_lines(repo / "src/VisitorEventBuffer.java", buffer)
    write_lines(repo / "test/VisitorEventBufferTest.java", ["    @Test", "    void flushesOnCapacity() {", "    }"])
    shas["tests"] = commit_all(repo, "add capacity flush with tests")

    (repo / "src/OldName.java").rename(repo / "src/NewName.java")
    shas["rename"] = commit_all(repo, "rename the named source")

    (repo / "src/Before.java").unlink()
    moved[4] = "// moved line 5 edited"
    write_lines(repo / "src/After.java", moved)
    shas["move"] = commit_all(repo, "move a source and edit one line")

    buffer.remove("    legacyFlush();")
    write_lines(repo / "src/VisitorEventBuffer.java", buffer)
    (repo / "src/Legacy.java").unlink()
    shas["removal"] = commit_all(repo, "remove the legacy flush")
    return shas


def validate_review_citations() -> None:
    """Exercise revision-aware anchor and commit-attribution verification, and pin its wording."""
    document = (ROOT / "skills/implementation-review/SKILL.md").read_text(encoding="utf-8")
    for required in (
        BLOB_TYPE_COMMAND,
        LINE_COUNT_COMMAND,
        COMMIT_PATCH_COMMAND,
        "`git merge-base <fixed-point> HEAD`",
        "the **review base**",
        "the **reviewed head**",
        "It is the cumulative change of every reviewed commit, not the change of any one commit.",
        "`<path>:<start>[-<end>]` (new)",
        "Take line numbers only from the hunk headers",
        "Never cite a line's position in the diff, in this prompt, or in any assembled source bundle",
        "Cite standards documents and originating sources by path or name and a quotation, not by line number.",
        "Commit-list order or proximity is not evidence.",
        "Do not run git commands; use the provided diff output.",
        "Verify every source anchor and commit attribution before aggregating",
        "A finding that points at code must carry at least one anchor; one without an anchor is a failed anchor.",
        "A finding with no code to point at, such as a missing requirement, needs none.",
        "then read only the file section whose old or new path is the claimed path",
        "A pure rename section has no added or removed lines, so it supports no claim.",
        "A file location cited in any other form, such as a line named in prose, is a failed anchor too.",
        "checked against the review base, not rejected because the reviewed head lacks it",
        "Never present a failed anchor as verified evidence, drop its finding, or substitute an anchor of your own.",
        "mark that axis and the overall review **incomplete**",
        "keep the other axis's verified report",
        "commit attribution undecided",
        "Light cleaning never changes a finding's anchor, commit attribution, or meaning.",
        "Name the reviewed range as `<fixed-point>...HEAD`",
    ):
        if required not in document:
            fail(f"implementation-review citation contract is missing {required!r}")
    for brief in ("**Standards sub-agent prompt**", "**Spec sub-agent prompt**"):
        prompt = document.partition(brief)[2].partition("sub-agent prompt**")[0]
        if "The anchor context from step 1 and the anchor rules" not in prompt:
            fail(f"implementation-review {brief} does not carry the anchor context and anchor rules")

    with tempfile.TemporaryDirectory(prefix="skills-review-citations-") as temp_value:
        repo = Path(temp_value)
        shas = build_history(repo)
        base, head = shas["base"], shas["removal"]
        commits = [shas["tests"], shas["rename"], shas["move"], shas["removal"]]

        def anchor(text: str) -> str:
            return anchor_verdict(repo, parse_anchor(text), base=base, head=head)

        # Coordinates derived from the cumulative diff's hunk headers name real file lines.
        diff = git(repo, "diff", "--find-renames", f"{base}...{head}").decode()
        coordinates = hunk_coordinates(diff)
        added = next(entry for entry in coordinates if entry["text"] == "+        flush();")
        removed = next(entry for entry in coordinates if entry["text"] == "-    legacyFlush();")
        if (added["new_path"], added["new"], removed["old_path"], removed["old"]) != (
            "src/VisitorEventBuffer.java", 11, "src/VisitorEventBuffer.java", 20,
        ):
            fail(f"hunk-header coordinates do not name the real file lines: {added}, {removed}")
        for entry, side, sha, path, line in (
            (added, "new", head, added["new_path"], added["new"]),
            (removed, "old", base, removed["old_path"], removed["old"]),
        ):
            actual = git(repo, "cat-file", "-p", f"{sha}:{path}").decode().split("\n")[line - 1]
            if actual != entry["text"][1:]:
                fail(f"a derived {side}-side coordinate does not hold the diff line it names: {actual!r}")
            if anchor(f"`{path}:{line}` ({side})") != "verified":
                fail(f"a derived {side}-side coordinate was not verified")

        # A concatenated bundle numbers the same line far beyond the file it belongs to.
        bundle = [f"prompt line {number}" for number in range(1, 784)] + diff.split("\n")
        position = bundle.index("+        flush();") + 1
        if position <= 50:
            fail("the concatenated bundle scenario does not place the cited line beyond the file")
        if anchor(f"`src/VisitorEventBuffer.java:{position}` (new)") != "out-of-range":
            fail("a bundle-numbered citation was accepted as a source line")

        cases = {
            "the 48-line file cited at 784-785 on its baseline side": ("`src/VisitorEventBuffer.java:784-785` (old)", "out-of-range"),
            "the reported 784-785 citation at the reviewed head": ("`src/VisitorEventBuffer.java:784-785` (new)", "out-of-range"),
            "the last baseline line of the 48-line file": ("`src/VisitorEventBuffer.java:48` (old)", "verified"),
            "a valid new-side range": ("`src/VisitorEventBuffer.java:10-12` (new)", "verified"),
            "a new-side line beyond the reviewed head": ("`src/VisitorEventBuffer.java:51` (new)", "out-of-range"),
            "a deleted file at the review base": ("`src/Legacy.java:5` (old)", "verified"),
            "a deleted file at the reviewed head": ("`src/Legacy.java:5` (new)", "missing-path"),
            "a pre-rename path at the review base": ("`src/OldName.java:3` (old)", "verified"),
            "a pre-rename path at the reviewed head": ("`src/OldName.java:3` (new)", "missing-path"),
            "a post-rename path at the reviewed head": ("`src/NewName.java:3-20` (new)", "verified"),
            "a post-rename path at the review base": ("`src/NewName.java:3` (old)", "missing-path"),
            "an added test file at the reviewed head": ("`test/VisitorEventBufferTest.java:2` (new)", "verified"),
            "a directory instead of a file": ("`src:1` (new)", "missing-path"),
            "a reversed range": ("`src/VisitorEventBuffer.java:12-10` (new)", "invalid-anchor"),
            "a zero line": ("`src/VisitorEventBuffer.java:0` (new)", "invalid-anchor"),
            "a non-numeric line": ("`src/VisitorEventBuffer.java:abc` (new)", "invalid-anchor"),
            "an anchor without a side": ("`src/VisitorEventBuffer.java:10`", "invalid-anchor"),
            "a hunk header offered as a coordinate": ("`@@ -18,7 +21,6 @@` (new)", "invalid-anchor"),
            "a location named in prose": ("line 784 of src/VisitorEventBuffer.java", "invalid-anchor"),
        }
        for label, (text, expected) in cases.items():
            verdict = anchor(text)
            if verdict != expected:
                fail(f"implementation-review anchor check: {label} gave {verdict!r} (expected {expected!r})")

        # Commit attribution needs the named commit's own patch; cumulative changes stay cumulative.
        test_line = "void flushesOnCapacity() {"
        feature_line = "void flushOnCapacity() {"
        claims = {
            "the earlier commit added the tests": ((shas["tests"], "test/VisitorEventBufferTest.java", "tested", test_line), "supported"),
            "the later removal commit credited with the earlier tests": (
                (shas["removal"], "test/VisitorEventBufferTest.java", "tested", test_line), "unsupported"),
            "the removal commit removed the legacy call": (
                (shas["removal"], "src/VisitorEventBuffer.java", "removed", "legacyFlush();"), "supported"),
            "the earlier commit credited with the later removal": (
                (shas["tests"], "src/VisitorEventBuffer.java", "removed", "legacyFlush();"), "unsupported"),
            "the contributing commit that added the feature": (
                (shas["tests"], "src/VisitorEventBuffer.java", "added", feature_line), "supported"),
            "another contributing commit credited with the feature": (
                (shas["removal"], "src/VisitorEventBuffer.java", "added", feature_line), "unsupported"),
            "the rename commit credited with the deletion": (
                (shas["rename"], "src/Legacy.java", "removed", "// legacy line 5"), "unsupported"),
            "the deletion commit removed the deleted file's lines": (
                (shas["removal"], "src/Legacy.java", "removed", "// legacy line 5"), "supported"),
            "the right commit credited under another path it changed": (
                (shas["tests"], "test/VisitorEventBufferTest.java", "added", feature_line), "unsupported"),
            "a commit outside the reviewed range": ((base, "src/Legacy.java", "added", "// legacy line 5"), "outside-range"),
            "a pure rename credited with adding the moved lines": (
                (shas["rename"], "src/NewName.java", "added", "// named line 3"), "unsupported"),
            "a pure rename credited with testing the moved lines": (
                (shas["rename"], "src/NewName.java", "tested", "// named line 3"), "unsupported"),
            "a pure rename credited with removing the old path's lines": (
                (shas["rename"], "src/OldName.java", "removed", "// named line 3"), "unsupported"),
            "a rename with an edit added the edited line": (
                (shas["move"], "src/After.java", "added", "// moved line 5 edited"), "supported"),
            "a rename with an edit removed the replaced line under the old path": (
                (shas["move"], "src/Before.java", "removed", "// moved line 5"), "supported"),
            "a rename with an edit credited with an unchanged line": (
                (shas["move"], "src/After.java", "added", "// moved line 6"), "unsupported"),
        }
        for label, ((sha, path, change, quote), expected) in claims.items():
            verdict = attribution_verdict(
                repo, {"commit": sha, "path": path, "change": change, "quote": quote}, commits=commits,
            )
            if verdict != expected:
                fail(f"implementation-review commit attribution: {label} gave {verdict!r} (expected {expected!r})")

    # Every code finding needs an anchor; a failed or missing one goes back to its reviewer once,
    # and an uncorrectable one leaves the axis incomplete.
    def finding(*anchors: str, code: bool = True) -> dict:
        return {"code": code, "anchors": list(anchors)}

    def axis(*findings: dict, corrections=None, attributions=(), attribution_corrections=None) -> dict:
        return {"findings": list(findings), "corrections": corrections or {}, "attributions": list(attributions),
                "attribution_corrections": attribution_corrections or {}}

    verified = finding("verified")
    outcomes = {
        "two verified axes": (
            {"Standards": axis(verified), "Spec": axis(finding("verified", "verified"))},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
        "a genuinely clean report with no findings": (
            {"Standards": axis(), "Spec": axis()},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
        "a finding with no code to point at, such as a missing requirement": (
            {"Standards": axis(verified), "Spec": axis(finding(code=False))},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
        "an unanchored code finding": (
            {"Standards": axis(finding()), "Spec": axis(verified)},
            ("incomplete", {"Standards": "incomplete", "Spec": "complete"}),
        ),
        "an unanchored code finding given a verified anchor on correction": (
            {"Standards": axis(finding(), corrections={0: "verified"}), "Spec": axis(verified)},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
        "an uncorrectable Spec reference": (
            {"Standards": axis(verified), "Spec": axis(finding("out-of-range"))},
            ("incomplete", {"Standards": "complete", "Spec": "incomplete"}),
        ),
        "a corrected Spec reference": (
            {"Standards": axis(verified), "Spec": axis(finding("out-of-range"), corrections={0: "verified"})},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
        "a correction that fails verification again": (
            {"Standards": axis(verified), "Spec": axis(finding("out-of-range"), corrections={0: "missing-path"})},
            ("incomplete", {"Standards": "complete", "Spec": "incomplete"}),
        ),
        "one failed anchor among a finding's verified anchors": (
            {"Standards": axis(finding("verified", "missing-path")), "Spec": axis(verified)},
            ("incomplete", {"Standards": "incomplete", "Spec": "complete"}),
        ),
        "an uncorrected commit attribution": (
            {"Standards": axis(verified), "Spec": axis(verified, attributions=["unsupported"])},
            ("complete", {"Standards": "complete", "Spec": "complete"}),
        ),
    }
    for label, (axes, (overall, statuses)) in outcomes.items():
        result = review_outcome(axes)
        if result["overall"] != overall or {name: entry["status"] for name, entry in result["axes"].items()} != statuses:
            fail(f"implementation-review aggregation: {label} gave {result}")
    preserved = review_outcome({"Standards": axis(verified), "Spec": axis(verified, finding(), finding("out-of-range"))})["axes"]
    if preserved["Spec"]["unverified"] != [1, 2] or preserved["Standards"]["unverified"]:
        fail("an incomplete axis must list its unverified findings and keep the other axis's results")
    undecided = review_outcome({
        "Standards": axis(verified),
        "Spec": axis(verified, attributions=["supported", "unsupported", "outside-range"], attribution_corrections={2: "supported"}),
    })["axes"]["Spec"]
    if undecided["undecided"] != [1]:
        fail(f"an unsupported commit attribution must stay as a cumulative finding with its attribution undecided: {undecided}")
