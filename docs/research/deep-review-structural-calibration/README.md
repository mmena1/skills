# Structural scout recall calibration

Research date: 2026-10-09. Repository research only; no skill changes, production changes, tracker writes, or published comments.

A recall regression is plausible but unestablished. PR #58 removed concrete discovery prompts and changed several adjudication layers together. It did not introduce the requirement for an alternative at scout admission, and it did not change structural scout models. The historical corpus supplies useful candidate concerns, not an unbiased recall measurement or automatic gold labels. The next justified action is a blinded, paired calibration run, followed by a small discovery-cue ablation if misses survive neutral adjudication.

## Deliverables and evidence boundaries

- [Case catalog](case-catalog.json): five immutable reviewed snapshots and thirteen concern records, each with mechanism, maintenance task, candidate alternative, acceptance source, disposition, and evidence tier. Evaluator-only.
- [Rubric history](rubric-history.md): exact treatments and later model/orchestration confounders, with primary-source links. Evaluator-only.
- [Capsule preparation](prepare-capsules.py): a runnable source-only materializer that verifies exact source trees/diffs and removes original commit history. It does not invoke models or implement a security boundary.

Primary evidence was fetched from GitHub REST PR/review/comment/commit/issue/timeline APIs and GraphQL `pullRequest.reviewThreads`, including `comments.originalCommit.oid`. Code and fix diffs were independently inspected. No historical private scout transcripts or model invocation receipts were available. The GitHub publishing account is the same maintainer across these discussions, and several reviews explicitly describe AI assistance. A later assessment, acceptance reply, implementation, or re-review supports independent workflow adjudication; it does not prove multiple independent human reviewers, measured maintenance time, or the original scout's identity.

Raw evidence and actual preflight receipts are retained outside the repository at `/home/martin/.local/share/skills-research/structural-calibration-20261009/`. The repository checker scans ignored scratch text too; raw historical prose contains characters prohibited in this repository, so those source records were preserved outside its scan. Treat that entire directory as evaluator-only.

## Historical case catalog

The following are accepted concerns, separated by mechanism rather than historical finding number. Full evidence, constraints and candidate alternatives are in the JSON catalog. Fixed concerns still require neutral label adjudication: a fix demonstrates acceptance and an implementation, not by itself a qualifying structural cost.

