# Repository check modules

`python scripts/check.py` is the canonical fast check. Its `main` calls every validation group explicitly, in an order that decides which failure is reported first, and turns the first `CheckFailure` into one `FAIL:` line on stderr with exit status 1. The groups live in this package, owned by responsibility. Everything runs on the standard library.

## Two layers

- **Models and rules**: the top-level modules. They parse documents, hold pinned contract text, and model documented workflows over snapshots. Importing one runs nothing.
- **Group runners**: the `scenarios/` modules. Each `validate_*` runner reads the real documents and fixtures, then exercises the models through scenario tables, fakes, temporary copies, and mutation self-tests.

Imports point one way: `scenarios/` modules and `check.py` import models, and models import only `common`, other models, or the sibling `scripts/generate_agents.py`. A model never imports a runner or the entry point. A responsibility with no scenarios keeps its runner beside its rules (`layout`, `references`, `native_agents`).

## Ownership

| Module | Owns |
| --- | --- |
| `common` | Repository-root resolution, `CheckFailure`, and `fail`. Nothing else is shared. |
| `layout` | The flat skill layout, frontmatter parsing, and the reviewed invocation roster with its Claude, Devin, and Codex controls. |
| `references` | Retired files, stale names (including retired skills and the legacy spec terms, with a line-scoped migration exception), the em-dash rule, relative links, and README skill links. |
| `agent_brief` | Agent Brief completeness, trusted authorship, and comment precedence. |
| `tracker_contract` | Tracker capabilities, downstream gates, standalone authority modes, the branch-satisfied operation, and authority resolution. |
| `reconciliation` | The `/reconcile` readiness classification and reconciliation plan model. |
| `implementation` | The `/implement` start gate, branch gate, and branch-satisfied blocker models. |
| `pr_handoff` | The `/write-pr` ticket plan model and the pinned PR/merge handoff sentences. |
| `review_citations` | The implementation-review source anchor, commit attribution, and aggregation model, with its pinned Git commands. |
| `native_agents` | In-memory rendering of every role manifest and generated-file ownership in Git. |
| `deep_review` | Deep-review pinned roles, the lens catalog, and each document rule catalog with its `*_problems` checker. |
| `scenarios/tracker` | Tracker capability, implementation authority, and standalone authority mode groups. |
| `scenarios/implementation` | Review routing, working copy, and branch-satisfied blocker groups. |
| `scenarios/reconciliation` | Reconciliation plan scenarios and the reconciliation migration contract. |
| `scenarios/pr_handoff` | Ticket plan scenarios and the multi-ticket handoff wording. |
| `scenarios/review_citations` | Anchor and commit attribution scenarios over a disposable Git repository, and the implementation-review citation wording. |
| `scenarios/deep_review` | The deep-review group and its mutation self-tests. |
| `scenarios/agent_generation` | Generator runs over temporary skill copies, for the fixture skill and deep review. |
| `scenarios/spec_naming` | The spec naming convention (`Spec: <name>` titles and `spec.md` paths) in `/to-spec`, the tracker seeds, `/design-review`, and `/to-tickets`, and the `setup-skills` legacy-terminology migration wording. |
| `scenarios/portfolio` | The `/portfolio` read-only, registry-only, and GitHub-tracker-only wording. |
| `scenarios/wizard` | The wizard helper's unittest suite, run as a subprocess. |

`references` holds the stale-reference literals its scanner matches, so it is the one script that scanner exempts. Keep those literals there.

## Adding a check

1. Put the parsing, rule catalog, or workflow model in the module that owns the responsibility, or in a new top-level module when no owner fits.
2. Put its scenarios and assertions in the matching `validate_*` runner under `scenarios/`, reporting each failure through `fail` with the input location in the message.
3. Call a new runner from `main` in `scripts/check.py`, placed where its failures should be reported relative to the other groups.

## Focused checks

Run one group, or call one model, without the whole suite:

```text
PYTHONPATH=scripts python -c "from repo_checks.scenarios.reconciliation import validate_reconciliation; validate_reconciliation()"
```

Silence means it passed; a failure raises `CheckFailure` with the same message `check.py` prints after `FAIL:`. Run the full `python scripts/check.py` before committing.
