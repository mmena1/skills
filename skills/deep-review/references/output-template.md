# Deep Review Output Template

```markdown
## Deep Review Results

Reviewed: [confirmed target]
Base / reviewed head / current head: [base] / [reviewed SHA] / [current SHA]
Publication: [PR # / local only / stale and blocked]
Scouts: [selected scouts]
Validation: [run / not needed / incomplete]
Context snapshot: [target-bound files/manifests, omitted optional files, warnings, or "empty"]
Runtime: [harness identity/version] | Skill: [reviewed commit/version]

**Pipeline:** Hypotheses [discovered] → [after dedupe]; Validation [findings] Finding, [disproved] Disproved, [unresolved] Unresolved
**Status:** complete | stale | **Review incomplete**: [scout/validator failure and affected hypotheses]

**Headline takeaway:** [most important Finding, "No findings" when complete with zero Findings and zero Unresolved items, "<N> unresolved item(s) need discussion" when complete with no Findings but Unresolved items, or "Review incomplete"]

### Runtime acceptance receipt

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
| PR head change | PASS / FAIL / NOT EXERCISED | [coordinator observation] |
| Cleanup | PASS / FAIL / NOT EXERCISED | [coordinator observation] |

### Action policy

For complete, current runs, classify each Finding deterministically by final severity and fix size:

| Final severity | Fix size | Action |
|---|---|---|
| blocker, high, medium, or low | small and unambiguous (about 20 changed lines or fewer) | fix-now |
| blocker, high, medium, or low | larger than about 20 lines or cross-module | follow-up |

Unresolved items always map to `discuss`. Incomplete or stale runs have no actionable PASS result and cannot publish.

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
   Suggested fix: [concrete remediation]

#### Discuss

1. **Title**: Finding | Action: discuss
   File: path/to/file:line
   Comment scope: point | method/design | compact range
   Source anchor: [location and side]
   Anchor rationale: [semantic rationale]
   Severity: blocker | high | medium | low
   Evidence: [validator evidence]
   Why it matters: [impact]
   Discussion prompt: [question or tradeoff]

#### Follow-up

1. **Title**: Finding | Action: follow-up
   File: path/to/file:line
   Severity: blocker | high | medium | low
   Evidence: [validator evidence]
   Why it matters: [impact]
   Follow-up scope: [next ticket or PR scope]

### Unresolved

Unresolved outcomes are always Action: discuss and are not Findings.

1. **Title**
   File: path/to/file:line
   Evidence: [source evidence]
   Validation attempted: [probe/check and result]
   Remaining question: [what could not be established]
   Decision: post to PR | keep private / investigate | discard

### Recommended Actions

- [ ] Fix fix-now Finding #1
- [ ] Discuss Finding #1 or Unresolved item #1
- [ ] Decide Unresolved item #1
```
