# Deterministic deep-review run-state updates

Research date: 2026-10-15. Investigation for [issue #121](https://github.com/mmena1/skills/issues/121), governed by its newest trusted Agent Brief. This is repository research only. It ships no helper, wires nothing into the deep-review skill, and changes no skill text. The run-state contract it models is `skills/deep-review/protocol.md` as of `main` at `388a424`, after #125 (separate publication submission and read-back outcomes) and #126 (record identity, preserved records, and follow-up revalidation).

**Recommendation: implement candidate C, a script-free clarification of how the coordinator updates the run state, conditional on the native runtime verification gate showing how each harness reads before it edits. Decline candidate B, the shipped script helper.** When the coordinator can place targeted edits without re-reading the whole record, C cuts the bytes through its context to 3.3 to 6.0 percent of whole-record rewriting with read-back comparison, within about 1 percentage point of B, with no new code and no new invocation or permission surface. When a harness forces a full read before every edit, C falls to about 51 percent, roughly the cost of a rewrite without comparison, so the gate must measure that. B is declined regardless. File-mutating execution through Devin's `exec` tool conflicts with maintainer-reported runtime tool guidance and is classified unsupported there. B would also add a shipped executable, a runtime Python dependency, per-harness approvals, and a schema copy that can drift. No candidate is viable on any harness yet. Every harness label below is a static compatibility assessment, and the [native runtime verification gate](#native-runtime-verification-gate) must pass before the [proposed implementation issue](#proposed-implementation-issue-not-filed) is approved.

## Deliverables

| File | Purpose |
| --- | --- |
| [`synthetic_records.py`](synthetic_records.py) | Deterministic synthetic run-state records: two full reviews of about 72 KB and 30 KB and one follow-up revalidation, each built from its mode's skeleton by an ordered list of persistence steps. |
| [`run_state_helper.py`](run_state_helper.py) | Throwaway prototype of candidate B. Research only. |
| [`test_run_state_helper.py`](test_run_state_helper.py) | 28 runnable tests that demonstrate every property this report claims for B. |
| [`benchmark.py`](benchmark.py) | Replays every step for every profile and measures candidates A, B, and C, including a file-backed sequential replay of C's edits. |
| [`test_benchmark.py`](test_benchmark.py) | 3 tests that C's measured edits apply in sequence and reproduce every reference record exactly. |
| [`test_synthetic_records.py`](test_synthetic_records.py) | 5 fixture-fidelity tests whose expected values are copied from the protocol text: final concern outcomes, the full and follow-up receipt rows, and the PR-wide read-back source. |

Run from the repository root:

```text
python -m unittest discover -s docs/research/deep-review-run-state-updates -p "test_*.py"
python docs/research/deep-review-run-state-updates/benchmark.py
```

The prototype needs Python 3.9 or newer on a POSIX system, because its lock uses `fcntl.flock` and its reads use `O_NOFOLLOW`. These artifacts live outside the shipped skill and are not installed. `python scripts/check.py` does not run them, and this investigation does not enlarge it.

## What the protocol requires

`protocol.md` ("Context capture and persisted run state") requires one coordinator-owned `run-state.json`, or an equivalent single record. It begins with a **record identity**: format version, run ID, mode (`full` or `follow-up`), repository, target kind and key, base and reviewed head SHAs, completion time, completeness, and, only in a follow-up record, lineage naming the source full-review run and earlier follow-ups. It then holds the pinned baseline identity and restoration status, scout completion and provenance, canonical hypotheses with original IDs, origins, deduplication evidence, and context references, every completed validator outcome and its evidence, PR discussion retrieval and overlap dispositions, incomplete-run and unattempted-hypothesis status, the runtime acceptance receipt, final report data, cleanup status, the intended record directory for preservation, and, when publication occurs, the exact publication payload with each entry's canonical concern ID, the submission outcome and its identifiers, the read-back verification outcome with its source, time, and diagnostics, and the created comment identifiers. A follow-up record also preserves each selected concern's original record verbatim and records each status, deferral, and thread state. The context snapshot stays separate. `final-report.md` is optional, and `publication-receipt.json` exists only when publication occurs, recording the submission and verification outcomes separately.

The protocol therefore requires repeated *persistence*, at least at these moments:

- once the record identity and the baseline are established, and after each restoration;
- after each scout completes or fails, because completed evidence must survive a failed wave;
- once canonical hypotheses exist after deduplication, or, in follow-up mode, once the source record and selection are confirmed;
- after each validator outcome, because each outcome must be preserved "outside probe state" before the next restoration;
- before submitting a publication (the final payload, pinned head, account, and start time), after the submission, and after read-back verification;
- after PR discussion comparison, for the receipt and final report data, for the cleanup outcome, for completion, and for the intended record directory before preservation.

It does **not** require whole-record reconstruction. It is silent on the update mechanism, so a coordinator may legally re-emit the whole record at every step. It also does not require model comparison of whole records. Record preservation now copies `run-state.json` last with the fixed `cp` operation (or the selected byte-for-byte equivalent) and verifies byte equality, which is deterministic. The protocol already rejects model-authored reconstruction for context capture ("must not use model-authored writes to reconstruct contents"). This investigation asks whether the same reasoning should extend to run-state updates.

## Evidence boundary

The maintainer-supplied Devin retrospective is not attached to the issue or the repository. Everything it alone supports is labelled **reported, unverified**.

| Claim | Status |
| --- | --- |
| The coordinator repeatedly edited and compared state records of about 72 KB and 30 KB. | Reported, unverified. |
| Which exact operations repeated, and how often. | Reported, unverified. The synthetic step lists (37, 22, and 15 steps) are this research's assumption, not the observed count. |
| Which artifact each reported size belonged to. | Reported, unverified. The sizes could be two run states, one run state at two moments, or the run state and `final-report.md`. The benchmark assumes two full-review run states of different sizes. |
| The actual token and tool-call overhead observed. | Reported, unverified. No transcript, token count, or tool-call count is available. |
| Whether the Devin coordinator wrote through shell commands or native `write` and `edit` tools. | Reported, unverified. The repository's Devin runs for issue #71 do not record the run-state write mechanism either. |
| Devin's `exec` tool guidance says: "DO NOT use it for file operations (reading, writing, editing, searching, finding files) - use the specialized tools instead." | Reported by the maintainer from the earlier Devin runtime investigation, in review of this research. Not recorded in this repository. The Devin version it applies to and whether it is still current are unverified. |
| The run's preservation checks passed, and no data was lost or corrupted. | Reported, unverified. Nothing in the evidence demonstrates loss or corruption. |
| Context and tool overhead from whole-record rewriting, and its size relative to targeted updates. | Holds from the synthetic benchmark below, under its stated assumptions. |
| The properties claimed for candidate B, that C's counted edits apply, and that the fixtures follow the protocol's concern, receipt, and read-back rules. | Hold from the prototype's, benchmark's, and fixture tests. |

## Synthetic records

`synthetic_records.py` builds every record deterministically from a fixed seed and a fixed vocabulary, so every run produces identical bytes.

- **Layout.** UTF-8 JSON with two-space indentation and insertion-ordered keys, the layout every candidate writes. The record identity follows the protocol's field names. Field names and nesting elsewhere are this research's assumptions, since the protocol fixes contents, not a schema.
- **Contents.** One slot per enumerated item: `record`, the identity above, with `lineage` only in a follow-up record; `baseline.identity` and `baseline.restorations`; `scouts`, keyed by lens; `hypotheses`; `validator_outcomes`, for static and writable phases, where a writable adjudication replaces its static `Needs probe` transition as the final outcome; `pr_discussion`; `run_status`; `runtime_acceptance_receipt`, with every full-review scenario row, and in a follow-up record also the 13 follow-up rows, with the full-review-only rows marked not run; `final_report`; `cleanup`; `publication`, with the payload (a JSON string whose entries carry `concern_id`, so its bytes are exact), the pre-submission record, the submission outcome, the read-back verification outcome with the PR-wide comments endpoint as its source, and the comment identifiers; `preservation`, with the intended record directory and any failure; `follow_up`, null in a full review and otherwise holding the source record, the verbatim selected concerns, deferrals, and thread states; and `runtime_constraints`.
- **Profiles.** `large`: a full review with 5 scouts, 14 hypotheses, 3 probes, 10 dispositions, and a 6-comment publication, serializing to 71,548 bytes in 37 steps. `medium`: a full review with 2 scouts, 6 hypotheses, 1 probe, 4 dispositions, and a 3-comment publication, serializing to 30,445 bytes in 22 steps. In both, only final Finding and Unresolved outcomes are compared with PR discussion, given actions, and published. `follow-up`: a follow-up revalidation of the first 5 concerns in the large review's concern inventory (its final Finding and Unresolved outcomes), each preserved with its final original outcome and evidence, with 1 deferred, 1 probe, no scouts, and no publication, because follow-up is read-only toward GitHub by default. It serializes to 32,081 bytes in 15 steps. Prose lengths were tuned so the two full reviews land near the reported sizes.
- **Steps.** Each step is one persistence moment listed above. Batching steps lowers A's cost roughly in proportion and leaves B and C nearly unchanged.

## Candidates

- **A, model-authored whole-record rewrite.** The freedom the protocol currently leaves: the coordinator writes the complete new record with its native write tool at every step. The reported pattern adds a full read-back to compare records.
- **B, fixed script helper.** `run_state_helper.py` with three commands. `init --mode` creates the mode's skeleton in a fresh run directory and marks it as coordinator-owned. `update` applies an all-or-none list of `set` and `append` operations addressed by JSON Pointer, guarded by `--expect-sha256`. `finalize-receipt` writes `publication-receipt.json` from the payload, outcomes, and identifiers already in the record. It has no delete operation.
- **C, native targeted edit.** The coordinator writes its mode's skeleton once, then changes only the fields each step adds or changes with its harness's string-replacement or patch tool: `Edit` in Claude Code, `apply_patch` in Codex, `edit` in Devin. The layout must stay stable so anchors stay unique. A variant adds one read-only JSON validity check after each edit.

Candidates that would give up the single consolidated record, such as per-stage files or a separate append-only journal, were rejected under the brief.

## Measurements

`benchmark.py` counts UTF-8 bytes that pass through the coordinator's context: text it must emit in a tool call and text a tool call returns. B's outputs are measured by running the prototype.

C is measured by a **file-backed sequential replay**. Starting from the skeleton on disk, each step applies string replacements to the real file in sequence. Each edit is found against the file as it stands, as the smallest old string that occurs exactly once there, widened by whole lines until it is unique. The replay asserts that each old string is unique when applied and that the file equals the reference record after every step; `test_benchmark.py` checks every profile. The counted edits are therefore edits a string-replacement tool can actually apply. The oracle that chooses them still knows the exact current file, so **C's main figure is an optimistic bound**: it assumes the coordinator holds every anchor it edits. The read-before-edit row is the pessimistic bound for a harness or session that must read the whole current file before each edit. Final report prose is excluded because every candidate authors it once.

Large full review, 71,548 bytes, 37 steps:

| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite, no comparison | 1,441.0 KiB | 0.0 KiB | 37 | 9.2 KiB | 1,450.2 KiB | 50.2% |
| A, whole-record rewrite plus read-back comparison | 1,441.0 KiB | 1,441.0 KiB | 74 | 9.2 KiB | 2,891.2 KiB | 100.0% |
| B, fixed helper | 76.5 KiB | 3.5 KiB | 38 | 0.4 KiB | 80.4 KiB | 2.8% |
| C, native targeted edit, optimistic bound | 85.0 KiB | 0.0 KiB | 39 | 9.2 KiB | 94.1 KiB | 3.3% |
| C plus one validity check per step | 87.8 KiB | 0.1 KiB | 76 | 9.2 KiB | 97.1 KiB | 3.4% |
| C with a full read before every edit | 85.0 KiB | 1,373.1 KiB | 77 | 9.2 KiB | 1,467.2 KiB | 50.7% |

Medium full review, 30,445 bytes, 22 steps:

| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite, no comparison | 390.8 KiB | 0.0 KiB | 22 | 4.5 KiB | 395.3 KiB | 50.3% |
| A, whole-record rewrite plus read-back comparison | 390.8 KiB | 390.8 KiB | 44 | 4.5 KiB | 786.1 KiB | 100.0% |
| B, fixed helper | 33.6 KiB | 2.1 KiB | 23 | 0.4 KiB | 36.1 KiB | 4.6% |
| C, native targeted edit, optimistic bound | 34.1 KiB | 0.0 KiB | 24 | 4.5 KiB | 38.7 KiB | 4.9% |
| C plus one validity check per step | 35.8 KiB | 0.1 KiB | 46 | 4.5 KiB | 40.5 KiB | 5.1% |
| C with a full read before every edit | 34.1 KiB | 363.0 KiB | 47 | 4.5 KiB | 401.6 KiB | 51.1% |

Follow-up revalidation, 32,081 bytes, 15 steps, no publication:

| Candidate | Emitted by updates | Read by updates | Update tool calls | Receipt finalization | Total through context | Share of A with comparison |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite, no comparison | 334.4 KiB | 0.0 KiB | 15 | 0.0 KiB | 334.4 KiB | 50.0% |
| A, whole-record rewrite plus read-back comparison | 334.4 KiB | 334.4 KiB | 30 | 0.0 KiB | 668.7 KiB | 100.0% |
| B, fixed helper | 32.5 KiB | 1.5 KiB | 16 | 0.0 KiB | 34.0 KiB | 5.1% |
| C, native targeted edit, optimistic bound | 40.1 KiB | 0.0 KiB | 18 | 0.0 KiB | 40.1 KiB | 6.0% |
| C plus one validity check per step | 41.2 KiB | 0.0 KiB | 33 | 0.0 KiB | 41.3 KiB | 6.2% |
| C with a full read before every edit | 40.1 KiB | 306.4 KiB | 35 | 0.0 KiB | 346.5 KiB | 51.8% |

Per update, from the same runs:

| Per update, emitted by the coordinator | Large mean | Large largest step | Medium mean | Medium largest step | Follow-up mean | Follow-up largest step |
| --- | --- | --- | --- | --- | --- | --- |
| A, whole-record rewrite | 38.9 KiB | 69.9 KiB | 17.8 KiB | 29.7 KiB | 22.3 KiB | 31.3 KiB |
| B, fixed helper | 2.0 KiB | 21.4 KiB | 1.5 KiB | 8.2 KiB | 2.0 KiB | 16.0 KiB |
| C, native targeted edit | 2.2 KiB | 22.0 KiB | 1.4 KiB | 8.3 KiB | 2.2 KiB | 16.9 KiB |

A with comparison reads back as many bytes as it emits. B reads back about 94 bytes per update, the helper's digest and size. In its optimistic bound, C reads back only the edit tool's short success message, plus 3 bytes read and about 80 bytes of command emitted when a validity check follows. In its pessimistic bound, C reads the whole current file before each edit. The largest step for B and C is the one that records all canonical hypotheses or selected concerns at once, which is new information either way. At finalization, A and C emit the whole receipt, 9.2 KiB and 4.5 KiB including the payload and both outcomes, while B emits only its command and reads back its digest, 0.4 KiB.

How to read these numbers:

- **Token bound.** At 3.5 to 4 bytes per token for JSON-heavy text, A with comparison passes about 740,000 to 850,000 tokens on the large record, 200,000 to 230,000 on the medium one, and 170,000 to 195,000 on the follow-up. B passes about 21,000 to 24,000, 9,000 to 11,000, and 9,000 to 10,000. C's optimistic bound passes about 24,000 to 28,000, 10,000 to 11,000, and 10,000 to 12,000. The ratio between candidates does not depend on the bytes-per-token assumption.
- **The floor.** The ops documents alone, meaning the new information each step contributes, total 69.2 KiB, 29.2 KiB, and 29.4 KiB. B's update emissions stay within about 15 percent of that floor and C's within about 40 percent. A's cost is quadratic: each step re-emits everything persisted so far.
- **What separates B and C.** In the optimistic bound, C pays for anchor context and re-emits the receipt, while B pays for command lines and outputs. The difference is 13.7 KiB, 2.6 KiB, and 6.1 KiB.
- **Read-before-edit sensitivity.** C's advantage depends almost entirely on not re-reading the whole record per edit. With a full read before every edit, C costs 50.7 to 51.8 percent of A with comparison, about the same as A without comparison. Partial or occasional re-reads, for example one full read after each context compaction, fall between the two bounds, each adding at most one record. The proposed clarification still removes confirm-only read-back, which alone halves A's cost, but the remaining savings exist only where a harness can place edits without a full read each time. That is now a required measurement in the native runtime verification gate.

## Correctness

| Property | A, whole-record rewrite | B, fixed helper | C, native targeted edit |
| --- | --- | --- | --- |
| Atomic replacement | Not established. It depends on each harness's write tool, which no source found documents. | **Demonstrated.** Sibling temporary file, `fsync`, then rename. An injected hard exit after a partial write leaves the previous record byte-identical, and an injected failure removes the temporary file. | Not established, for the same reason as A. It is no worse than today. |
| Unrelated-field preservation | The model re-transcribes every byte at every step, so the whole record is exposed to transcription error each time. | **Demonstrated byte-for-byte.** The serializer is deterministic, and a one-field update changes exactly one line of a 72 KB record. Replaying every profile's steps reproduces each reference record exactly. | Byte-for-byte outside the replaced string, by construction. The replay reproduces every reference record exactly, and the session observation below agrees. Only the edited region is exposed to transcription. |
| Schema and update validation | None. | **Demonstrated.** It refuses malformed documents, unknown operations, whole-record and unknown-field writes, type violations, writes to fixed-key objects, and lineage or follow-up state in a full record. Recorded evidence arrays, comment identifiers, and follow-up selections are append-only. The record identity, baseline identity, payload, and submission outcome are write-once. A set on an ancestor that contains any of them is refused, and a multi-operation update applies all or none. | None built in. A read-only JSON validity check catches syntax errors, not schema errors. |
| Concurrent or stale change | None. A rewrite silently overwrites a concurrent change. | **Demonstrated.** A SHA-256 compare-and-swap refuses a stale update, and a held `flock` refuses a second writer. The kernel releases the lock on exit, so a killed helper leaves no stale lock. The first prototype's `O_EXCL` lock file failed that test. | None. Observed below: an edit made after an external change succeeded and silently kept both changes. |
| Traversal, symlink escapes, run-path confinement | Governed only by the harness's permission rules. | **Demonstrated.** It refuses `..` paths, run directories outside the declared root, a symlinked run directory, a symlinked ancestor that escapes the root, a symlinked record (leaving its target untouched), and directories it did not initialize. It writes nothing outside its own files and deletes nothing. | Governed only by the harness's permission rules. |
| Exact payload and outcomes in the receipt | The model re-emits the payload and both outcomes into the receipt. | **Demonstrated.** The receipt is derived from the recorded payload, with its SHA-256, the submission and verification outcomes kept separate, and the comment identifiers. It is refused before a submission outcome exists, and an existing receipt is never replaced. | Same as A. |

The concurrency rows matter less than they look. The protocol makes the run state coordinator-owned, and no scout or validator writes it, so the realistic risk is a retry or crash, not a race between writers.

**Supplemental observation, not verified execution.** In this investigation's own Claude Code 2.1.300 session (a cloud session in auto mode, not a deep-review coordinator and not a user's own permission settings), candidate C's mechanics were exercised on the earlier large synthetic record in a scratch directory. The file had been written by a `python3` command run through `Bash` and inspected only with `grep` and `sha256sum` (`c254bb78…e0491` before editing), never with the `Read` tool. The first `Edit` call nevertheless returned "has been updated successfully", although this session's `Edit` tool description says a prior `Read` is required, so that requirement was not enforced here. After an external `sed` changed `cleanup.leftovers`, a second `Edit` returned the same success message with a note that the file had changed on disk. Afterwards `grep` showed both the second edit and the external change, and `python3 -m json.tool` accepted the file. There was no stale-file refusal. The prototype's tests also invoked candidate B through `Bash` in the same session. Neither observation meets the brief's definition of verified execution, and one unexplained success does not establish that Claude Code never requires a read before an edit.

