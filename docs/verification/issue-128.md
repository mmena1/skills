# Issue #128 verification: modular repository validation

Issue #128 split `scripts/check.py` into the `scripts/repo_checks/` package. `python scripts/check.py` is still the canonical command, and its `main` still calls the same 19 validation groups in the same order. [`scripts/repo_checks/README.md`](../../scripts/repo_checks/README.md) says which module owns each responsibility. This record holds the evidence that every check, scenario, and observable behavior was preserved.

## Implementation baseline

The planning snapshot `388a4242e9b65e9ed5d584038ed30ee2b61ef14a` is not the implementation baseline. Between that commit and the baseline, the suite gained the deep-review probe environment checks (#130) and grew from 3,538 to 3,632 lines with the same 19 groups. The baseline was pinned at the commit this change starts from, before any restructuring:

| Item | Value |
| --- | --- |
| Baseline commit | `216a446ccc2308cd737e113d2d0bb4e71872f1a9` |
| Python | 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0] |
| Platform | Linux-6.18.44-fc-v139-x86_64-with-glibc2.39 |
| Tools | git 2.43.0, GNU bash 5.2.21 |
| Worktree | clean (`git status --porcelain` empty); only the ignored `scripts/__pycache__/` appeared after runs |

Fixture state at the baseline, as Git blob IDs:

| Path | Blob |
| --- | --- |
| `tests/fixtures/agent-skill/SKILL.md` | `69f8268ccc0f6d5b0d15e15a3934f4656e17653d` |
| `tests/fixtures/agent-skill/harnesses/roles.toml` | `fb3400d505fd5ff401dd336ce6c25947967955ff` |
| `tests/fixtures/agent-skill/reviewers/probe.md` | `aaa372afb1ddb062a59745f1bdee64a163db0782` |
| `tests/fixtures/agent-skill/reviewers/reviewer.md` | `9b2dcb5f24dbb4fe24a6beff6015c6f3b4c6a47a` |
| `tests/fixtures/tracker-contract/local-partial.md` | `cd543b91f8902635d2155c4c5c03b882be7d1b14` |
| `tests/fixtures/tracker-contract/standalone-incomplete.md` | `9acaa9150dabdc2950e9bd47d430d19cc32b61c5` |
| `scripts/test_wizard.py` | `2861dfb9f60f74874d090836a22feb18ca900928` |
| `scripts/generate_agents.py` | `ebd71c73008ec34e23d381a40a0d7dd7955c9638` |

These files are unchanged by this work.

| Command (from the repository root unless noted) | Exit | stdout | stderr |
| --- | --- | --- | --- |
| `python3.12 scripts/check.py` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.12 /home/user/skills/scripts/check.py`, run from `/tmp` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.13 scripts/check.py` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.12 scripts/test_installers.py` | 0 | `Installer integration tests passed.` | empty |

## After the refactor

Run on the same machine against the refactored tree:

| Command | Exit | stdout | stderr |
| --- | --- | --- | --- |
| `python3.12 scripts/check.py` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.12 /home/user/skills/scripts/check.py`, run from `/tmp` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.13 scripts/check.py` and `python3.11 scripts/check.py` | 0 | `Repository checks passed for 31 skills.` | empty |
| `python3.12 scripts/test_installers.py` | 0 | `Installer integration tests passed.` | empty |
| `git diff --check` | 0 | empty | empty |

Neither the workflow in `.github/workflows/check.yml` nor its platform gating changed. Its separate `repository` and `installers` jobs run both entry points with Python 3.12 on Ubuntu and macOS. This machine is Linux only, so macOS evidence comes from those CI jobs on the pushed branch.

## Inventory

### How preservation was checked

- **Verbatim moves.** A slicer moved each top-level statement of the baseline `check.py` into its owning module by source line, together with the comment block directly above it. A second script parsed the baseline and every new module. It confirmed that each of the 126 baseline statements exists exactly once, that 123 are byte-for-byte identical to the baseline source, and that no module defines anything new. The other 3 differ only by the adaptations listed below. All `#` comment lines in the baseline appear unchanged in the new files. The scenario tables, parameterized cases, mutation self-tests, failure messages, and fixture reads below sit inside those identical function bodies, so they are preserved by construction.
- **Imports.** `pyflakes` reports no undefined or unused names in `check.py`, `test_installers.py`, or the package. The added code is limited to module docstrings, import lines, the two `__init__.py` files, and the import list in `check.py`.
- **Mechanical adaptations**, the only changed lines inside moved statements:
  - `ROOT` in `common.py` uses `parents[2]` instead of `parents[1]`, because the module sits one directory deeper than `scripts/check.py`. It resolves to the same repository root from any working directory.
  - `INTENTIONAL_STALE_REFERENCE_FILES` and the upstream-identity exemption in `validate_repository_references` name `scripts/repo_checks/references.py` instead of `scripts/check.py`. The stale-name and upstream-identity literals the scanner matches moved there, and no other script holds them. The scan scope (`iter_repository_text`) and every rejection rule are unchanged. `scripts/check.py` is no longer exempt, because it no longer carries those literals.
  - `scripts/test_installers.py` imports `ROOT`, `SKILLS`, `CheckFailure`, and `fail` from `repo_checks.common`, `DEEP_REVIEW_ROLES` from `repo_checks.deep_review`, and `RENAMED_SKILLS` from `repo_checks.references`, instead of from `check`. The values are the same objects, defined once, so no contract is duplicated. The installer suite still imports nothing from `check.py` and still runs separately.

