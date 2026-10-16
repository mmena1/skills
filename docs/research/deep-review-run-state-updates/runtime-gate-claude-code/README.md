# Claude Code runtime gate evidence for issue #131

Run date: 2026-10-16. This records the Claude Code portion of the native runtime verification gate in [issue #131](https://github.com/mmena1/skills/issues/131), following the [research report's gate](../README.md#native-runtime-verification-gate). It does not claim that the overall gate passed: Codex and Devin remain separate requirements, and a maintainer must review this evidence before any readiness change.

**Result: Claude Code FAIL for the gate as a whole.** The full review met every observed mechanism requirement: one initial `Write`, then only targeted `Edit` calls, with no read of the record. The follow-up run, working from the same clarified protocol, never used `Write` or `Edit` for the run state. It created and twice rewrote the whole record through `Bash` with inline `python3` scripts. With one run per mode, that is one compliant run and one non-compliant run, so reliable Edit-only maintenance is not established.

**Executor caveat.** The issue asks for human-executed evidence. A Claude Code agent session executed this run in a claude.ai cloud container, and acted as the confirming human at each confirmation gate. Whether that satisfies "human-executed" is for the maintainer to decide.

## Setup

| Item | Value |
| --- | --- |
| Harness | Claude Code 2.1.301 (`claude --version`), Linux cloud container. The coordinator ran on `claude-opus-5-5`, the session's model. |
| Normally installed `/deep-review` | `~/.claude/skills/deep-review` is a symlink to a separate checkout, `~/.mmena1-skills`, at `f6a41e2`. That is 13 commits behind `main` (`3c41b6e`), and its protocol has no follow-up mode, so it could not run this gate. It was left untouched: its links and its `protocol.md` SHA-256 (`65d2775a…6eb2a`) were identical before and after. |
| Skill under test | A scratch clone of `mmena1/skills` at `3c41b6e`, plus one local, unpushed commit, `c7f7bee`. That commit inserts the research report's proposed text verbatim as a new paragraph after the paragraph that defines `run-state.json` in `skills/deep-review/protocol.md` (`setup/protocol-clarification.patch`). No tracked repository file was changed for the test. |
| Installation | `HOME=<scratch>/home ./install.sh --claude` from the scratch clone, which linked the skills and generated native agents into an isolated config directory. The coordinator ran with `CLAUDE_CONFIG_DIR` pointed there, so the real `~/.claude` was never read or written by the test runs. |
| Review target | A separate clean full-history clone of `mmena1/skills`. Records were preserved to its own `.git/deep-review/records/`. |
| Invocation | Headless `claude -p` turns, resumed with `--resume` to answer each confirmation (`setup/turn.sh`). Prompts were the bare slash commands and replies of `confirm, with docs and conventions` and `confirm`; nothing mentioned run-state handling. |

### Effective permissions

This cloud session runs in `auto` mode, and its launcher settings allow only `Skill`. The coordinator ran with `--permission-mode auto`, the same `permissions.allow: ["Skill"]` (`setup/settings.json`), and `--permission-prompts none`. That last flag is stricter, not looser: it denies automatically anything that would prompt, because no person can answer in print mode. No managed settings file exists. The launcher's Stop hook, a cloud git-hygiene hook rather than a permission rule, was omitted. No permission was loosened.

This approximates the user's settings rather than reproducing an interactive, human-attended session. Every run-state write targeted the run directory, which the coordinator placed in its own session scratchpad under `/tmp/claude-0/`. `Edit` permission behavior for a run state elsewhere, such as inside the workspace, was not exercised.

## Runs

| Run | Command | Outcome |
| --- | --- | --- |
| Full review, run ID `20261016T142016Z-8d2974`, session `472fab68-5ca7-4c10-80ea-5ed7be9da43e` | `/deep-review 32b5ba1^..32b5ba1`, selecting `docs` and `conventions` | Complete, local and non-posting (mmena1/skills#20 is closed). Two concurrent scouts produced 6 hypotheses, kept as 6 after dedupe. Each went to its own `deep-review-validator-static` invocation, capacity-bounded at 4 slots with refills. Results: 2 Findings (H1, H5) and 4 Disproved. No `Needs probe`, so the writable phase was not entered. |
| Follow-up, run ID `20261016T143007Z-8bc27d`, session `21713ef3-79ba-4893-98b3-00cb1c87948d` | `/deep-review follow-up 32b5ba1^..1499f65 record=20261016T142016Z-8d2974` | Complete. Selection `all` resolved to H1 and H5. H1 Addressed, citing `1499f65`; H5 Not addressed (low). Lineage names the source run. |

A hypothesis reached validator adjudication in both runs, so validator-outcome persistence was exercised and no other range was needed.

## Requirements

| Requirement | Status | Observed evidence |
| --- | --- | --- |
| Harness version recorded | PASS | `claude --version` gives `2.1.301 (Claude Code)`, and both receipts record `Claude Code 2.1.301 (Linux, auto mode)`. |
| User's own permission settings | NOT VERIFIED | Approximated as described above: auto mode, prompts auto-denied, isolated config. No interactive session was run. |
| Full review: run state created once with `Write` | PASS | One `Write` of 2,142 B at 14:20:28Z, after the worktree and baseline were set (`transcripts/full-t2.jsonl`, tool index 5). |
| Full review: later updates only by targeted `Edit` | PASS | Five `Edit` calls followed, at tool indexes 32, 60, 67, 68, and 69, with `old_string` anchors of 42, 19, 254, 93, and 50 B. No later `Write` and no `Bash` write touched the record. Replaying the `Write` and the five edits in order reproduces the preserved `run-state.json` byte for byte, and every anchor was unique when applied. |
| Follow-up: run state created once with `Write` | FAIL | Never used `Write`. Tool index 4 created the record with `json.dump` from an inline `python3 -I` script run through `Bash`. That script copied the original concern objects from the source record programmatically. |
| Follow-up: later updates only by targeted `Edit` | FAIL | Never used `Edit`. Tool indexes 16 and 18 each loaded, modified, and re-dumped the whole record with inline `python3`, which is whole-file rewriting by an ad-hoc script. The model did not re-emit the record through its context. The follow-up's `final-report.md` was also written by a `Bash` heredoc. |
| Edits required prior reads | PASS (observed); NOT EXERCISED after compaction | All five `Edit` calls succeeded without any `Read` of the record. The `Write` and each `Edit` result told the coordinator that its file state was current and needed no read-back. No compaction occurred in any run. |
| Every run-state read recorded with tool, scope, reason, and bytes | PASS | See [Reads](#reads). Neither coordinator read its own record through context. |
| Permission prompts, refusals, and recovery | PASS (zero observed); recovery NOT EXERCISED | `permission_denials` is empty in all four turns. The auto-mode classifier checked some `Agent` calls and one `Bash` call and approved each one. No run-state `Write` or `Edit` was checked, prompted, or refused, and no failed or refused edit occurred, so recovery was not exercised. |
| JSON validity | PASS | `python3 -m json.tool` accepts both preserved records. The full-review coordinator also ran one subprocess `json.load` check before preserving. |
| Record identity and completeness | PASS, with two content defects | Both records carry every identity field, and only the follow-up record has `lineage`. Defect 1: the full review wrote `completed_at` as `2026-10-16T14:30:00Z` at 14:26:15Z, a rounded, model-authored time four minutes in the future. The follow-up's script used the clock and wrote 14:32:23Z correctly. Defect 2: the full review stored each hypothesis as ID, origins, file, title, severity, and context references, without the scout's source evidence, expected impact, or falsification condition. The follow-up flagged this and passed the record verbatim rather than reconstructing it. Neither defect follows from the edit mechanism. |
| Follow-up lineage and original concern records | PASS | `lineage.source_run_id` is `20261016T142016Z-8d2974` and `follow_up_run_ids` is empty. Each selected concern's hypothesis, original outcome, and original reviewed head equal the source record's values. The source record's SHA-256 (`52f4791c…95965`) was unchanged after the follow-up. |
| Preservation correctness | PASS | Both runs recorded the intended record directory before copying, copied with `cp` (`run-state.json` last), verified each file with `cmp`, made no state change after the copy, and removed the run directory only after verification. |
| Unrelated state retained, no unexpected changes | PASS (full review); NOT VERIFIED (follow-up) | The full review's byte-exact replay shows that only the edited regions changed. The follow-up's script rewrites leave no per-step trace to compare. |
| Persistence moments | Observation, not attributable | The full review persisted 6 times: creation, after dedupe, after H1 to H4, and three edits after worktree removal. Neither scout completion was persisted separately. H5 and H6 outcomes were first persisted only after the worktree was removed. This batches the research's per-scout and per-outcome persistence points. With no control run on the unclarified protocol, this cannot be attributed to the clarification. |
| Publication, receipt, and payload safeguards | NOT EXERCISED | Both runs were local and non-posting, so no `publication-receipt.json` was created. |
| Probe-phase restoration persistence | NOT EXERCISED | No `Needs probe` outcome occurred. |

## Reads

| Run | Tool and scope | Target | Reason | Bytes through context |
| --- | --- | --- | --- | --- |
| Full review | none | its own `run-state.json` | none needed | 0 |
| Full review | `Bash`, whole file in a subprocess (`python3 -c "json.load(...)"`) | its own record, before preservation | validity check | 21 B line (`run-state valid JSON`) in a 187 B command result |
| Full review | `Bash` `cp` and `cmp` | its own record | preservation and byte-equality verification | no file content |
| Follow-up | `Bash` `cat`, whole file | the source record | follow-up discovery, as the protocol requires | 9,062 B |
| Follow-up | `python3` subprocesses, whole file | the source record and its own record | creation and the two script rewrites | 0 B of file content (results: `ok` and a directory listing) |

## Read cost against the research bounds

Full review, final record 8,854 B, 6 persistence points. The byte-exact replay gives the record size after each point: 2,142, 4,268, 5,780, 7,095, 8,830, and 8,854 B.

| Measure | Bytes | Share of A with comparison |
| --- | --- | --- |
| A, whole-record rewrite, no comparison (sum of the sizes above) | 36,969 | 50.0% |
| A, whole-record rewrite plus read-back | 73,938 | 100.0% |
| Observed C: 12,115 B emitted by the `Write` and `Edit` calls plus 1,880 B of tool success messages | 13,995 | 18.9% |
| C with a full read before each of the 5 edits (pessimistic bound) | 42,110 | 57.0% |

The observed read cost of the record is 0 B, against 28,115 B for the pessimistic bound, so reads sat exactly at the optimistic bound. The total share is above the research's optimistic 3.3 to 6.0 percent because this record is small and persisted only 6 times. A's cost grows quadratically with the number of steps, and here most edit bytes are new information: 7,170 of the 9,549 B emitted by the edits are `new_string` content. Measured in reads, the result is the optimistic bound, not the pessimistic one.

The follow-up does not fit either C bound because it did not use C. It emitted 14,391 B in its three state-writing `Bash` commands, including about 5 KB of final report in a heredoc, and read back 51 B. The protocol's 9,062 B discovery read of the source record falls outside the research's model, which counts only reads made by updates.

## What this means for the recommendation

- Claude Code can maintain the run state with one `Write` and targeted `Edit` calls, without reads and with byte-exact preservation of unrelated content, as observed in one full review.
- The follow-up shows that the proposed wording does not reliably produce that behavior. "The harness's targeted file-edit tool" names no tool and does not exclude script-mediated writes, and the coordinator chose an inline script that rewrites the whole file. Unlike the research's proposed text, issue #131's desired behavior names Claude Code `Edit` explicitly. Such scripts are close to candidate B without its safeguards, and as the research notes, they bypass a user's `Edit` permission rules.
- One plausible motive is that the follow-up must preserve original concern records verbatim, and a script copies them without model transcription. That is an inference, not an observation, and the two later rewrites had no such motive.
- Under the issue's decision rule, Claude Code is not yet viable for candidate C as worded. A maintainer may revise the text to name each harness's tool and exclude shell or script writes to the run state, then rerun the follow-up. One run per mode cannot establish reliability either way.

## Evidence

All raw evidence is in [`claude-code-gate-131-evidence.tar.gz`](claude-code-gate-131-evidence.tar.gz), whose `SHA256SUMS` lists every file. Link these from issue #131:

| Evidence | Path in the archive | SHA-256 prefix |
| --- | --- | --- |
| Full-review transcript, target echo turn | `transcripts/full-t1.jsonl` | `57794707` |
| Full-review transcript, run turn: the `Write`, the five `Edit` calls, scouts, validators, cleanup, and preservation | `transcripts/full-t2.jsonl` | `7995af1b` |
| Follow-up transcript, discovery and confirmation turn | `transcripts/fu-t1.jsonl` | `4b75614f` |
| Follow-up transcript, run turn: the `python3` state writes at tool indexes 4, 16, and 18 | `transcripts/fu-t2.jsonl` | `9a74f07e` |
| Preserved full-review record and receipt | `records/20261016T142016Z-8d2974/run-state.json` and `final-report.md` | `52f4791c`, `be54273a` |
| Preserved follow-up record and receipt | `records/20261016T143007Z-8bc27d/run-state.json` and `final-report.md` | `bcb2b574`, `3c407386` |
| Every run-state `Write`, `Edit`, and `Bash` call with full inputs and results | `analysis/full-t2-edits.txt` and `analysis/fu-t2-state-cmds.txt` | `d5aa2c85`, `75728164` |
| Per-call byte counts | `analysis/full-review-run-state-traffic.txt` and `analysis/follow-up-run-state-traffic.txt` | `3bf38534`, `93fa730b` |
| Applied clarification, runner, environment, settings, and versions | `setup/` | see `SHA256SUMS` |

Each transcript is Claude Code `stream-json` output from `--verbose`, including subagent messages tagged with `parent_tool_use_id`. Tool indexes count every `tool_use` in a turn's file in order, subagents' included. The isolated config's session JSONL files were left out because they embed the account email.

## Environment changes

- The real `~/.claude`, the `~/.mmena1-skills` checkout, and this repository's working tree were unchanged.
- An early un-isolated smoke test inherited this session's ID and wrote a transcript under `~/.claude/projects/` for a scratch directory. It held only a one-word prompt and reply, and it was deleted. Whether the cloud session's transcript sync picked it up first cannot be checked or undone from inside the container.
- Scratch clones, the isolated config, and nested session temp files lived under `/tmp/claude-0/`, which is reclaimed with the container.
