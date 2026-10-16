# Issue #119 probe environment verification

Authority: the complete trusted issue-body Agent Brief in [#119](https://github.com/mmena1/skills/issues/119), verified parentless, open, unassigned and ready with no native blockers before claim. The author was a human account with current admin permission. Implementation baseline: `388a4242e9b65e9ed5d584038ed30ee2b61ef14a`. Verification date: 2026-10-15 (America/Bogota).

## Contract and scenario checks

The [shared environment contract](../../skills/deep-review/references/probe-environment.md) is the authority for coordinator setup/handoff and writable validator behavior. [Focused scenarios](../../skills/deep-review/references/probe-environment-scenarios.md) exercise those issue-approved seams. These scenario assessments apply the instructions to controlled inputs; they are distinct from native execution.

| Scenario assessed | Contract application |
| --- | --- |
| Stale Python environment missing declared httpx/openai | Reject shared reuse and MagicMock import substitution; verify a new owned environment or retain a qualified limitation. This does not reproduce mtg-copilot PR #140. |
| Successful verified setup | Require actual runtime/dependency versions and pinned code origins before executable evidence; preserve commands and results before restoration. |
| Native manager other than uv | Use the pinned Poetry convention, lock and selected test group within owned paths; record a limitation if isolation is impossible. |
| Plain manifest | Use the declared venv/pip convention; record absent lock/groups and actual resolved versions. |
| Unavailable/failed setup | Separate unattempted operational failure with an incomplete run from completed inconclusive validation, including follow-up status qualification. |
| Justified mocking | Name the transport replacement, explain independence of request construction and exclude claims about network delivery. Dependencies/imports still require verification. |
| Claim-invalidating mocking | A fake SDK cannot establish SDK serialization/retry behavior; qualify the outcome unless independent static evidence settles it. |
| Restoration removes the environment | Persist evidence outside probe state and re-establish/re-verify before another probe. |
| Retained environment/cache contamination | Dispose of or invalidate owned artifacts and verify again; inability to eliminate contamination stops validation incomplete. |
| Ambiguous prerequisites or wrong origin/version | Record the specific missing/conflicting declaration or observed mismatch before accepting executable evidence. |

Canonical checks guard the operative clauses, coordinator/validator pointers, receipt guidance, and scenario inventory. Removal mutations verify those guards fail when protected text disappears. The initial checks failed before the environment contract and before the scenario catalog were added, then passed after each slice. These static checks establish contract consistency, not runtime compliance.

## Native targeted smoke

Evidence root: `/tmp/skills-119-smoke-noiyxz56/`. Each smoke uses one committed disposable fixture target with empty context manifests, one declared offline local wheel (`fixturedep==1.0.0`), a simulated caller venv lacking that dependency, and a caller sentinel. Fixture packages are actual installed test distributions, not replacements for missing production imports. No application API, real project environment, scout, static wave, or publication is exercised. Static completion and `Needs probe` are controlled inputs. The generated native validator is used without changing normal installed agents, model pins, or configuration.

Codex CLI 0.160.0: the process-local native-role path points at the canonical generated TOML. The ephemeral parent reported that launching `deep-review-validator-probe` failed with `no rollout found for thread id`. The event stream does not independently expose that launch response, so the error is coordinator-recorded, not an independently established harness diagnosis. No native probe outcome is available and no replacement/retry occurred. The coordinator recorded H1 as not validated due to review failure, marked the run incomplete, left A/B/C unexercised, restored the exact fixture baseline, and verified an unchanged caller. This establishes no probe-runtime acceptance. See `codex/run-state.json`, `codex/events.jsonl`, `codex/stderr.log`, and `codex/final.md`.

Claude Code 2.1.287: a process-local project agent is copied byte for byte from the generated native Markdown. Native calls and child tool results are retained in `claude/events.jsonl` and `claude-verified/events.jsonl`. The normal project/agent configuration is not edited. Setup uses local wheel files and disables package caches/network access.

| Native case | Observed result |
| --- | --- |
| System Python setup A/B | Two sequential native probe calls returned Unresolved: Python 3.14.4 lacked ensurepip/pip, so setup failed. No bounded execution or dependency substitution followed. Results and limitations survived restoration outside probe state. |
| Setup forbidden C | A third native call inspected declarations and returned Unresolved with needed confirmation; no setup/check was invented. |
| Verified runtime A | Existing Python 3.11.16 satisfied the target's declared convention; the native probe created its own venv, installed fixturedep 1.0.0 offline with pip 24.0, ran consistency and code-origin checks, and observed calculate(3) returning 9 instead of 6. Finding used real production imports. |
| Verified runtime B | A new sequential native invocation re-established and verified the environment after A's restoration removed it, then independently returned Finding from the same actual result. |

The first verified probe also inspected/executed the simulated caller interpreter to reject it, under an overly broad coordinator handoff that allowed read-only inspection. It created a bytecode directory inside the disposable target outside its initially named environment/temp paths. These deviations are recorded in the run state; caller fingerprints stayed unchanged and exact restoration removed all artifacts. This is limited setup/verification/outcome evidence, not an aggregate isolation or full-protocol PASS. The final shared contract explicitly rejects caller hints without inspecting/executing them; the focused caller-boundary check uses that tightened contract.

The final check ran the generated role directly with `claude --agent deep-review-validator-probe`, with root acting as coordinator and supplying the environment contract. Its event stream records `claude-sonnet-5-5`, real owned venv/pip setup, verified versions/import origins, and a Finding from calculate(3) returning 9. Inspection of every native tool input found no caller-path access. Root independently repeated the production import/version/result check, verified byte-identical caller fingerprints, saved the result and provenance before restoration, and verified the exact clean baseline with the venv/temp directory removed afterward. No bytecode artifact remained. This tests the final validator handoff boundary directly, not nested launch or a full coordinator run. Evidence: `claude-boundary/events.jsonl` and `claude-boundary/run-state.json`.

Claude session identities: setup-limitation run `41b04c76-2a4f-45e4-8453-33ae14e0bfc2`; verified two-invocation run `5dfc38df-2e43-489c-ac83-096f4ff1e802`; final direct-role boundary run `d78b5a73-0e12-48c1-b2ab-10eb02e49670`. Source hashes, prompts, exact command arrays, manifests, raw event results and final run states remain under the evidence root. `root-verification.json` records root's independent observations and verified baseline identities. After evidence retention, only the exact controlled target/caller fixture directories were removed; `root-cleanup.json` records every path, `controlled-fixtures.tar.gz` retains their original repositories and sentinel state, and `SHA256SUMS` covers the retained artifacts. The prepared Codex verified-runtime fixture was never invoked after the initial launch failure.

Devin is unavailable on this host (`command -v devin` found no executable). Its targeted native cases remain `NOT EXERCISED`. The broader #71 campaign, other-manager execution, real httpx/openai installation, Windows-native behavior and full cross-harness acceptance remain unexercised; neither static checks nor fixture outcomes establish them.

## Repository verification

`python3 scripts/check.py`, canonical `python3 scripts/generate_agents.py`, and `git diff --check` pass. Generated native agent files remain ignored and untracked. No installer or native installation behavior changed, so installer integration changes are outside this issue.
