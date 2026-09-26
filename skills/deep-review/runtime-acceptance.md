# Runtime Acceptance Matrix

Static checks cannot prove multi-agent orchestration. Every real review therefore emits a passive receipt in its run state and final report with the harness identity/version, reviewed skill commit, selected roles, and observed result for every row. Use `PASS`, `FAIL`, or `NOT EXERCISED`; unobserved behavior is never a pass.

| Scenario | Devin expected result | Claude Code expected result | Codex expected result |
| --- | --- | --- | --- |
| Zero hypotheses | No validator launches; report says all selected dimensions completed with nothing to validate | Same | Same |
| Surviving hypotheses | Independent static validator launches for every canonical hypothesis | Same | Same |
| Capacity-bounded static validation | When hypotheses exceed available validator slots, queued hypotheses launch as slots free, every hypothesis is attempted once, and capacity alone does not make the run incomplete | Same, with a fixed pool of 4 slots refilled in canonical hypothesis order | Same |
| Multiple selected scouts | Every selected scout starts in one simultaneous wave | Every selected scout launches as a parallel agent call in one message | Same |
| Insufficient scout capacity | Review stops before launching any scout and reports required versus available capacity | No capacity is checked in advance; a refused or non-starting scout launch stops the review and marks it incomplete, and the receipt records the gate as observed at launch | Same |
| Validator probes | Static wave completes first; baseline is verified, then restored before every sequential writable probe | Same | Same |
| Scout failure | Running scouts may finish; run becomes incomplete and cannot publish or claim PASS/`No findings` | Same | Same |
| Validator partial failure | Completed outcomes remain; queued hypotheses continue in canonical order until each is attempted once; run is incomplete and the writable phase is blocked | Same | Same |
| PR head change | Reviewed and current SHAs are reported; result is stale and publication is blocked | Same | Same |
| Cleanup | Only the current run's worktree, context snapshot, and run directory are removed | Same | Same |

Normal reviews exercise only paths they encounter. Keep rare failures and transitions `NOT EXERCISED` until natural execution or a targeted smoke run observes them; never perturb a real review solely to fill the matrix. After changes to `SKILL.md` orchestration, `harnesses/roles.toml`, or reviewer bodies, targeted Devin, Codex, and Claude Code smoke runs remain required for important gaps not covered by passive receipts.

Cross-harness acceptance passes only when collected receipts and targeted smoke evidence show every harness preserves the protocol's state meanings, failure behavior, publication safeguards, and single-worktree invariant. Different hypotheses or wording across harnesses are expected and do not fail behavioral equivalence.

## Smoke runs

Targeted smoke runs record agent discovery and launch evidence that passive receipts cannot provide.

| Date | Harness | Skill commit | Check | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-26 | Codex CLI 0.156.1, Windows | `2043c9b` | Hyphenated native agent types spawn after `./install.sh --codex` | PASS | One `codex exec` parent thread spawned `deep-review-scout`, `deep-review-structural`, `deep-review-validator-static`, and `deep-review-validator-probe` by exact name. Each child session recorded the hyphenated `agent_role`, ran its pinned `gpt-6-luna` or `gpt-6-sol` model, and replied `READY`. Codex 0.156.1 did not load project-scoped `.codex/agents`, so the agents were installed in the user agent directory. |
| 2026-09-26 | Claude Code 2.1.283, Windows | Not applicable: scratch agents | `Bash(<pattern>)` entries in an agent's `tools` confine its Bash | FAIL | In a scratch project, an agent whose `tools` listed `Read`, `Bash(git status:*)`, and `Bash(git log:*)` ran `echo pwned > marker-pattern.txt` and wrote the file when the session allowed `Bash`. Without that session approval, the same agent ran `git status --short` but its `echo` and `git diff --output=...` calls were refused by the permission system, not by its tool list. The read-only roles therefore get `Read`, `Grep`, `Glob`, and `Bash` with instruction-enforced confinement. |