### Group runners

`main` in `scripts/check.py` calls these runners in the baseline order. That order decides which failure is reported first.

| Position | Runner | New owner | Scenarios, cases, and mutation self-tests it runs | Fixtures and inputs |
| --- | --- | --- | --- | --- |
| 1 | `validate_layout_and_skills` | `layout` | none; returns the skill names the success line counts | `skills/` tree, every `SKILL.md` and `agents/openai.yaml` |
| 2 | `validate_repository_references` | `references` | none | every repository text file, `README.md` |
| 3 | `validate_implementation_authority_contract` | `scenarios/tracker` | 28 required contract texts; Agent Brief examples; `incomplete_briefs` (3 plus one per required field); `accepted` (6); `rejected` (10); `precedence` (5); standalone frontier, held-state, and `/to-tickets` publication scenarios | tracker contract and seed, `skills/triage/AGENT-BRIEF.md`, the `implement`, `reconcile`, `triage`, `to-tickets`, and `setup-skills` skills |
| 4 | `validate_implementation_review_routing_contract` | `scenarios/implementation` | required routing and report phrases; native-composition ordering | the `implementation-review`, `implement`, and `deep-review` skills and deep-review Codex metadata |
| 5 | `validate_implementation_working_copy_contract` | `scenarios/implementation` | required phrases; branch gate `cases` (7) | `skills/implement/SKILL.md` |
| 6 | `validate_standalone_authority_modes` | `scenarios/tracker` | required phrases; `expected_modes` (9); current and stale verdicts; start-gate `cases` (21) | both tracker seeds, the repository tracker, both `tests/fixtures/tracker-contract/` files, the workflow skills |
| 7 | `validate_tracker_capability_contract` | `scenarios/tracker` | canonical capability list; downstream gates; `unlisted_gates` self-tests (3); `expected_gaps` (6) and first-gap migration | both tracker seeds, the repository tracker, `tests/fixtures/tracker-contract/local-partial.md` |
| 8 | `validate_reconciliation` | `scenarios/reconciliation` | reconciliation plan scenarios: dependent scopes, held labels, native and fallback discovery, idempotent rerun, invalid dependents, trusted comments, five standalone `modes`, and stopped triggers | both tracker seeds, `tests/fixtures/tracker-contract/standalone-incomplete.md` |
| 9 | `validate_reconciliation_contract` | `scenarios/reconciliation` | required phrases; frontier promotion lines; older trigger-only migration per seed | `reconcile` and `setup-skills` skills, both tracker seeds, the repository tracker |
| 10 | `validate_pr_ticket_plan` | `scenarios/pr_handoff` | ticket plan scenarios: GitHub and local trackers, rejected records (4), manual evidence (3), exclusions, shared commits, non-default base and auto-close (2), single ticket, blockers, and a three-ticket chain | none beyond the model |
| 11 | `validate_multi_ticket_pr_contract` | `scenarios/pr_handoff` | required and retired `/write-pr` phrases; handoff sentence per tracker; older single-ticket tracker stays current | `write-pr`, `implement`, and `setup-skills` skills, GitHub seed, repository tracker |
| 12 | `validate_branch_satisfied_blockers` | `scenarios/implementation` | operation pinning; partial operations (2); validation `verdicts` (25); `starts` (4); `unchanged` (10 plus 8 failure verdicts); mapped held labels; override; reconciliation isolation; chain and `/write-pr` revalidation | GitHub seed, repository tracker, local seed, the `implement`, `write-pr`, and `setup-skills` skills |
| 13 | `validate_native_agents` | `native_agents` | none | every role manifest, including `tests/fixtures/agent-skill` |
| 14 | `validate_generated_agents_untracked` | `native_agents` | none | Git index and `.gitignore` for each manifest's harnesses |
| 15 | `validate_deep_review` | `scenarios/deep_review` | probe environment, access, and audience checks with clause-removal and weakening mutations; role `cases` (8); runtime `scenario_mutations` (3); follow-up clause removals and `mutations` (11); duplicate-copy scan | `skills/deep-review/` and every repository text file |
| 16 | `validate_deep_review_generation` | `scenarios/agent_generation` | obsolete generic scout outputs (3); pinned fields per role and harness; idempotent regeneration | temporary copy of `skills/deep-review` |
| 17 | `validate_agent_generation_contract` | `scenarios/agent_generation` | determinism; freshness `cases` (4); `malformed` manifests (2); generated and manifest `sandbox_mode`; one removal per required harness field | temporary copies of `tests/fixtures/agent-skill` |
| 18 | `validate_portfolio_sync` | `scenarios/portfolio_sync` | write-surface checks; dry run, stale plans (2), apply, repeat runs (2); failure cases (9); read-only and closed Projects (2); partial apply; closure during apply; inaccessible members | `skills/experimental/portfolio-sync/scripts/portfolio_sync.py`, `skills/experimental/portfolio/SKILL.md`, `FakePortfolio` |
| 19 | `validate_wizard` | `scenarios/wizard` | the 16 unittest cases in `scripts/test_wizard.py`, run as a subprocess | `skills/wizard/template.sh` |

