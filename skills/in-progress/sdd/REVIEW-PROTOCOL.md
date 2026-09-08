# Review protocol

Review immutable committed ranges. Implementer claims are evidence to verify, not conclusions to trust.

## Chunk review

After independently verifying a worker branch, the root coordinator invokes `/code-review` with:

- fixed point: chunk base SHA;
- head: verified chunk head SHA;
- complete diff and commit list captured by the coordinator;
- chunk manifest;
- full bodies and acceptance criteria for every completed ticket in the chunk;
- applicable PRD and ADR constraints;
- repository standards sources and context manifest;
- worker report and verification evidence;
- every required deterministic validator with executable PASS evidence, including coordinator-run fallback evidence for worker-blocked commands;
- any authorized baseline failure, its quoted explicit owning requirement, and evidence that the final chunk head turns it green.

`/code-review` dispatches two fresh axes:

- **Standards** — repository conventions, ADR compliance, test quality, deep-module shape, and quality risks.
- **Spec** — every acceptance criterion, missing behavior, incorrect behavior, and scope creep across the chunk.

Run at most two chunk review pairs concurrently. Keep each pair isolated from other chunks.

## Findings

Classify a finding as **load-bearing** when it concerns missing or wrong required behavior, security, data integrity, an ADR or hard repository rule, an invalid public seam, required verification, or a defect that can invalidate downstream work.

A judgment-call smell or optional simplification is not automatically load-bearing. The coordinator may rule against a finding, but records the finding, ruling, reason, and cost if wrong in the ledger.

A chunk is approved only when both axes have no accepted load-bearing findings, every ticket acceptance criterion has evidence, every authorized red baseline is green at the reviewed head, and every required deterministic validator has executable PASS evidence. Manual artifact inspection does not replace a required validator.

## Repair circuit

Round one and two resume the original worker with:

- exact findings and severity;
- owning ticket where known;
- prior reviewed head;
- current branch head;
- focused reproduction or verification command.

Round three uses a fresh escalation worker with the original packet, current diff, all prior findings, rulings, and failed repair evidence.

Every repair is a new `fixup!` commit targeted at one ticket commit. After each round, reconcile validators against the repaired changed paths and invalidate evidence whenever the covered artifact hash, exact command, executable/runtime fingerprint, or execution tree changed. Run every invalidated validator, using coordinator fallback for worker-blocked commands, before capturing the fix range and dispatching a scoped Standards and Spec re-review that:

1. verifies every accepted prior finding;
2. verifies current executable PASS evidence for every affected required validator;
3. inspects the fix diff for regressions and scope creep;
4. leaves unrelated already-approved code closed.

Run a complete two-axis review again only when repairs materially change design, public behavior, or scope. After round three, park the chunk when a load-bearing finding remains; continue unrelated chunks.

## Normalize before integration

The coordinator runs non-interactive autosquash on the temporary chunk branch after approval. Capture the tree hash before and after; they must match. Verify the rewritten history contains exactly one commit per ticket, in ticket order, with repository-compliant subjects. Review approval attaches to content, so any tree change invalidates it and requires review again.

## Integration conflict

A fresh integration worker receives:

- both tickets' full intent and acceptance criteria;
- current integration head;
- incoming ticket commit and original chunk base;
- both diffs;
- applicable ADR and module-boundary constraints;
- focused verification commands.

Resolve by preserving both intents, not by choosing one side's lines. If preservation requires a product decision, stop with `needs-info`. Re-run verification for both affected tickets before continuing.

## Final review

After all runnable chunks and closeout work converge, verify no required deterministic validator is failed, blocked, missing, or stale, then invoke `/code-review` from the captured run start to integration head. The Spec axis receives the full PRD, complete ticket set, status map, and rulings. The Standards axis receives the full net diff and all governance sources.

Give all accepted final findings to one aggregate fix worker. Final repairs use ticket-targeted fixup commits on the integration branch. The coordinator autosquashes and proves unchanged tree content, then reconciles the repaired head against the validator inventory, invalidates and reruns every affected validator, reruns broad verification, and dispatches one scoped re-review only after all required validators have current executable PASS evidence.

The caller branch moves only when no accepted load-bearing final finding remains.
