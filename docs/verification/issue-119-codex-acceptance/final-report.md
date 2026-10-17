# Codex targeted native acceptance of PR #130

Run date: 2026-10-16 America/Bogota (native events 2026-10-17 UTC). Reviewed latest head: `e31ead5ff2f45b67cbe29cea95f8bf202f4a6621`; rechecked unchanged before publication. PR remains open and draft. No implementation changes or merge.

**Targeted requested scenarios PASS.** No observed failure in the tested paths. This is a bounded coordinator/probe acceptance run using controlled disposable fixtures. It is not full cross-harness or end-to-end deep-review acceptance. The Claude bundle supplied expected behavior and fixture design only; every Codex observation below comes from fresh native Codex events.

## Results

| Scenario | Result | Observation or exact blocker |
| --- | --- | --- |
| Allowed sandboxed probe / P1 | **PASS** | Native validator created venv, built/installed the hash-locked local sdist, verified Python 3.11.16, fixturedep 1.0.0, pip consistency and app/dependency origins; calculate(3) printed 9; Finding. |
| Fresh setup after restoration / P2 | **PASS** | P1 venv removed. Native P2 recreated and independently verified its environment, ignored caller/prior-probe hints, label(3) printed <3>; Disproved. |
| Insufficient execution authority / P3 | **PASS** | Owned paths without a supplied sandbox or exact authorization: only nine read-only commands, no setup/import/check; Unresolved. |
| Locked dependency mismatch / P4 | **PASS** | Coordinator installed then seeded owned metadata 0.9.0 against unchanged 1.0.0 lock. Native validator observed mismatch despite pip check succeeding; no behavior check or repair; Unresolved. |
| Wrong production code origin / P5 | **PASS** | Coordinator seeded a byte-identical stale app plus startup preload in owned candidate. Native validator observed app from owned-tmp/stale/app.py despite matching 1.0.0 metadata and successful pip check; no behavior check or repair; Unresolved. |
| Process gate and child coverage | **PASS** | Final Bubblewrap canary: owned persistent writes succeed; caller/venv/Git/simulated-home/shared/contract/evidence writes denied with EROFS in parent and child; external connect ENETUNREACH; nested user namespace denied; capability sets zero, NoNewPrivs 1. P1/P2 actual build hooks and children show same controlled write denials. |
| Bounded native coordinator handoff | **PASS** | Actual Codex CLI coordinator launched exactly one PR-head native probe per H1-H5, sequentially. Native timestamps verify baseline restoration before launch, final response before preservation, preservation before restoration, and restoration before next invocation. P4/P5 setup/seed is coordinator behavior, not validator behavior. |
| Evidence preservation | **PASS** | Five complete native responses match consolidated pre-restoration copies byte for byte; gate/contract/declaration identities, hook logs, candidate setup/seed outputs, provenance and qualified outcomes survive. Native UUIDs recovered from public session metadata after run; task identities were available to coordinator at launch. |
| Exact baseline restoration | **PASS** | Every invocation verifies pinned HEAD/tree, empty status including ignored/untracked files, absent .venv and empty owned tmp. Measured caller checkout, caller Git excluding worktree administration, caller venv, simulated home and shared temp hashes remain unchanged. |
| Global configuration and permission scope | **PASS** | Both existing Codex config files and all measured global native-role files have unchanged SHA-256. Isolated coordinator inherited current danger-full-access/never policy; each role inherited it. No escalation or role-specific permission override. Only wrapper commands are mechanically confined. |
| Fixture cleanup | **PASS** | Final environment absent, registered fixture worktree removed through git worktree remove, fixture/runtime/isolated native home and temporary credential link removed; no sandbox mounts remain in host namespace. Source checkout clean at reviewed head. |
| Explicit authorization branch | **NOT EXERCISED** | No exact authorization for unconfined setup/import/check supplied; allowed cases use verified sandbox only. |
| Natural full coordinator pipeline | **NOT EXERCISED** | Successful static wave and Needs probe transitions are crafted inputs. No scouts/static wave, natural transition, GitHub overlap/publication, full-review cleanup/record receipt, broader #71 campaign or failure/capacity/head-change paths. |
| Poetry / other native manager | **NOT EXERCISED** | Fixture documents ordinary venv/pip; no Poetry project or manager executed. |
| Real httpx/openai installation | **NOT EXERCISED** | Only controlled offline fixturedep distribution executed; no application API calls. |
| Windows-native or desktop-app roles | **NOT EXERCISED** | Actual native Codex CLI 0.160.0 ran on Linux/WSL2, not Windows-native or desktop tool runtime. Existing shared Codex roles predate this gate and remain untouched. |
| No-lock manifest, unavailable/failed native setup, ambiguous prerequisites | **NOT EXERCISED** | Locked fixture setup succeeded. Earlier system ensurepip fixture-construction failure occurred before any native invocation and is not a native failed-setup result. |
| Justified / claim-invalidating mocking | **NOT EXERCISED** | No mocking proposed or used. Controlled fixture package is declared/locked; stale-origin seeding is an explicit contamination input, not validator evidence of behavior. |
| Retained dependency environment contamination | **NOT EXERCISED** | Every venv is in the worktree and removed. P5 owned temporary stale code was disposed, but no dependency environment retained across probes was reused. |

