## Summary

```text
restore baseline -> process execution gate -> owned setup
                 -> verify runtime/dependencies/code origins
                 -> bounded check -> preserve provenance -> restore
```

Require a verified, run-owned dependency environment before accepting executable writable-probe evidence. Separate path ownership from process isolation: executable setup/imports/checks require a verified effective sandbox covering child processes, or exact user authorization with residual access disclosed. Missing both stops execution with a qualified outcome.

Align coordinator/validator handoffs, provenance and receipt guidance; add focused scenarios, canonical guards and two reviewable evidence bundles: the [implementation and process-gate bundle](https://github.com/mmena1/skills/blob/a0159003ac7b243fc6e5fbce66f2259dae7e144e/docs/verification/issue-119-evidence/README.md) with [hashes](https://github.com/mmena1/skills/blob/a0159003ac7b243fc6e5fbce66f2259dae7e144e/docs/verification/issue-119-evidence/SHA256SUMS), and the [targeted native acceptance bundle](https://github.com/mmena1/skills/blob/d5ae39a7083d0e84285392ef4b3539f76acd843d/docs/verification/issue-119-native-acceptance/README.md) with [hashes](https://github.com/mmena1/skills/blob/d5ae39a7083d0e84285392ef4b3539f76acd843d/docs/verification/issue-119-native-acceptance/SHA256SUMS).

Closes #119

Auto-closure is unverified. After merge, verify #119 is closed, close it explicitly if needed, then run `/reconcile 119`.

## Evidence

**Merge gate: native acceptance is incomplete. This PR remains draft.** One narrower acceptance decision is approved, for Devin only ([decision](https://github.com/mmena1/skills/pull/130#issuecomment-6224937076)); Codex coverage and coordinator integration are not waived and still need an explicit assessment.

- **Before:** Dependency verification was not mandatory, and an owned venv/cache path did not constrain executable install hooks.
- **After:** `python3 scripts/check.py` passes for 31 skills, including clause-removal and published-evidence integrity regressions; whitespace checks pass. Generated native agents were refreshed and remain ignored/untracked.
- **Claude Code 2.1.301 targeted native acceptance (2026-10-16):** the PR-head generated `deep-review-validator-probe` succeeded on all three probes, with the session acting as coordinator and a verified namespace sandbox as the process gate. P1 ran venv creation, the hash-locked install (including its PEP 517 backend), dependency/origin verification and the bounded check inside the sandbox and returned Finding. P2 re-established its own environment after exact-baseline restoration, ignored the stale caller and prior-probe environments, and returned Disproved. P3, with no gate satisfied, ran no target-controlled setup, import or probe and returned Unresolved. The gate canary, hook logs, restoration logs and caller/home/shared fingerprints support the bounded fixture isolation claims only. This does not prove Devin's or Codex's positive path. See the [report](https://github.com/mmena1/skills/blob/d5ae39a7083d0e84285392ef4b3539f76acd843d/docs/verification/issue-119-native-acceptance/README.md).
- **Devin CLI 3000.11.3 targeted native acceptance (2026-10-16, macOS, [evidence](https://github.com/mmena1/skills/pull/130#issuecomment-6224760038)):**
  - Observed: the denied path **PASSED**. The PR-head generated `deep-review-validator-probe` (`gpt-6-luna-high`, child `2309cdc3`) received an unsatisfied gate, made one read-only call, ran no target-controlled setup/import/check and returned Unresolved. The sandbox canary held the scoped filesystem restrictions for parent and child. Raw TCP to `140.82.112.3:443` was **reachable** despite an allowlist naming only `acceptance.invalid`, so the domain allowlist does not block IP egress; per the [maintainer's policy clarification](https://github.com/mmena1/skills/pull/130#issuecomment-6224883962), disclosed outbound TCP is acceptable for this workflow.
  - Not exercised: successful isolated dependency setup, import and bounded probe; sequential restoration between executable probes; and the native `/deep-review` coordinator handoff. These remain `NOT EXERCISED`, not PASS.
  - Approved narrower scope: the maintainer [waived those Devin-specific test requirements for this PR](https://github.com/mmena1/skills/pull/130#issuecomment-6224937076) given the execution cost. No further Devin run is requested before the merge decision. The waiver does not change the runtime safety contract and grants no permission for setup hooks, imports or external API calls outside a verified or authorized boundary.
- The earlier direct Claude native-role regression returned Unresolved with only Read/Glob calls when neither a process boundary nor scoped executable-hook/import authorization was supplied. No target setup/import/probe ran.
- A controlled PEP 517 backend and child wrote simulated caller/home markers with ordinary process access; under the recorded Bubblewrap policy those writes failed with EROFS while owned writes succeeded. This is a process-boundary experiment, not native coordinator acceptance.
- Published older Claude setup/import/restoration observations predate the process gate. They are historical measurements, not compliance evidence for the revised contract. The [2026-10-15 verification note](https://github.com/mmena1/skills/blob/e31ead5ff2f45b67cbe29cea95f8bf202f4a6621/docs/verification/issue-119-probe-environments.md) is labelled as a dated historical report.
- **Remaining gaps (not waived):** current Codex targeted smoke; native coordinator enforcement of the handoff (the Claude and Devin runs exercised the validator directly); and the explicit-authorization branch of the gate. These are `NOT EXERCISED`. Poetry execution, real httpx/openai installation and Windows-native behavior also remain unexercised. Each needs evidence or an explicit, documented, maintainer-approved decision before marking ready.

## Merge Danger

**Door:** two-way

**Blast Radius:** limited

Changes deep-review probe instructions and their checks; reverting restores the prior protocol.
