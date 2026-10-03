# Runtime Acceptance Matrix

Static checks cannot prove multi-agent orchestration. Every real review therefore emits a passive receipt in its run state and final report with the harness identity/version, reviewed skill commit, selected roles, and observed result for every row. Use `PASS`, `FAIL`, or `NOT EXERCISED`; unobserved behavior is never a pass.

| Scenario | Devin expected result | Claude Code expected result | Codex expected result |
| --- | --- | --- | --- |
| Zero hypotheses | No validator launches; report says all selected dimensions completed with nothing to validate | Same | Same |
| Surviving hypotheses | Independent static validator launches for every canonical hypothesis | Same | Same |
| Capacity-bounded static validation | When hypotheses exceed available validator slots, queued hypotheses launch as slots free, every hypothesis is attempted once, and capacity alone does not make the run incomplete | Same, with at most 4 slots bounded by the concurrent subagent cap; a concurrency refusal requeues the hypothesis instead of failing it | Same |
| Multiple selected scouts | Every selected scout starts in one simultaneous wave | Every selected scout launches as a parallel agent call in one message | Same |
| Insufficient scout capacity | Review stops before launching any scout and reports required versus available capacity | Same when the selected scouts exceed the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` cap; a concurrency refusal at launch from slots occupied outside the session stops the review and marks it incomplete, and the receipt records that part of the gate as observed at launch | Same |
| Validator probes | Static wave completes first; baseline is verified, then restored before every sequential writable probe | Same | Same |
| Scout failure | Running scouts may finish; run becomes incomplete and cannot publish or claim PASS/`No findings` | Same | Same |
| Validator partial failure | Completed outcomes remain; queued hypotheses continue in canonical order until each is attempted once; run is incomplete and the writable phase is blocked | Same | Same |
| PR-review-overlap | Complete inline threads with resolution status, published review summaries, and concrete conversation concerns are fetched only after independent validation; semantic matches suppress open overlaps, retain resolved defects with links, keep distinct mechanisms, and are re-checked before publication | Same | Same |
| PR head change | Reviewed and current SHAs are reported; result is stale and publication is blocked | Same | Same |
| Cleanup | Only the current run's worktree, context snapshot, and run directory are removed | Same | Same |

Normal reviews exercise only paths they encounter. Keep rare failures and transitions `NOT EXERCISED` until natural execution or a targeted smoke run observes them; never perturb a real review solely to fill the matrix. After changes to `SKILL.md` orchestration, `harnesses/roles.toml`, or reviewer bodies, targeted Devin, Codex, and Claude Code smoke runs remain required for important gaps not covered by passive receipts.

Cross-harness acceptance passes only when collected receipts and targeted smoke evidence show every harness preserves the protocol's state meanings, failure behavior, publication safeguards, and single-worktree invariant. Different hypotheses or wording across harnesses are expected and do not fail behavioral equivalence.

## PR-review-overlap scenarios

Use the coordinator's final report and proposed publication payload as the observation seams. Inspect scout and static/writable validator inputs to verify no existing PR discussion was supplied. Observe these cases in targeted smoke runs or natural reviews, retaining evidence per case in the shared receipt; an aggregate `PASS` describes only the cases actually observed, not the entire table.

| Case | Expected observation |
| --- | --- |
| Equivalent open inline concern | Finding or Unresolved item stays visible as already reported with the prior link and semantic reason; no new comment is proposed or posted. |
| Earlier speculative open concern independently confirmed | Finding retains decisive validator evidence and notes independent confirmation; publication remains suppressed. |
| Equivalent resolved thread, defect persists | Finding stays actionable against the reviewed commit; any approved publication is a new comment linking the prior thread. No reply or thread mutation occurs. |
| Same location, different failure or mechanism; uncertain equivalence | Items remain distinct and use normal publication rules. |
| Prior claim that the defect was fixed | Independent outcome is unchanged; a resolved thread does not suppress a persisting Finding. |
| Equivalent review summary or conversation concern | Concrete concern is included and linked as already reported; empty reviews and administrative chatter are ignored. |
| More than one thread/comment page; resolved or outdated anchors | All connections, including nested replies, are exhausted and usable concerns are retained. |
| Discussion retrieval fails or is partial | Gap is reported; completed validation evidence survives and publication is blocked. |
| New equivalent open concern after approval, unchanged head | Final re-fetch suppresses it and refreshes report/counts; an empty payload causes no review submission. |
| Resolution changes after approval | Overlap is recomputed; adding a prior link or otherwise changing a comment body requires fresh approval and payload validation. |
| Head changes during publication preparation | Reviewed/current SHAs are reported and publication stops under the existing freshness gate. |
| Branch/range without a uniquely associated PR | Discussion retrieval is skipped; local report is unchanged except for the skipped status and the receipt stays `NOT EXERCISED`. |

Record `FAIL` when an observed path violates the contract and `NOT EXERCISED` when comparison never ran. Static repository checks verify receipt consistency, not semantic matching or live publication behavior.

## Smoke runs

Targeted smoke runs record agent discovery and launch evidence that passive receipts cannot provide.

| Date | Harness | Skill commit | Check | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-26 | Codex CLI 0.156.1, Windows | `2043c9b` | Hyphenated native agent types spawn after `./install.sh --codex` | PASS | One `codex exec` parent thread spawned `deep-review-scout`, `deep-review-structural`, `deep-review-validator-static`, and `deep-review-validator-probe` by exact name. Each child session recorded the hyphenated `agent_role`, ran its pinned `gpt-6-luna` or `gpt-6-sol` model, and replied `READY`. Codex 0.156.1 did not load project-scoped `.codex/agents`, so the agents were installed in the user agent directory. |
| 2026-09-26 | Claude Code 2.1.283, Windows | Not applicable: scratch agents | `Bash(<pattern>)` entries in an agent's `tools` confine its Bash | FAIL | In a scratch project, an agent whose `tools` listed `Read`, `Bash(git status:*)`, and `Bash(git log:*)` ran `echo pwned > marker-pattern.txt` and wrote the file when the session allowed `Bash`. Without that session approval, the same agent ran `git status --short` but its `echo` and `git diff --output=...` calls were refused by the permission system, not by its tool list. The read-only roles therefore get `Read`, `Grep`, `Glob`, and `Bash` with instruction-enforced confinement. |
| 2026-09-26 | Claude Code 2.1.283, Windows | `9712de3` | Local-only `/deep-review` of mmena1/skills#20 (merged, 10 added docs lines) with the `docs` and `conventions` scouts after `./install.sh --claude`: agents are discovered, run their pinned model, and launch in one parallel scout message | PASS | Headless `claude -p` discovered all four `deep-review-*` agents at session start (the installer copied them with managed markers because the account cannot create file symbolic links). The coordinator ran on the session's model and launched `deep-review-scout` twice as parallel agent calls in one message; both children ran the pinned `sonnet` model and returned `No hypotheses`, so no validator launched. Scouts used only `Read`, `Grep`, and read-only Bash (`git diff`, `git log`, `git show`, `cat`, `find`, `ls`) and changed nothing. Cleanup removed the worktree registration and context snapshot and left the caller checkout clean. Receipt below. |
| 2026-09-26 | Claude Code 2.1.283, Windows | `9712de3` | The same run's scouts confine their inspection to the pinned worktree and reviewed target | FAIL | Some scout reads targeted the caller checkout (`C:/code/skills`) and history after the reviewed head instead of the pinned worktree. Neither scout raised a concern from that content, but instruction-enforced confinement did not keep them inside the single pinned worktree. Addressed in `c59272c`, which roots every role's reads and Git commands at the pinned worktree and reviewed history; see the rerun below. |
| 2026-09-26 | Claude Code 2.1.283, Windows | `c59272c` | The scout gate reads the concurrent subagent cap before launch: `/deep-review` of mmena1/skills#20 with the `docs` and `conventions` scouts under `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=1` | PASS | The coordinator read the cap (1) and the session's running subagents (0), reported 2 scouts required against 1 slot available, and stopped before any agent launch, context capture, or worktree creation. The report was incomplete and not publishable. The receipt marked only Insufficient scout capacity `PASS`; every other row stayed `NOT EXERCISED`. |
| 2026-09-26 | Claude Code 2.1.283, Windows | `c59272c` | Rerun of the local-only mmena1/skills#20 review with the `docs` and `conventions` scouts: roles confine inspection to the pinned worktree and reviewed history | PASS | With the cap unset (20), both scouts launched in one message on `sonnet`. One hypothesis survived and received one `deep-review-validator-static` invocation on `opus`, which returned Disproved. All 7 validator tool calls and 22 of 23 scout tool calls addressed the pinned worktree or the skill's own contract files, and every Git command named SHAs reachable from the reviewed head. One scout call, `git -C "C:/code/skills/AppData" status`, targeted a nonexistent path under the caller checkout and failed without reading anything; the maintainer accepted this as passing because no content outside the worktree was inspected, while noting that confinement remains instruction-enforced. Receipt below. |

Claude Code smoke receipt for mmena1/skills#20 (skill `9712de3`, native agents launched: `deep-review-scout` for `docs` and `conventions`):

| Scenario | Status | Observed evidence |
| --- | --- | --- |
| Zero hypotheses | PASS | Both scouts returned `No hypotheses`; no validator manifest was created and no validator launched. |
| Surviving hypotheses | NOT EXERCISED | No hypotheses survived. |
| Capacity-bounded static validation | NOT EXERCISED | No hypotheses, so the 4-slot pool was never used. |
| Multiple selected scouts | PASS | Both selected scouts launched as parallel agent calls in one message and completed. |
| Insufficient scout capacity | NOT EXERCISED | No launch was refused; the gate was observed at launch, not verified in advance. |
| Validator probes | NOT EXERCISED | No `Needs probe` outcome. |
| Scout failure | NOT EXERCISED | Both scouts succeeded. |
| Validator partial failure | NOT EXERCISED | No validator launched. |
| PR head change | NOT EXERCISED | The head stayed `c9fbab3` through the final freshness check. |
| Cleanup | PASS | Only the run's worktree and context snapshot were removed, `git worktree list` no longer showed the worktree, and `run-state.json` and `final-report.md` were preserved. |

Claude Code smoke receipt for the mmena1/skills#20 rerun (skill `c59272c`, native agents launched: `deep-review-scout` for `docs` and `conventions`, `deep-review-validator-static` for H1):

| Scenario | Status | Observed evidence |
| --- | --- | --- |
| Zero hypotheses | NOT EXERCISED | One hypothesis survived. |
| Surviving hypotheses | PASS | H1 received one independent static adjudication, which returned Disproved. |
| Capacity-bounded static validation | NOT EXERCISED | One hypothesis against 4 slots, so the queue never exceeded capacity. |
| Multiple selected scouts | PASS | Both selected scouts launched as parallel agent calls in one message and completed. |
| Insufficient scout capacity | NOT EXERCISED | The cap was 20 with no running subagents, so 2 scouts fit and no launch was refused. |
| Validator probes | NOT EXERCISED | No `Needs probe` outcome; the baseline was verified after the static phase. |
| Scout failure | NOT EXERCISED | Both scouts succeeded. |
| Validator partial failure | NOT EXERCISED | The only static invocation succeeded. |
| PR head change | NOT EXERCISED | The head stayed `c9fbab3` through the final freshness check. |
| Cleanup | PASS | Only the run's worktree and context snapshot were removed, `git worktree list` no longer showed the worktree, and `run-state.json` and `final-report.md` were preserved. |