| ID | Case | Mechanism and concrete maintenance burden | Disposition and evidence |
| --- | --- | --- | --- |
| S01 | #72 | Validity flags are written across parser paths and recombined in `result`; establishing surviving outcomes/issue provenance requires tracking several lifetimes and terminal branches. | Fixed in merged #74/#73. [Original concern](https://github.com/mmena1/mtg-copilot/pull/72#discussion_r4116298686), [independent assessment](https://github.com/mmena1/mtg-copilot/pull/72#pullrequestreview-5331391668). Keep the sticky-continuity correctness bug separate. |
| S02 | #72 | Four repeated positional parse-result signatures plus a one-to-one match conversion require coordinated representation edits and traversal without separate policy. | Fixed in [#74](https://github.com/mmena1/mtg-copilot/pull/74). [Concern](https://github.com/mmena1/mtg-copilot/pull/72#discussion_r4116298689); #73 names the result and removes the intermediate. |
| S03 | #72 | Public `line` lacks file identity after overlap merging, while `locations` is authoritative; a new consumer must reconcile two location contracts and retained-occurrence ordering. | Removed in `bd9d9a4`, independently [verified](https://github.com/mmena1/mtg-copilot/pull/72#pullrequestreview-5331457940). Treat public maintenance ambiguity separately from any alleged runtime bug. |
| S04 | #72 | Always-false public `replay_ready` adds a concept whose semantics belong to later extraction; implementing extraction must reconcile premature inspector API with `production_support`. | Removed in `bd9d9a4`. [Concern](https://github.com/mmena1/mtg-copilot/pull/72#discussion_r4116298693). Borderline candidate: exclude from gold if neutral inspection finds only a speculative future preference. |
| S05 | #91 | Context expiry, fresh-source selection and qualification independently encode freshness; a policy change needs coordinated edits to prevent availability/pinning drift. | Fixed in `d0c3579`; [concern](https://github.com/mmena1/mtg-copilot/pull/91#discussion_r4174692980), [acceptance](https://github.com/mmena1/mtg-copilot/pull/91#pullrequestreview-5402575136), [verification](https://github.com/mmena1/mtg-copilot/pull/91#pullrequestreview-5402599766). |
| S06 | #91 | Repeated availability lookup and an implied prevalence condition require tracing three functions across two modules to establish that a branch changes nothing. | Advisory fixed with S05 in `d0c3579`. [Concern](https://github.com/mmena1/mtg-copilot/pull/91#discussion_r4174692991). Preserve meaningful prevalence disclosure and mismatch-check order. |
| S07 | #94 | Artifact/catalog checks live in spine with anonymous absence; profile/legality/time checks live in meta context with explicit reasons. Explaining or extending eligibility requires two policy owners plus pin validation. | [Accepted advisory](https://github.com/mmena1/mtg-copilot/pull/94#pullrequestreview-5403117115), tracked in [#95](https://github.com/mmena1/mtg-copilot/issues/95), still open. A comment reports local implementation `1e8ab5ea` and tests; current main retains split ownership. Provisional. |
| S08 | #94 | Three builders turn projection into a defaulted boolean and helpers turn it back into disclosure; a new builder must coordinate redundant state, with omission found only at request validation. | Fixed in `03bf05af`; [concern](https://github.com/mmena1/mtg-copilot/pull/94#discussion_r4175127411), [verified reply](https://github.com/mmena1/mtg-copilot/pull/94#discussion_r4175200696). Existing outputs were safe. |
| S09 | #102 | Campaign refusal precedence is duplicated in admission/pre-case checks and refusal-to-shortfall mapping is repeated; adding/reordering a reason requires three coordinated edits. | Explicitly deferred to open [#104](https://github.com/mmena1/mtg-copilot/issues/104). [Concern](https://github.com/mmena1/mtg-copilot/pull/102#discussion_r4178292788), [assessment](https://github.com/mmena1/mtg-copilot/pull/102#pullrequestreview-5407110920). Provisional. Preserve pre-construction stop and durable admission. |
| S10 | #102 | Five helpers repeat price lookup/absence logic; changing accounting policy needs coordinated edits preserving absent input, unpriced configurations and legitimate zero. | Annotation fixed in `7fce676`; broader refactor deferred to [#104](https://github.com/mmena1/mtg-copilot/issues/104). [Concern](https://github.com/mmena1/mtg-copilot/pull/102#discussion_r4178292792). Provisional; a price-only alternative loses necessary input context. |
| S11 | #108 | Bare operational error strings and multiple `ValueError` sources force callers to infer recovery by parsing an undocumented text protocol. | Typed boundary error fixed in `f5145112` and retained in final rebased head. [Concern](https://github.com/mmena1/mtg-copilot/pull/108#discussion_r4190041620), [assessment](https://github.com/mmena1/mtg-copilot/pull/108#pullrequestreview-5422066600), [verification](https://github.com/mmena1/mtg-copilot/pull/108#pullrequestreview-5422351758). Auxiliary contract/correctness case, excluded from primary structural recall. Typed exceptions and failure values are both acceptable. |
| S12 | #108 | Freeze/load repeat validity policy in different orders; adding a precondition requires updating both, while an extra review verification compensates for review/packet ordering. | Accepted [follow-up](https://github.com/mmena1/mtg-copilot/pull/108#discussion_r4190269653), open [#109](https://github.com/mmena1/mtg-copilot/issues/109), still duplicated on current main. Provisional. |
| S13 | #108 | Four internal flows pass a placeholder reviewer to a public authorization/lock guard; future caller-specific behavior couples internal logic to a fictitious identity and packet recursion. | Accepted [follow-up](https://github.com/mmena1/mtg-copilot/pull/108#discussion_r4190269861), open [#110](https://github.com/mmena1/mtg-copilot/issues/110), still present on current main. Provisional. Preserve error and packet order. |

There are seven fixed structural candidates, five provisional follow-up concerns, and one auxiliary contract concern. This is not a denominator of thirteen confirmed structural defects. #73 is closed after merged #74; #95, #104, #109, and #110 are open as of the research date. Resolved GitHub threads do not imply implemented follow-ups: #108's deferred threads are resolved while their issues remain open.

The parser follow-up changed two externally observable provenance classifications as well as structure. Those correctness corrections cannot be used as proof that every proposed structural alternative preserves behavior. Conversely, a passing test suite does not disprove a demonstrated maintenance cost.

