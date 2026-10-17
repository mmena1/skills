# Issue #119 verification and accepted scope

The [maintainer decision for PR #130](https://github.com/mmena1/skills/pull/130#issuecomment-6227887598) approves the existing targeted evidence as sufficient for issue #119. No additional native acceptance runs are required. This accepts the listed coverage limitations for this PR only; it does not weaken the runtime safety contract or turn unobserved cases into passes. Ordinary CI, review and merge protections still apply.

## Durable evidence archive

The [immutable evidence-archive v1 prerelease](https://github.com/mmena1/skills/releases/tag/issue-119-evidence-v1) is an audit archive, not a product release. Download the [complete archive](https://github.com/mmena1/skills/releases/download/issue-119-evidence-v1/issue-119-evidence-v1.tar.gz) and its [SHA-256 checksum](https://github.com/mmena1/skills/releases/download/issue-119-evidence-v1/issue-119-evidence-v1.tar.gz.sha256).

```text
f65d16a0c6807f6965d5867a4eb8d336ea00bb5058b674924cd61f27144bc2f5
```

The archive preserves all 125 files from the three sanitized bundles and the dated historical report, byte for byte with original modes. It retains manifests, native events, run state, source identities, results and verification records. Its own inventory covers 133 files, in addition to the inventory itself. Selected public tracker records preserve the acceptance decision, Devin waiver/results and network policy.

The prerelease tag points to existing evidence-free base `388a4242e9b65e9ed5d584038ed30ee2b61ef14a` on `main`, not to an evidence-heavy PR commit. Archive source head: `0d3df5f75aeddc33cd6cb294de6ff0422996ead7`. Accepted targeted evidence was collected at:

- Claude Code: `a0159003ac7b243fc6e5fbce66f2259dae7e144e`.
- Codex P1-P5 and Devin denied path: `e31ead5ff2f45b67cbe29cea95f8bf202f4a6621`.

`ARCHIVE-METADATA.json` binds the original Git blobs, modes, SHA-256 identities and original inventory checks. Earlier reports remain dated historical observations; the maintainer decision supersedes their earlier pending-acceptance statements. The dated probe-environment report was archived because its permanent rules already live in the shared contract and its observations are historical.

## Accepted observations and limitations

| Evidence | Status and scope |
| --- | --- |
| Claude Code targeted acceptance | **PASS**: owned setup, locked dependencies/code origins, bounded checks, exact restoration, a fresh second environment and denied-path behavior in controlled fixtures. |
| Codex targeted acceptance | **PASS**: P1-P5 allowed/denied cases, fresh environment, wrong locked-version and code-origin rejection, bounded native coordinator handoff, provenance preservation and restored baselines. |
| Devin denied path | **PASS**; disclosed outbound TCP is accepted by the [maintainer network policy](https://github.com/mmena1/skills/pull/130#issuecomment-6224883962). |
| Other Devin execution/restoration/coordinator cases | **NOT EXERCISED**, explicitly waived for this PR by the [Devin decision](https://github.com/mmena1/skills/pull/130#issuecomment-6224937076) and the final acceptance decision. |
| Other unexercised scenarios below | **NOT EXERCISED**, accepted coverage limitations for #119, not PASS. |

Accepted unexercised coverage includes a natural full pipeline with real scout/static waves, organic `Needs probe`, publication and the full coordinator receipt; the exact explicit-user-authorization gate branch; Poetry or another manager; real httpx/openai installation; Windows-native/desktop behavior; no-lock and failed/unavailable setup; ambiguous prerequisites; justified/invalidating mocking; retained-environment contamination and the other documented uncommon paths. These observations establish neither general caller/home non-mutation nor cross-harness full-pipeline equivalence. The Codex handoff used controlled static inputs; Claude and Devin exercised the validator directly.

## Preserved safeguards

The authoritative [probe environment contract](../../skills/deep-review/references/probe-environment.md), [focused regression scenarios](../../skills/deep-review/references/probe-environment-scenarios.md), coordinator/validator instructions and receipt guidance remain unchanged by this cleanup. The reusable `scripts/check.py` rule catalog, pointer checks, scenario checks and clause-removal mutation checks remain in place. Only the historical bundle's inventory check and its artifact-specific mutation fixtures were removed from repository CI; they do not govern `/deep-review` behavior.

## Archive verification and history

Before removing evidence from the PR, the published archive and checksum were downloaded anonymously. Their bytes matched the uploaded assets, the archive's full inventory and all three original inventories verified, and every original file matched its committed source identity and mode. GitHub reported the prerelease immutable after the repository's previous immutability setting was restored. No credentials, private configuration, hidden reasoning or raw unredacted sessions were added; the original sanitization policies and deliberate omissions remain intact.

With the two assets in the current directory:

```sh
sha256sum --check issue-119-evidence-v1.tar.gz.sha256
tar -xzf issue-119-evidence-v1.tar.gz
cd issue-119-evidence-v1
sha256sum --check SHA256SUMS
```

The captured scripts/hooks are evidence, not verification commands to execute. No Claude, Codex or Devin acceptance was rerun for this cleanup. Use a **squash merge** so the evidence-heavy commits already in the unchanged PR history do not become ancestors of `main`.
