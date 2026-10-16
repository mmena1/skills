# Issue #119 reviewable evidence

**Native acceptance is incomplete. PR #130 stays draft.** No narrower acceptance decision is approved. These artifacts make bounded observations inspectable; they do not establish full coordinator execution across supported harnesses.

The files in this directory are repository artifacts available with this PR and its commit history. Local paths inside historical records identify the original controlled fixtures, not a location a reviewer must access. Every published file except the checksum list itself has a SHA-256 entry in [SHA256SUMS](SHA256SUMS). Run `python3 scripts/check.py` from the repository root to verify the bundle and its inventory. On systems with sha256sum, the standalone check is:

```sh
cd docs/verification/issue-119-evidence
sha256sum --check SHA256SUMS
```

Checksums bind the published files; they are not provider attestations or proof of unexercised behavior. The canonical check verifies integrity and exercises missing-file and altered-byte failures. It never runs the archived commands or the install-hook experiment.

## Current process-gate checks

| Artifact | Observation and limit |
| --- | --- |
| [Native handoff input](process-gate/native-input.json), [visible events](process-gate/native-visible-events.jsonl), [root verification](process-gate/native-root-verification.json) | Updated generated Claude native validator, direct-role session `ae3e5309-d34c-44f7-b488-1f55ef7deef4`: only Read/Glob calls, Unresolved because neither a verified process boundary nor exact hook/import authorization was supplied. No environment or hook marker was created; the controlled target stayed clean and was removed after recording results. This is one denied-path handoff regression, not a full coordinator run or an allowed-path sandbox test. Source identities and native tool correlation fields are retained. |
| [PEP 517 experiment](process-gate/experiment.py), [actual results](process-gate/experiment-results.json) | A locally authored controlled backend and its child wrote owned, simulated caller and simulated home markers with ordinary process access, despite an owned venv. The same backend under the recorded Bubblewrap read/write policy wrote only the owned marker; caller/home writes failed with EROFS in both parent and child. Commands, outputs, hook source hash and exact fixture cleanup are recorded. This is a process-boundary experiment, not native agent acceptance. No real caller/home was targeted. |

The experiment is intentionally confined to its own caller/home fixtures. Existing Python 3.11.16 with ensurepip and Bubblewrap 0.11.1 were used, without network or global installation. Its explicit controlled unconfined case demonstrates the danger; it is not an admitted review execution path. An unchanged pre-existing sentinel alone did not detect the extra marker writes, so the results retain directory-level marker observations too. Repeating the experiment requires a suitable existing runtime and effective sandbox capability; no universal setup tool is introduced.

## Historical bounded observations

These observations preceded the process execution gate. They cannot establish that the revised gate was obeyed or that arbitrary setup hooks cannot mutate caller/home state. The first verified probe inspected its simulated caller and created bytecode outside its initially named paths; those deviations remain visible. Later fingerprints cover only the measured controlled fixture identities, not an unchanged real home or shared environment in general.

| Artifact | Recorded coverage |
| --- | --- |
| [Claude setup-limitation events](historical/claude-visible-events.jsonl) | Three native invocations and their actual tool results: two ensurepip/pip setup failures and one setup-forbidden handoff returned Unresolved. |
| [Claude verified events](historical/claude-verified-visible-events.jsonl) | Two sequential invocations created an owned venv, installed a real offline fixture distribution, verified versions/origins, observed 9 instead of the fixture's expected 6, and restored before re-establishment. Includes the disclosed deviations. |
| [Claude direct-role events](historical/claude-boundary-visible-events.jsonl) | The earlier tightened caller-path handoff used real installed imports and returned Finding without caller-path access. It did not exercise the subsequently added process execution gate. |
| [Recorded run states](historical/run-states.json), [root verification](historical/root-verification.json), [cleanup](historical/root-cleanup.json) | Coordinator-recorded provenance, outcomes, measured fingerprints and restoration/cleanup. Read alongside native events; a record's own narrative is not independent proof of its claim. Codex's launch error is coordinator-recorded with no independently exposed native launch response or usable probe outcome. |
| [Fixture sources and wheel bytes](historical/fixtures.json), [source at 10579a9](historical/source-10579a9.json), [initial source identities](historical/evidence-source.json) | Controlled fixture content and exact wheel bytes with hashes, plus the implemented pre-review source. Event Read results retain the actual instruction version each native call saw; the initial identities are an earlier snapshot, not a claim that every case used identical instructions. |

The run-state headers containing `mode: full` came from bounded smoke instrumentation; their recorded scope excludes a full review. That header never establishes full-review acceptance. Static completion/Needs probe were controlled inputs, not observed static waves. The fixtures are not mtg-copilot, httpx or openai runtime evidence.

## Export and remaining gaps

[Export policy](export-policy.json) records source hashes and field selection. Visible text, tool inputs/results, event IDs, parent tool-use IDs, timestamps and served model fields were retained without rewriting their contents. Hidden reasoning, usage/cost/account rate-limit telemetry, unrelated initialization/stderr, authentication and configuration files were omitted. The retained paths and fixture emails describe controlled test data. No secrets or account credentials were selected; credential-pattern checks found no matches. Original-file hashes identify local inputs; they do not make unpublished originals retrievable or verifiable.

No Codex usable probe, Devin run, current allowed-path native sandbox run, current explicit-authorization native run, or full coordinator execution across supported harnesses is established here. Other-manager execution, real httpx/openai installation and Windows-native behavior remain unexercised. The historical evidence and the new negative gate regression do not satisfy those gaps. Keep the PR draft until the required observations are collected or the human owner explicitly approves and records a narrower acceptance decision.