## Exact reviewed commits and bases

Use these original snapshots, not final PR heads, squash merges, or today's `base.sha` substituted retrospectively. Each base is the original implementation chain's parent and an ancestor of the reviewed head. These full identifiers also appear in the machine-readable catalog.

| Case | Original review base | Reviewed pre-fix head | First relevant later fix |
| --- | --- | --- | --- |
| M72 | `5542ce2b4f6a04e5df4d53c5992c238733d86f51` | `f9acf3a39d2af2ff6e34ce53e9e54d9371382c4f` | `bd9d9a42ffb1f248653381e8c0b4d6d4bd54229b`; S01/S02 later fixed by #74 |
| M91 | `ad18e21533fb8da562e4351ade0d4bd9e546b8f3` | `6a276a789b7e1d8d385f4e9382ea14f2d1c4f358` | `d0c3579209615563c826b4acd0651daec7d56b60` |
| M94 | `b681583d2d9080d60e44fc4e02b4b5aba93e6f39` | `58eb456461cbff688c83c42f3e2b3078c1df748f` | `03bf05afd90c84ad546a730b2ce3a1a783fb0d4c`; S07 tracked separately |
| M102 | `2273f7c13e1c4a804e39a442025643442cf5e00d` | `518bd84c4e5a81047f4886b835e4d7999659c895` | `7fce676ff6960d075616beb89e8fdfbbb8c7221b`; broad refactors remain |
| M108 | `4aab2dd02c45e1fc84cf765e539d645a6a0ff65a` | `44c542485fcebbd3d5746502087857af982f27f7` | `f5145112e9a78cae717798c8dd135a1b229faef6`; S12/S13 remain |

