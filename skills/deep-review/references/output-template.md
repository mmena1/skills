# Deep Review Output Template

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
**PR review overlap:** [complete / incomplete and publication blocked / skipped: no uniquely associated PR]; Already reported [item count], Prior resolved discussion [item count], Distinct [item count]; Newly published [actual count / not requested]

**Headline takeaway:** [most important Finding, "No findings" when complete with zero Findings and zero Unresolved items, "<N> unresolved item(s) need discussion" when complete with no Findings but Unresolved items, or "Review incomplete"]

### Runtime acceptance receipt

Describe the enforcement mechanism specified by the active harness in `SKILL.md`, with observed inherited session policy when available. Distinguish instructions from mechanical isolation and phase access from additional permissions.

| Scenario | Status | Observed evidence |
|---|---|---|
| Zero hypotheses | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Surviving hypotheses | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Capacity-bounded static validation | PASS / FAIL / NOT EXERCISED | [hypothesis count, available slots, queue order, and observed completion] |
| Multiple selected scouts | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Insufficient scout capacity | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
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
```
