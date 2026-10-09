# Runtime Acceptance Matrix

Static checks cannot prove multi-agent orchestration. Every real review therefore emits a passive receipt in its run state and final report with the harness identity/version, reviewed skill commit, each selected lens with the native agent used for it, the validator agents that ran, and observed result for every row. Use `PASS`, `FAIL`, or `NOT EXERCISED`; unobserved behavior is never a pass.

| Scenario | Devin expected result | Claude Code expected result | Codex expected result |
| --- | --- | --- | --- |
| Zero hypotheses | No validator launches; report says all selected dimensions completed with nothing to validate | Same | Same |
| Surviving hypotheses | Independent static validator launches for every canonical hypothesis | Same | Same |
| Capacity-bounded static validation | When hypotheses exceed available validator slots, queued hypotheses launch as slots free, every hypothesis is attempted once, and capacity alone does not make the run incomplete | Same, with at most 4 slots bounded by the concurrent subagent cap; a concurrency refusal requeues the hypothesis instead of failing it | Same |
| Multiple selected scouts | The native agent of every selected lens, and only those, starts in one simultaneous wave | The native agent of every selected lens, and only those, launches as a parallel agent call in one message | Same |
| Insufficient scout capacity | Review stops before launching any scout and reports required versus available capacity | Same when the selected scouts exceed the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` cap; a concurrency refusal at launch from slots occupied outside the session stops the review and marks it incomplete, and the receipt records that part of the gate as observed at launch | Same |
| Validator probes | Static wave completes first; baseline is verified, then restored before every sequential writable probe | Same | Same |
| Scout failure | Running scouts may finish; run becomes incomplete and cannot publish or claim PASS/`No findings` | Same | Same |
| Validator partial failure | Completed outcomes remain; queued hypotheses continue in canonical order until each is attempted once; run is incomplete and the writable phase is blocked | Same | Same |
| PR-review-overlap | Complete inline threads with resolution status, published review summaries, and concrete conversation concerns are fetched only after independent validation; semantic matches suppress open overlaps, retain resolved defects with links, keep distinct mechanisms, and are re-checked before publication | Same | Same |
| PR head change | Reviewed and current SHAs are reported; result is stale and publication is blocked | Same | Same |
| Cleanup | Only the current run's worktree, context snapshot, and run directory are removed | Same | Same |

Normal reviews exercise only paths they encounter. Keep rare failures and transitions `NOT EXERCISED` until natural execution or a targeted smoke run observes them; never perturb a real review solely to fill the matrix. After changes to `SKILL.md` orchestration, `harnesses/roles.toml`, or reviewer bodies, targeted Devin, Codex, and Claude Code smoke runs remain required for important gaps not covered by passive receipts.

Cross-harness acceptance passes only when collected receipts and targeted smoke evidence show every harness preserves the protocol's state meanings, failure behavior, publication safeguards, and single-worktree invariant. Different hypotheses or wording across harnesses are expected and do not fail behavioral equivalence.

## Enforcement mechanism in new receipts

Codex scouts and static validators are instruction-enforced within the parent's inherited effective sandbox and approval policy. The writable probe inherits that same policy, cannot override it per role, and receives no probe-specific permission. New receipts and reports describe this boundary and record observed policy when available. A difference between inherited policy and a role's read-only or writable behavior contract alone is not a review failure. Historical rows, receipts, and evidence tables below remain unchanged.

## Native agents per lens

Each selected lens runs in its own native agent, and the receipt names the agent used for each selected lens:

| Lens | Native agent |
| --- | --- |
| `bugs` | `deep-review-scout-bugs` |
| `conventions` | `deep-review-scout-conventions` |
| `history` | `deep-review-scout-history` |
| `docs` | `deep-review-scout-docs` |
| `structural` | `deep-review-structural` |

Static adjudication runs as `deep-review-validator-static` and writable probes as `deep-review-validator-probe`. Smoke rows and receipts below that name `deep-review-scout` record the former generic scout, which ran the `bugs`, `conventions`, `history`, and `docs` lenses with one shared model. They remain historical evidence and are not evidence for the lens-specific agents.

## Scout launch-grouping receipts

For `Multiple selected scouts`, retain the native parent message or model response identity and each launch's call ID, selected lens, exact native agent, launch outcome and child identity when created. Include the pinned worktree and base/head identity shared by the calls, the evidence source, and all scout launch attempts in the wave, including failed or extra calls. A session/thread ID or a whole user-turn ID alone does not identify one parent model response. Apply these rules to the observed evidence:

| Observation | Receipt result | Review consequence |
| --- | --- | --- |
| Native boundaries identify all and only the selected scout calls, once each, in one parent message or response, emitted before any launch result is consumed or another parent inference occurs; every launch starts on the same pinned worktree | PASS | Establishes only the scout launch row; other rows require their own evidence. |
| Native evidence confirms separate parent responses, an intervening result consumption or parent inference, a missing/extra/duplicate scout, a launch failure, or different pinned worktrees | FAIL | Mark the review incomplete, allow running scouts to finish, preserve completed diagnostic evidence and block PASS, `No findings`, and publication. |
| No confirmed violation, but native grouping evidence is unavailable or incomplete, even when all selected children overlap | NOT EXERCISED | Record the exact missing boundary, call identity, or launch observation; never infer a grouping PASS or invent a dispatch failure. |

Confirmed violations take precedence over other evidence gaps. The retained #80 case below is FAIL: docs and conventions have distinct native response IDs and the docs launch result precedes the conventions call. Their overlap and the original coordinator's PASS narrative cannot overturn that evidence. Conversely, one shared native response containing the complete selected call set can pass when the remaining launch observations above are present.

A passive receipt uses observations already available to the coordinator through the active runtime's supported tools, trace, or API. It does not require a normal review to discover or parse private session logs. When the runtime does not expose grouping boundaries or call identities, record that gap as `NOT EXERCISED`. Timestamps, child overlap, and a coordinator's statement that it dispatched one wave are insufficient substitutes for native grouping evidence.

### Targeted Codex native launch smoke

When explicitly running a targeted dispatch smoke, use a throwaway installation and exactly the native docs and conventions scouts on one clean pinned worktree, with the same base/head and an explicit immutable context bundle and bounded lens manifests. Check role availability and capacity first, then follow the Codex dispatch mechanism in `SKILL.md` for one launch attempt. Wait for running children and retain their outputs even after a violation. Keep native role/model pins, the coordinator's existing model/effort selection, normal user configuration, and global concurrency policy unchanged. Do not launch validators or claim full pipeline acceptance from this bounded smoke.

Retain harness/version, tested skill commit, target/worktree identity, prompt, native launch calls/results and call IDs, parent message/response identities, and raw evidence hashes. Prefer a supported native export when it exposes the required boundaries. If it does not, this explicitly targeted verification may inspect and retain only the isolated smoke session's native trace read-only, recording how calls were associated with parent responses. This is smoke verification, not a new log-parsing obligation for passive receipts. If neither source establishes grouping, record `NOT EXERCISED` with the gap; an observed violation remains `FAIL`. Do not repeat a failed dispatch until a run happens to pass.

Record the new dated smoke result separately from historical acceptance rows and raw receipts. A correction or successful later smoke never rewrites or erases a historical failure. Keep the Devin #77 investigation separate.

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
| Review summary repeats a resolved inline concern from the same review | Retained GraphQL parent review IDs join to the summary's REST IDs; the matching resolved thread controls the summary concern's status, so the persisting Finding stays actionable and any new comment links the prior discussion. |
| One review contains a resolved matching concern and an unrelated open thread | Shared review membership does not collapse different concerns or give the whole summary one resolution status; the unrelated open thread does not suppress the persisting Finding. |
| More than one thread/comment page; resolved or outdated anchors | All connections, including nested replies, are exhausted and usable concerns are retained. |
| Discussion retrieval fails or is partial | Gap is reported; completed validation evidence survives and publication is blocked. |
| New equivalent open concern after approval, unchanged head | Final re-fetch suppresses it and refreshes report/counts; an empty payload causes no review submission. |
| Resolution changes after approval | Overlap is recomputed; adding a prior link or otherwise changing a comment body requires fresh approval and payload validation. |
| Head changes during publication preparation | Reviewed/current SHAs are reported and publication stops under the existing freshness gate. |
| Branch/range without a uniquely associated PR | Discussion retrieval is skipped; local report is unchanged except for the skipped status and the receipt stays `NOT EXERCISED`. |

Record `FAIL` when an observed path violates the contract and `NOT EXERCISED` when comparison never ran. Static repository checks verify receipt consistency, not semantic matching or live publication behavior.

## Structural evidence scenarios

Use bounded controlled targets: a small committed base and head with no context artifacts, reviewed by the generated structural scout and static validator agents with no design-guidance skill supplied. A crafted canonical hypothesis is a valid validator input, because the validator receives exactly one hypothesis per invocation. Observe the scout's hypotheses or `No hypotheses` and each validator's outcome and evidence. Static repository checks cannot show these outcomes, so record each case as observed or not exercised.

| Case | Expected observation |
| --- | --- |
| Demonstrated cost with a qualifying alternative | The scout emits one hypothesis naming the burdened task, the causal mechanism, and a behavior-preserving alternative that reduces the cost; the validator returns a Finding whose Recommendation states the reduced cost as the required outcome. |
| Equivalent cost under different techniques | The same cost expressed in imperative code and in a declarative pipeline receives the same admission, potential severity, and outcome; neither style counts as evidence. |
| Style-only alternative | A shorter or differently styled rewrite with no demonstrated cost produces no hypothesis, and a crafted hypothesis that argues it is Disproved as a style or design preference. |
| Locally justified helper, adapter, or dependency injection | Added indirection that isolates knowledge, supports a needed test seam, or follows a governing local convention produces no hypothesis, and a crafted single-adapter or fewer-layers hypothesis is Disproved without appeal to any design philosophy. |
| Alternative with an equal or greater burden | A hypothesis whose alternative adds modes, hides policy, or scatters knowledge is Disproved on that ground. |
| Structural review without a design-guidance skill | Selecting `structural` passes preflight, and the scout admits and the validators adjudicate without any supplied design contract. |

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
| 2026-10-05 | Claude Code 2.1.289, Linux | `b3a568e` | Reference run before the architecture-neutral standard: the structural scout on the five controlled targets described below, with the then-required `codebase-design` contract supplied | FAIL | Outcomes matched the cases below: both duplicated-rule targets produced one hypothesis and the other three produced `No hypotheses`. Every admission and rejection, however, was argued from `codebase-design` checks ("concept singularity", "passes the deletion test", "improves depth", "Adapter reality"). On the single-adapter target the scout wrote that Adapter reality "would normally call this a hypothetical seam" and admitted nothing only because a tracked convention overrode it, so conformity to a design philosophy, not demonstrated cost, decided adjudication. |
| 2026-10-05 | Claude Code 2.1.289, Linux | `37b5a6b` | The structural scout applies the structural evidence standard with no design-guidance skill supplied | PASS | See the structural evidence receipt below. Both duplicated-rule targets produced one equivalent medium hypothesis naming the burdened task, mechanism, and alternative; the style-only, locally justified DI and adapter, and single-adapter convention targets produced `No hypotheses`, each rejection argued from task cost. One style-only scout run delivered its result and then ended on an API error; a clean rerun gave the same result. |
| 2026-10-05 | Claude Code 2.1.289, Linux | `37b5a6b` | The static validator adjudicates structural hypotheses by the same standard | FAIL | Both scout hypotheses became medium Findings, and the crafted style and single-adapter hypotheses were Disproved. The crafted equal-burden hypothesis was not Disproved: the validator rejected its cost and its alternative, then returned a Finding for a different cost (the duplicated rule) at the same code. Addressed in `c948ae9`. |
| 2026-10-05 | Claude Code 2.1.289, Linux | `c948ae9` | Rerun: the static validator adjudicates the hypothesis's own cost and mechanism | PASS | The equal-burden hypothesis was Disproved because its navigation cost was not borne and its string-keyed dispatcher added burden; the validator named the duplicated rule as a different concern that "cannot stand in for H1". The imperative positive hypothesis remained a medium Finding with the same required outcome. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 1, discovery after fresh install: all seven lens-specific agents are discoverable by exact name after `./install.sh --claude` | PASS | Runtime. In a throwaway home directory, the installer linked seven `deep-review-*.md` agents. A headless `claude -p` session's init event listed exactly those seven, and one parent message launched all seven by exact `subagent_type`. `subagent_stats` reported 7 spawned, 7 completed, 0 failed, 0 refused, one per type, and each child replied `READY`. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `6abc08d` → `52ec495` | Issue #71 check 2, discovery after upgrade from the generic scout layout: rerunning the installer leaves the seven agents and no invocable `deep-review-scout` | PASS | Runtime. A throwaway home directory was installed at `6abc08d` (`deep-review-scout`, `deep-review-structural`, and both validators). After that checkout moved to `52ec495`, the rerun installer regenerated the agents, removing `harnesses/claude/deep-review-scout.md`, and printed `Removing repository-managed agent absent from desired set: .../agents/deep-review-scout.md`. It then linked the seven agents. A new session's init event listed only the seven. An Agent call with `subagent_type` `deep-review-scout` returned `Agent type 'deep-review-scout' not found`, followed by a list of available agents with no generic scout, and nothing spawned. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 2, upgrade from a standalone `mmena1/deep-review` installation | NOT EXERCISED | Not applicable to Claude Code. The standalone installer at its final commit `1f8e7f9` accepts only `--devin`, `--codex`, and `--all`, and no commit in its history contains a Claude Code path, so no Claude Code legacy installation exists to migrate. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 3, pinned model and effort: every role serves its pinned model and effort | PASS | Runtime. For each launched role, the served model comes from the child's assistant messages in the stream and in its subagent transcript, and the effort from the `effort` and `perTurnEffort` fields that Claude Code records on each child turn: `scout-bugs` `claude-opus-5-5` `high`, `scout-conventions` `claude-haiku-5-5` `high`, `scout-history` `claude-sonnet-5-5` `high`, `scout-docs` `claude-haiku-5-5` `high`, `structural` `claude-opus-5-5` `high`, `validator-static` `claude-opus-5-5` `high`, `validator-probe` `claude-sonnet-5-5` `high`. The parent sessions recorded `medium`, so `high` was not inherited. The API response does not echo effort, so the effort evidence is the harness's own record of the effort it sent. Configuration only: the generated frontmatter's `model` and `effort` match `harnesses/roles.toml`. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 4, lens selection and single wave: a local-only `/deep-review 32b5ba1^..32b5ba1` (the mmena1/skills#20 change) selecting `docs` and `conventions` | PASS | Runtime. One coordinator message held exactly two Agent calls, `deep-review-scout-docs` and `deep-review-scout-conventions`. `subagent_stats.by_type` shows no other scout, and their transcripts overlap (21:15:40 to 21:16:35 and 21:15:46 to 21:17:20 UTC). Each scout prompt carried only its own lens slug. Every child tool call addressed the run's worktree or context snapshot. Receipt below. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 5, capacity preflight: the same review under `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=1`, set only on the smoke process | PASS | Runtime. The coordinator read the cap (1) and the session's running subagents (0). It reported 2 scouts required against 1 slot available, naming exactly `deep-review-scout-docs` and `deep-review-scout-conventions`, and stopped before any agent launch, context capture, or worktree creation, recording the stop in a run directory holding only `run-state.json`. `subagent_stats.spawned` was 0, `git worktree list` was unchanged, and the report was incomplete and non-publishing. Only Insufficient scout capacity was marked `PASS`. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 6, missing native role: the same review with `deep-review-scout-docs.md` removed from a throwaway home's agent directory | PASS | Runtime. The init event listed six agents, without `deep-review-scout-docs`. The coordinator passed the capacity check (2 of 20). It then stopped before analysis, naming `deep-review-scout-docs` as missing for the `docs` lens, and launched no agent (`subagent_stats.spawned` 0). It made no substitution, and it created no worktree, context snapshot, or run directory. |
| 2026-10-08 | Claude Code 2.1.295, Linux | `52ec495` | Issue #71 check 7, pipeline compatibility: the check 4 run's natural hypotheses reach static validation | PASS | Runtime. The scouts emitted 5 hypotheses, and deduplication merged them into canonical H1 to H3, retaining the original IDs. Exactly three `deep-review-validator-static` invocations were launched in one message, within the 4-slot limit, and each prompt carried exactly one of H1, H2, and H3. All three ran on `claude-opus-5-5` at `high` effort and returned Finding, Disproved, and Disproved. No probe was needed, and the receipt named the native agent for each lens and the validator that ran. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 1, discovery after fresh `./install.sh --devin` | PASS | Runtime. Session `insidious-wombat` exposed all seven exact profiles and launched each successfully: bugs `180940d1`, conventions `5ffb0d99`, history `1533ee79`, docs `3583821b`, structural `ba8fe660`, static `c48e7ead`, probe `977fde0a`. Every child completed, with READY or an intentional missing-input stop. This load-only test does not establish a simultaneous scout wave. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6abc08d` → `6ccd9f3` | Issue #71 check 2, upgrade from the generic scout layout | PASS | Runtime. Before upgrade, `humdrum-statistic` launched `deep-review-scout` as child `5efe16e4`, which replied READY. The installer retired its managed link. After upgrade, `clean-echium` exposed only the seven current profiles, rejected the exact retired profile with `Subagent failed to start.` and no child ID, then launched all seven current profiles successfully in one native message. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | Legacy `1f8e7f9` → `6ccd9f3` | Issue #71 check 2, standalone `mmena1/deep-review` migration | PASS | Runtime. The actual archived installer's `--devin` installation exposed its four `code-reviewer*` profiles and launched `code-reviewer` as `cf3ef1ba`. The current installer removed those four managed links and the composed legacy skill. In `elemental-pitcher`, each retired exact name failed to start without a child ID; all seven new profiles launched and completed. The legacy checkout stayed clean. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 3, pinned models and reported effort variants for all seven roles | PASS | Runtime. `clean-echium` child inference metadata records `generation_model`, request IDs, and the response-statistics Model label: bugs, structural, static use `gpt-6-1-sol-high` / GPT-6.1 Sol High Thinking; conventions, history, docs, probe use `gpt-6-luna-high` / GPT-6 Luna High Thinking. The parent uses `gpt-6-1-sol-medium`. High is observed as the harness's served variant; no separate server-echoed reasoning-effort field is exposed. Per-role evidence below. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 4, selected two-scout native launch and single-wave grouping | FAIL | Runtime. Bounded scout session `temporal-star` launched exactly docs `6ab9946d` and conventions `1955d130`, on the same pinned worktree and their own lens manifests. Their execution overlapped, but native assistant messages `b19c22a0…` and `d3d2c331…` held one launch each, with distinct inference request IDs; ATIF steps 9 and 10 also separate them. The parent's final claim of one-message grouping is contradicted by those messages. This phase-level smoke is not a complete coordinator review. Follow-up [#77](https://github.com/mmena1/skills/issues/77). |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Enabled capacity observability required for the full coordinator review | FAIL | Runtime capability gap. The enabled two-lens coordinator stopped before analysis with required capacity 2 and available capacity unknown: no supported capacity observation seam was exposed by the native tools, CLI help, or installed documentation. Its state records `blocked_unverified_capacity`, no spawn calls, and an incomplete, non-publishing result. Failing closed was correct; the missing usable harness mechanism blocks the full review. Follow-up [#76](https://github.com/mmena1/skills/issues/76). |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 5, insufficient capacity with native subagents disabled in an isolated installation | PASS | Runtime. In `determined-toucan`, the supported temporary `subagents_enabled: false` setting removed both native launch/read tools from the actual tool definitions. The coordinator reported exactly docs and conventions, 2 required scouts and 0 available, and stopped before analysis, any child launch, worktree/context creation, fetch, or publication. This proves only the zero-capacity case. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 5, enabled numeric concurrency cap below the two-scout count | NOT EXERCISED | No documented enabled cap or available-slot query was found. No unsupported configuration key was invented, and no normal or global concurrency policy was changed. Disabled subagents do not prove enforcement of an enabled numeric cap. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 6, missing selected native role | PASS | Runtime. Only the throwaway installation's `deep-review-scout-docs` link was removed. The smoke session exposed six profiles, named that exact missing docs agent, and stopped before analysis with zero child launches, no worktree/context creation, and no substitute profile or model. Capacity was not inferred as passed. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Issue #71 check 7, complete coordinator pipeline compatibility | NOT EXERCISED | The full coordinator stopped at unverified capacity before scouting. The separate bounded scout and static-handoff tests below do not establish a complete protocol run, its capacity-bounded queue, or its passive pipeline receipt. No full-review pass is inferred from them. |
| 2026-10-08 | Devin CLI 3000.11.3 (9c803229faa4), macOS | `6ccd9f3` | Supplemental natural-hypothesis handoff between native scouts and static validator | PASS | Runtime, phase-level only. The bounded docs scout naturally emitted `docs-H1`; conventions returned No hypotheses. The sole concern became H1, retaining its original ID and origin, and exactly one foreground `deep-review-validator-static` child `71ad27b6` independently returned a low Finding against the same pinned worktree. No synthetic hypothesis, additional validator, writable probe, publication, or fix was used. This is not acceptance of the blocked full pipeline. |

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