Runners 3, 6, and 7 belong to one module but stay interleaved with runners 4 and 5, as in the baseline, so the first failure reported does not change.

### Execution reachability

A profiling hook (`sys.setprofile`) recorded every function executed while `check.main()` ran on the healthy tree, and the result was compared with every function and method defined in `check.py` and the package. All 77 executed, including all 24 `validate_*` functions: the 19 groups plus the 5 deep-review sub-validators that `validate_deep_review` calls. Execution comes from the explicit calls in `main`, not from imports or file names.

### Isolation

- Each of the 18 modules imports alone in a fresh interpreter (`PYTHONPATH=scripts python3.12 -c "import repo_checks.<module>"`), with no output, no side effects, and no other runners imported. For example, importing `repo_checks.reconciliation` loads only `common`, `agent_brief`, and `tracker_contract`.
- `PYTHONPATH=scripts python3.12 -c "from repo_checks.scenarios.reconciliation import validate_reconciliation; validate_reconciliation()"` runs one group on its own. It passed from both the repository root and `/tmp`.
- The import graph has no cycles. No model module imports a `scenarios/` module or `check.py`. Mutable state stays where it was: the module-level `STALE_PATTERNS` extension in `references` and the helper registration in `sys.modules` inside `validate_portfolio_sync`.
- `import test_installers` resolves its shared names from the package on its own.

## Differential comparison