## Maintenance burden

| | A | B | C |
| --- | --- | --- | --- |
| Code | None. | 363-line helper and 324-line test file in this prototype. A shipped version would also need Windows locking and symlink handling (`msvcrt.locking`; Windows has no `O_NOFOLLOW`), which is more code. | None. One to three sentences of protocol text. |
| New invocation surface | None. | A shipped executable inside the skill directory. The coordinator must resolve its installed path, which differs by harness (`~/.agents/skills` for Codex and Devin, `~/.claude/skills` for Claude Code) and by link or copy installation. It needs a Python interpreter at review time. The installers require Python 3.11 only when installing skills with native agents, which does not guarantee one on a later or remote review host. On Devin it would run through `exec`, which is unsupported for file operations (below). | None. It uses the native file-edit tool family A already uses. |
| Permission surface | The harness's write tool. | One new shell command to approve on Codex and Claude Code. On Devin, no approval makes it supported, because the restriction is a tool-use instruction rather than a prompt. | The harness's edit tool, the same permission class as A. |
| Test burden | None. | Its own test suite, which cannot be added to `scripts/check.py` under this brief, so it needs a new CI step. The contract already moved twice during this investigation (#125 and #126), and each move had to be mirrored in the helper's schema, a second source of truth. | Runtime acceptance only. |

## Harness compatibility

Each harness carries exactly one label per candidate. No candidate was invoked by a real deep-review coordinator on any harness, so none carries **Verified execution**, and none is called viable anywhere.

| Candidate | Codex | Devin | Claude Code |
| --- | --- | --- | --- |
| A, whole-record rewrite | Static compatibility assessment | Static compatibility assessment | Static compatibility assessment |
| B, fixed helper | Static compatibility assessment | Static compatibility assessment: unsupported | Static compatibility assessment |
| C, native targeted edit | Static compatibility assessment | Static compatibility assessment | Static compatibility assessment |

The static assessments draw on documentation, the generated native agent tool lists in `skills/deep-review/harnesses/roles.toml`, the recorded runtime evidence in `skills/deep-review/runtime-acceptance.md`, and the maintainer-reported Devin tool guidance above. The coordinator is the user's own harness session, not a generated role, so it has the harness's full native tool set under the session's permissions. The protocol names a fixed `cp` for context capture and record preservation, but allows "the harness's byte-for-byte equivalent selected before the run", so it does not by itself establish that shell-based file writes are permitted on every harness.

### Devin

The brief requires this evaluation before any script recommendation. This session's network policy blocked direct access to `docs.devin.ai`, as recorded for the issue #70 verification, so the documentation below was read through search results that quote it. Where quoted copies disagree, the disagreement is stated.

- **Tool-use restriction.** The maintainer reports that Devin's `exec` tool guidance, quoted during the earlier Devin runtime investigation, says: "DO NOT use it for file operations (reading, writing, editing, searching, finding files) - use the specialized tools instead." This is an operation-level instruction about which tool may perform file operations. It is separate from permission-mode approval. An `Exec(...)` allow rule or Bypass mode answers an approval prompt; it does not make a forbidden use of the tool permitted. Its applicable Devin version and current wording are unverified.
- **Permission modes** ([permissions](https://docs.devin.ai/cli/reference/permissions), [essential commands](https://docs.devin.ai/cli/essential-commands), [commands and flags](https://docs.devin.ai/cli/reference/commands)). Normal, the default, auto-approves reads, while "writes and shell commands require your explicit approval". Accept Edits auto-approves file edits inside the workspace, while shell commands and writes outside the workspace still prompt. Smart uses a model to judge other actions and never auto-approves some categories. Bypass auto-approves all tool calls. Autonomous requires `--sandbox`; shell commands auto-approve inside the OS-level sandbox, but direct `edit` and `write` calls still prompt because "those tools operate outside the sandbox". A [mirror of the permissions page](https://devin-cli.mintlify.app/reference/permissions) instead lists Autonomous edits as auto-approved, which contradicts the official page.
- **Rules** ([team settings](https://docs.devin.ai/cli/enterprise/team-settings), [configuration precedence](https://docs.devin.ai/cli/reference/configuration/global-vs-local)). `Exec(cmd)`, `Write(path)`, and `Read(path)` scopes, or bare tool names, go into deny, ask, and allow lists. Deny is checked first, and ask overrides allow. Organization rules apply in every mode.
- **Print mode.** `devin -p` runs one non-interactive turn. No documentation found says how an unanswerable prompt is resolved. In the issue #71 Devin acceptance runs (Devin CLI 3000.11.3), "the initial print-mode attempt refused a permission-gated tool before analysis", and the coordinator was rerun with a process-local permission mode (`skills/deep-review/runtime-acceptance.md`).
- **Native tools.** The repository grants Devin's writable probe role `write` and `edit`, and its read-only roles `exec`, consistent with the guidance above.

**Conclusion for Devin.** File-mutating helper execution through `exec` is **unsupported** on Devin unless an allowed invocation mechanism is demonstrated. The reported guidance assigns file writing and editing to the specialized tools, and no documented or observed mechanism lets a repository-shipped script perform them in its place. Permission configuration cannot change that classification, so per-harness adaptation through an `Exec` allow rule is not available. B is therefore not a cross-harness solution. C uses Devin's `edit` and `write`, the tools the guidance names for file operations and the same class that today's whole-record writes use, so it introduces no new Devin requirement. Whether Devin's `edit` needs a prior read is unknown and is part of the gate.

The same guidance may bear on the protocol's fixed `cp` for context capture and record preservation on Devin. The protocol already allows a harness-selected byte-for-byte equivalent there. Deciding what that equivalent is on Devin is outside this issue and is noted for the maintainer.

### Codex

The [sandboxing concepts page](https://developers.openai.com/codex/concepts/sandboxing) was read through quoting search results, because direct access was blocked. The common preset is `sandbox_mode = "workspace-write"` with `approval_policy = "on-request"`. Workspace-write permits reads and writes inside the working directory, and a documentation mirror adds temporary directories such as `/tmp`. `on-request` pauses only for actions beyond the sandbox, and `never` never prompts but stays sandboxed. Native agents inherit the parent's sandbox and approval policy, as `skills/deep-review/SKILL.md` records. For B, a `python3` helper writing inside a writable root runs without a prompt under that preset. A run directory outside the writable roots needs approval, for B and C alike. For C, `apply_patch` hunks carry their own context lines, and no documented requirement to read the whole file first was found, but the coordinator must still hold current anchor text. The harness's runtime acceptance records the coordinator's sandbox but never its run-state write mechanism, so neither path is verified.

### Claude Code

The [permissions page](https://code.claude.com/docs/en/permissions) was read directly. Bash commands require approval except a built-in read-only set, and file modification requires approval in the default mode. `acceptEdits` "automatically accepts file edits and common filesystem commands such as `mkdir`, `touch`, `mv`, and `cp`" in the working directories. A `python3` helper is not among those commands, so B prompts even in `acceptEdits` unless a `Bash(python3 <helper path> *)` allow rule exists. `dontAsk` denies anything not pre-approved, so B and C each need an allow rule there. Writes that resolve outside the working directories are not auto-approved in `acceptEdits`. The page also states that Read and Edit deny rules "don't apply to ... arbitrary subprocesses that read or write files indirectly, like a Python or Node script that opens files itself", so B's writes would bypass a user's `Edit` rules entirely while C stays inside them. For C's read cost, this session's `Edit` tool description says a prior `Read` is required, and the harness tracks file state after its own `Write` and `Edit` calls, so a coordinator that created the record normally needs no re-read until the file changes externally or context is compacted. That compaction behavior is unverified, and the one observed `Edit` without a `Read` is unexplained. No deep-review role sets `permissionMode`, so the user's own settings apply.

## Interaction with protocol invariants

No candidate relaxes any of these, and none changes the record's schema, contents, ownership, or semantics.

- **Cleanup approval.** No candidate deletes anything. B has no delete operation, and its tests confirm it removes nothing. Worktree removal keeps its narrowly scoped authorization.
- **Record preservation.** No candidate copies records. Preservation stays the protocol's fixed copy into the record root, `run-state.json` last, with byte-equality verification. The run state must not change after that copy, and every candidate's last update is the intended record directory, before it. B's root confinement covers the run directory only and never the record root.
- **Caller-worktree isolation.** B writes only inside a run directory it initialized, below a declared root that must be the coordinator's run area, never the caller checkout. C edits only the run-state path. Under C, as under A, isolation relies on the coordinator naming the right path within the harness's permissions.
- **Exact baseline restoration.** No candidate touches the pinned worktree. The protocol's ordering stays in force: persist the outcome, then restore. B makes that persistence point atomic. C makes it no less atomic than today.
- **Immutable context snapshot.** No candidate writes to it. B's tests confirm a sibling `context` directory is untouched.
- **Byte-exact publication payload and receipt.** B derives the receipt from the recorded payload and outcomes and refuses to replace an existing receipt. A and C transcribe them once more into the receipt, as today. This is the one place where B has a correctness advantage not matched by C, and it applies only to publishing runs. Nothing so far has shown a transcription mismatch here. If one is ever observed, a narrow receipt-finalization mechanism is the bounded follow-up, not a general persistence helper, and on Devin it would also have to avoid `exec`-based file writes.

## Recommendation

**Implement candidate C as a protocol clarification, conditional on the native runtime verification gate. Decline candidate B.**

- **Savings.** In its optimistic bound, C removes 96.7, 95.1, and 94.0 percent of the bytes of A with comparison on the large, medium, and follow-up records. Against A without comparison, the figures are 93.5, 90.2, and 88.0 percent. B saves about another 0.3 to 0.9 percentage points. In its pessimistic bound, with a full read before every edit, C removes only about 48 to 49 percent, essentially the confirm-only read-back the clarification forbids. The gate decides where each harness falls.
- **Why decline B.** It is unsupported on Devin, so it is not a cross-harness solution. Elsewhere it would cost about 690 lines of code and tests before Windows support, a shipped executable with harness-specific path resolution, a runtime Python requirement, one new approval per harness, an `Edit`-rule bypass on Claude Code, and a schema that this investigation already had to update twice to follow the protocol. Its only unmatched advantages are atomicity, schema enforcement, and receipt derivation, protecting against failures no evidence has shown.
- **Tradeoffs accepted with C.** There is no atomicity guarantee and no schema validation, both unchanged from today. Concurrent changes go undetected, which matters little for a single-writer record. An edit can produce malformed JSON. Where a harness allows a read-only command without extra approval, one validity check per step catches that for 3 bytes of output, about 80 bytes of command, and one extra tool call.
- **Decline condition for C.** If the gate shows that a harness cannot perform targeted edits on the run-state path under its normal permissions, or must read the whole record before every edit, revise this to adapt per harness, or decline for that harness. A failing harness keeps C non-viable there.

### Proposed skill text

The only proposed skill change clarifies how the record is updated. It would sit in `skills/deep-review/protocol.md` after the paragraph that defines `run-state.json`:

> The coordinator creates the run state once and then updates it in place with the harness's targeted file-edit tool, changing only the fields each step adds or changes. It does not re-emit or reconstruct the whole record to make an update, or re-read it only to confirm one. It may re-read the record when it needs current content to place an edit, for example after context compaction or a refused edit.

The record's schema, contents, record identity, coordinator ownership, preservation, and semantics stay unchanged.

## Native runtime verification gate

These requirements remain unverified for the recommended candidate C on every harness. Each must pass before the implementation issue is approved. Use a local, non-posting review of a committed range with the `docs` and `conventions` scouts, such as the documented `32b5ba1^..32b5ba1`. Validator-outcome updates are exercised only when at least one hypothesis survives, so record whether one did and repeat on another range if none does. Then run one `/deep-review follow-up` against that review's preserved record. For every run, also record each read of `run-state.json` the coordinator makes: its tool, whether it read the whole file or a range, and why.

1. **Codex.** Install with `./install.sh --codex`, then start Codex under its normal sandbox and approval policy, with the proposed text applied to the installed protocol. Run `/deep-review` on the chosen range and confirm. Record `codex --version`. Expected: the session JSONL shows the run state created once and every later change made by an `apply_patch` hunk touching only the changed fields, with no whole-record write and no whole-file read per edit. Every approval prompt is recorded, and none goes beyond those the run already needed. `python3 -m json.tool run-state.json` succeeds, and every enumerated item, including the record identity, is present in the preserved record.
2. **Devin.** Install with `./install.sh --devin`, and run the same review interactively in Normal mode, then with `devin -p` under the mode the user normally uses for print runs. Record `devin --version` and the current `exec` tool guidance text. Expected: run-state changes arrive through `edit` calls, never `exec`. For each mode, the receipt records which `edit` and `write` calls prompted, ran, or were refused, and whether `edit` required a prior read. The final record is valid and complete.
3. **Claude Code.** Install with `./install.sh --claude`, and run the same review under the user's own permission settings. Record `claude --version`. Expected: the transcript shows `Edit` calls touching only changed fields after the initial `Write`, no whole-record `Write` after the first, each permission prompt recorded, and each `Read` of the record with its reason. The final record is valid and complete.
4. **Read cost.** For each harness, compare the observed bytes read from `run-state.json` against the optimistic and pessimistic bounds above. If a harness reads the whole record before most edits, C's savings there are about half of A's cost, and the recommendation must be revised for that harness.
5. **Retrospective.** Where the original Devin retrospective is available, confirm or correct each "reported, unverified" claim in the evidence boundary above, especially which artifacts the 72 KB and 30 KB sizes belonged to and whether the coordinator wrote through `exec` or native tools.

## Proposed implementation issue (not filed)

Proposed text for maintainer triage. It is not filed.

> **Title:** Clarify that deep-review updates its run state in place
>
> **Summary:** Add one clarification to `skills/deep-review/protocol.md` so the coordinator creates `run-state.json` once and updates it with the harness's targeted file-edit tool. It never re-emits or reconstructs the whole record to make an update or re-reads it only to confirm one, and it may still re-read the record to place an edit after context compaction or a refused edit.
>
> **Narrow interface:** Protocol text only (see "Proposed skill text" in `docs/research/deep-review-run-state-updates/README.md`). No helper, script, schema, content, record identity, preservation, ownership, or semantic change. `SKILL.md`, `harnesses/roles.toml`, reviewer bodies, and installers are untouched.
>
> **Expected savings:** On synthetic full-review records of 72 KB and 30 KB and a 32 KB follow-up record, under the protocol as of `388a424`, bytes through the coordinator's context fall to 3.3, 4.9, and 6.0 percent of whole-record rewriting with comparison when edits are placed without full re-reads, and to about 51 percent when every edit needs a full read. Per update, the mean emission falls from 38.9 KiB to 2.2 KiB on the large record.
>
> **Validation scenarios:** `python scripts/check.py` and `git diff --check` pass. The native runtime verification gate in the research report passes on Codex, Devin, and Claude Code for a full review and a follow-up, with harness version, read cost, and evidence recorded in `skills/deep-review/runtime-acceptance.md`. Each run shows targeted edits only after the initial write and a valid, complete preserved record.
>
> **Blocked by:** the native runtime verification gate in `docs/research/deep-review-run-state-updates/README.md` (human-executed, per harness). A harness that fails it keeps the change non-viable there, and the recommendation must then be revised to adapt per harness or decline.
>
> **Out of scope:** a persistence or finalization helper, changes to the run-state schema or contents, evidence integrity standards, record preservation, cleanup authorization, scout scheduling, validator-capacity accounting (#118), and probe dependency environments (#119).