Structural evidence receipt for the 2026-10-05 controlled runs (skills `37b5a6b` and `c948ae9`). Each role ran as a Claude Code subagent on the role's pinned model, instructed to adopt the generated `harnesses/claude/deep-review-<role>.md` body; the session's installed native agents linked to an older checkout, so native agent discovery was not exercised. Each target was a throwaway two-commit Git repository with an empty context snapshot:

- duplicated rule, imperative: the diff adds a third inline copy of a qualification rule that a tracked document says changes together for three benefits;
- duplicated rule, declarative: the same rule and change, written as comprehension filters;
- style only: an explicit accumulation loop and a single-use named eligibility predicate;
- justified DI and adapter: an injected clock that a boundary test drives, and a payment adapter that isolates cents conversion, currency, idempotency key, and error translation;
- single-adapter convention: a one-implementation mail port that a tracked repository instruction requires.

| Case | Status | Observed evidence |
| --- | --- | --- |
| Demonstrated cost with a qualifying alternative | PASS | The imperative target produced one hypothesis: the coordinated rule change bears three unlinked copies, and one named predicate reduces them to one. The validator returned a medium Finding whose Recommendation required one place to own the rule, left the predicate's location to the author, and ruled out comment-only and cross-benefit shortcuts. |
| Equivalent cost under different techniques | PASS | The declarative target produced the same hypothesis, potential severity, Finding, severity, and required outcome as the imperative one. Its scout recorded that the comprehension style counted as evidence in neither direction. |
| Style-only alternative | PASS | No hypothesis. A crafted hypothesis proposing `sum(...)` and inlining the predicate was Disproved: no task got cheaper, and inlining would relocate the eligibility policy and drop its name. |
| Locally justified helper, adapter, or dependency injection | PASS | No hypothesis on either target. The clock seam carries test isolation and the adapter carries vendor knowledge; a crafted hypothesis calling the mail port a hypothetical single-adapter seam was Disproved because removing it breaks the tracked convention and hides the dependency, and the validator noted that counting adapters is not evidence. |
| Alternative with an equal or greater burden | PASS | After `c948ae9`, a crafted hypothesis proposing a string-keyed `kind` dispatcher was Disproved on its own cost and alternative. Before that fix it was turned into a Finding for a different cost, recorded as FAIL above. |
| Structural review without a design-guidance skill | NOT EXERCISED | Scouts admitted and validators adjudicated with no design skill supplied, but no coordinator run exercised the revised preflight or selection. |