The baseline and refactored canonical commands ran with `python3.12` against the same healthy tree and the same controlled invalid inputs. Each variant is a fixture repository built from `git archive 216a446`. The refactored variant then overlays `scripts/check.py`, `scripts/test_installers.py`, and `scripts/repo_checks/`. All files are committed, so the Git-based ownership check sees the baseline's tracked state. Both variants are built at the same path, one after the other, so absolute paths inside diagnostics match.

For every input, the harness hashed the whole fixture (file contents plus the Git index) before and after mutating it, and required the hash to change. After the run it hard-reset and cleaned the fixture, then required the original hash again. Every mutation changed its input and every restore matched. Exit status, stdout, and stderr were compared exactly, with one normalization: unittest's `Ran N tests in X.XXXs` line has its elapsed time replaced, because wall-clock time is the only nondeterministic output. It appears only when the wizard group fails.

Of the 43 inputs, 42 give identical exit status, stdout, and stderr. Every failure goes to stderr with an empty stdout, and every success goes to stdout with an empty stderr. Of the 42 identical rows, 3 combine failures from several groups and get the same first failure. The one difference is the intended exemption relocation. A stale literal appended to `scripts/check.py` was exempt in the baseline, where that file held the scanner's literals, and is rejected now. The same literal appended to the file that holds the scanner's literals (`scripts/check.py` in the baseline, `scripts/repo_checks/references.py` now) is accepted by both.

Output lines that name the retired assistant are shown as `<retired-name>` here, because this record is itself subject to the stale-reference scan.

