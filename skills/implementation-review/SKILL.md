---
name: implementation-review
description: Verify a committed implementation diff from a fixed baseline against its originating issue/spec requirements and repository standards. Use only for implementation-conformance review; generic PR reviews and broad defect-discovery tasks must not select this skill. Deep-review remains explicit-only.
---

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

Run this workflow for explicit implementation-conformance review or when an already-invoked workflow composes it with a fixed point and source. Do not select it for generic PR review requests or broad defect-discovery tasks. Those requests must not trigger implementation-review; deep-review remains explicit-only.

The issue tracker should have been provided to you. If `docs/agents/issue-tracker.md` is missing, tell the user to run `/setup-skills`.

## Reviewer authorization preflight

Before any reviewer is dispatched, assess whether the active harness will authorize the reviewer roles this review needs, so a blocked role surfaces before work is stranded in review. The preflight never launches a reviewer: no dummy, probe, or fabricated reviewer tests a permission.

**Required roles.** Standards is always required. Spec is required whenever an originating source is available. A standalone run applies the preflight after step 2 has resolved whether a source exists and before step 4, and may skip Spec as "no spec available". When `/implement` composes this skill it applies the preflight in its start gates with both Standards and Spec required, because it always supplies a source bundle.

**Assessment.** Classify each required role, using only capability or approval information the active harness reliably exposes without side effects. Never infer one role's authorization from another's, or from user intent or these instructions.

- **Established**: the harness reports the role as authorized. Proceed with no added confirmation prompt.
- **Known blocked**: the harness reports the role as refused or as needing approval it has not given. Request once the narrowest authorization the harness supports, scoped to this ticket's review, naming every required role and covering the review's fixed-point re-review iterations. A grant authorizes only the roles it covers, and any required role it leaves blocked is a denial. Proceed once every blocked role is covered. On denial, stop and report the affected roles and the consequence: the review cannot complete, so closeout cannot succeed. The user can still grant the permission with the harness's supported controls and rerun.
- **Indeterminate**: no reliable non-mutating check exists, or the harness approves only at invocation. Explain the limitation, name the affected roles and the possible consequence, and continue without stating or implying that authorization has been granted.

**Limits.** Never request a global, broader-than-ticket, or permanent permission, weaken a reviewer's permissions or read-only contract, or substitute a coordinator-only check for a blocked role. The preflight is one assessment and at most one request. Repeated review cycles add no request of this skill's own when the harness permits the requested scope; where the harness itself prompts per invocation, those prompts are the harness's, and the preflight must not claim advance coverage for them. A permission failure during the actual review is an incomplete review under step 5, never a review success.

**Harness mechanisms.** Each statement is labelled documented, observed (harness, version, date), or inferred. A harness with no documented advance check is indeterminate.

| Harness | Advance check and grant |
| --- | --- |
| Codex | Documented in this repository (`GLOSSARY.md`): native reviewer agents inherit the parent's effective sandbox and approval policy. Inferred, neither observed nor documented: this skill's reviewers inherit it the same way, and no side-effect-free query of whether a reviewer launch will be approved exists, so the roles are indeterminate unless the session exposes an explicit grant or refusal. |
| Devin | Inferred, neither observed nor documented: no advance check or advance grant for sub-agent launches was found, so the roles are indeterminate unless the session exposes an explicit grant or refusal. |
| Claude Code | Documented in this repository (`deep-review` harness mechanisms): a sub-agent launch can be refused at invocation, and agent tool use follows the user's own permission settings. Inferred, neither observed nor documented: no side-effect-free pre-check of a sub-agent launch exists, so the roles are indeterminate unless the session exposes an explicit grant or refusal. |

## Process

### 1. Pin the fixed point

Use the fixed point supplied by the invoking workflow, if present. Otherwise, use the fixed point explicitly provided by the user. When composed by `/implement`, the fixed point is `BASELINE`. Ask the user for a fixed point only when neither the caller nor the user provided one.

Run the diff once in the parent and keep the output: `git diff --find-renames <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also capture the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents.

Pin both sides of the diff by SHA: the **review base** is `git merge-base <fixed-point> HEAD`, the diff's old side, and the **reviewed head** is `git rev-parse HEAD`, its new side. Label the diff as `<fixed-point>...HEAD` between those SHAs. It is the cumulative change of every reviewed commit, not the change of any one commit.

Then build the anchor context reviewers cite from. Run `git diff --find-renames --name-status <fixed-point>...HEAD` and record, for each changed file, its status, its old-side path at the review base (none for an added file), its new-side path at the reviewed head (none for a deleted file), and each existing side's line count from `git cat-file -p <sha>:<path> | awk 'END { print NR }'`.

### 2. Identify the originating sources

Look for the originating spec, in this order:

1. A source bundle supplied by the caller. For an implementation ticket, this is the ticket for scope and acceptance criteria plus its approved parent or spec for architecture and settled decisions.
2. Issue references in the commit messages, fetched via the workflow in `docs/agents/issue-tracker.md`.
3. A path the user passed as an argument.
4. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
5. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

When the source bundle contains both a ticket and parent, preserve their roles. The ticket controls scope; the approved parent controls architecture. Report contradictions instead of silently choosing one.

### 3. Identify the standards sources

Search the repository for standards documents that apply to the changed files. Include repository guidance such as `AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `STYLEGUIDE.md`, and equivalent documents, plus relevant coding guidance in `README` or `docs` files. Inspect each candidate and record its path and applicable content. If the search finds no applicable standards, record that result; do not invent repository standards.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

