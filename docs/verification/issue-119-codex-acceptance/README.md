# Issue #119 Codex native acceptance evidence

Publication of the existing Codex acceptance records for [PR #130](https://github.com/mmena1/skills/pull/130), collected on 2026-10-16 America/Bogota (2026-10-17 UTC) at reviewed head `e31ead5ff2f45b67cbe29cea95f8bf202f4a6621`. This commit publishes those observations; it does not rerun acceptance or extend coverage to this later documentation commit.

## Results and scope

The [original final report](final-report.md) contains the complete scenario matrix and limitations. Five actual `deep-review-validator-probe` invocations ran under Codex CLI 0.160.0 on Linux/WSL2 with PR-head generated roles and an actual native Codex coordinator.

| Scenario | Observed result |
| --- | --- |
| Allowed sandboxed setup, verification and bounded check (P1) | PASS; Finding, `calculate(3)` printed `9`. |
| Fresh environment after restoration (P2) | PASS; Disproved, `label(3)` printed `<3>`. |
| Unsatisfied execution gate (P3) | PASS; Unresolved, no target-controlled setup/import/check. |
| Wrong locked dependency version (P4) | PASS; Unresolved, behavior check withheld. |
| Wrong production code origin (P5) | PASS; Unresolved, behavior check withheld. |
| Bounded native coordinator handoff, evidence preservation and exact restoration | PASS within the recorded fixture scope. |

No tested path failed. The successful static phase and `Needs probe` transitions were controlled inputs. Natural full-pipeline orchestration, explicit authorization for unconfined execution, Poetry, real httpx/openai installation, Windows/desktop behavior and the other edge cases in the original report remain **NOT EXERCISED**. The existing Devin-specific acceptance decision remains separate. This publication does not approve merge, change those statuses or satisfy missing cases. Claude evidence was a reference for expected behavior, not proof of Codex behavior.

The native role tool calls inherited full access and relied on their behavioral instructions. Target-controlled executable commands used the separately canary-verified Bubblewrap boundary. The bundle preserves that distinction and only claims integrity for the controlled paths actually measured.

## Reviewable records

- [run-state.json](run-state.json): consolidated per-invocation provenance, complete responses saved before restoration, contracts, hook logs, fingerprints and qualified outcomes.
- [events/](events/): sanitized native events for the coordinator and five validators; exact commands, results, native identities and public messages.
- [native-index.json.txt](native-index.json.txt), [audit.json](audit.json) and [verification.json](verification.json): event index, exact-response comparisons, native ordering, role-body identities and verification records.
- [public-native-receipt.json](public-native-receipt.json): compact native receipt previously embedded in the [initial PR findings](https://github.com/mmena1/skills/pull/130#issuecomment-6227659278).
- [contracts/](contracts/), [roles/](roles/), [fixture/](fixture/) and [tools/](tools/): historical contract/role snapshots, controlled fixture bytes and instrumentation. Generated role snapshots here are evidence, not installed agent files or a second source of workflow authority. Fixture hooks intentionally attempted controlled writes; inspect these artifacts without executing them.
- [preservation-receipt.json](preservation-receipt.json), [publication-receipt.json.txt](publication-receipt.json.txt) and [publication/](publication/): earlier cleanup, local preservation and initial PR report publication records. They predate this repository publication.

## Sanitization and source identity

The [original export policy](export-policy.json) documents the native event selection. Hidden reasoning, credentials, opaque native task payloads, private base instructions and unrelated developer instructions were excluded in that export. No opaque task prose was decrypted. The parent prompt, named contracts, launch identities and actual child reads remain available.

This publication retains **61 source files byte for byte**. Two historical JSON records are published as `native-index.json.txt` and `publication-receipt.json.txt` so captured historical terminology remains evidence rather than current prose. Contract and validator Markdown snapshots similarly use `.md.txt` names to distinguish captured evidence from authoritative skill documents. All snapshot contents and hashes are unchanged, and the provenance inventory records the original names. The standalone `isolated-config.toml` is omitted conservatively; its original hash is retained. No private configuration contents are added. Observed runtime policy/model fields and hashes of configuration/role files remain as evidence, without publishing those private files.

[source-inventory.json](source-inventory.json) records every original path/hash and its retained or omitted status. [source-SHA256SUMS](source-SHA256SUMS) is an unchanged copy of the local source inventory. It identifies the original archive, including the omitted configuration; use the new inventory below to verify this published bundle. [publication-policy.json](publication-policy.json) records this publication's exclusions and static inspection scope. The original local archive remains unchanged.

Historical `/tmp` paths in native commands no longer exist. The fixture, environments and temporary credential link were removed during the original acceptance cleanup. The original report's “latest head”, draft status and publication statements refer to that earlier observation, not a claim of fresh acceptance here.

## Verify the published bytes

From this directory:

```sh
sha256sum --check SHA256SUMS
```

`SHA256SUMS` covers every published regular file except itself. Source hashes, native transcript commitments, fixture source identities and the original receipt hashes remain intact; the publication inventory adds hashes for this README and the provenance files. Checksum and static repository checks for this publication do not represent another native acceptance run.
