# Deep Review Output Template

Omit the Comment audience note when no confirmed PR is associated.

```markdown
## Deep Review Results

Reviewed: [confirmed target]
Base / reviewed head / current head: [base] / [reviewed SHA] / [current SHA]
Publication: [PR # / local only / stale and blocked]
Scouts: [each selected lens and its native agent, for example `bugs` → `deep-review-scout-bugs`]
Validation: [run / not needed / incomplete]
Context snapshot: [target-bound files/manifests, omitted optional files, warnings, or "empty"]
Runtime: [harness identity/version] | Skill: [reviewed commit/version] | Validator agents: [validator agents that ran, or none]

**Pipeline:** Hypotheses [discovered] → [after dedupe]; Validation [findings] Finding, [disproved] Disproved, [unresolved] Unresolved
**Status:** complete | stale | **Review incomplete**: [scout/validator failure and affected hypotheses]
**PR review overlap:** [complete / incomplete and publication blocked / skipped: no uniquely associated PR]; Already reported [item count], Prior resolved discussion [item count], Distinct [item count]; Newly published [actual count / not requested]; Submission [submitted / rejected / ambiguous / not requested]; Read-back [verified / mismatch / verification incomplete / not requested]

**Headline takeaway:** [most important Finding, "No findings" when complete with zero Findings and zero Unresolved items, "<N> unresolved item(s) need discussion" when complete with no Findings but Unresolved items, or "Review incomplete"]

### Runtime acceptance receipt

Describe the enforcement mechanism specified by the active harness in `SKILL.md`, with observed inherited session policy when available. Distinguish instructions from mechanical isolation and phase access from additional permissions.

| Scenario | Status | Observed evidence |
|---|---|---|
| Zero hypotheses | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Surviving hypotheses | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Capacity-bounded static validation | PASS / FAIL / NOT EXERCISED | [hypothesis count, declared capacity limit if any, queue order, and observed completion] |
| Multiple selected scouts | PASS / FAIL / NOT EXERCISED | [observed selected scout launches and whether dispatch completed before waiting for any scout to complete] |
| Insufficient scout capacity | PASS / FAIL / NOT EXERCISED | [strict-preflight counts or an actual launch refusal; report no available count when capacity is observed only at launch] |
| Validator probes | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Scout failure | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Validator partial failure | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| PR-review-overlap | PASS / FAIL / NOT EXERCISED | [discussion retrieval, independent inputs, dispositions/links, and publication re-check when observed] |
| PR head change | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Cleanup | PASS / FAIL / NOT EXERCISED | [coordinator observation] |

### Action policy

For complete, current runs, classify each Finding deterministically by its remedy and fix size:

| Final severity | Remedy | Fix size | Action |
|---|---|---|---|
| blocker, high, medium, or low | one clearly correct remedy | small and unambiguous (about 20 changed lines or fewer) | fix-now |
| blocker, high, medium, or low | one clearly correct remedy | larger than about 20 lines or cross-module | follow-up |
| blocker, high, medium, or low | needs the author's design or tradeoff judgment, including a structural Finding with several acceptable remedies | any | discuss |

Unresolved items always map to `discuss`. Incomplete or stale runs have no actionable PASS result and cannot publish.

For a structural Finding, Evidence states the demonstrated cost, its causal mechanism, and how the behavior-preserving alternative reduces that cost without an equal or greater burden; Why it matters names the reasoning or maintenance task the cost burdens. Never present a design technique, paradigm, or abstraction count as the reason for a structural Finding or its remediation.

For each affected Finding or Unresolved item below, add an **Overlap** note: `Already reported` or `Prior resolved discussion`, prior link(s), and the semantic match reason. Note independent confirmation when a Finding establishes an earlier speculative concern. Keep the item under its original outcome/action with its evidence and remediation; `Already reported` suppresses a new comment, not the finding or its counts. Counts cover Findings and Unresolved items once each. Incomplete overlap retrieval blocks publication and must not be reported as zero overlaps or a passed comparison.

### Review failure

When the run is incomplete, preserve completed outcomes but list every unattempted hypothesis as **Not validated due to review failure**. Do not render the report as `No findings`, PASS, current, or publishable.


### Findings

#### Fix now

1. **Title**: Finding | Action: fix-now
   File: path/to/file:line
   Comment scope: point | method/design | compact range
   Source anchor: [single line, declaration, or range with diff side]
   Anchor rationale: [why this is the smallest representative location]
   Severity: blocker | high | medium | low
   Evidence: [validator evidence]
   Why it matters: [impact]
   Suggested remediation: [required outcome, relevant constraints, and a concrete implementation shape when confidently established]

#### Discuss

1. **Title**: Finding | Action: discuss
   File: path/to/file:line
   Comment scope: point | method/design | compact range
   Source anchor: [location and side]
   Anchor rationale: [semantic rationale]
   Severity: blocker | high | medium | low
   Evidence: [validator evidence]
   Why it matters: [impact]
   Discussion prompt: [decision-complete question: the concern or tradeoff, specific enough that the author knows which decision to resolve]

#### Follow-up

1. **Title**: Finding | Action: follow-up
   File: path/to/file:line
   Severity: blocker | high | medium | low
   Evidence: [validator evidence]
   Why it matters: [impact]
   Follow-up scope: [required outcome and scope of the next ticket or PR; an implementation shape only when confidently established]

### Unresolved

Unresolved outcomes are always Action: discuss and are not Findings.

1. **Title**
   File: path/to/file:line
   Evidence: [source evidence]
   Validation attempted: [probe/check and result]
   Remaining question: [what could not be established and the decision it leaves for the author]
   Decision: post to PR | keep private / investigate | discard

### Recommended Actions

- [ ] Fix fix-now Finding #1 [use existing discussion link when already reported]
- [ ] Discuss Finding #1 or Unresolved item #1 [use existing discussion link when already reported]
- [ ] Decide Unresolved item #1

**Comment audience:** `human` (default) or `agent`; include `audience: agent` when requesting publication. Omitting audience uses human wording without an extra confirmation step.
```

