# Structural scout rubric history and treatment boundaries

Research date: 2026-10-09. This note uses primary GitHub PR/issue records and immutable repository commits. It does not establish that a recall regression occurred, and contains no new benchmark execution results. Historical scenario results below are reports recorded by the original implementer, not reruns in this investigation.

## Exact treatment revisions

| Revision | Exact commit | Meaning |
| --- | --- | --- |
| A: immediately before PR #58 | `b3a568ec926abc17326213dfb3bd00a48feb256a` | PR #58 base, including PR #55's structural admission/validation work and PR #56's overlap handling |
| Initial neutral implementation | `37b5a6b9d73a5f0fdd67bbd17db848cafeb6210c` | First PR #58 commit; contains a subsequently observed validator substitution failure |
| Validator correction | `c948ae9324b1af6ff6c4413e9491e723434bf280` | Prevents validating a different cost instead of the hypothesis's own cost |
| Accepted PR #58 head | `b091fa137a3b23ebd999790cb33d7a9d7fa1a32b` | Final accepted PR implementation |
| B: merged PR #58 | `5e61f1a0494701f4844c04351235fa77714d9c4e` | Mainline comparison treatment, before later model/orchestration changes |
| Latest deep-review revision audited | `ac3993be968d800ca8a8ff0b1bc59d1b9d431217` | Includes later roles, installation, sandbox documentation, and concurrent-dispatch changes; the local tip `63981d07b0c6c40d23c3000abc36309ceff8f12b` adds the unrelated portfolio skill |

