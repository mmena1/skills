# Structural scout calibration benchmark

The bounded harness for issue #89: a blinded, paired comparison of the structural scout contract before PR #58 (treatment A, `b3a568ec926abc17326213dfb3bd00a48feb256a`) and after it (treatment B, `5e61f1a0494701f4844c04351235fa77714d9c4e`), with every emitted hypothesis replayed through B's pinned validator. It uses the research pins and definitions in the [research README](../README.md) and the [case catalog](../case-catalog.json) unchanged. Results and their interpretation live in [report.md](report.md).

Everything in this directory is evaluator-only. A reviewer or validator session never sees it.

## Boundary design

Prompt instructions, a namespace launch or role configuration alone are not the boundary. Three enforced layers are:

1. **No inherited model tools.** Each session is a fresh `claude -p` process with `--tools ""`, `--strict-mcp-config`, `--setting-sources ""`, `--disable-slash-commands`, `--no-session-persistence`, a replaced system prompt, an empty neutral working directory under `/tmp`, a scrubbed environment, and exactly one MCP server, `capsule`. Memory, skills, agents, connectors, web tools and persistent context are therefore absent.
2. **One capsule, jailed.** The `capsule` server ([capsule_server.py](capsule_server.py)) offers four read-only tools (`list_files`, `read_file`, `search`, and `git` limited to `diff`, `show`, `log`, `status`, `ls-files` and `grep` naming only the two synthetic SHAs). It runs inside bubblewrap with `--unshare-all --clearenv`, mounting only `/usr`, the one capsule repository read-only, the server file and a per-session access-log directory. Evaluator storage, sibling capsules, the depot, this repository, the host home, credentials and the network do not exist inside the jail.
3. **A recording, fail-closed broker.** The CLI reaches the API only through a local proxy ([broker.py](broker.py)). Provider credentials and network stay in the CLI and proxy processes, which the model cannot command. The proxy records every request (credentials redacted) and refuses, with HTTP 403, any request that offers a tool other than the four capsule tools, carries `mcp_servers`, names another model or effort, contains an evaluator-only token (original SHAs, fixture and treatment commits, evaluator paths) absent from the capsule itself, contains context the session did not intend (anything besides our two prompts, the model's turns, tool results and three allowlisted CLI templates), or exceeds the budget. A refusal fails the session with a named status, and that run is invalid.

`calibrate.py isolation` exercises this boundary through the real launch, never through prompts: for every capsule it drives the real jailed server with permitted and forbidden calls, runs a probe inside the identical jail, and launches the real CLI four times to show a working round trip and the refusal of an inherited tool, a wrong effort and a leaked token.

Two CLI behaviors were discovered by these fail-closed checks and corrected before any benchmark session: the `--max-budget-usd` notice (the dollar cap is not used; the proxy budget is authoritative) and the silent-turn nudge (`CLAUDE_CODE_SILENT_TURN_REMINDER=0`). Both corrections are recorded in the evidence `receipts/corrections.jsonl`.

## Prerequisites

- Linux (tested on WSL2, kernel 6.18) with bubblewrap 0.11 or newer and unprivileged user namespaces. macOS and Windows hosts cannot run the boundary as written.
- Python 3.11 or newer (tested with 3.14) and Git (tested with 2.53).
- The Claude CLI on `PATH`, authenticated with the host's existing login (tested with 2.1.287). Credentials are never copied or changed.
- `gh` authenticated with read access to `mmena1/mtg-copilot`, only to populate the evaluator depot.
- Access to the chosen model. This run used `claude-opus-5-5` at `high` effort, the Claude assignment for both the structural scout and the static validator at A, B and current main. Model and effort are operator inputs; no fallback model is ever passed, and a different served model fails the session as `model_mismatch`.

## Procedure

Choose a new evidence directory outside the repository; the repository check scans ignored files, and raw model text contains prose it rejects. The runner refuses an evidence path inside the repository.

```bash
export EVIDENCE=~/.local/share/skills-research/structural-calibration-benchmark-20261009
export BENCH=docs/research/deep-review-structural-calibration/benchmark
```

1. Check out the benchmark revision and run the offline checks:

   ```bash
   python3 docs/research/deep-review-structural-calibration/test_prepare_capsules.py
   python3 $BENCH/test_benchmark.py
   python3 scripts/check.py
   ```

2. Populate one new, non-shallow evaluator depot with all ten pinned SHAs (see the catalog). A missing object makes the preparer stop before creating output and name the case, SHAs and checked repositories.

   ```bash
   git init --bare $EVIDENCE/inputs/corpus.git
   git -c 'credential.helper=!gh auth git-credential' --git-dir=$EVIDENCE/inputs/corpus.git fetch --no-tags \
     https://github.com/mmena1/mtg-copilot.git \
     5542ce2b4f6a04e5df4d53c5992c238733d86f51 f9acf3a39d2af2ff6e34ce53e9e54d9371382c4f \
     ad18e21533fb8da562e4351ade0d4bd9e546b8f3 6a276a789b7e1d8d385f4e9382ea14f2d1c4f358 \
     b681583d2d9080d60e44fc4e02b4b5aba93e6f39 58eb456461cbff688c83c42f3e2b3078c1df748f \
     2273f7c13e1c4a804e39a442025643442cf5e00d 518bd84c4e5a81047f4886b835e4d7999659c895 \
     4aab2dd02c45e1fc84cf765e539d645a6a0ff65a 44c542485fcebbd3d5746502087857af982f27f7
   ```

3. Prepare. This builds deterministic base, head and decoy-future commits for the five controls and the validator challenge fixture from `fixtures/`, runs the unmodified research preparer twice into new directories over all eleven pairs (it resolves every pair even when the pilot schedules four), compares the two receipts, and exports and hashes the treatment files from this repository's history.

   ```bash
   python3 $BENCH/calibrate.py prepare --evidence $EVIDENCE --repository $EVIDENCE/inputs/corpus.git --seed 20261009-issue89
   ```

4. Exercise the boundary. Nothing that calls a model runs until this receipt passes.

   ```bash
   python3 $BENCH/calibrate.py isolation --evidence $EVIDENCE --model claude-opus-5-5 --effort high
   ```

5. Adjudicate labels and controls independently, then freeze them. Two fresh sessions per candidate see only the capsule and a minimal restatement (no dispositions, comments, fixes, treatments or remedies) and must establish task, cost, mechanism, diff relevance and their own qualifying alternative under B's quoted neutral standard. Agreement decides; disagreement goes to a fresh resolver; an unresolved disagreement is provisional. Controls must be independently confirmed negative.

   ```bash
   python3 $BENCH/calibrate.py adjudicate --evidence $EVIDENCE --model claude-opus-5-5 --effort high --workers 4
   ```

6. Freeze and run the pilot (M91, M94, N1, N2; one repetition per arm; validator cap 12), then write the pilot gate receipt.

   ```bash
   python3 $BENCH/calibrate.py freeze --evidence $EVIDENCE --phase pilot --seed 20261009-issue89 --model claude-opus-5-5 --effort high --workers 4
   python3 $BENCH/calibrate.py run --evidence $EVIDENCE --phase pilot
   python3 $BENCH/calibrate.py gate --evidence $EVIDENCE --phase pilot
   ```

   If unique hypotheses exceed the cap, `run` stops with replay incomplete and refuses to continue until a prospective revision is recorded; it never drops hypotheses or reruns selectively:

   ```bash
   python3 $BENCH/calibrate.py revise-budget --evidence $EVIDENCE --phase pilot --validator-cap 16 --reason "..."
   ```

7. Only after `gate-pilot.json` says PASS, freeze the full schedule (all five cases and five controls, two arms, three repetitions: sixty scouts) with its validator cap, run it, and write the completion receipt:

   ```bash
   python3 $BENCH/calibrate.py freeze --evidence $EVIDENCE --phase full --seed 20261009-issue89-full --model claude-opus-5-5 --effort high --workers 4 --validator-cap 180
   python3 $BENCH/calibrate.py run --evidence $EVIDENCE --phase full
   python3 $BENCH/calibrate.py gate --evidence $EVIDENCE --phase full
   ```

8. Regenerate every score without model calls, then seal the evidence:

   ```bash
   python3 $BENCH/calibrate.py score --evidence $EVIDENCE --phase pilot
   python3 $BENCH/calibrate.py score --evidence $EVIDENCE --phase full
   python3 $BENCH/calibrate.py manifest --evidence $EVIDENCE
   ```

Record any failed attempt or correction with `calibrate.py note --evidence $EVIDENCE --text "..."`. Prompts, pins, budgets, schedules and scores reproduce; stochastic model answers do not.

## Exit and status behavior

A command that cannot proceed exits non-zero with `STOP: <reason>`: a missing or failing prerequisite receipt, an existing frozen receipt, an evidence path inside the repository, a changed capsule diff, an interrupted session directory, or incomplete replay at the cap. Every session ends with exactly one status in `meta.json`:

| Status | Meaning |
| --- | --- |
| `completed` | Clean run; the only status whose output is scored. A completed `No hypotheses` is the semantic zero. |
| `confinement_failure` | A non-capsule tool, extra MCP server or remote tool reached a request. |
| `leaked_context`, `unexpected_context` | An evaluator token, or context the session did not intend, reached a request. |
| `model_mismatch`, `effort_mismatch` | Requested or served model or effort differed from the plan. An unavailable model surfaces here or as `api_error`; no substitute is tried. |
| `budget_exhausted` | Request, cumulative output or peak context limit reached. |
| `timeout`, `api_error`, `launch_failure`, `truncation`, `missing_output` | Execution failures. |
| `unusable_output` | Assigned at collection: neither hypotheses nor a clean zero, or no validator outcome. |

Failures are excluded from successful-run recall and reported with paired completion and an operational intention-to-run lower bound. Scouts and validators are never rerun. Evaluator sessions (adjudicators, assessors, resolvers, auditors, classifier) get one prospective rerun after an execution failure.

## Preregistered budgets

The research suggested 24,000 total tokens per scout and 12,000 per validator. A scout must receive the complete original diff, which alone is about 17,000 to 25,000 tokens for these cases, so those ceilings cannot be met. The supported, enforced, identical equivalents are:

| Role | Wall time | Model requests | Peak context (input plus output) | Cumulative output |
| --- | --- | --- | --- | --- |
| Scout | 25 min | 80 | 250,000 | 64,000 |
| Validator (replay and challenges) | 15 min | 50 | 200,000 | 32,000 |
| Adjudicator, auditor | 15 min | 50 | 200,000 | 32,000 |
| Assessor, resolver, classifier | 15 min | 4 | 200,000 | 32,000 |

The proxy enforces the token and request limits by refusing the next request; the runner kills the process group at the wall limit. Tool output is truncated at 60,000 characters per call and search at 200 matches, identically for every role. The pilot validator cap is 12 unique static replays. The seven gating validator challenges and one supplementary challenge have their own budget. Static validation is the only adjudication: `Needs probe` is recorded as a transition and never executed.

## Evidence layout

| Path | Contents |
| --- | --- |
| `inputs/corpus.git`, `inputs/fixture-source.git` | Evaluator depots. Never mounted. |
| `inputs/preparation-1`, `inputs/preparation-2` | Two preparer outputs; only `capsules/<alias>/repository` is ever mounted, one per session. |
| `inputs/treatments/` | Exported pinned contracts and the quoted neutral standard. |
| `receipts/` | Preparation, treatments, isolation, labels, controls, challenges, plans, pools and opaque replay mappings, assessments, novelty audits, rejection reasons, budget revisions, gate and completion receipts, corrections, and superseded attempts. |
| `sessions/<phase>/<role>/<name>/` | Per session: exact system and user prompts, MCP launch, full API request and response log, CLI event stream, stderr, tool access log, final text and `meta.json` (status, observed model, effort, tools, CLI build, usage, timing). |
| `results/` | Machine-readable scores per phase. |
| `MANIFEST.sha256` | Integrity manifest of every evidence file. |

## Tests

`test_benchmark.py` exercises the real interfaces offline with a fake upstream API and a fake CLI: confinement denials through the real jail and their fail-closed detection when a mount leaks, capsule tool denials, proxy refusals and budget exhaustion, execution failure versus clean zero, mismatched resolved settings, deterministic scheduling and preparation, label blindness of control capsules and prompts, parsing, deduplicated and grouped credits, provisional, novel and uncertain classification, N/A denominators, and the full pilot pipeline through cap exhaustion, a prospective revision, assessment, scoring and a passing gate. Tests needing bubblewrap or the treatment commits skip when those are unavailable (for example in a shallow CI checkout). Tested platform: Linux on WSL2 only.

Paths not exercised: hosts without bubblewrap, other CLI versions or providers, runtime probes, and Codex or Devin execution.
