# Runtime Acceptance Matrix

Static checks cannot prove multi-agent orchestration. Every real review therefore emits a passive receipt in its run state and final report with the harness identity/version, reviewed skill commit, selected roles, and observed result for every row. Use `PASS`, `FAIL`, or `NOT EXERCISED`; unobserved behavior is never a pass.

| Scenario | Devin expected result | Codex expected result |
| --- | --- | --- |
| Zero hypotheses | No validator launches; report says all selected dimensions completed with nothing to validate | Same |
| Surviving hypotheses | Independent static validator launches for every canonical hypothesis | Same |
| Multiple selected scouts | Every selected scout starts in one simultaneous wave | Same |
| Insufficient scout capacity | Review stops before launching any scout and reports required versus available capacity | Same |
| Validator uses probes | Static wave completes first; baseline is verified, then restored before every sequential writable probe | Same |
| One scout fails | Running scouts may finish; run becomes incomplete and cannot publish or claim PASS/`No findings` | Same |
| Validator fails partway | Completed outcomes remain; queued hypotheses continue in canonical order until each is attempted once; run is incomplete and the writable phase is blocked | Same |
| Capacity-bounded static validation | When hypotheses exceed available validator slots, queued hypotheses launch as slots free, every hypothesis is attempted once, and capacity alone does not make the run incomplete | Same |
| PR head changes | Reviewed and current SHAs are reported; result is stale and publication is blocked | Same |
| Cleanup | Only the current run's worktree, context snapshot, and run directory are removed | Same |

Normal reviews exercise only paths they encounter. Keep rare failures and transitions `NOT EXERCISED` until natural execution or a targeted smoke run observes them; never perturb a real review solely to fill the matrix. After changes to `SKILL.md` orchestration, `harnesses/roles.toml`, or reviewer bodies, targeted Devin and Codex smoke runs remain required for important gaps not covered by passive receipts.

Cross-harness acceptance passes only when collected receipts and targeted smoke evidence show both harnesses preserve the protocol's state meanings, failure behavior, publication safeguards, and single-worktree invariant. Different hypotheses or wording across harnesses are expected and do not fail behavioral equivalence.

## Smoke runs

Targeted smoke runs record agent discovery and launch evidence that passive receipts cannot provide.

| Date | Harness | Skill commit | Check | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-26 | Codex CLI 0.156.1, Windows | `2043c9b` | Hyphenated native agent types spawn after `./install.sh --codex` | PASS | One `codex exec` parent thread spawned `deep-review-scout`, `deep-review-structural`, `deep-review-validator-static`, and `deep-review-validator-probe` by exact name. Each child session recorded the hyphenated `agent_role`, ran its pinned `gpt-6-luna` or `gpt-6-sol` model, and replied `READY`. Codex 0.156.1 did not load project-scoped `.codex/agents`, so the agents were installed in the user agent directory. |