The PR API explicitly reports A as its base, the accepted head above, and B as its merge commit. Prefer A versus B for a reproducible mainline comparison; do not use initial `37b5a6b` as the post-change treatment because it precedes the validator correction. [PR #58](https://github.com/mmena1/skills/pull/58), [merged change](https://github.com/mmena1/skills/commit/5e61f1a0494701f4844c04351235fa77714d9c4e).

Treatment inputs must come from the selected revision rather than today's installed generated agents:

- `skills/deep-review/reviewers/SCOUT.md`
- `skills/deep-review/reviewers/lenses/structural.md`
- `skills/deep-review/reviewers/validator.md`
- `skills/deep-review/protocol.md`
- `skills/deep-review/harnesses/roles.toml`
- For authentic A only: `skills/codebase-design/SKILL.md`, required by the old coordinator and used by the lens/validator.

Record the commit and content hash for each input. `GLOSSARY.md`, output templates, review-comment/overlap guidance, and `runtime-acceptance.md` are part of the wider contract, but the historical acceptance receipt must never be supplied as reviewer context because it contains scenario labels and answers. [A protocol](https://github.com/mmena1/skills/blob/b3a568ec926abc17326213dfb3bd00a48feb256a/skills/deep-review/protocol.md), [B protocol](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/protocol.md).

## What PR #58 changed

| Contract layer | Before | After | Calibration implication |
| --- | --- | --- | --- |
| Structural discovery mission | Ambitious simplification; explicit Code Judo and What to Flag Aggressively sections | Demonstrated task cost; seven investigation signals, each explicitly insufficient by itself; no quota | Search salience and concrete discovery examples changed, independently of validator rigor |
| Concrete search examples | Ad hoc conditions on busy flows, repeated policy, feature leakage, wrong-layer logic, pass-through abstractions, hidden shape assumptions, optional modes, duplicate concepts, responsibility growth, serial/nonatomic orchestration | Poor locality, duplicated knowledge, hidden coupling, unnecessary indirection/states, excessive change surface, responsibility mixing | Categories remain in broad form, but several operational prompts disappear; test coverage rather than infer equivalence from category names |
| Scope | Pre-existing complexity may qualify when the diff worsens it or reveals a clear local simplification | Pre-existing structure qualifies when the diff worsens its cost or makes a changed task bear it | Borderline diff-exposed concerns need an explicit review-task link; a possible additional admission narrowing |
| Responsibility scan | Required on substantial changed flows with control plus parsing/validation, optionality/casts, repeated policy, or growth | Same triggers and separately nameable responsibilities retained | It is incorrect to say #58 removed responsibility scanning |
| Scout admission | Concrete maintainability-cost evidence plus demonstrated behavior-preserving simplification; proof supplied in source evidence | Demonstrated cost on an identifiable task plus behavior-preserving alternative that reduces that cost without equal/greater burden | Both versions already require an alternative at admission. The regression hypothesis cannot simply be that post-change scouts newly need proof |
| Design authority | Deletion, locality, and depth judged by supplied `codebase-design` | No mandatory design skill; techniques and abstraction counts cannot establish or reject a concern | Restoring that authority would reverse the owner-approved neutrality requirement |
| Validator | Establish cost and simplification using supplied design contract | Independently establish task/cost/mechanism and cost reduction; another alternative can establish the same concern, another cost cannot substitute | Validator rejection can change independently of scout discovery; measure each stage |
| Coordinator/deduplication | Same underlying structural problem and mechanism | Same cost on same task and mechanism; technique/alternative is not a merge key | End-to-end recall can change via merging/reporting; direct scout comparison avoids this confound |
| Reporting | Structural problem/reasoning or locality cost | Task, cost, causal mechanism, and reduction; no technique-based justification | Presentation changed, so semantic matching must ignore historical finding wording |
| Runtime roles/models | Existing manifest | Unchanged manifest | There was no model or role change in #58 itself |

Sources: [A scout](https://github.com/mmena1/skills/blob/b3a568ec926abc17326213dfb3bd00a48feb256a/skills/deep-review/reviewers/SCOUT.md), [A lens](https://github.com/mmena1/skills/blob/b3a568ec926abc17326213dfb3bd00a48feb256a/skills/deep-review/reviewers/lenses/structural.md), [B scout](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/reviewers/SCOUT.md), [B lens](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/reviewers/lenses/structural.md), [B validator](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/reviewers/validator.md), [PR #58 diff](https://github.com/mmena1/skills/pull/58/files).

The intended contract was explicitly conservative and architecture neutral, while retaining detectability of all seven structural cost families and the older guardrails. Missing accepted concerns would therefore be a calibration problem, not evidence that neutrality itself should be abandoned. [Issue #57](https://github.com/mmena1/skills/issues/57).

## Model and orchestration confounders after PR #58

| Change | Exact mainline commit | Effect relevant to this investigation |
| --- | --- | --- |
| PR #59 | `31076eec5aaa532264eb829bb66547a83c61b20a` | Devin structural changed `gpt-5-6-sol-medium` to `gpt-6-sol-medium`; static validator `gpt-5-6-sol-high` to `gpt-6-sol-high` |
| PR #68 | `c2d497feb09ab7c911e5b217757de8f6e6f55467` | Devin structural/static became `gpt-6-1-sol-high`; generic Codex scout changed, but specialized Codex structural remained unchanged |
| PR #74 | `52ec4956668cd9efa9195f3ac7113b8c80b434d3` | Generic nonstructural scout split into lens-specific native roles; mandatory exact native dispatch and stronger role preflight; structural remains common scout plus structural lens |
| PR #75 | `3e9ea4d725f61eaa97264f36d7bf625a68fa3ec3` | Native runtime evidence recorded; these installation/launch observations must not be treated as rubric recall measurements |
| PR #81 | `aa1ddfc3d49b69e8939d2b4d47204827735975c3` | Codex agents moved to marked regular-file copies because symlinked native role files fail to load; failed launch is execution failure, not a recall miss |
| PR #83 | `a8b99e955dab80369930e8a8f73466a16e00a798` | Removed ineffective per-role Codex sandbox fields; clarified inherited permissions and static no-artifact contract |
| PR #84 | `ac3993be968d800ca8a8ff0b1bc59d1b9d431217` | All selected scouts must dispatch before waiting; separate parent responses allowed; incomplete zero-hypothesis waves cannot count as success |

Sources: [#59](https://github.com/mmena1/skills/pull/59), [#68](https://github.com/mmena1/skills/pull/68), [#74](https://github.com/mmena1/skills/pull/74), [#75](https://github.com/mmena1/skills/pull/75), [#81](https://github.com/mmena1/skills/pull/81), [#83](https://github.com/mmena1/skills/pull/83), [#84](https://github.com/mmena1/skills/pull/84).

At A, B, and current main, the specialized Codex structural scout and static validator are both `gpt-6.1-sol` with `high` effort; the Claude equivalents are both `claude-opus-5-5` with `high` effort. Their model assignments were not downgraded across #58 or these later revisions. This establishes source configuration, not the actual model/effort used in every historical review. Actual historical invocations require receipts. [A manifest](https://github.com/mmena1/skills/blob/b3a568ec926abc17326213dfb3bd00a48feb256a/skills/deep-review/harnesses/roles.toml), [current manifest](https://github.com/mmena1/skills/blob/ac3993be968d800ca8a8ff0b1bc59d1b9d431217/skills/deep-review/harnesses/roles.toml).

## What the existing controlled evidence establishes

The acceptance document records five throwaway targets: duplicated rule in imperative and declarative forms, style-only rewrite, justified DI/adapter, and a locally required single-adapter convention. The pre-change and post-change scouts produced the same admission outcomes: one hypothesis each on the two duplication cases, none on the other three. Post-change validators confirmed both positives and rejected crafted preference hypotheses. An equal-burden crafted hypothesis initially became a Finding for a different duplicated-rule concern; `c948ae9` corrected that substitution and its rerun was Disproved. One style-only run ended with an API error after output, and a clean rerun agreed. [Immutable acceptance receipt](https://github.com/mmena1/skills/blob/5e61f1a0494701f4844c04351235fa77714d9c4e/skills/deep-review/runtime-acceptance.md).

The reference scout run is labeled FAIL because it reasoned from the opinionated design contract, not because it missed the positive cases. The document explicitly reports no full coordinator run, no discovered native-agent invocation, and no Codex/Devin run. These five cases support narrow duplication recall and preference rejection, not broad historical responsibility-mixing, hidden-state, boundary, or orchestration recall. They are historical observations, not measured performance on the mtg-copilot corpus.

## Controlled comparison recommendation

1. Primary discovery contrast: run A and B scout bodies with the same case snapshot, exact base/head diff, empty or identical approved context manifest, same model/effort, tool access, output budget, timeout, and fresh independent session. Authentic A requires the pinned `codebase-design` contract; B forbids it as supplied authority. That dependency difference is part of #58, not an uncontrolled later-model difference.
2. Replay all emitted hypotheses through one common neutral validator at B, with identical conditions and exactly one hypothesis per invocation. This measures whether each scout discovers concerns that survive the desired architecture-neutral standard. Preserve raw scout output so a lost finding can be localized to admission versus validation.
3. Secondary contract contrast: cross each scout's output with A and B validators, recording the A validator's required design contract. This separates validator rejection from discovery. It also reveals architecture-preference admissions that the neutral validator properly rejects. Old validators cannot establish the neutrality of a benchmark label.
4. Do not present a lens-only swap under conflicting common admission/validator text as an authentic historical treatment. If needed after the primary comparison, label a discovery-cue ablation explicitly: keep B admission and B validator, add selected neutral investigation questions derived from A, retain B's cost/task/alternative threshold. This tests cue loss without silently reinstating old design authority.
5. Keep coordinator/native-agent acceptance separate. Use a frozen direct-role harness for semantic calibration and separately check installation, actual model/effort, complete outputs, and dispatch. Do not score an agent-loading or API error as No hypotheses. The target's Git object database, filesystem, and network access must exclude future fixes; prompt confinement alone is insufficient leakage prevention.

None of these comparisons has been executed in this note. The artifact is a design for the parent benchmark, not a prediction presented as an observed result.

## Preliminary causal assessment and minimum candidate intervention

A plausible mechanism is reduced discovery coverage: concrete search examples and ambitious search language disappeared while strict admission text became more prominent. A separate plausible mechanism is narrower interpretation of diff-exposed pre-existing costs. A third is validator rejection of alternatives that relocate costs or of hypotheses that rely on design preference. The third may be correct behavior rather than regression. Existing five-target evidence cannot choose among these mechanisms, and configured Codex/Claude structural models do not support a model-downgrade explanation.

If the neutral common validator independently confirms missed historical costs and cue ablation improves paired discovery without increasing control false positives, the smallest justified change is a short, architecture-neutral investigation checklist in the structural lens: trace one changed rule across copies/callers, separate nameable responsibilities and reasons to change, inventory states/optionality, and ask which coherent maintenance task now needs scattered knowledge. Keep the task/cost/mechanism/alternative admission threshold, independent validation, local-contract respect, no quota, and same-concern validation rule. Do not restore `codebase-design`, aggressive finding language, abstraction-count evidence, or a preferred remedy. This is conditional scope for a later ticket, not a proposed production edit or an established fix.