| Controlled input | Exit (baseline / refactored) | Stream | First output line (refactored) | Outputs |
| --- | --- | --- | --- | --- |
| healthy tree | 0 / 0 | stdout | Repository checks passed for 31 skills. | identical |
| healthy tree, invoked from outside the repository | 0 / 0 | stdout | Repository checks passed for 31 skills. | identical |
| layout: a skill without agents/openai.yaml | 1 / 1 | stderr | FAIL: skills/tdd: missing agents/openai.yaml | identical |
| invocation: a user-invoked skill without disable-model-invocation | 1 / 1 | stderr | FAIL: skills/implement/SKILL.md: Claude model invocation disagrees with user classification | identical |
| layout: an invalid frontmatter key | 1 / 1 | stderr | FAIL: skills/grilling/SKILL.md:3: invalid frontmatter key 'Description' | identical |
| references: an em dash in a document | 1 / 1 | stderr | FAIL: docs/agents/domain.md: em dash violates repository style | identical |
| references: a stale reference in a document | 1 / 1 | stderr | FAIL: docs/agents/domain.md:55: stale <retired-name> reference | identical |
| references: a broken relative link | 1 / 1 | stderr | FAIL: README.md:134: broken relative link './missing.md' | identical |
| references: a README without a canonical skill link | 1 / 1 | stderr | FAIL: README.md does not link canonical SKILL.md for tdd | identical |
| references: a retired file | 1 / 1 | stderr | FAIL: retired file remains: CHANGELOG.md | identical |
| references: a stale literal in an unexempted script | 1 / 1 | stderr | FAIL: scripts/generate_agents.py:275: stale <retired-name> reference | identical |
| references: a stale literal in scripts/check.py | 0 / 1 | stdout / stderr | FAIL: scripts/check.py:63: stale <retired-name> reference | differ: intended exemption relocation |
| references: a stale literal in the file holding the scanner's literals | 0 / 0 | stdout | Repository checks passed for 31 skills. | identical |
| tracker: a contract without frontier promotion | 1 / 1 | stderr | FAIL: /setup-skills would report this repository's tracker as outdated | identical |
| tracker: an altered partial-tracker fixture | 1 / 1 | stderr | FAIL: a migration that added only the first gap was not reported incomplete with its remaining gaps | identical |
| tracker: an incomplete-standalone fixture claiming the full brief rule | 1 / 1 | stderr | FAIL: standalone authority mode of a tracker stating no mode: expected 'undeclared', found 'incomplete' | identical |
| authority: /implement without the comment precedence rule | 1 / 1 | stderr | FAIL: implementation authority contract is missing 'newest complete trusted brief comment' | identical |
| review routing: implementation-review without explicit-only deep review | 1 / 1 | stderr | FAIL: implementation-review description is missing routing purpose 'Deep-review remains explicit-only' | identical |
| working copy: /implement stopping on a detached HEAD | 1 / 1 | stderr | FAIL: /implement working-copy contract is missing 'If HEAD is detached' | identical |
| standalone modes: /setup-skills without the parent-only mode | 1 / 1 | stderr | FAIL: standalone authority mode contract is missing '**Parent-only (current)**' | identical |
| reconciliation: /reconcile without per-dependent authority | 1 / 1 | stderr | FAIL: expanded reconciliation workflow is missing "Resolve each dependent's own authority" | identical |
| pr handoff: /write-pr assuming closure | 1 / 1 | stderr | FAIL: /write-pr multi-ticket contract is missing 'Closure is never assumed.' | identical |
| pr handoff: a tracker without the multi-ticket sentence | 1 / 1 | stderr | FAIL: docs/agents/issue-tracker.md: PR/merge handoff is missing the multi-ticket closing and verification sentence | identical |
| branch-satisfied: a tracker letting /reconcile read branches | 1 / 1 | stderr | FAIL: /setup-skills would report this repository's tracker as outdated | identical |
| native agents: an unsupported harness directory | 1 / 1 | stderr | FAIL: skills/deep-review/harnesses: unsupported harness directories emacs | identical |
| native agents: a malformed fixture manifest | 1 / 1 | stderr | FAIL: malformed role manifest: agent-skill/harnesses/roles.toml: roles.scout must declare at least one harness | identical |
| generated agents: a tracked generated agent | 1 / 1 | stderr | FAIL: generated agent files are tracked by Git: skills/deep-review/harnesses/claude/deep-review-structural.md; run git rm --cached on them | identical |
| deep review: a removed probe environment rule | 1 / 1 | stderr | FAIL: skills/deep-review/references/probe-environment.md: missing probe environment rule 'Authorization is not mechanical isolation' | identical |
| deep review: harness-specific text in shared content | 1 / 1 | stderr | FAIL: skills/deep-review/protocol.md: harness-specific text 'Codex' in shared deep-review content | identical |
| deep review: a drifted role model | 1 / 1 | stderr | FAIL: deep-review role 'scout-conventions' drifted from its pinned harness models and limits | identical |
| deep review: a duplicate copy of a shared source | 1 / 1 | stderr | FAIL: docs/duplicate.md: duplicate copy of skills/deep-review/GLOSSARY.md | identical |
| deep review: a removed follow-up rule | 1 / 1 | stderr | FAIL: deep-review/protocol.md: missing follow-up contract 'Follow-up never replies to, edits, resolves, or reopens an existing thread.' | identical |
| deep review: a removed audience rule | 1 / 1 | stderr | FAIL: deep-review/references/pr-review-comments.md: missing publication contract "Never infer the audience from the PR author's identity" | identical |
| deep review: divergent runtime scenario names | 1 / 1 | stderr | FAIL: skills/deep-review/runtime-acceptance.md: runtime acceptance scenarios differ from references/output-template.md | identical |
| deep-review generation: obsolete outputs kept | 1 / 1 | stderr | FAIL: regenerating deep-review agents kept the obsolete generic scout output: harnesses/claude/deep-review-scout.md, harnesses/codex/deep-review-scout.toml, harnesses/devin/deep-review-scout/AGENT.md | identical |
| agent generation: hand-edited output accepted | 1 / 1 | stderr | FAIL: agent freshness check accepted a stale generated agent file | identical |
| portfolio sync: a second named mutation | 1 / 1 | stderr | FAIL: portfolio-sync: the helper must send exactly one named mutation, AddProjectItem | identical |
| portfolio sync: a changed in-sync report | 1 / 1 | stderr | FAIL: portfolio-sync: a repeated run dry run must be a no-op | identical |
| portfolio: the read-only skill without its sync recommendation | 1 / 1 | stderr | FAIL: portfolio: must recommend `/portfolio-sync` for open work absent from the Project | identical |
| wizard: a broken helper | 1 / 1 | stderr | FAIL: wizard helper regression checks failed: | identical after timing normalization |
| first failure: layout, references, and portfolio failures together | 1 / 1 | stderr | FAIL: skills/tdd: missing agents/openai.yaml | identical |
| first failure: deep review and PR handoff failures together | 1 / 1 | stderr | FAIL: /write-pr multi-ticket contract is missing 'Closure is never assumed.' | identical |
| first failure: wizard and agent generation failures together | 1 / 1 | stderr | FAIL: agent freshness check accepted a stale generated agent file | identical |

