# Deterministic deep-review run-state updates

Research date: 2026-10-15. Investigation for [issue #121](https://github.com/mmena1/skills/issues/121), governed by its newest trusted Agent Brief. This is repository research only. It ships no helper, wires nothing into the deep-review skill, and changes no skill text.

**Recommendation: implement candidate C, a script-free clarification of how the coordinator updates the run state, and decline candidate B, the shipped script helper.** Both B and C remove about 93 to 97 percent of the bytes that model-authored whole-record rewrites pass through the coordinator's context. C does it with no new code and no new invocation or permission surface. B's added savings over C are small: 14.8 KiB on the 72 KB record and 3.3 KiB on the 30 KB record. Its added correctness guarantees protect against failures that no evidence has shown, and it costs a shipped executable, a runtime Python dependency, per-harness invocation and permission work, Windows gaps, and a schema copy that can drift from the protocol. No candidate is viable on any harness yet. Every harness label below is a static compatibility assessment, and the [native runtime verification gate](#native-runtime-verification-gate) must pass before the [proposed implementation issue](#proposed-implementation-issue-not-filed) is approved.

## Deliverables

| File | Purpose |
| --- | --- |
| [`synthetic_records.py`](synthetic_records.py) | Deterministic synthetic run-state records of about 72 KB and 30 KB, built from an empty skeleton by an ordered list of persistence steps. |
| [`run_state_helper.py`](run_state_helper.py) | Throwaway prototype of candidate B. Research only. |
| [`test_run_state_helper.py`](test_run_state_helper.py) | 24 runnable tests that demonstrate every property this report claims for B. |
| [`benchmark.py`](benchmark.py) | Replays every step for both records and measures candidates A, B, and C. |

Run from the repository root:

```text
python -m unittest discover -s docs/research/deep-review-run-state-updates -p "test_*.py"
python docs/research/deep-review-run-state-updates/benchmark.py
```

The prototype needs Python 3.9 or newer on a POSIX system, because its lock uses `fcntl.flock` and its reads use `O_NOFOLLOW`. These artifacts live outside the shipped skill and are not installed. `python scripts/check.py` does not run them, and this investigation does not enlarge it.

## What the protocol requires

`skills/deep-review/protocol.md` ("Context capture and persisted run state") requires one coordinator-owned `run-state.json`, or an equivalent single record. It holds the pinned baseline identity and restoration status, scout completion and provenance, canonical hypotheses with original IDs, origins, deduplication evidence, and context references, every completed validator outcome and its evidence, PR discussion retrieval and overlap dispositions, incomplete-run and unattempted-hypothesis status, the runtime acceptance receipt, final report data, cleanup status, and, when publication occurs, the exact publication payload. The context snapshot stays separate. `final-report.md` is optional, and `publication-receipt.json` exists only when publication occurs.

The protocol therefore requires repeated *persistence*, at least at these moments:

- once the baseline is established and verified, and after each restoration;
- after each scout completes or fails, because completed evidence must survive a failed wave;
- once canonical hypotheses exist after deduplication;
- after each validator outcome, because each outcome must be preserved "outside probe state" before the next restoration;
- after PR discussion comparison, for the receipt, final report data, publication payload, and cleanup status.

It does **not** require whole-record reconstruction. It is silent on the update mechanism, so a coordinator may legally re-emit the whole record at every step. It also requires preservation checks before the snapshot and run directory are removed, but does not require the model to perform them by reading and comparing whole records. The protocol already rejects model-authored reconstruction for the analogous context-capture case ("must not use model-authored writes to reconstruct contents"). This investigation asks whether the same reasoning should extend to the run state.

## Evidence boundary

The maintainer-supplied Devin retrospective is not attached to the issue or the repository. Everything it alone supports is labelled **reported, unverified**.

| Claim | Status |
| --- | --- |
| The coordinator repeatedly edited and compared state records of about 72 KB and 30 KB. | Reported, unverified. |
| Which exact operations repeated, and how often. | Reported, unverified. The retrospective's count and sequence are unavailable. The synthetic step lists (32 and 17 steps) are this research's assumption, not the observed count. |
| Which artifact each reported size belonged to. | Reported, unverified. The sizes could be two run states, one run state at two moments, or the run state and `final-report.md`. The benchmark assumes two run-state records from runs of different sizes. |
| The actual token and tool-call overhead observed. | Reported, unverified. No transcript, token count, or tool-call count is available. |
| Whether the Devin coordinator wrote through shell commands or native `write` and `edit` tools. | Reported, unverified. The repository's Devin runs for issue #71 do not record the run-state write mechanism either. |
| The run's preservation checks passed, and no data was lost or corrupted. | Reported, unverified. Nothing in the evidence demonstrates loss or corruption. |
| Context and tool overhead from whole-record rewriting, and its size relative to targeted updates. | Holds from the synthetic benchmark below, under its stated assumptions. |
| The properties claimed for candidate B. | Hold from the prototype's tests. |

## Synthetic records

`synthetic_records.py` builds both records deterministically from a fixed seed and a fixed vocabulary, so every run produces identical bytes.

- **Layout.** UTF-8 JSON with two-space indentation and insertion-ordered keys, the layout every candidate writes. Field names and nesting are this research's assumptions. The protocol fixes contents, not a schema.
- **Contents.** One slot per enumerated item: `baseline.identity` (repository, PR, base and head SHAs, merge ref, tree, worktree and context paths) and `baseline.restorations`; `scouts`, keyed by lens, with agent, status, manifest, timestamps, and provenance; `hypotheses`, with ID, original IDs, origin, title, location, potential severity, concern, evidence, deduplication evidence, and context references; `validator_outcomes`, for static and writable phases, with outcome, evidence, recommendation, and the probe's question and check; `pr_discussion`, with retrieval completeness, timestamp, and dispositions with reasons and links; `run_status`; `runtime_acceptance_receipt`, with all eleven scenario rows; `final_report`; `cleanup`; `publication.payload`, stored as a JSON string so its bytes are exact; and `runtime_constraints`.
- **Sizes.** The `large` profile has 5 scouts, 14 hypotheses, 3 probes, 10 dispositions, and a 6-comment payload, and serializes to 73,163 bytes. The `medium` profile has 2 scouts, 6 hypotheses, 1 probe, 4 dispositions, and a 3-comment payload, and serializes to 31,117 bytes. Prose lengths were tuned to land near the reported sizes.
- **Steps.** Each step is one persistence moment listed above: one per scout, one for all canonical hypotheses, one per validator outcome, one per restoration, and one each for discussion, receipt, final report, payload, and cleanup. Batching steps lowers A's cost roughly in proportion and leaves B and C nearly unchanged.

## Candidates

- **A, model-authored whole-record rewrite.** The current freedom the protocol leaves: the coordinator writes the complete new record with its native write tool at every step. The reported pattern adds a full read-back to compare records.
- **B, fixed script helper.** `run_state_helper.py` with three commands. `init` creates the skeleton in a fresh run directory and marks it as coordinator-owned. `update` applies an all-or-none list of `set` and `append` operations addressed by JSON Pointer, guarded by `--expect-sha256`. `finalize-receipt` writes `publication-receipt.json` from the payload already in the record. It has no delete operation.
- **C, native targeted edit.** The coordinator writes the empty skeleton once, then changes only the fields each step adds or changes with its harness's string-replacement or patch tool: `Edit` in Claude Code, `apply_patch` in Codex, `edit` in Devin. The layout must stay stable so anchors stay unique. A variant adds one read-only JSON validity check after each edit.

Candidates that would give up the single consolidated record, such as per-stage files or a separate append-only journal, were rejected under the brief.

## Measurements

`benchmark.py` counts UTF-8 bytes that pass through the coordinator's context: text it must emit in a tool call and text a tool call returns. B's outputs are measured by running the prototype. C's edits are measured by finding, for each changed region, the smallest old string that occurs exactly once in the file, widening line context until it is unique. Final report prose is excluded because every candidate authors it once.

Large record, 73,163 bytes, 32 steps:

| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite, no comparison | 1,209.8 KiB | 0.0 KiB | 32 | 7.9 KiB | 1,217.7 KiB | 50.2% |
| A, whole-record rewrite plus read-back comparison | 1,209.8 KiB | 1,209.8 KiB | 64 | 7.9 KiB | 2,427.5 KiB | 100.0% |
| B, fixed helper | 76.7 KiB | 3.1 KiB | 33 | 0.5 KiB | 80.2 KiB | 3.3% |
| C, native targeted edit | 87.1 KiB | 0.0 KiB | 33 | 7.9 KiB | 95.0 KiB | 3.9% |
| C plus one validity check per step | 89.6 KiB | 0.1 KiB | 65 | 7.9 KiB | 97.5 KiB | 4.0% |

Medium record, 31,117 bytes, 17 steps:

| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite, no comparison | 282.9 KiB | 0.0 KiB | 17 | 3.9 KiB | 286.8 KiB | 50.3% |
| A, whole-record rewrite plus read-back comparison | 282.9 KiB | 282.9 KiB | 34 | 3.9 KiB | 569.8 KiB | 100.0% |
| B, fixed helper | 33.0 KiB | 1.7 KiB | 18 | 0.5 KiB | 35.2 KiB | 6.2% |
| C, native targeted edit | 34.6 KiB | 0.0 KiB | 18 | 3.9 KiB | 38.5 KiB | 6.8% |
| C plus one validity check per step | 35.9 KiB | 0.0 KiB | 35 | 3.9 KiB | 39.8 KiB | 7.0% |

Per update, from the same runs:

| Per update, emitted by the coordinator | Large mean | Large largest step | Medium mean | Medium largest step |
| --- | --- | --- | --- | --- |
| A, whole-record rewrite | 37.8 KiB | 71.4 KiB | 16.6 KiB | 30.4 KiB |
| B, fixed helper | 2.3 KiB | 22.7 KiB | 1.8 KiB | 8.9 KiB |
| C, native targeted edit | 2.6 KiB | 23.3 KiB | 1.9 KiB | 9.0 KiB |

A with comparison reads back as many bytes as it emits. B reads back about 94 bytes per update, the helper's digest and size. C reads back only the edit tool's short success message, plus 3 bytes read and about 80 bytes of command emitted when a validity check follows. The largest step for B and C is the one that records all canonical hypotheses at once, which is new information either way. At finalization, A and C emit the whole receipt, 7.9 KiB and 3.9 KiB including the payload, while B emits only the receipt metadata and reads back its digest, 0.5 KiB.

How to read these numbers:

- **Token bound.** At 3.5 to 4 bytes per token for JSON-heavy text, A with comparison passes about 620,000 to 710,000 tokens on the large record and about 146,000 to 167,000 on the medium one. B passes about 20,500 to 23,500 and 9,000 to 10,300. C passes about 24,300 to 27,800 and 9,900 to 11,300. The ratio between candidates does not depend on the bytes-per-token assumption.
- **The floor.** The ops documents alone, meaning the new information each step contributes, total 70.4 KiB and 29.6 KiB. B's and C's update emissions stay within about 25 percent of that floor. A's cost is quadratic: each step re-emits everything persisted so far.
- **What separates B and C.** C pays for anchor context (a few lines per edit) and re-emits the payload in the receipt. B pays for command lines and outputs. The difference is 14.8 KiB on the large record and 3.3 KiB on the medium one.
- **Sensitivity.** C counts no read because the coordinator wrote every anchor it edits. Each forced re-read, for example after context compaction or a refused edit, adds at most one full record (71.4 KiB or 30.4 KiB). C stays well below A unless re-reads happen at nearly every step. Tool calls per update are one for A without comparison, B, and C, and two for A with comparison and C with a check.

## Correctness

| Property | A, whole-record rewrite | B, fixed helper | C, native targeted edit |
| --- | --- | --- | --- |
| Atomic replacement | Not established. It depends on each harness's write tool, which no source found documents. | **Demonstrated.** Sibling temporary file, `fsync`, then rename. An injected hard exit after a partial write leaves the previous record byte-identical, and an injected failure removes the temporary file. | Not established, for the same reason as A. It is no worse than today. |
| Unrelated-field preservation | The model re-transcribes every byte at every step, so the whole record is exposed to transcription error each time. | **Demonstrated byte-for-byte.** The serializer is deterministic, and a one-field update changes exactly one line of a 73 KB record. Replaying all steps reproduces the reference record exactly. | Byte-for-byte outside the replaced string, by construction. Observed once below. Only the edited region is exposed to transcription. |
| Schema and update validation | None. | **Demonstrated.** It refuses malformed documents, unknown operations, whole-record and unknown-field writes, type violations, and writes to fixed-key objects. Recorded evidence arrays are append-only, the baseline identity and payload are write-once, a set on an ancestor that contains either is refused, and a multi-operation update applies all or none. | None built in. A read-only JSON validity check catches syntax errors, not schema errors. |
| Concurrent or stale change | None. A rewrite silently overwrites a concurrent change. | **Demonstrated.** A SHA-256 compare-and-swap refuses a stale update, and a held `flock` refuses a second writer. The kernel releases the lock on exit, so a killed helper leaves no stale lock. The first prototype's `O_EXCL` lock file failed that test. | None. Observed below: an edit made after an external change succeeded and silently kept both changes. |
| Traversal, symlink escapes, run-path confinement | Governed only by the harness's permission rules. | **Demonstrated.** It refuses `..` paths, run directories outside the declared root, a symlinked run directory, a symlinked ancestor that escapes the root, a symlinked record (leaving its target untouched), and directories it did not initialize. It writes nothing outside its own files and deletes nothing. | Governed only by the harness's permission rules. |
| Exact payload in the receipt | The model re-emits the payload into the receipt. | **Demonstrated.** The receipt is derived from the recorded payload with its SHA-256, and an existing receipt is never replaced. | Same as A. |

The concurrency rows matter less than they look. The protocol makes the run state coordinator-owned, and no scout or validator writes it, so the realistic risk is a retry or crash, not a race between writers.

**Supplemental observation, not verified execution.** In this investigation's own Claude Code 2.1.300 session (a cloud session in auto mode, not a deep-review coordinator and not a user's own permission settings), candidate C's mechanics were exercised on the large synthetic record in a scratch directory. One `Edit` replaced the cleanup status. The result was byte-identical to the reference record with only that field changed, and it stayed valid JSON. The file had been written by a `python3` command run through `Bash` and inspected only with `grep` and `sha256sum` (`c254bb78…e0491` before editing), never with the `Read` tool. The first `Edit` call nevertheless returned "has been updated successfully", although this session's `Edit` tool description says a prior `Read` is required, so that requirement was not enforced here. After an external `sed` changed `cleanup.leftovers`, a second `Edit` returned the same success message with a note that the file had changed on disk. Afterwards `grep` showed both the second edit and the external change, and `python3 -m json.tool` accepted the file. There was no stale-file refusal. The prototype's tests also invoked candidate B through `Bash` in the same session. Neither observation meets the brief's definition of verified execution.

## Maintenance burden

| | A | B | C |
| --- | --- | --- | --- |
| Code | None. | 315-line helper and 290-line test file in this prototype. A shipped version would also need Windows locking and symlink handling (`msvcrt.locking`; Windows has no `O_NOFOLLOW`), which is more code. | None. One to three sentences of protocol text. |
| New invocation surface | None. | A shipped executable inside the skill directory. The coordinator must resolve its installed path, which differs by harness (`~/.agents/skills` for Codex and Devin, `~/.claude/skills` for Claude Code) and by link or copy installation. It needs a Python interpreter at review time. The installers require Python 3.11 only when installing skills with native agents, which does not guarantee one on a later or remote review host. | None. It uses the native file-edit tool family A already uses. |
| Permission surface | The harness's write tool. | One new shell command to approve on every harness, separately from the shell writes the protocol already needs. | The harness's edit tool, the same permission class as A. |
| Test burden | None. | Its own test suite, which cannot be added to `scripts/check.py` under this brief, so it needs a new CI step. Every future change to the protocol's run-state contents must also change the helper's schema, creating a second source of truth. | Runtime acceptance only. |

## Harness compatibility

Each harness carries exactly one label per candidate. No candidate was invoked by a real deep-review coordinator on any harness, so none carries **Verified execution**, and none is called viable anywhere.

| Candidate | Codex | Devin | Claude Code |
| --- | --- | --- | --- |
| A, whole-record rewrite | Static compatibility assessment | Static compatibility assessment | Static compatibility assessment |
| B, fixed helper | Static compatibility assessment | Static compatibility assessment | Static compatibility assessment |
| C, native targeted edit | Static compatibility assessment | Static compatibility assessment | Static compatibility assessment |

The static assessments draw on documentation, the generated native agent tool lists in `skills/deep-review/harnesses/roles.toml`, and the recorded runtime evidence in `skills/deep-review/runtime-acceptance.md`. The coordinator is the user's own harness session, not a generated role, so it has the harness's full native tool set under the session's permissions. In every harness, the protocol already requires the coordinator to run write-capable shell commands: the context snapshot's fixed `cp`, `git worktree add`, and exact baseline restoration. A coordinator that can run deep-review at all can therefore already execute some shell writes. B adds one more command to approve.

### Devin

The brief requires this evaluation before any script recommendation. This session's network policy blocked direct access to `docs.devin.ai`, as recorded for the issue #70 verification, so the documentation below was read through search results that quote it. Where quoted copies disagree, the disagreement is stated.

- **Permission modes** ([permissions](https://docs.devin.ai/cli/reference/permissions), [essential commands](https://docs.devin.ai/cli/essential-commands), [commands and flags](https://docs.devin.ai/cli/reference/commands)). Normal, the default, auto-approves reads, while "writes and shell commands require your explicit approval". Accept Edits auto-approves file edits inside the workspace, while shell commands and writes outside the workspace still prompt. Smart uses a model to judge other actions and never auto-approves some categories. Bypass auto-approves all tool calls. Autonomous requires `--sandbox`. There, shell commands auto-approve because the OS-level sandbox bounds them, but direct `edit` and `write` calls still prompt because "those tools operate outside the sandbox". A [mirror of the permissions page](https://devin-cli.mintlify.app/reference/permissions) instead lists Autonomous edits as auto-approved, which contradicts the official page. The mode is set by `--permission-mode` or `DEVIN_PERMISSION_MODE`.
- **Rules** ([team settings](https://docs.devin.ai/cli/enterprise/team-settings), [configuration precedence](https://docs.devin.ai/cli/reference/configuration/global-vs-local)). `Exec(cmd)`, `Write(path)`, and `Read(path)` scopes, or bare tool names, go into deny, ask, and allow lists. Deny is checked first, and ask overrides allow. Organization rules apply in every mode. In sandbox sessions, writable roots derive from granted `Write(...)` scopes plus workspace directories ([configuration](https://docs.devin.ai/cli/extensibility/configuration)).
- **Print mode.** `devin -p` runs one non-interactive turn. No documentation found says how an unanswerable prompt is resolved. Repository evidence fills part of the gap: in the issue #71 Devin acceptance runs (Devin CLI 3000.11.3), "the initial print-mode attempt refused a permission-gated tool before analysis", and the coordinator was rerun with a process-local permission mode (`skills/deep-review/runtime-acceptance.md`).
- **Native tools.** The repository grants Devin's writable probe role `write` and `edit`, and its read-only roles `exec`. No source found says that Devin requires file writes to go through `write` and `edit` rather than `exec`.

**Conclusion for Devin.** Shell-based writes are not disallowed, but they are not reliable without configuration. They prompt in Normal and Accept Edits unless an `Exec(...)` allow rule matches, a prompt in print mode was observed to refuse the tool, and they run unprompted only in Autonomous or Bypass mode. Native `edit` and `write` prompt in Normal and Autonomous and run unprompted in Accept Edits inside the workspace. Neither path is unprompted in every mode, and which one the reported coordinator used is unknown. A script helper is therefore **not** established as a cross-harness solution. Per-harness adaptation would have to pair B with an `Exec` allow rule or a permission mode on Devin, which changes the user's configuration. C uses the same `edit` and `write` class that today's whole-record writes use, so it introduces no new Devin permission requirement.

### Codex

The [sandboxing concepts page](https://developers.openai.com/codex/concepts/sandboxing) was read through quoting search results, because direct access was blocked. The common preset is `sandbox_mode = "workspace-write"` with `approval_policy = "on-request"`. Workspace-write permits reads and writes inside the working directory, and a documentation mirror adds temporary directories such as `/tmp`. `on-request` pauses only for actions beyond the sandbox, and `never` never prompts but stays sandboxed. Native agents inherit the parent's sandbox and approval policy, as `skills/deep-review/SKILL.md` records. For B, a `python3` helper writing inside a writable root runs without a prompt under that preset. A run directory outside the writable roots needs approval, for B and C alike. For C, `apply_patch` edits are subject to the same writable roots. The harness's own runtime acceptance records the coordinator's sandbox but never its run-state write mechanism, so neither path is verified.

### Claude Code

The [permissions page](https://code.claude.com/docs/en/permissions) was read directly. Bash commands require approval except a built-in read-only set, and file modification requires approval in the default mode. `acceptEdits` "automatically accepts file edits and common filesystem commands such as `mkdir`, `touch`, `mv`, and `cp`" in the working directories. A `python3` helper is not among those commands, so B prompts even in `acceptEdits` unless a `Bash(python3 <helper path> *)` allow rule exists. `dontAsk` denies anything not pre-approved, so B and C each need an allow rule there. Writes that resolve outside the working directories are not auto-approved in `acceptEdits`. The page also states that Read and Edit deny rules "don't apply to ... arbitrary subprocesses that read or write files indirectly, like a Python or Node script that opens files itself". B's writes would therefore bypass a user's `Edit` rules entirely, governed only by the one `Bash` rule that admits the helper. C stays inside the user's `Edit` rules. No deep-review role sets `permissionMode`, so the user's own settings apply.

## Interaction with protocol invariants

No candidate relaxes any of these, and none changes the record's schema, contents, ownership, or semantics.

- **Cleanup approval.** No candidate deletes anything. B has no delete operation, and its tests confirm it removes nothing. Worktree removal keeps its narrowly scoped authorization, and the snapshot and run directory are still removed only after preservation checks pass.
- **Caller-worktree isolation.** B writes only inside a run directory it initialized, below a declared root that must be the coordinator's run area, never the caller checkout. C edits only the run-state path. Under C, as under A, isolation relies on the coordinator naming the right path within the harness's permissions.
- **Exact baseline restoration.** No candidate touches the pinned worktree. The protocol's ordering stays in force: persist the outcome, then restore. B makes that persistence point atomic. C makes it no less atomic than today.
- **Immutable context snapshot.** No candidate writes to it. B's tests confirm a sibling `context` directory is untouched.
- **Byte-exact publication payload and receipt.** B derives the receipt from the recorded payload and refuses to replace an existing receipt. A and C transcribe the payload once more into the receipt, as today. This is the one place where B has a correctness advantage not matched by C, and it applies only to publishing runs. Nothing so far has shown a transcription mismatch here. If one is ever observed, a single narrow receipt-finalization helper is the bounded follow-up, not a general persistence helper.

## Recommendation

**Implement candidate C as a protocol clarification. Decline candidate B.**

- **Savings.** C removes 96.1 percent of the bytes of A with comparison on the large record and 93.2 percent on the medium one. Against A without comparison, the figures are 92.2 and 86.6 percent. B saves about another 0.6 percentage points.
- **Cost.** C costs one to three sentences of protocol text and no new permission surface on any harness. B would cost about 600 lines of code and tests before Windows support, a new shipped executable with harness-specific path resolution, a runtime Python requirement, one new approval per harness, an `Edit`-rule bypass on Claude Code, unreliable print-mode behavior on Devin, and a second schema that can drift from the protocol.
- **Tradeoffs accepted with C.** There is no atomicity guarantee and no schema validation, both unchanged from today. Concurrent changes go undetected, which matters little for a single-writer record. An edit can produce malformed JSON. Where a harness allows a read-only command without extra approval, one validity check per step catches that for 3 bytes of output, about 80 bytes of command, and one extra tool call per step.
- **Decline condition for C.** If the native runtime verification gate shows that a harness cannot perform targeted edits on the run-state path under its normal permissions, revise this to adapt per harness, or decline for that harness. A failing harness keeps C non-viable there.

### Proposed skill text

The only proposed skill change clarifies how the record is updated. It would sit in `skills/deep-review/protocol.md` after the paragraph that defines `run-state.json`:

> The coordinator creates the run state once and then updates it in place with the harness's targeted file-edit tool, changing only the fields each step adds or changes. It does not re-emit or reconstruct the whole record to make an update, or re-read it only to confirm one. It may re-read the record when it needs current content to place an edit, for example after context compaction or a refused edit.

The record's schema, contents, coordinator ownership, and semantics stay unchanged.

## Native runtime verification gate

These requirements remain unverified for the recommended candidate C on every harness. Each must pass before the implementation issue is approved. Use a local, non-posting review of a committed range with the `docs` and `conventions` scouts, such as the documented `32b5ba1^..32b5ba1`. Validator-outcome updates are exercised only when at least one hypothesis survives, so record whether one did and repeat on another range if none does.

1. **Codex.** Install with `./install.sh --codex`, then start Codex under its normal sandbox and approval policy, with the proposed text applied to the installed protocol. Run `/deep-review` on the chosen range and confirm. Record `codex --version`. Expected: the session JSONL shows the run state created once and every later change made by an `apply_patch` hunk touching only the changed fields, with no whole-record write. Every approval prompt is recorded, and none goes beyond those the run already needed. `python3 -m json.tool run-state.json` succeeds, and every enumerated item is present.
2. **Devin.** Install with `./install.sh --devin`, and run the same review interactively in Normal mode, then with `devin -p` under the mode the user normally uses for print runs. Record `devin --version`. Expected: run-state changes arrive through `edit` calls, not `exec`. For each mode, the receipt records which of `edit`, `write`, and `exec` file writes prompted, ran, or were refused. The final record is valid and complete.
3. **Claude Code.** Install with `./install.sh --claude`, and run the same review under the user's own permission settings. Record `claude --version`. Expected: the transcript shows `Edit` calls touching only changed fields after the initial `Write`, no whole-record `Write` after the first, and each permission prompt recorded. The final record is valid and complete.
4. **Retrospective.** Where the original Devin retrospective is available, confirm or correct each "reported, unverified" claim in the evidence boundary above, especially which artifacts the 72 KB and 30 KB sizes belonged to and whether the coordinator wrote through `exec` or native tools.

## Proposed implementation issue (not filed)

Proposed text for maintainer triage. It is not filed.

> **Title:** Clarify that deep-review updates its run state in place
>
> **Summary:** Add one clarification to `skills/deep-review/protocol.md` so the coordinator creates `run-state.json` once and updates it with the harness's targeted file-edit tool. It never re-emits or reconstructs the whole record to make an update or re-reads it only to confirm one, and it may still re-read the record to place an edit after context compaction or a refused edit.
>
> **Narrow interface:** Protocol text only (see "Proposed skill text" in `docs/research/deep-review-run-state-updates/README.md`). No helper, script, schema, content, ownership, or semantic change. `SKILL.md`, `harnesses/roles.toml`, reviewer bodies, and installers are untouched.
>
> **Expected savings:** On synthetic 72 KB and 30 KB records, bytes through the coordinator's context fall to 3.9 and 6.8 percent of whole-record rewriting with comparison, from about 2.4 MiB to 95 KiB and from 570 KiB to 39 KiB. Per update, the mean emission falls from 37.8 KiB to 2.6 KiB and from 16.6 KiB to 1.9 KiB. Each re-read needed to place an edit adds at most one record.
>
> **Validation scenarios:** `python scripts/check.py` and `git diff --check` pass. The native runtime verification gate in the research report passes on Codex, Devin, and Claude Code, with harness version and evidence recorded in `skills/deep-review/runtime-acceptance.md`. Each run shows targeted edits only after the initial write and a valid, complete final record.
>
> **Blocked by:** the native runtime verification gate in `docs/research/deep-review-run-state-updates/README.md` (human-executed, per harness). A harness that fails it keeps the change non-viable there, and the recommendation must then be revised to adapt per harness or decline.
>
> **Out of scope:** a persistence or finalization helper, changes to the run-state schema or contents, evidence integrity standards, cleanup authorization, scout scheduling, validator-capacity accounting (#118), and probe dependency environments (#119).