## Native identity and boundaries

Codex CLI `0.160.0` on Linux/WSL2. Native coordinator `01a14752-f839-7393-870e-a7f50b4287f9` used the user-configured `gpt-6.1-sol` / `high`. Native probes used the unchanged manifest pin `gpt-6-luna` / `high`. Configuration and regular native-role copies live only in an isolated run-owned CODEX_HOME. The current validator body was observed intact inside every child native developer message; only that equality check and the public source body hash are exported, not other developer instructions.

Generated probe role SHA-256: `d29627307c2bc17bcf30c69182430e97cab64f94abbc703318f009870c5ff8c6`. Environment reference SHA-256: `81e9d1a374f7b3453b1d695e9d564ce4288b85cf85e660ccc00617e4657e2198`. Canonical validator body identity is separately in verification.json.

Fixture baseline/head `fa305faf85d6a69a722f53b4a598143177e54b49`, tree `756b5bd67958292adc4a900acfc2a9acda1bcf9d`. The fixture is a locked plain Python project with local fixturedep sdist and a controlled PEP 517 backend. Its stale caller venv is known from fixture construction, not inspected by the validators. The seed for P5 uses a byte-identical reviewed app copy to isolate the origin check. No mock replaces required behavior.

| Case | Native task | Native UUID | Outcome | Commands |
| --- | --- | --- | --- | --- |
| P1 | `/root/p1` | `01a14753-f820-7280-b3f3-b34047fc8e1a` | Finding | 6 |
| P2 | `/root/p2` | `01a14754-f21f-7ca2-85fc-cb6570d8f131` | Disproved | 9 |
| P3 | `/root/p3` | `01a14756-1954-75b0-a7dd-e87e6a215769` | Unresolved | 9 |
| P4 | `/root/p4` | `01a14758-ca39-7222-9a33-b19dc8d05078` | Unresolved | 5 |
| P5 | `/root/p5` | `01a1475a-1a91-7733-9b46-733dd417220d` | Unresolved | 6 |

Native role tool calls have the inherited full-access policy and instruction-enforced confinement. They gain no permissions. All target-controlled executable setup, production imports, consistency checks and bounded checks used sbx-run. Bubblewrap provides isolated namespaces, read-only /usr, /etc, copied runtime and fixture, read-only worktree .git pointer, owned worktree/temp binds, private /tmp/dev/proc, zero capabilities and no_new_privs. Host persistent writes are limited to owned worktree/temp. Real home paths are absent; network and further user namespaces are unavailable. Observations establish these fixture boundaries, not general non-mutation of the real home.

An early sandbox shakedown had a writable private root and permitted nested user namespaces; it was rejected and narrowed before any native target setup. The final canary and wrapper hashes are supplied in every allowed gate. System Python lacked ensurepip during initial fixture construction; the fixture was rebuilt to declare an already available CPython 3.11.16 copied into the run, without a global install. Neither preliminary result counts as native validator behavior.

The coordinator could not see P5's full verification command in its delivered child report. The outer audit recovered that exact command and output from the native CommandExecution event, so this command-text gap is closed in events/ and native-index.json.

P4 includes one failed read-only lookup of a guessed dist-info filename, followed by a successful read of the actual metadata. The error is retained in native events. Adjudication completed; no repair or behavior probe was attempted.

## Evidence and remaining decisions

`run-state.json` is the consolidated provenance and outcome record. `events/` contains sanitized visible native events; `native-index.json`, `audit.json` and `verification.json` bind native UUIDs, model/policy observations, exact commands/results, final responses, preservation ordering, role-load equality and integrity checks. `contracts/`, `roles/`, `fixture/` and `tools/` hold reviewable inputs. `export-policy.json` documents exclusions. Native encrypted task prose is not decrypted; the parent prompt, named environment contracts, launch identities and actual child contract reads remain available. No credentials, hidden reasoning or unrelated developer instructions are exported. Native per-session event files are runtime artifacts, not a second environment ledger.

The bounded Codex allowed/denied, environment verification, coordinator handoff, preservation and restoration gaps now have observations. Broader natural end-to-end orchestration remains NOT EXERCISED. The PR summary still requires evidence or an explicit maintainer decision for the authorization branch, Poetry, real httpx/openai installation and Windows-native behavior. The existing Devin-specific waiver is unchanged. Other unexercised regression scenarios above are coverage limits, not observed failures. Existing shared Codex roles remain stale; refreshing those installs is a separate operational action excluded by this request.

Repository validation: `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check.py` passed for 31 skills; `git diff --check` passed. Source worktree is clean at the reviewed head. `SHA256SUMS` binds the exported files; `preservation-receipt.json` records byte-verified preservation and actual temporary-directory cleanup.