Apply the reviewer authorization preflight first, unless the invoking workflow already applied it for this review.

Both prompts carry these **anchor rules**, pasted in full:

- A source anchor names a repository file, its side, and a real line or range: `` `<path>:<start>[-<end>]` (new) `` for the reviewed head, or `(old)` for the review base. Use `(old)` for removed lines and for a deleted or pre-rename path. Use `(new)` for added and current lines.
- Take line numbers only from the hunk headers. In `@@ -a,b +c,d @@`, the first line below the header is old line `a` and new line `c`; a context line advances both counts, a `-` line only the old count, and a `+` line only the new count. A hunk header is not a coordinate. Never cite a line's position in the diff, in this prompt, or in any assembled source bundle, or any other offset that is not a line of the file.
- Cite standards documents and originating sources by path or name and a quotation, not by line number.
- The diff is the cumulative `<fixed-point>...HEAD` change, so attribute a finding to it rather than to a commit. Claim that a particular commit added, removed, or tested something only when you name that commit, the path, and the quoted changed line; the coordinator checks the claim against that commit's own patch. Commit-list order or proximity is not evidence.

**Standards sub-agent prompt** should include:

- The full diff output and commit list.
- The anchor context from step 1 and the anchor rules above.
- The applicable standards-source paths and their contents from step 3, **plus the smell baseline from step 3** pasted in full. The sub-agent has no other access to them. When no applicable standards documents were found, say so explicitly.
- The brief: "Report, per file or hunk where relevant: (a) every place the diff violates a documented standard, citing the standard file and rule; and (b) any baseline smell, naming it and quoting the hunk. Label documented-standard violations Blocking. Label baseline smells Advisory unless they also demonstrate a documented or correctness violation. A documented repo standard overrides the baseline. Skip anything tooling enforces. Anchor every finding that points at code under the anchor rules. Do not run git commands; use the provided diff output. Under 400 words."

**Spec sub-agent prompt** should include:

- The full diff output and commit list.
- The anchor context from step 1 and the anchor rules above.
- The path or fetched contents of every source in the source bundle, with each source's role stated.
- The brief: "Report Blocking findings for: (a) requirements that are missing or partial; (b) behavior that was not requested; (c) requirements whose implementation appears incorrect; and (d) contradictions between ticket scope and approved parent architecture. Quote the controlling source for each finding. Anchor every finding that points at code under the anchor rules. Do not run git commands; use the provided diff output. Under 400 words."

The Standards report is always applicable. The Spec report is applicable when an originating source is available. If no originating source is available, skip the Spec sub-agent, mark the Spec axis as skipped with "no spec available," and let the Standards axis complete.

### 5. Aggregate

Wait until every applicable sub-agent returns a report before aggregating.

Verify every source anchor and commit attribution before aggregating, mechanically and against the pinned SHAs. A finding that points at code must carry at least one anchor; one without an anchor is a failed anchor. A finding with no code to point at, such as a missing requirement, needs none. Check each anchor at the reviewed head for `(new)` and at the review base for `(old)`, using that side's SHA as `<sha>`:

1. Reject an anchor with no side, a line that is not a positive integer, or an end before its start. A file location cited in any other form, such as a line named in prose, is a failed anchor too.
2. Reject it unless `git cat-file -t <sha>:<path>` prints `blob`. A deleted or pre-rename path is checked against the review base, not rejected because the reviewed head lacks it; an added or post-rename path exists only at the reviewed head.
3. Reject it when its end exceeds the line count from `git cat-file -p <sha>:<path> | awk 'END { print NR }'`.

Check each claim that a commit added, removed, or tested something against that commit's own patch. Take the whole patch with rename detection, `git show --format= --find-renames <commit>`, then read only the file section whose old or new path is the claimed path; filtering the command by path instead can show a pure rename as a whole new or deleted file. A pure rename section has no added or removed lines, so it supports no claim. The commit must be in the captured commit list, and the quoted line must be an added (`+`) line for an added or tested claim, or a removed (`-`) line for a removed claim.

Send each failed anchor or claim, with the reason it failed, back to the reviewer that made it and ask once for a correction with evidence; verify the correction the same way. Never present a failed anchor as verified evidence, drop its finding, or substitute an anchor of your own. When an anchor stays unverified, list it with its failure, mark that axis and the overall review **incomplete**, and keep the other axis's verified report. When a commit claim stays unsupported, keep the finding as part of the cumulative diff and mark it visibly as commit attribution undecided, without crediting another commit.

Name the reviewed range as `<fixed-point>...HEAD` with the review base and reviewed head SHAs. Present the reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Light cleaning never changes a finding's anchor, commit attribution, or meaning. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_). When Spec was skipped, retain its heading and state why.

If an applicable sub-agent fails or returns no report, identify which report is missing and why, include any report that did arrive under its axis, and mark the overall review **incomplete**. Never present an incomplete review as a completed aggregate.

End a complete report with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent. For an incomplete review, state that it is incomplete instead of reporting a complete aggregate.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