Deduplication, action classification, reporting, and publication of structural Findings were not exercised because no coordinator run took place. Codex and Devin were not exercised; their generated agents embed the same reviewer bodies.

## Lens-specific agent smoke runs (issue #71)

The 2026-10-08 Claude Code rows above ran in a Linux cloud container at skill `52ec495`, which contains the installer retirement change (#69) and the lens-specific scouts (#70). Each run used a throwaway home directory, a scratch checkout, and an environment stripped of the parent session's variables, so no operator installation or concurrency setting changed. Runtime evidence comes from headless `claude -p --output-format stream-json --verbose` events, including the init event's agent list, each Agent call and its parent message, child assistant messages, and the final `subagent_stats`, and from the per-child subagent transcripts and their metadata. Configuration evidence (generated files and pinned fields) is labeled as such and does not count toward a check. The review coordinator ran on the session's model at `medium` effort; only the roles are under test.

Claude Code smoke receipt for the local-only `32b5ba1^..32b5ba1` review (skill `52ec495`, native agents launched: `deep-review-scout-docs` for `docs`, `deep-review-scout-conventions` for `conventions`, `deep-review-validator-static` for H1, H2, and H3):

| Scenario | Status | Observed evidence |
| --- | --- | --- |
| Zero hypotheses | NOT EXERCISED | The scouts emitted 5 hypotheses. |
| Surviving hypotheses | PASS | H1, H2, and H3 each received exactly one independent `deep-review-validator-static` adjudication: Finding, Disproved, Disproved. |
| Capacity-bounded static validation | NOT EXERCISED | 3 hypotheses against 4 slots, so no hypothesis queued. |
| Multiple selected scouts | PASS | Both selected scouts, and only those, launched as parallel agent calls in one message and completed. |
| Insufficient scout capacity | NOT EXERCISED | The cap was 20 with no running subagents, so 2 scouts fit and no launch was refused. Observed separately under a cap of 1; see the check 5 row. |
| Validator probes | NOT EXERCISED | No `Needs probe` outcome; the baseline was verified after the static phase. |
| Scout failure | NOT EXERCISED | Both scouts succeeded. |
| Validator partial failure | NOT EXERCISED | All three static invocations succeeded. |
| PR-review-overlap | NOT EXERCISED | No PR is uniquely associated with the range, so discussion retrieval was skipped. |
| PR head change | NOT EXERCISED | No PR; the range head stayed `32b5ba1` through the final freshness check. |
| Cleanup | PASS | Only the run's worktree and context snapshot were removed, `git worktree list` no longer showed the worktree, the caller checkout stayed clean, and `run-state.json` and `final-report.md` were preserved. |

### 2026-10-08 Devin native smoke result

Devin CLI `3000.11.3` (build `9c803229faa4`) ran on macOS, Darwin `27.0.0`, against PR #75 head `6ccd9f399e1ac7f1abf7b7392bb55824a8bff0a0`. That base retains the Claude Code evidence above and includes the merged #69 installer retirement and #70 lens-specific agents. These are Devin results, not Codex results; Codex was not run in this acceptance pass.

Every installation used a throwaway `HOME` and `XDG_CONFIG_HOME` beneath `/tmp/devin-native-smoke-71.9nP1qv`, with scratch Git clones. The missing-role test unlinked only the selected agent link it had just installed. The capacity test changed only its separate temporary configuration using the documented `subagents_enabled: false` switch. Imports from other harnesses and automatic updates were disabled only in the temporary configurations. The existing authenticated data directory was reused through `XDG_DATA_HOME`, without reading, copying, or displaying credential contents; ordinary session data and logs were written there. No normal agent files, configuration, model pins, or concurrency policy were changed.

Runtime evidence comes from `devin -p --export` ATIF conversations and the native persisted message forest for these exact smoke session IDs. The message database was queried read-only, restricted to those sessions. Parent tool calls/results establish discovery and launch outcomes. Child assistant metadata supplies `generation_model`, inference `request_id`, `started_generation_at`, `created_at`, and the response-statistics Model label. Native parent message IDs and their request IDs establish grouping; a parent's narrative alone is not evidence. The initial print-mode attempt refused a permission-gated tool before analysis; the enabled coordinator was rerun with a process-local permission mode in the scratch checkout, without changing permission configuration.

Configuration evidence only: `devin doctor --json` loaded seven profiles after the fresh and upgrade installs, four historical profiles before each upgrade, and six after the docs agent link was removed. The generated `AGENT.md` pins matched the manifest, and the authenticated model catalog listed both exact pinned IDs. Neither the doctor output, generated fields, nor catalog availability is counted as serving or launch acceptance.

The `clean-echium` upgraded-install session provides unambiguous runtime model evidence for every role. Each child task named its exact profile, and one assistant message launched all seven; all completed. The parent's variant was `gpt-6-1-sol-medium`, not either pinned child variant.

| Native agent | Child ID | Observed `generation_model` | Observed Model response statistic | Inference request ID |
| --- | --- | --- | --- | --- |
| `deep-review-scout-bugs` | `68619d8a` | `gpt-6-1-sol-high` | GPT-6.1 Sol High Thinking | `b4cb7b07-5284-478b-9fc4-91aac4d72405` |
| `deep-review-scout-conventions` | `b8e0b82b` | `gpt-6-luna-high` | GPT-6 Luna High Thinking | `cdafd471-0d66-4e5e-91ae-6e9c63d30cb3` |
| `deep-review-scout-history` | `bb4b5998` | `gpt-6-luna-high` | GPT-6 Luna High Thinking | `a8c82824-e58f-44c4-8f84-0fa3706c9724` |
| `deep-review-scout-docs` | `9afd5383` | `gpt-6-luna-high` | GPT-6 Luna High Thinking | `69091bee-552e-4905-bb87-c5c36547b3db` |
| `deep-review-structural` | `daca2750` | `gpt-6-1-sol-high` | GPT-6.1 Sol High Thinking | `54911ead-1d62-452c-843e-c1ccacb31b2f` |
| `deep-review-validator-static` | `238f13d2` | `gpt-6-1-sol-high` | GPT-6.1 Sol High Thinking | `f069eb9b-ea60-442b-b157-b5e991208dde` |
| `deep-review-validator-probe` | `8eb8320e` | `gpt-6-luna-high` | GPT-6 Luna High Thinking | `ff2dd653-e5eb-40d7-8a3d-bf3358a355af` |

This observes the harness-recorded High Thinking variant on successful child inference, not an agent's self-report or a model string read from configuration. No independent server-echoed effort field was exposed, so effort beyond the reported variant remains unverified. The probe profile's load is not evidence of writable-probe behavior.

The full coordinator session `capricious-fibre`, selecting `docs` and `conventions` on local range `32b5ba1^..32b5ba1`, recorded required capacity 2 and available capacity unknown. It stopped before analysis, worktree creation, context capture, or any subagent launch. Its preserved `review-run/run-state.json` and `final-report.md` mark every standard scenario `NOT EXERCISED`, with an incomplete, non-publishing result. The contract's fail-closed behavior was honored; the missing supported enabled-capacity mechanism is the capability failure filed as [#76](https://github.com/mmena1/skills/issues/76). Unknown capacity is not a passing insufficient-capacity test.

A separate phase-level smoke used one clean pinned worktree at `32b5ba1796db8f594f8ec721129c4ac3bbefdc65`, base `2672c670e1699150bfc333cd2d2e1f751ae2e058`, and an explicit empty read-only context bundle. Exactly the two selected native scouts ran, but their native parent assistant messages were distinct:

| Scout | Parent message ID | Parent inference request ID | Child inference interval, UTC |
| --- | --- | --- | --- |
| `docs` / `6ab9946d` | `b19c22a0-1853-4669-86d5-f771e348cf08` | `a25a9203-d8ce-4d6b-8dc2-a8860bb6e8fa` | 21:44:18.189734 to 21:45:06.193012 |
| `conventions` / `1955d130` | `d3d2c331-b24b-4f1d-8e91-59c17ed61008` | `12afd753-7f54-46cd-8475-d18744e9d2d1` | 21:44:25.657966 to 21:44:46.698218 |

Each parent message contained one `run_subagent` call with `is_background: true`; another parent inference intervened. Child execution overlapped, but the required single-wave grouping failed. The parent's final report falsely claimed both calls were in one assistant message. Native message IDs and distinct inference requests rule out export formatting as the explanation. Follow-up [#77](https://github.com/mmena1/skills/issues/77) covers the dispatch and receipt discrepancy. The successfully grouped seven-profile discovery run establishes that grouped calls are possible, not that this two-scout run complied.

Docs naturally returned `docs-H1`, a glossary pointer to a then-unavailable skill; conventions returned `No hypotheses`. The sole hypothesis became H1 retaining docs provenance, without a duplicate or fabricated concern. Supplemental handoff session `mewing-nutria` launched exactly one foreground `deep-review-validator-static`, child `71ad27b6`, with H1 and a late-bound empty validator manifest. It returned a low Finding, independently citing the pinned glossary, catalog, and `git ls-tree` evidence; its five child turns record `gpt-6-1-sol-high` from 21:47:06.953846 to 21:47:58.026588 UTC. No writable probe was needed or launched. This passes native-role interoperability only. It does not repair the failed scout wave or establish the full coordinator pipeline, queue, or passive receipt, so check 7 remains `NOT EXERCISED`.

Local raw evidence remains under `/tmp/devin-native-smoke-71.9nP1qv`: `discovery.json`, `generic-before.json`, `generic-after.json`, `legacy-before.json`, `legacy-after.json`, `review-rerun.json`, `capacity.json`, `missing.json`, `two-scout.json`, and `static.json`. `child-evidence.json` preserves child inference metadata, `launch-grouping.json` preserves the exact native launch messages, and `verified-evidence-index.json` records session IDs, spawn-call counts, and SHA-256 for each export. Runtime-evidence assertions checked the exact discovery/migration profiles, absence of callable subagent tools in the zero-capacity session, zero launches in the stopped sessions, all seven served variants, two distinct scout launch messages, and the sole H1 static invocation. These assertions inspect actual runtime artifacts; the repository checker and installer integration suite remain separate static/integration verification, not native acceptance. The clean test worktree was removed after preserving evidence; the temporary installations, immutable context, and evidence files are intentionally retained for inspection. `python3 scripts/check.py` passed for 28 skills, `python3 scripts/test_installers.py` passed on macOS through Bash, and `git diff --check` passed. The Windows PowerShell installer path was not exercised.

Coverage from the Claude Code and Devin smoke passes, before the Codex pass below (Claude Code skill `52ec495`; Devin skill `6ccd9f3`):

| Harness | PASS | FAIL | NOT EXERCISED |
| --- | --- | --- | --- |
| Claude Code 2.1.295, Linux | 1 fresh discovery; 2 upgrade from the generic scout layout; 3 model and effort for all seven roles; 4 two-lens single wave; 5 capacity preflight; 6 missing native role; 7 pipeline compatibility | None | Check 2 from a standalone `mmena1/deep-review` installation, which has no Claude Code form. Not run on Windows, where the installer copies agents when file symbolic links are unavailable. |
| Devin CLI 3000.11.3, macOS | 1 fresh discovery; 2 generic-scout upgrade and standalone migration; 3 all seven harness-reported model/High Thinking variants; 5 zero-capacity stop; 6 missing selected native role. Supplemental natural-hypothesis native static handoff also passed. | 4 single-wave grouping in the bounded two-scout smoke, [#77](https://github.com/mmena1/skills/issues/77); enabled capacity observation needed for a complete review, [#76](https://github.com/mmena1/skills/issues/76). | Complete coordinator two-scout execution and check 7 pipeline compatibility; check 5 enabled numeric-cap enforcement; independently server-echoed effort; writable-probe behavior. No Windows/copy-fallback runtime run. |

The Codex results and remaining acceptance checks are recorded below. These Claude Code and Devin passes supplied no Codex runtime evidence.

Cross-harness coverage is consolidated after the Codex results below. No reviewer behavior, role manifest, installer, model configuration, or acceptance scenario was changed by these smoke passes. Issue #71 stays open.


## Codex CLI smoke, 2026-10-08

Issue [#71](https://github.com/mmena1/skills/issues/71), using skill commit `52ec4956668cd9efa9195f3ac7113b8c80b434d3`, which contains the merged implementations of [#69](https://github.com/mmena1/skills/issues/69) and [#70](https://github.com/mmena1/skills/issues/70). Harness: Codex CLI 0.160.0, native multi-agent v2, Linux x86_64 on WSL2, kernel `6.18.33.2-microsoft-standard-WSL2`. Every coordinator ran on the existing `gpt-6.1-sol` / `high` selection; spawn calls supplied no model or effort overrides.

Each installation used a separate home and matching Codex state directory. The normal Linux and Windows configurations and agent directories were left unchanged. The installer, protocol, role manifest, generated model assignments, and reviewer bodies were not changed. For the copy control, an isolated PATH shim made `ln` fail, exercising the installer's existing marked-copy fallback; the agent files were not hand-edited. That control's passes do not erase failures in the default symbolic-link installation.

| Date | Harness | Skill commit | Check | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 1. Discovery after fresh Bash install | PASS | The live `spawn_agent` tool advertised all seven exact native types. Discovery parent `01a11dab-b128-7581-b3ae-91d45dd684b4`. This verifies catalog discovery only; launch failed as recorded below. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | Native launch after the default linked install | FAIL | All seven exact-name readiness launches returned `agent type is currently not available`; no child session was created. Stderr reported `failed to apply role to config: Symbolic link loop (os error 40)`, although the links resolved normally to readable generated files. The default two-scout review also failed at its first native launch. Follow-up [#78](https://github.com/mmena1/skills/issues/78). |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 2. Discovery after in-place skills upgrade | PASS | Installed commit `6abc08d` with the former generic scout, checked out `52ec495` in that same disposable source checkout, then reran the installer. Runtime parent `01a11dac-d2f4-7230-94e9-5dedee56f589` advertised exactly the seven new types and rejected an attempted `deep-review-scout` launch with `unknown agent_type 'deep-review-scout'`. This is migration/discovery evidence; it does not claim successful linked launches. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 2. Discovery after standalone legacy upgrade | PASS | Ran the actual `mmena1/deep-review` installer at `1f8e7f92af27bec6e73c263b024b8e82554c1ed1`, then the current skills installer in the same isolated home. Runtime parent `01a11dac-d30d-7dc3-bca3-292698c4b96d` advertised all seven new types and rejected `deep-review-scout` as unknown. The standalone checkout remained clean. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | Fresh copy-fallback discovery and launch | PASS | Parent `01a11dac-b31e-7ed2-a4e6-ef7f6de5ddaa` launched all seven exact native types in capacity-safe readiness batches. Every child returned `READY`. Neither file inspection nor adopting a generated prompt was counted as a launch. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 3. Pinned model and effort, default linked install | NOT EXERCISED | Every attempted launch failed before child creation, so no reviewer model or effort was served in this installation. Generated fields alone do not establish runtime selection. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 3. Pinned model and effort, copy fallback | PASS | Each child's `session_meta.agent_role` identified the exact native role, and its `turn_context.model` and `effort` matched the pinned values. All seven returned `READY`; per-role records are below. The docs and conventions review children independently reported `gpt-6-luna` / `high`. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 4. Two selected scouts in one wave, default linked install | FAIL | Local range review parent `01a11dac-d305-7342-b773-81d5724cdab5` had 6 available slots for 2 selected scouts, but `deep-review-scout-docs` could not launch. No child started, no substitute was used, and the review remained incomplete and non-publishable. Same defect as [#78](https://github.com/mmena1/skills/issues/78). |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 4. Two selected scouts in one wave, copy fallback | FAIL | Parent `01a11dad-38c7-7f30-8312-6ec0da643993` launched only docs and conventions, at `22:42:38.018Z` and `22:42:45.792Z`, but in separate model responses. The first tool result arrived at `22:42:38.149Z`, before the second call. Their `token_usage_record.response_id` values differ, as recorded below. Both children overlapped on the same pinned worktree, but overlap does not satisfy parallel calls in one message. The parent receipt incorrectly reported PASS. Docs child `01a11dae-cf49-7b31-aa22-5fc8be023c44`; conventions child `01a11dae-eda6-7c71-8ce3-ad7e497119b8`. Follow-up [#80](https://github.com/mmena1/skills/issues/80). |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 5. Capacity preflight | PASS | With isolated `agents.max_concurrent_threads_per_session = 1`, parent `01a11dac-d2ff-74f2-b48e-6fcddc46b91c` observed only its own coordinator in the live agent list, reported 2 required scouts versus 1 available, and stopped before any `spawn_agent` call, target analysis, context capture, or worktree creation. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 6. Missing selected native role | PASS | Removed only the isolated copy installation's docs agent. Parent `01a11dac-d2fa-76c3-aa13-1bd5aec23e88` named `deep-review-scout-docs` as missing and stopped before any scout launch, target analysis, context capture, or worktree creation. Capacity was sufficient, 2 required versus 6 available; no generic agent, other scout, coordinator analysis, or model substituted. |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | Native role sandbox selection | FAIL | All seven copy-fallback readiness children, and both review scouts, recorded `sandbox_policy.type = danger-full-access`, inherited from the coordinator. The generated scout/static roles declare `read-only`, and the probe declares `workspace-write`. Model and effort pins were honored in those same records. This is an observed runtime policy metadata mismatch; write enforcement was not probed. Follow-up [#79](https://github.com/mmena1/skills/issues/79). |
| 2026-10-08 | Codex CLI 0.160.0, Linux/WSL2 | `52ec495` | 7. Pipeline compatibility after natural hypotheses | NOT EXERCISED | In the copy-fallback review, conventions returned `No hypotheses` and docs emitted `docs-H1` about a glossary reference. The coordinator observed the sandbox mismatch, marked the review incomplete, preserved the hypothesis as not validated due to review failure, and stopped before static adjudication. Readiness launches of validator agents do not count as hypothesis validation. Neither one-invocation-per-canonical-hypothesis behavior nor a completed validator receipt was exercised. |

Observed readiness model/effort records, from parent `01a11dac-b31e-7ed2-a4e6-ef7f6de5ddaa`:

| Native role | Observed model | Observed effort | Child session, all returned READY |
| --- | --- | --- | --- |
| `deep-review-scout-bugs` | `gpt-6.1-sol` | `high` | `01a11dac-cc13-7cb2-8b6e-b718fc516e34` |
| `deep-review-scout-conventions` | `gpt-6-luna` | `high` | `01a11dac-d5dc-7150-94e7-52854bac4ae2` |
| `deep-review-scout-history` | `gpt-6-luna` | `high` | `01a11dac-e13d-7473-9f28-0f38ecd1c482` |
| `deep-review-scout-docs` | `gpt-6-luna` | `high` | `01a11dac-ec42-72d1-b780-92e341ec7b2b` |
| `deep-review-structural` | `gpt-6.1-sol` | `high` | `01a11dac-f5bc-7c02-9ff5-15235b95d559` |
| `deep-review-validator-static` | `gpt-6.1-sol` | `high` | `01a11dac-ffee-7de0-b7ad-5ace5865b13b` |
| `deep-review-validator-probe` | `gpt-6-luna` | `high` | `01a11dad-30f2-7ad0-b562-a571f40e4d19` |

The local reviews used the existing committed documentation range `2672c670e1699150bfc333cd2d2e1f751ae2e058..c9fbab3e9227ad8147f2aa29a75e56dc682833b1`, ten added lines, with an explicitly empty context snapshot. No hypothesis was injected and no validation outcome was forced. The copy review's receipt named both native scouts, recorded their actual model/effort and the sandbox failure, and listed no validator agents as having run. Its one-wave PASS was incorrect; the acceptance record corrects it from native call and response evidence while retaining the original receipt unchanged.

Combined passive receipt for the linked review, copy review, and capacity gate, scoped to their actual observations:

| Scenario | Status | Observed evidence |
| --- | --- | --- |
| Zero hypotheses | NOT EXERCISED | Linked scouting failed to start; copy scouting produced one hypothesis. Neither run took the successful zero-hypothesis path. |
| Surviving hypotheses | NOT EXERCISED | One natural docs hypothesis remained unvalidated after the runtime sandbox failure; no static adjudicator ran. |
| Capacity-bounded static validation | NOT EXERCISED | No static queue was executed. |
| Multiple selected scouts | FAIL | Default linked installation could not launch the wave (#78). Copy-fallback children overlapped, but separate parent model responses failed the required one-message grouping, and the receipt incorrectly reported PASS (#80). |
| Insufficient scout capacity | PASS | The isolated one-slot run stopped before launch and reported exactly 2 required and 1 available. |
| Validator probes | NOT EXERCISED | No static adjudication or `Needs probe` transition; readiness of the probe role is not a writable validation run. |
| Scout failure | PASS | Default native launch failure produced an incomplete, non-publishable review; no running child needed waiting, and no substitution or `No findings` claim occurred. |
| Validator partial failure | NOT EXERCISED | No validator adjudication began. |
| PR-review-overlap | NOT EXERCISED | Local committed-range reviews, without a uniquely associated open PR; no comparison or publication occurred. |
| PR head change | NOT EXERCISED | Fixed local range; no PR freshness transition was exercised. |
| Cleanup | PASS | Each coordinator preserved its state/report, removed only its own authorized worktree and context/run directory, and verified registration removal. Both caller and standalone checkouts stayed clean. The capacity and missing-agent runs created no worktree to remove. |

Runtime evidence is retained locally at `/home/martin/.codex/2026-10-08-issue-71-ljefe80e/`: `*.events.jsonl`, `*.stderr.log`, `*.prompt.txt`, installation logs, native child rollouts under the isolated homes, `runtime-observations.json`, `codex-launch-grouping.json`, and `SHA256SUMS`. The four review/preflight exits preserved `review-links-report.md`, `review-copy-report.md`, `capacity-report.md`, `missing-report.md` and matching `*-run-state.json` files. `normal-before.json` and `normal-after.json` verify unchanged normal configuration/agent contents and link targets. Credentials copied for isolation were removed after execution. Static file inspection and repository checks are configuration/maintenance evidence only; none supplied a runtime PASS.

Issue #71 combined coverage by harness, incorporating the Claude Code and Devin evidence above:

| Check | Codex CLI | Claude Code | Devin CLI |
| --- | --- | --- | --- |
| 1. Fresh discovery | PASS for the live seven-type catalog; default linked launch separately FAIL | PASS | PASS |
| 2. Upgrade discovery | PASS for same-checkout and actual standalone migrations, including runtime rejection of the retired type | PASS for generic-scout upgrade; standalone migration NOT EXERCISED because no historical Claude Code form exists | PASS for generic-scout and actual standalone migrations |
| 3. Pinned model and effort | PASS for all seven copy-fallback roles; NOT EXERCISED for unlaunchable linked roles | PASS for all seven roles' runtime models and harness-recorded high effort | PASS for all seven harness-reported model/High Thinking variants; independent server-echoed effort NOT EXERCISED |
| 4. Exact two-scout concurrent wave | FAIL for default linked launches (#78) and copy-fallback one-message grouping/receipt (#80); child execution did overlap | PASS | FAIL for bounded one-message grouping (#77); full coordinator execution NOT EXERCISED |
| 5. Capacity preflight | PASS, required 2 versus available 1 | PASS, cap 1 versus required 2 | PASS for disabled capacity, required 2 versus available 0; enabled numeric-cap enforcement NOT EXERCISED; usable enabled-capacity observation fails (#76) |
| 6. Missing native role | PASS | PASS | PASS |
| 7. Natural pipeline compatibility | NOT EXERCISED: reported sandbox failure blocked static adjudication | PASS, one static invocation for each of H1, H2, and H3 | NOT EXERCISED: enabled-capacity preflight blocked a complete coordinator review; supplemental native H1 handoff PASS only |

Native Codex launch grouping, from parent `01a11dad-38c7-7f30-8312-6ec0da643993`:

| Scout | Launch time, UTC | Parent model response ID |
| --- | --- | --- |
| docs | 22:42:38.018 | `resp_04b1a2f827a3fce7016ac81c5f2ab88193a6c2e49a08445052` |
| conventions | 22:42:45.792 | `resp_04b1a2f827a3fce7016ac81c67a3a08193b62d06d1c2108c04` |

The docs launch result was consumed before the conventions response. The response IDs are from native token-usage records, not the coordinator's report; distinct responses establish the grouping failure. Both selected children ran, and no other scout launched, but those observations alone do not establish the required single-message wave. The original copy review receipt is retained as evidence of the false PASS; `codex-launch-grouping.json` records the correction and raw source hash. No rerun or fix was performed for this correction.

Remaining acceptance by harness:

- Codex: resolve or characterize default linked launch failure (#78), reported sandbox selection mismatch (#79), and launch grouping/receipt failure (#80). Then rerun the affected native checks and exercise the natural static-validation pipeline and native-agent receipt. Model/effort selection is observed for all seven copy-fallback roles; linked-role serving remains NOT EXERCISED. Actual write enforcement and writable-probe behavior remain NOT EXERCISED.
- Claude Code: Windows/copy-fallback runtime behavior remains NOT EXERCISED. The seven core Linux checks have passing evidence above. Standalone migration is NOT EXERCISED because there was no historical Claude Code installation form; it is not inferred as PASS.
- Devin: resolve or characterize enabled capacity observation (#76) and one-message scout grouping/receipt (#77), then run the complete coordinator wave and pipeline. Enabled numeric-cap enforcement, independent server-echoed effort, writable-probe behavior, and Windows/copy-fallback runtime behavior remain NOT EXERCISED.

Cross-harness acceptance is incomplete: Codex has three observed failures and an unexercised pipeline, Devin retains its two linked failures and explicit coverage gaps, and Claude Code retains its platform and unavailable legacy-form gaps. Issue #71 remains open. Follow-ups record failures; no protocol, installer, model configuration, or reviewer behavior was fixed in this task.
