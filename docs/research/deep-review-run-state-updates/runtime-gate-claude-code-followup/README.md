# Claude Code follow-up diagnostic for issue #131

Run date: 2026-10-16. **Diagnostic only. This is not passing evidence for [issue #131](https://github.com/mmena1/skills/issues/131), and it does not claim that the Claude Code gate or the overall gate passed.**

This investigates why the [earlier Claude Code gate run](https://github.com/mmena1/skills/blob/1b633c528a3e83c1948e258f205dc5e6d7ed2088/docs/research/deep-review-run-state-updates/runtime-gate-claude-code/README.md) (commit `1b633c5`) wrote its follow-up run state through inline `python3` scripts, although its full review used one `Write` and targeted `Edit` calls. It then tests a strengthened wording with one focused follow-up run in an isolated installation.

## Findings

1. **The proposed wording did not exclude script writes.** The [research report's text](../README.md#proposed-skill-text) says "the harness's targeted file-edit tool". It names no tool, and it does not forbid a shell command or script. It only forbids re-emitting or reconstructing "the whole record". An inline `python3` script that loads, modifies, and re-dumps the record emits no record text through the model's context, so a coordinator can read it as compliant. Nothing in the protocol addresses the follow-up's need to copy original concern records "verbatim", and a script copies them without transcription. That makes a script the easy path. The wording therefore permits script-based updates and does nothing to discourage them.
2. **With the strengthened wording, the follow-up wrote its run state with native tools only.** The run state was created by one `Write` and changed by one `Edit`. No `Bash` or `python3` call wrote it, and the coordinator never read it back. The final report, which the wording does not cover, was also written with `Write` and `Edit` instead of the earlier heredoc. The original concern records were transcribed exactly, and preservation was byte-exact. There was only one subsequent `Edit`, and no validator ran, so this shows the mechanism, not reliability.
3. **Issue #131's planned scope conflicts with the repository check.** `scripts/check.py` rejects the names `Claude`, `Codex`, and `Devin` in shared deep-review files, `protocol.md` included. Issue #131 asks to change only `protocol.md` and to name each harness's tool there, which cannot pass. The tested form passes: a harness-neutral rule in `protocol.md` plus a per-harness row in `SKILL.md`. That touches a skill entry point, which the issue marks out of scope, so a maintainer has to choose how to resolve this.
4. **The source record is not valid for follow-up acceptance.** H1 and H5 in source record `20261016T142016Z-8d2974` lack four required hypothesis fields, and their validator evidence is a summary. The earlier follow-up and this run's first confirmation both reported "incomplete coverage: none" anyway. The protocol defines incomplete evidence only as the absence of a whole element, not a partly present one. This loss of evidence happened in the full review. It is a separate problem from issue #131 and is described [below](#separate-problem-preserved-hypotheses-and-evidence-are-summarized).
5. **Another full-review test is required.** See [Next test](#next-test).

## Setup

| Item | Value |
| --- | --- |
| Harness | Claude Code 2.1.301, Linux cloud container, model `claude-opus-5-5`, the same as the earlier run. |
| Skill under test | Scratch clone at `3c41b6e`, the base of the earlier run, plus one local, unpushed commit, `167b880`, with the strengthened wording (`setup/strengthened-wording.patch`). |
| Installation | `HOME=<scratch>/home ./install.sh --claude`, run with `CLAUDE_CONFIG_DIR` pointed at the isolated config. The runner script and flags match the earlier run apart from paths: `--permission-mode auto`, `--permission-prompts none`, and `permissions.allow: ["Skill"]`. |
| Production skill | `~/.claude/skills/deep-review` links to `~/.mmena1-skills` at `f6a41e2`. Its links, `protocol.md` SHA-256 (`65d2775a…6eb2a`), clean status, and HEAD are identical before and after. The real `~/.claude/projects` is unchanged. |
| Review target | Fresh full-history clone of `mmena1/skills` on `main` (`3c41b6e`). The preserved source record `20261016T142016Z-8d2974` was copied from the earlier evidence archive into its record root with `cp`, and its SHA-256 (`52f4791c…95965`) matched the archive's `SHA256SUMS`. |
| Command | `/deep-review follow-up 32b5ba1^..1499f65 record=20261016T142016Z-8d2974`, the same as the earlier follow-up. No prompt mentioned issue #131 or how to write the run state. |

### Strengthened wording

`protocol.md`, a new paragraph after the one that defines `run-state.json`:

> The coordinator creates the run state once with the harness's native file-creation tool and then updates it in place with the harness's native targeted file-edit tool, both named under "Run-state writes" in `SKILL.md`. Each update changes only the fields the current step adds or changes. The coordinator never creates, rewrites, or updates the run state through a shell command, an inline or ad-hoc script such as `python3`, `jq`, or `sed`, a heredoc or output redirection, or any other executable, and it never falls back to one when a native write or edit fails or is refused. This applies equally to a follow-up run state: the coordinator writes each selected concern's original record into it with the native creation or edit tool, keeping the source record's values unchanged. It does not re-emit or reconstruct the whole record to make an update, or re-read it only to confirm one. It may re-read the record when it needs current content to place an edit, for example after context compaction or a refused edit. This rule governs only how the run state is written: context capture and record preservation keep their fixed byte-exact `cp` operation and byte-equality verification unchanged.

`SKILL.md`, a new "Run-state writes" row in the harness mechanism table:

| Codex | Devin | Claude Code |
| --- | --- | --- |
| Create `run-state.json` once and make every later change with `apply_patch`, each hunk limited to the changed fields. | Create `run-state.json` once with `write` and make every later change with `edit`. Never use `exec` to create or change it. | Create `run-state.json` once with `Write` and make every later change with `Edit`. Never use `Bash`, including an inline `python3` script or a heredoc, to create or change it. |

`python3 scripts/check.py` passes on the scratch clone with this split. A first draft that named the harnesses in `protocol.md` failed the check with `harness-specific text 'Claude' in shared deep-review content`.

## Run

Session `ec5729b6-61a7-47b3-af78-582b6e35ae58`, run ID `20261016T155535Z-c41f7a`.

1. **Turn 1, discovery and confirmation.** The coordinator offered H1 and H5 for validation and reported "Incomplete coverage: none", while noting that the hypothesis entries were abbreviated.
2. **Human decision.** The maintainer rejected that confirmation. They directed that H1 and H5 be classified as incomplete coverage, that nothing be reconstructed or given an Addressed or Not addressed status, and that the run be authorized only as a local, non-posting diagnostic, proceeding only as far as the follow-up protocol allows. That direction was passed to the coordinator as one message (`transcripts/fu-t2-relayed-reply.txt`). The message did not mention issue #131 or how to write the run state.
3. **Turn 2.** The coordinator took the authorization as confirming the revised scope and did not ask again. It recorded both concerns as incomplete coverage with Incomplete status, launched no validator, created no worktree or context snapshot because no concern was eligible, labeled the run state and final report "DIAGNOSTIC ONLY … not passing acceptance evidence", and preserved the records. It recorded its own "Missing prior evidence" receipt row as FAIL, because the first confirmation had offered the incomplete concerns for validation.

`permission_denials` is empty in both turns, the stream has no permission or classifier events, and no compaction occurred.

## State-changing calls and reads

Every call in both turns is in `analysis/fu-t1-calls.txt` and `analysis/fu-t2-calls.txt`. All other calls were read-only `Bash` commands, such as `git` and `gh` queries, `ls`, and reads of the skill's reference files.

| Turn, index | Tool | Target | Effect | Bytes |
| --- | --- | --- | --- | --- |
| t2, 3 | `Write` | `run-state.json` | Initial creation, including lineage, the original concern records, incomplete coverage, statuses, the receipt, the diagnostic label, and the intended record directory | 8,778 B content |
| t2, 4 | `Write` | `final-report.md` | Creation, with a `CLEANUP_AND_RECORDS_PENDING` placeholder | 4,993 B content |
| t2, 5 | `Edit` | `run-state.json` | `cleanup` changed from pending to its actual outcome | old 61 B, new 123 B |
| t2, 6 | `Edit` | `final-report.md` | Placeholder replaced with the record path | old 36 B, new 215 B |
| t2, 7 | `Bash` | record root | `test -e` guard, `mkdir`, `cp` of `final-report.md`, `cp` of `run-state.json` last, `cmp` of both, then `rm -r` of the run directory after `VERIFIED` | no file content returned |

| Read | Tool and scope | Reason | Bytes through context |
| --- | --- | --- | --- |
| Source `run-state.json` | `Bash` `cat`, whole file (t1, 3) | Follow-up discovery and concern inventory, as the protocol requires | 9,117 B result |
| Source `final-report.md` | `Bash` `cat`, whole file (t1, 4) | Discovery context | part of a 5,922 B result |
| Own `run-state.json` | none | none | 0 B |

There was no `Bash`, `python3`, heredoc, or redirection write to the run state, and no `Read` of it. The `Edit` succeeded without a prior read, as in the earlier full review.

## Correctness

| Check | Result |
| --- | --- |
| JSON validity | Valid, 8,840 B. |
| Replay | Applying the `Write` and the one `Edit` from the transcript reproduces the preserved `run-state.json` byte for byte, and the anchor was unique. |
| Record identity | Every identity field is present, with mode `follow-up`, completeness `incomplete`, and lineage `source_run_id: 20261016T142016Z-8d2974` with no earlier follow-ups. |
| Original concern records | For H1 and H5, the `hypothesis`, the original `outcome` with evidence and recommendation, and the original reviewed head SHA each equal the source record's values exactly as parsed JSON. They are exact copies of what the source holds, and the source holds abbreviated hypotheses. |
| Incomplete coverage | Both concerns are recorded with the missing fields named, and nothing was reconstructed. |
| Preservation | Intended record directory recorded before copying, guard against an existing directory, `run-state.json` copied last, `cmp` verified both files, and no state change after the copy. The run directory was removed only after verification. |
| Source record | SHA-256 unchanged after the run. |
| Cleanup | No worktree was created, `git worktree list` shows only the caller checkout, and the target's status is clean. |
| Publication | Not exercised. The run was local, non-posting, and created no receipt. |

### Defects in this run not caused by the run-state wording

- **`completed_at` written early.** It holds `15:55:35Z`, the `date` output from tool index 1, and the run finished at about `15:56:43Z`. The earlier full review wrote a rounded time four minutes in the future. The earlier follow-up's script read the clock when it finalized. See [Tradeoffs](#tradeoffs).
- **Report claims preservation before it ran.** The final report's "Records: preserved at …" line was edited in before the copy. Had preservation failed, the preserved report would have been wrong. The protocol requires recording the actual cleanup outcome before preservation and recording a preservation failure afterwards. It says nothing about pre-claiming success, but the result can mislead.
- **No worktree or context snapshot for an empty selection.** The protocol says every mechanism other than scouting "runs unchanged", and it has no rule for a run in which no concern is eligible. Skipping both is reasonable, but the protocol does not specify it.

## Verbatim copying with native edits

The follow-up must preserve each selected concern's original record "verbatim". With scripts prohibited, the coordinator copies those values through its own context. It reads the source record (here a 9 KB `cat`) and re-emits the concern values in its `Write`. Here that was about 2 KB for two abbreviated concerns, and it was exact.

- **Size grows with complete records.** A complete record per concern has nine hypothesis fields and the validator's full evidence. The earlier full review's validators returned 3.7 to 4.1 KB each, against about 0.5 KB stored. That suggests roughly 5 KB per concern, so a follow-up on ten concerns would transcribe about 50 KB. That is still far below rewriting the whole record at each step, but it is model-authored copying, with the transcription-error exposure the research attributes to candidate A, applied once to this data.
- **The script path was not byte-exact either.** The earlier `json.load` and `json.dump` script preserved values, not bytes, and "verbatim" is satisfied at the value level in both cases.
- **No deterministic confirmation exists for the copy.** Unlike preservation, nothing checks the copy. The strengthened wording forbids a read only to confirm an update, and a script check is a confirm-only read even when it returns only a boolean. Whether a single read-only value comparison of the copied concern records against the source should be allowed is a maintainer decision. Context capture has the same tension, and there it is solved with a fixed copy operation, not a transcription.
- **Record-copy operations are unaffected.** Context capture and record preservation still use `cp` and `cmp`, the wording says so explicitly, and this run's preservation shows it.

## Missing hypothesis information and delayed persistence

**Missing hypothesis information is an existing protocol violation, not an effect of the clarification.**

- Both scouts in the earlier full review returned complete hypotheses with all nine fields. The `docs` scout's output was 7,004 characters for three hypotheses, and the coordinator sent the full text to each validator.
- When it wrote `run-state.json`, the coordinator kept only `id`, `origins`, `file`, `title`, `potential_severity`, and `context_references`. It added all six hypotheses in one `Edit` whose `new_string` was 2,168 B.
- It also stored each validator's 3.7 to 4.1 KB result as about 0.5 KB of evidence and recommendation.
- The protocol requires the run state to hold "canonical hypotheses" and "every completed validator outcome and evidence", and its Hypothesis definition requires source evidence, expected impact, and a falsification condition. The record therefore breaks the existing contract.
- The run-state list never says that every field of the Hypothesis shape must be stored, and the follow-up's incomplete-evidence rule lists only missing elements. Those two gaps let both follow-ups accept the abbreviated record.
- No control run on the unclarified protocol exists. The applied clarification's emphasis on changing "only the fields each step adds" may encourage compact entries, but the hypotheses field was new in that step, so the wording did not require summarizing it. Whether the wording contributed cannot be determined from this evidence.

**Delayed persistence is a risk that the protocol does not forbid, and its cause is undetermined.**

- In the earlier full review, both scout completions were persisted together after deduplication, H1 to H4 were persisted together, and H5 and H6 outcomes were first written after the worktree was removed.
- The protocol mandates persistence timing in only a few places:
  - preserve completed scout evidence when a scout wave fails;
  - preserve each outcome before a probe restoration;
  - record the cleanup outcome before preservation;
  - record the intended record directory before copying.
- The research's list of per-scout and per-outcome persistence moments is its own inference from the protocol. No writable probe ran, so batching the static outcomes broke no stated rule. It does mean that a crash during the static phase would lose completed outcomes.
- This diagnostic ran no validator, so it could not observe outcome persistence. Here the run state was created once, after every decision was made, and edited once for cleanup. With no intermediate steps, that is consistent with the protocol.
- Whether the clarification encourages batching edits remains untested, because no control exists.

## Tradeoffs

- **Clock values.** Without `Bash` writes, the coordinator cannot stamp the clock into the record directly. It must run `date` and transcribe the output in an `Edit`. Both native-tool runs wrote an inaccurate `completed_at`: one four minutes in the future, the other about a minute early. Taking the time with `date` immediately before the final edit would fix this without a script, but no current text asks for that.
- **Verbatim copy cost.** See [Verbatim copying with native edits](#verbatim-copying-with-native-edits). The copy is bounded and one-time, but it has no deterministic check.
- **Failure handling.** Banning any fallback means a refused or failed `Edit` can only be retried natively after a re-read. The wording does not say what happens when that still fails. Adding a rule would change failure semantics, which issue #131 excludes, so it is left open.
- **Scope of files.** The rule covers only the run state. In this run the coordinator also wrote `final-report.md` natively, but nothing requires it to.
- **Permission surface.** `Write` and `Edit` stay inside the user's edit permission rules, which script writes bypass. Under `auto` mode with prompts disabled, no run-state write was checked or prompted. Behavior under `default` or `acceptEdits` mode, and for a run directory inside the workspace, was not exercised.

## Assessment

- **Compliance.** The revised wording produced compliant run-state writes in this one follow-up: one `Write`, then `Edit`, with no script or shell writes and no fallback. It also replaced the earlier heredoc for the final report.
- **Coverage.** This is one run. Only one subsequent `Edit` occurred, and no validator outcome was persisted. The original concern records copied were abbreviated. The run therefore shows that the revised wording can produce the behavior, not that it does so reliably, and it is not acceptance evidence.
- **Scope.** The wording cannot ship in the form issue #131 describes because of the `check.py` restriction. Shipping it requires a maintainer decision to allow a `SKILL.md` harness-table row, or to keep `protocol.md` harness-neutral and name the tools elsewhere.
- **Gate status.** The Claude Code gate stays failed, as recorded at `1b633c5`, until a complete full review and follow-up pass under the wording that will ship. Codex and Devin remain separate requirements.

## Next test

A full review is required, for three reasons:

- This follow-up never persisted a validator outcome.
- The strengthened wording has not been run in a full review.
- No valid source record exists.

To obtain a valid source record without reconstructing anything:

1. Install the wording intended for shipping, including the `SKILL.md` row if that is the chosen form, in an isolated configuration.
2. Run a local, non-posting full review with the `docs` and `conventions` scouts on a range where at least one hypothesis survives, for example `32b5ba1^..32b5ba1` again.
3. **Before using the record**, compare it with the transcript. Every canonical hypothesis must have all nine fields with the scout's text, and every outcome must carry the validator's evidence, not a summary.
   - If it does not, the record is not a valid source, and the evidence-loss problem below blocks the follow-up part of the gate.
   - Do not repair the record from the transcript. That would be reconstruction.
4. Then run `/deep-review follow-up` on that record against a later head, and record the same call and read inventory as here.

Because the evidence-loss problem may recur, step 3 can fail independently of issue #131. If it does, fix the evidence-loss problem first and repeat the full review.

## Separate problem: preserved hypotheses and evidence are summarized

This is not part of issue #131 and should be triaged separately. A full-review coordinator stored canonical hypotheses without source evidence, expected impact, falsification condition, or suggested validation, and stored validator results as short summaries. The protocol's follow-up rule treats only missing elements as incomplete original evidence, so a later follow-up accepted those summaries as complete. A fix would likely:

- state that the run state stores each canonical hypothesis with every field of the Hypothesis shape and each validator outcome with its full evidence;
- extend the incomplete-evidence rule to an original hypothesis that lacks a required field.

## Evidence

All raw evidence is in [`claude-code-gate-131-followup-evidence.tar.gz`](claude-code-gate-131-followup-evidence.tar.gz), whose `SHA256SUMS` lists every file.

| Evidence | Path in the archive | SHA-256 prefix |
| --- | --- | --- |
| Turn 1 transcript, discovery and first confirmation | `transcripts/fu-t1.jsonl` | `19f2234d` |
| Message passed to the coordinator with the maintainer's direction | `transcripts/fu-t2-relayed-reply.txt` | `c592a942` |
| Turn 2 transcript, with the `Write`, `Edit`, and preservation calls | `transcripts/fu-t2.jsonl` | `7c3bc86c` |
| Every tool call with inputs, results, and byte counts | `analysis/fu-t1-calls.txt` and `analysis/fu-t2-calls.txt` | `8efd5353`, `c7918f51` |
| Preserved follow-up record | `records/20261016T155535Z-c41f7a/run-state.json` and `final-report.md` | `7dc88e50`, `5819a8ef` |
| Strengthened wording, runner, environment, settings, versions, source-record checksum, production snapshots | `setup/` | see `SHA256SUMS` |

The source record `20261016T142016Z-8d2974` is not repeated here. It is in the earlier archive at `1b633c5`, and this run's copy matched it byte for byte. The isolated configuration's session JSONL files are left out, as in the earlier run.