## Follow-up revalidation variant

Use this variant, never the full template above, for `/deep-review follow-up`. It never shows PASS or a `No findings` headline. Omit the Comment audience note when no confirmed PR is associated.

```markdown
## Deep Review Follow-up

**Follow-up revalidation: not a full PR review.** Only the selected concerns were revalidated; code outside the selected concerns was not reviewed.

Reviewed: [confirmed target]
Source record: [run ID] at [record path]; completeness [complete / incomplete / stale / missing identity confirmed by the user]; older matching full-review records [count]; skipped records [path and reason for each, or none]
Prior follow-ups: [run IDs whose lineage names the source record, or none]
Base / original reviewed head / new reviewed head / current head: [base] / [source record's reviewed SHA] / [reviewed SHA] / [current SHA]
Scouts: none ran (follow-up mode)
Validation: [run / not needed / incomplete]
Context snapshot: [target-bound files/manifests, omitted optional files, warnings, or "empty"]
Runtime: [harness identity/version] | Skill: [reviewed commit/version] | Validator agents: [validator agents that ran, or none]
Records: [preserved record path / not preserved: reason and exact retained paths]

**Coverage:** Selected [canonical IDs]; Excluded [canonical IDs with reasons]; Deferred [canonical IDs with reasons]; Incomplete coverage [requested IDs or comments with reasons]
**Status counts:** Addressed [count], Not addressed [count], Incomplete [count], Deferred [count]
**Status:** current | stale: every status is stale, rerun required | **Revalidation incomplete**: [validator failure and affected concerns]

| Concern | Original concern | Status | Fresh evidence | Prior follow-up context | GitHub thread state |
|---|---|---|---|---|---|
| H[number] | [source run ID] H[number]: [title], original [Finding / Unresolved] at [path:line] | Addressed / Not addressed / Incomplete / Deferred | [Addressed: evidence and responsible change; Not addressed: evidence, current severity, and for a partial fix what changed and what remains; Incomplete: missing evidence or operational limitation; Deferred: the user's reason, or none given] | [latest prior status and any prior deferral, with run IDs, or none] | open / resolved / outdated / not published / unknown |

### Runtime acceptance receipt

Include every row of the full-review receipt first. Mark Zero hypotheses, Surviving hypotheses, Multiple selected scouts, Insufficient scout capacity, and Scout failure `NOT EXERCISED` with the evidence `Not run: full review only`. Then add:

| Scenario | Status | Observed evidence |
|---|---|---|
| Fixed concern | PASS / FAIL / NOT EXERCISED | [concern, fresh evidence, and the cited responsible change] |
| Persisting defect | PASS / FAIL / NOT EXERCISED | [concern, fresh evidence, and current severity] |
| Partial fix | PASS / FAIL / NOT EXERCISED | [what changed and what remains] |
| Missing prior evidence | PASS / FAIL / NOT EXERCISED | [requested ID or comment, the missing evidence, and that nothing was reconstructed] |
| Explicitly deferred concern | PASS / FAIL / NOT EXERCISED | [deferral, its reason, and that no validator ran for it] |
| Resolved thread with a persisting defect | PASS / FAIL / NOT EXERCISED | [resolved thread state beside the Not addressed status] |
| Head change during revalidation | PASS / FAIL / NOT EXERCISED | [reviewed and current SHAs and the stale statuses] |
| Multiple selected concerns | PASS / FAIL / NOT EXERCISED | [one follow-up adjudication per selected concern in canonical ID order] |
| Record discovery in a later session | PASS / FAIL / NOT EXERCISED | [source record found by repository and target key] |
| Discovery when the newest record is a narrower follow-up | PASS / FAIL / NOT EXERCISED | [latest full-review source chosen; follow-up record used only for prior context] |
| Record preservation from a linked worktree | PASS / FAIL / NOT EXERCISED | [caller worktree and the canonical record root reached] |
| Record preservation under a write restriction | PASS / FAIL / NOT EXERCISED | [restriction observed, unchanged outcomes, and exact retained paths] |

GitHub thread state comes only from recorded comment identifiers, retrieved after validation. A retrieval failure leaves it `unknown`, and a resolved thread never makes a concern Addressed.

**Comment audience:** `human` (default) or `agent`; a new comment is only for a Not addressed concern the user selects and goes through the existing overlap and publication gates.
```
