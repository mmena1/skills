# Context packet

Filesystem availability and active context are different budgets. Put complete governance within reach; inject only what the chunk needs to reason about.

## Governance snapshot

Inventory the repository's instruction chain before dispatch:

- every applicable `AGENTS.md` from workspace root to the implementation area;
- `CONTEXT.md` when present;
- the complete ADR collection named by repository instructions;
- coding, testing, security, documentation, and Git/workflow conventions reached from those files;
- tracked contribution or architecture guidance that imposes implementation rules.

Copy the inventory into `<worktree>/.sdd-context/`, preserving source-relative names beneath the snapshot, and write a manifest containing canonical source path, snapshot path, and content hash. Include tracked and local-only guidance. Exclude secrets, `.env` values, credentials, generated output, and unrelated personal notes.

Ensure `.sdd-context/` is ignored before copying. It is read-only worker input. The coordinator verifies every hash when accepting worker output.

## Active worker packet

Inject only:

- full bodies and acceptance criteria of tickets assigned to the chunk;
- applicable PRD clauses, copied exactly enough to preserve constraints;
- ticket-specific ADR decisions and a pointer to the complete ADR inventory;
- direct-blocker outcomes and integrated SHAs;
- repository rules that change how this chunk is implemented or verified;
- `/tdd` rules for public seams and the red-green loop;
- `/codebase-design` vocabulary for interfaces, seams, adapters, depth, leverage, and locality;
- worktree, branch, base SHA, allowed operations, repository-prescribed setup, per-worktree baseline evidence and classification, any authorized red baseline with its owning ticket and quoted explicit owning requirement, focused verification commands, required deterministic validators for changed artifact types, and report path.

Do not inject sibling ticket bodies, unrelated PRD sections, raw parent conversation history, other workers' reports, or the complete feature diff.

The worker scans every ADR inventory entry for applicability before editing and reads every possibly applicable ADR in full. A highlighted decision is a navigation aid, not permission to ignore the rest.

## Deterministic validators

Discover validators from repository guidance, build scripts, schema tooling, and expected artifact formats before dispatch. A validator is required when the repository already prescribes it or an available parser/compiler can deterministically reject an invalid artifact. Record its exact command and artifact scope in the packet. Do not install a new dependency merely to create a validator without user approval.

The pre-dispatch inventory is provisional. After every implementation or repair turn, the coordinator reconciles actual changed paths and artifact types against it. Newly applicable validators become required ledger entries even when the worker packet did not predict them; send an immutable addendum if the worker needs the new command.

When the worker cannot execute a required command, it reports the exact denial. The coordinator runs that same command in the same worktree; changing the command invalidates prior evidence.

## Blocker handoff

For each direct completed blocker, provide:

- ticket ID and one-sentence delivered behavior;
- final integrated SHA;
- public interface or seam now available;
- ruling or caveat downstream work must preserve;
- verification command that proves the blocker remains intact when relevant.

Do not copy the blocker's full ticket or implementation transcript unless a precise requirement cannot be preserved otherwise.

## Reviewer packet

A chunk reviewer receives the worker packet plus the coordinator-captured base/head diff, commits, worker report, verification evidence, and chunk manifest. It does not receive unrelated chunks.

The final reviewer is the exception: it receives the full PRD, all tickets, final status map, rulings, and net integrated diff because cross-chunk consistency is its task.

## Freshness

A packet is immutable once its worker starts. When a source rule, PRD, ticket, blocker outcome, or integration base changes, invalidate the packet and build a new one. Record source hashes in the ledger so a resumed run can detect stale packets rather than trusting them.