## Statement map

Each of the 126 top-level statements of the baseline `scripts/check.py`, with its baseline line range, its new owner, and how it moved.

| Baseline statement | Baseline lines | New owner | Move |
| --- | --- | --- | --- |
| `ROOT` | 23-23 | `scripts/repo_checks/common.py` | adapted: the module sits one directory deeper than scripts/check.py |
| `SKILLS` | 24-24 | `scripts/repo_checks/common.py` | verbatim |
| `TEXT_SUFFIXES` | 25-25 | `scripts/repo_checks/references.py` | verbatim |
| `RETIRED_BUCKETS` | 26-26 | `scripts/repo_checks/layout.py` | verbatim |
| `RETIRED_FILES` | 27-35 | `scripts/repo_checks/references.py` | verbatim |
| `STALE_PATTERNS` | 36-45 | `scripts/repo_checks/references.py` | verbatim |
| `RENAMED_SKILLS` | 48-48 | `scripts/repo_checks/references.py` | verbatim |
| `for _former` | 49-50 | `scripts/repo_checks/references.py` | verbatim |
| `INTENTIONAL_STALE_REFERENCE_FILES` | 51-51 | `scripts/repo_checks/references.py` | adapted: the stale-reference literals moved to references.py |
| `AGENT_BRIEF_HEADING` | 52-52 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `AGENT_BRIEF_REQUIRED_FIELDS` | 53-55 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `AGENT_BRIEF_OPTIONAL_FIELDS` | 56-56 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `AGENT_BRIEF_COMPLETENESS_RULE` | 59-63 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `AGENT_BRIEF_TRACKER_CONTRACT` | 66-76 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `RETIRED_STANDALONE_RECORD` | 77-77 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `STANDALONE_UNSUPPORTED` | 80-80 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `STANDALONE_CLAIMED` | 81-81 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `EVERY_TICKET_HAS_PARENT` | 82-84 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `CURRENT_STANDALONE_MODES` | 85-85 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `AUTHORITY_GRANTED` | 86-86 | `scripts/repo_checks/implementation.py` | verbatim |
| `TRACKER_CAPABILITY_HEADING` | 89-89 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `TRACKER_CAPABILITIES` | 90-117 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `TRACKER_GATE_PHRASES` | 121-139 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `TRACKER_GATE` | 140-143 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `BRANCH_SATISFIED_OPERATION` | 148-148 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `BRANCH_SATISFIED_CONTRACT` | 149-175 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `BRANCH_SATISFIED_ELEMENTS` | 179-196 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `STANDALONE_BRANCH_EXCEPTION` | 199-202 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `FAIL_CLOSED_BRANCH_EXCEPTION` | 203-207 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `TRIAGE_COMMENT_DISCLAIMER` | 208-208 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `TRUSTED_APPROVAL_PERMISSIONS` | 209-209 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `HELD_TRIAGE_STATES` | 211-211 | `scripts/repo_checks/reconciliation.py` | verbatim |
| `USER_INVOKED_SKILLS` | 212-218 | `scripts/repo_checks/layout.py` | verbatim |
| `MODEL_INVOKED_SKILLS` | 219-223 | `scripts/repo_checks/layout.py` | verbatim |
| `DEEP_REVIEW_READ_ONLY_TOOLS` | 227-227 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_CLAUDE_READ_ONLY_TOOLS` | 228-228 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_ROLES` | 229-265 | `scripts/repo_checks/deep_review.py` | verbatim |
| `HARNESS_SPECIFIC_TEXT` | 266-269 | `scripts/repo_checks/deep_review.py` | verbatim |
| `CheckFailure` | 272-273 | `scripts/repo_checks/common.py` | verbatim |
| `fail` | 276-277 | `scripts/repo_checks/common.py` | verbatim |
| `parse_frontmatter` | 280-313 | `scripts/repo_checks/layout.py` | verbatim |
| `skill_directories` | 316-320 | `scripts/repo_checks/layout.py` | verbatim |
| `codex_implicit_policy_values` | 323-338 | `scripts/repo_checks/layout.py` | verbatim |
| `validate_layout_and_skills` | 341-404 | `scripts/repo_checks/layout.py` | verbatim |
| `iter_repository_text` | 407-414 | `scripts/repo_checks/references.py` | verbatim |
| `validate_repository_references` | 417-461 | `scripts/repo_checks/references.py` | adapted: the upstream-identity literal moved to references.py |
| `agent_brief_fields` | 464-486 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `is_complete_agent_brief` | 489-498 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `is_trusted_author` | 501-503 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `resolve_agent_brief` | 506-517 | `scripts/repo_checks/agent_brief.py` | verbatim |
| `reconcile_ready` | 520-525 | `scripts/repo_checks/reconciliation.py` | verbatim |
| `standalone_frontier_numbers` | 528-540 | `scripts/repo_checks/reconciliation.py` | verbatim |
| `tracker_defines_retired_record` | 543-545 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `tracker_standalone_authority` | 548-565 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `tracker_is_current` | 568-575 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `resolve_issue_authority` | 578-596 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `branch_satisfied_operation` | 599-605 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `missing_branch_satisfied_elements` | 608-614 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `branch_satisfied_operation_state` | 617-621 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `tracker_defines_branch_satisfied_blockers` | 624-626 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `inverse_patch` | 629-631 | `scripts/repo_checks/implementation.py` | verbatim |
| `branch_satisfied_blocker` | 634-696 | `scripts/repo_checks/implementation.py` | verbatim |
| `implementation_start_gate` | 699-729 | `scripts/repo_checks/implementation.py` | verbatim |
| `implementation_branch_gate` | 732-741 | `scripts/repo_checks/implementation.py` | verbatim |
| `canonical_tracker_capabilities` | 744-756 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `missing_tracker_capabilities` | 759-774 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `gate_phrase_capabilities` | 777-792 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `gated_tracker_capabilities` | 795-817 | `scripts/repo_checks/tracker_contract.py` | verbatim |
| `validate_tracker_capability_contract` | 820-888 | `scripts/repo_checks/scenarios/tracker.py` | verbatim |
| `validate_implementation_authority_contract` | 891-1095 | `scripts/repo_checks/scenarios/tracker.py` | verbatim |
| `validate_implementation_review_routing_contract` | 1098-1156 | `scripts/repo_checks/scenarios/implementation.py` | verbatim |
| `validate_implementation_working_copy_contract` | 1159-1194 | `scripts/repo_checks/scenarios/implementation.py` | verbatim |
| `validate_standalone_authority_modes` | 1197-1343 | `scripts/repo_checks/scenarios/tracker.py` | verbatim |
| `reconciliation_plan` | 1346-1429 | `scripts/repo_checks/reconciliation.py` | verbatim |
| `validate_reconciliation` | 1432-1611 | `scripts/repo_checks/scenarios/reconciliation.py` | verbatim |
| `validate_reconciliation_contract` | 1614-1667 | `scripts/repo_checks/scenarios/reconciliation.py` | verbatim |
| `pr_ticket_plan` | 1670-1774 | `scripts/repo_checks/pr_handoff.py` | verbatim |
| `validate_pr_ticket_plan` | 1777-1933 | `scripts/repo_checks/scenarios/pr_handoff.py` | verbatim |
| `validate_branch_satisfied_blockers` | 1936-2269 | `scripts/repo_checks/scenarios/implementation.py` | verbatim |
| `MULTI_TICKET_HANDOFF` | 2272-2281 | `scripts/repo_checks/pr_handoff.py` | verbatim |
| `SINGLE_TICKET_HANDOFF` | 2282-2285 | `scripts/repo_checks/pr_handoff.py` | verbatim |
| `validate_multi_ticket_pr_contract` | 2288-2365 | `scripts/repo_checks/scenarios/pr_handoff.py` | verbatim |
| `validate_native_agents` | 2368-2396 | `scripts/repo_checks/native_agents.py` | verbatim |
| `git_paths` | 2399-2409 | `scripts/repo_checks/native_agents.py` | verbatim |
| `validate_generated_agents_untracked` | 2412-2426 | `scripts/repo_checks/native_agents.py` | verbatim |
| `deep_review_shared_sources` | 2429-2436 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_lens_role` | 2439-2441 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_catalog` | 2444-2447 | `scripts/repo_checks/deep_review.py` | verbatim |
| `reviewer_text` | 2450-2452 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_role_problems` | 2455-2492 | `scripts/repo_checks/deep_review.py` | verbatim |
| `validate_deep_review_role_contract` | 2495-2529 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `DEEP_REVIEW_ACCESS_RULES` | 2532-2553 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_CODEX_ACCESS_CELLS` | 2554-2563 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_access_problems` | 2566-2578 | `scripts/repo_checks/deep_review.py` | verbatim |
| `validate_deep_review_access_contract` | 2581-2599 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `DEEP_REVIEW_PUBLICATION_RULES` | 2602-2694 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_audience_problems` | 2697-2729 | `scripts/repo_checks/deep_review.py` | verbatim |
| `validate_deep_review_audience_contract` | 2732-2760 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `scenario_matrix_names` | 2763-2779 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_scenario_problems` | 2782-2812 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_FOLLOW_UP_RULES` | 2815-2875 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_FULL_ONLY_SCENARIOS` | 2876-2878 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_FOLLOW_UP_HEADING` | 2879-2879 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_PROTOCOL_SCENARIO` | 2880-2880 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_TEMPLATE_SCENARIO` | 2881-2881 | `scripts/repo_checks/deep_review.py` | verbatim |
| `DEEP_REVIEW_OBSERVATION_SCENARIO` | 2882-2882 | `scripts/repo_checks/deep_review.py` | verbatim |
| `markdown_section` | 2885-2893 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_follow_up_scenario_lists` | 2896-2908 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_follow_up_problems` | 2911-2944 | `scripts/repo_checks/deep_review.py` | verbatim |
| `validate_deep_review_follow_up_contract` | 2947-2989 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `DEEP_REVIEW_PROBE_ENVIRONMENT_RULES` | 2992-3057 | `scripts/repo_checks/deep_review.py` | verbatim |
| `deep_review_probe_environment_problems` | 3060-3067 | `scripts/repo_checks/deep_review.py` | verbatim |
| `validate_deep_review_probe_environment_contract` | 3070-3082 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `validate_deep_review` | 3085-3138 | `scripts/repo_checks/scenarios/deep_review.py` | verbatim |
| `markdown_agent_fields` | 3141-3155 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `validate_deep_review_generation` | 3158-3189 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `remove_generated_agents` | 3192-3195 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `snapshot_tree` | 3198-3199 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `validate_agent_generation_contract` | 3202-3323 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `without_manifest_field` | 3326-3339 | `scripts/repo_checks/scenarios/agent_generation.py` | verbatim |
| `PORTFOLIO_PROJECT_URL` | 3342-3342 | `scripts/repo_checks/scenarios/portfolio_sync.py` | verbatim |
| `FakePortfolio` | 3345-3429 | `scripts/repo_checks/scenarios/portfolio_sync.py` | verbatim |
| `validate_portfolio_sync` | 3432-3591 | `scripts/repo_checks/scenarios/portfolio_sync.py` | verbatim |
| `validate_wizard` | 3594-3600 | `scripts/repo_checks/scenarios/wizard.py` | verbatim |
| `main` | 3603-3628 | `scripts/check.py` | verbatim |
| `if __name__` | 3631-3632 | `scripts/check.py` | verbatim |