Commit provenance is recoverable through original review bodies and GraphQL `originalCommit`, then parent traversal. [M72 review](https://github.com/mmena1/mtg-copilot/pull/72#pullrequestreview-5331377882), [M91 review](https://github.com/mmena1/mtg-copilot/pull/91#pullrequestreview-5402575136), [M94 review](https://github.com/mmena1/mtg-copilot/pull/94#pullrequestreview-5403117115), [M102 assessment](https://github.com/mmena1/mtg-copilot/pull/102#pullrequestreview-5407110920), [M108 review](https://github.com/mmena1/mtg-copilot/pull/108#pullrequestreview-5422066600).

Important reconstruction hazards:

- PR #91 was rebased. Its current REST commit list includes `0639834c` (an earlier combined freshness change), followed by `a1a48759`; neither the final head nor its immediate predecessor is a trustworthy recreation of the original freshness concern. The original head `6a276a7` and original base above preserve it.
- PR #108 was rebased after the structural review and after another mainline PR landed. Its REST base `bd60c921` was committed at 23:58 UTC, after the 23:47 UTC structural review. The original base is `4aab2dd0`, parent of original implementation `3337b395`, rather than the later base. Its final head `bd423531` already contains the blocking fixes.
- REST review-comment `commit_id` can track a later remapping. For example #94's eligibility comment now names final head `03bf05af`, while GraphQL `originalCommit` is `58eb4564`. #72's structural comments similarly remap to `bd9d9a4`. Preserve original anchors and inspect them against the original head.
- #102 is a stack atop #101. Its base above excludes the subscription amendment under review. Final review still contains provisional refactors but the annotation and runtime findings are already fixed; use one original snapshot for the whole case.

## Treatments and controlled comparison

A is `mmena1/skills@b3a568ec926abc17326213dfb3bd00a48feb256a`; B is `mmena1/skills@5e61f1a0494701f4844c04351235fa77714d9c4e`, the accepted merge of PR #58. The detailed [history note](rubric-history.md) supplies per-layer changes and immutable source links.

Both A and B already require a concrete maintenance concern and behavior-preserving simplification/alternative before scout emission. #58 replaced opinionated design authority and concrete aggressive search prompts with task-cost signals, technique neutrality, and explicit burden comparisons. It retained responsibility scans. It also changed the validator, scope wording, deduplication and reporting, so a complete A/B run alone cannot attribute a difference to the lens.

Use the exact SCOUT plus structural lens from each revision. Authentic A also receives its pinned `codebase-design` dependency; authentic B does not. This is an intentional treatment difference. Do not mix A's lens with B's common contract and call it the historical A treatment. A lens-only or discovery-cue intervention is a separately named ablation.

The source-configured Codex structural scout and static validator stayed `gpt-6.1-sol/high` across #58 and later changes. Claude equivalents stayed `claude-opus-5-5/high`. Later Devin model changes and Codex native-role/installation/dispatch changes are separate factors. These are configuration facts, not receipts proving models used in the historical mtg reviews. The local checkout tip is `63981d07b0c6c40d23c3000abc36309ceff8f12b`; the history note audits deep-review through `ac3993be`, whose successor adds the unrelated portfolio skill.

Proposed experiments, in order:

1. **Discovery:** paired A/B scout runs on identical source, diff, tracked instructions, supplemental context, model/effort, tool surface, context budget and timeout. No other scouts, overlap suppression, coordinator adjudication, or published-review awareness. The structural role inspects the complete original base-to-head diff and surrounding source/tests. Supplemental context is empty in both arms; this is a controlled source-only calibration, not exact replay of an unknown historical bundle.
2. **Common neutral validation:** pool raw emitted hypotheses, remove treatment/model/run identifiers, assign fresh opaque IDs, and independently replay each through B's validator. Preserve the exact cost/task/mechanism and alternative. Its alternative may be improved for the same concern; a different mechanism cannot rescue it. Use the same model/effort and source access in every invocation. Static only unless the same predefined probe policy authorizes a decisive runtime check.
3. **Optional crossed validation:** validate the same pooled hypotheses under A and B to separate rejection-policy differences. A's design dependency is explicit; its outputs do not define neutral gold labels.
4. **Cue ablation, conditional on misses:** B plus a short neutral investigation checklist versus unchanged B, with B admission and B validation frozen. Add only cues, not historical answers or preferred remedies.
5. **Runtime integration, separate:** test actual native agent loading, resolved model/effort, full wave dispatch, output completion, and installed-body hashes. Attribute failures here to execution, not semantic recall. An end-to-end integration trial follows direct calibration; it is not required to diagnose discovery cues.

The model setting is a proposed fixed experiment setting, subject to the user's model selection. Do not escalate a struggling run or silently substitute an available model. Record the actual resolved identifier and effort, CLI/provider build, token budget, prompt hashes, capsule hashes, timestamps, exit status, tool log and truncation status. Reject a pair whose settings differ. If the exact requested model is unavailable, mark execution failure and stop that arm.

Start with M91 and M94 plus two negative controls, one replicate per arm: eight scout invocations, then at most twelve unique static validator invocations. Suggested ceilings are ten minutes and a fixed 24,000 total-token cap per scout, and five minutes/12,000 per validator, using identical supported caps. If the runner cannot enforce/report caps, establish its actual budget mechanism before comparison. Do not rerun selectively because an answer is disappointing. The larger preregistered run is five historical cases plus five controls, two arms, three independent repetitions: sixty scouts, with a separately capped validator batch. Randomize arm order per case/repetition. Use fresh sessions; no retained context between cases or arms.

## Blinding and prevention of future access

Prompt instructions alone are insufficient. A normal worktree shares a Git object database with future commits; prohibiting `git log --all` does not prevent `git show <fix-sha>`. A read-only sandbox can also expose the evaluator's files and current checkouts.

The materializer exports the original base and head into a new Git repository with exactly two synthetic commits and neutral messages/dates. It verifies original tree equality and byte-identical diffs. No original commits, remote, reflog history, alternates, sibling worktree links, hidden labels or fix objects are supplied. Reviewer manifests name only the synthetic SHAs and source scope. Full tracked source/instructions/tests are preserved. Original history is deliberately withheld in both arms; any later historical sensitivity test must use a separate repository containing only objects reachable from the original head, inspected for answers in commit messages.

Run each model in an isolated review session with access to exactly one capsule and one supplied treatment contract bundle. Keep this report, catalog, code that builds the capsules, source repositories, receipts, historical comments, issues, fixes, case mapping and scorer outside that boundary. Mount only regular files; forbid parent-path traversal, host home directories, connector access, GitHub, web search, and arbitrary network/file tools. Disable automatic memory, user skill discovery, persistent conversations and installed agents that could load today's contracts. Target tracked instructions remain available and identical across arms.

Preferred semantic runner: a broker supplies source through a read-only allowlisted file/Git service or a complete source packet, and sends no browsing/connector tools to the model. Provider network stays in the broker, never in reviewer shell tools. Validators use the same isolated interface. If an OS-contained agent runner is used instead, enforce the same filesystem/network boundary outside the model and verify it. The presence of `bwrap`, a role TOML, or a prompt promise is not sufficient evidence.

Before a reviewer run, have the runner execute deterministic access checks: label file, source checkout, sibling capsule, original fix object, alternate refs, GitHub/network lookup and environment credential access must all fail; allowed source reads and synthetic base/head diff must succeed. A leaked label/future artifact invalidates the run, even if the final answer looks independent. Historical source may identify the project or issue; do not rewrite production source to hide those legitimate facts, instead prevent retrieval of historical answers. Keep benchmark class names and expected outcomes out of target filenames, supplied prompts and visible session names.

Ground-truth construction is separate from reviewer execution. Before any A/B results are inspected, independent adjudicators examine the same pre-fix source and a minimally restated candidate concern without historical comments, disposition, fixes, review conclusions or treatment labels. They must establish task, mechanism, diff relevance, cost and a qualifying behavior-preserving alternative under the neutral standard. Lock eligible labels and excluded/provisional reasons. Disagreements remain excluded or provisional until independently resolved. Do not use the output of one treatment to retroactively expand that treatment's gold denominator.

## Negative controls

Use explicit base/head fixture pairs with normal domain/task contracts, then independently establish expected outcomes under neutral validation. These are required fixtures to construct for the calibration run, not already executed tests. Do not expose their IDs or descriptions below to reviewers.

| Control | Target design | What must not become a finding |
| --- | --- | --- |
| N1 | Same small rule implemented with an explicit loop versus a collection expression; both local, same invariants and change surface. | Syntax, shorter code, function length or nesting alone. |
| N2 | Adapter/DI boundary owns version translation and allows a test transport; removing it makes two callers restate translation and error policy. | Layer/helper/DI presence or a deletion preference that adds equal burden. |
| N3 | Small class owns durable lifecycle/resource acquisition and release; functions own transformations outside it. | A blanket functional-programming or deep-module preference, or class count. |
| N4 | Optional evidence and explicit status distinguish missing, invalid and valid inputs with materially different required behavior; guards expose those constraints. | Optionality, branch/state count, or collapsing states that changes behavior. |
| N5 | Two similar calculations have independent contracts/reasons to change, and a shared helper would introduce a mode parameter or hidden policy switch. | Textual duplication or abstraction extraction without shared knowledge. |

Also replay crafted validator-only hypotheses against these controls and one equal-burden alternative. Include a hypothesis that alleges indirection while another genuine duplicated-policy concern exists at the same code: the validator must reject the claimed indirection rather than substitute the other concern. Freeze these challenges before A/B output. The old acceptance receipt's five fixtures can be replicated as a supplementary suite, but that receipt contains labels and must never enter model context. No corpus case is globally negative merely because it has no catalog match: unknown valid findings are possible.

## Scoring and decision rules

The unit of a known concern is the same task, structural cost and causal mechanism, not a matching title, chosen refactor, helper name or historical line number. Score against frozen eligible labels; multiple hypotheses about the same concern count once. One broad hypothesis can cover several labels only if it independently states each task/cost/mechanism; report grouping and a conservative one-credit sensitivity result. Preserve different mechanisms at one anchor.

| Measure | Definition and handling |
| --- | --- |
| Known-concern scout recall | Eligible labels matched by an admission-qualified raw scout hypothesis / eligible labels in successful eligible case runs. A runtime-only bug, vague complexity claim or missing alternative is not a structural match. Report per concern and case, and macro-average across five cases. |
| Known-concern validated recall | Eligible labels whose matched hypothesis receives `Finding` under the common B validator / same eligible labels. Also report the paired difference and repeat stability. |
| Provisional follow-up coverage | Same two measures on S07/S09/S10/S12/S13, reported separately with their uncertainty; never merge them into confirmed recall by default. |
| Scout admission | Number of emitted hypotheses, independently admission-qualified fraction, schema violations, invalid/partial concern attempts, and per-case zero-hypothesis runs. Admission is emission, not the scout's private reasoning. An instructed-only output contract cannot measure undisclosed internal discovery. |
| Validator rejection | Counts/rates of `Disproved`, `Unresolved`, and `Needs probe`, split by rejection reason: absent cost/task, unchanged/legacy scope, essential structure, behavior change, relocated/equal burden, preference, insufficient evidence. `Needs probe` is a transition, not a final miss or false positive. |
| Novel findings | Deduplicated, label-unmatched hypotheses independently confirmed from permitted pre-fix source. Report useful novel yield and mechanism separately. Never call them false positives merely for missing from the catalog. Add them to a future benchmark version, not the current denominator. |
| False positives | Hypotheses independently disproved as incorrect costs/alternatives or architecture preferences, per successful case and per emitted hypothesis. Separately report control admission rate and control validated-finding rate. `Unresolved` is uncertainty, not automatically FP. Wrongful confirmation on a gold negative is validator FP; disagreement needs independent audit. |
| Execution failure | Launch/model/effort mismatch, API error, timeout, truncation, missing output, schema-only unusable output, confinement failure or leaked context. Exclude from successful-run recall denominators, but report failure counts and paired completion. Also publish an intention-to-run lower bound counting failed opportunities as unrecovered, clearly labeled operational rather than semantic recall. |

A clean completed `No hypotheses` is a semantic zero. A failed scout is not. A concern not emitted is an admission miss; raw output cannot tell whether the model never discovered it or privately rejected it. A concern emitted by both arms but rejected only under one validator is a validation difference. If current native output disappears while direct-role runs agree, investigate installation, orchestration, truncation and overlapping-review suppression before changing the rubric.

Freeze matching rules, budgets, labels and controls first. Have assessors blinded to treatment match outputs independently; adjudicate disagreement without looking at fixes or future source. Show every concern's A/B results rather than only an aggregate. Use paired case-level descriptive effects and resampling by case, not thirteen supposedly independent concerns. Five historical cases and three repetitions are small and selected for positive history; they cannot establish general review quality or a precise population false-positive rate.

A cue change is justified only if misses under B are independently eligible, a cue ablation recovers them reproducibly across more than one cost family, and controls/novel-candidate precision show no material degradation. If A's apparent advantage consists of preference findings or alternatives rejected under B, that is useful neutrality, not a recall regression. If both arms miss the same concerns, investigate corpus tasks, context and budget before assigning causality to #58. Do not weaken admission or validation merely to match historical counts.

## Actual observations versus predictions

Actual observations from this investigation:

- All five original snapshot pairs were reconstructed. Both original bases for rebased #91/#108 are ancestry-verified; future REST metadata would have contaminated those recreations.
- Five source-only capsules passed source tree equality and byte-identical diff checks. All known first-fix commit objects were absent. Each capsule has exactly two reachable commits, no remotes, no alternates and no unreachable objects. A second preparation reproduced all five synthetic commit, tree and diff hashes exactly.
- A basic `bwrap` user/pid/network namespace launch succeeded. Reviewer/provider integration and actual host filesystem/network denial have not been exercised. This is an isolation feasibility observation, not a secured model run.
- Canonical repository checks passed. The only added files are research/benchmark artifacts.
- Historical #58 acceptance reports identical A/B admission on its narrow five-fixture synthetic suite. Those are earlier reported results, not reruns here, and do not cover this corpus's full cost families. See the [immutable receipt](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/runtime-acceptance.md).

No fresh A/B reviewer or validator comparison ran. This research session contains the labels, comments and fixes; its available agents inherit host access, and no verified label-blind model broker was configured. Launching prompt-confined reviewers here would not satisfy the requested prevention of access. Fresh calibration recall, precision, admission and rejection rates are **NOT EXERCISED**, not zero. The capsule preflight is a preparation result, not an initial recall result.

Predictions to test, not observed results:

- Concrete cues may recover hidden state and internal-boundary coupling, especially S01/S07/S13, without needing an architecture preference.
- Duplication concerns S05/S09/S12 may already be retained because B explicitly names duplicated knowledge. Losing them would implicate search coverage, context or admission interpretation rather than a removed category alone.
- S04 and S10 may fail neutral adjudication because their current task burden or safe alternative is weaker than historical acceptance suggests. That would improve labels rather than prove regression.

PR #58 merged on 2026-10-05 at 16:12 UTC. #72/#91/#94/#102 reviews predate it; #108's structural review occurred afterward on 2026-10-05 at 23:47 UTC. This chronology prevents treating all five as known pre-change reviewer runs. Without installed-version/invocation receipts, it also cannot establish that #108 used B. [#58](https://github.com/mmena1/skills/pull/58), [#108 review](https://github.com/mmena1/mtg-copilot/pull/108#pullrequestreview-5422066600).

## Preliminary root cause and smallest candidate change

The best current hypothesis is a discovery-cue salience loss: detailed pattern prompts disappeared while prohibition/admission language became more prominent. A second hypothesis is interpreting the narrowed diff-exposed legacy wording as permission to inspect only newly added statements. Both require the paired experiment. A new alternative requirement and a Codex structural-model downgrade are contradicted by the source contracts. A different validator disposition, incomplete native launches or context differences remain plausible, and the historical comments cannot localize them.

The smallest candidate intervention is a short task-oriented investigation checklist in B's structural lens, tested first as an ablation:

- Trace one changed rule through all owners/callers and list which sites must change together.
- Trace state writes to outcome construction; identify which combinations a maintainer must establish.
- Separate caller authorization from internal invariants when changed internal flows borrow caller identity or ordering.
- Inspect one changed flow's independently nameable responsibilities and the concrete task affected by their combination.

These are questions for investigation, not findings or preferred remedies. Keep the task/cost/mechanism/qualifying-alternative admission threshold, technique neutrality, independent validation, same-concern rule, scope constraints and no quota unchanged. Do not restore `codebase-design` as adjudication authority or aggressive finding language. If calibration does not substantiate the cue hypothesis, make no rubric change.

## Proposed /to-tickets scope

This is a proposed breakdown only. No skill publication workflow was invoked and no issues were created.

1. **Reproduce a blinded structural calibration run.** Blocked by: none. Deliver a verified isolated runner, frozen/adjudicated catalog and five controls, prompt/capsule hashes, fixed-model paired A/B pilot, common neutral validator replay, scoring and failure receipts. Acceptance: label/fix/network/host-access challenges fail closed; all raw stages retained; provisional labels separate; user model choice honored; the run can be repeated from pins. Start with the bounded eight-scout pilot, expand only after it is valid. This is one complete executable research slice, not separate horizontal catalog/runner/scoring tickets.
2. **Restore neutral investigation cues if calibration demonstrates lost discovery.** Blocked by: ticket 1's completed and accepted causal result. Deliver only the smallest lens cue change justified by B-versus-ablation results, including paired regression controls and canonical repository checks. Acceptance: recovered eligible concerns in multiple cost families; no demonstrated control/precision regression; no changed admission/validator neutrality, remedy bias, quota, models or orchestration. If ticket 1 does not justify it, omit this ticket rather than queue a predetermined fix.

Keep model changes, installation fixes, orchestration changes and mtg-copilot refactors outside these scopes. Ticket 1 may recommend a separate runtime ticket only if actual receipts identify a runtime failure. Existing mtg follow-ups remain their own work; rediscovering them does not authorize implementation or duplicate issues.

## Reproduction commands

Use Python 3.11+ and Git. Source repositories and output directories are evaluator-only. If an original pre-rebase object is missing, fetch that exact SHA to a separate bare depot with the host's existing authentication; do not change credentials:

```bash
git init --bare /path/to/evaluator/corpus.git
git -c 'credential.helper=!gh auth git-credential' \
  --git-dir=/path/to/evaluator/corpus.git fetch --no-tags \
  https://github.com/mmena1/mtg-copilot.git \
  f9acf3a39d2af2ff6e34ce53e9e54d9371382c4f
```

Repeat exact-SHA fetching for missing base/head pins in the catalog. The depot and source checkouts must never be mounted into a reviewer environment. Then run:

```bash
python3 docs/research/deep-review-structural-calibration/prepare-capsules.py \
  --repository /path/to/mtg-copilot \
  --repository /path/to/evaluator/corpus.git \
  --output /path/to/evaluator/new-preflight \
  --seed 20261009-pilot
python3 scripts/check.py
git diff --check
```

The output directory must not already exist. Only one opaque `capsules/<alias>` is review input. The sibling `evaluator-receipt.json` contains mappings and pins and must remain hidden. Export treatment files from exact A/B skills commits on the evaluator side, hash them, and mount only the intended contract bundle. The model runner, negative fixture construction, independent label adjudication and scoring remain planned work in ticket 1; the preparation script alone is not a benchmark executor.
