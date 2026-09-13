# Chunking

A **ticket** is an acceptance and commit boundary. A **chunk** is an execution boundary: one fresh worker, one worktree, and one combined review over one or more tickets.

## Build the ticket graph

Parse blocker fields from current ticket content. Numbering is only a stable tie-breaker. Validate every blocker, reject cycles, and treat only verified completed tickets as satisfied.

Annotate each remaining ticket from its behavior, acceptance criteria, PRD constraints, and a lightweight codebase exploration:

- **Foundation** — behavior-preserving setup or prefactoring that enables later work.
- **Implementation** — user-visible behavior or an internal behavior required by it.
- **Migration** — one batch in an expand–migrate–contract sequence.
- **Convergence** — deletion, contraction, final verification, or cleanup after several branches meet.
- **Docs-only** — prose or local planning material with no executable surface.

Also record architectural seam, domain area, uncertainty, likely reasoning/debugging load, and rough reviewable churn. Estimates are guidance, not promises.

## Pack topologically

Produce a stable topological order. Among currently eligible tickets prefer, in order:

1. continuation through the same architectural boundary or public seam;
2. direct dependency continuation;
3. the same behavior, domain, and test seam;
4. similar reasoning and debugging load;
5. similar estimated changed lines;
6. original ticket order.

Pack contiguous, semantically cohesive portions of that order. Derive chunk blockers from the exact cross-chunk ticket edges, then validate the contracted chunk graph is acyclic.

Never combine unrelated work to fill a size target. Prefer a 100-line coherent chunk to a 700-line grab bag.

## Preserve frontier exposure

Grouping creates a barrier: external dependents cannot start until the whole chunk is reviewed and integrated.

- Fold small foundation work into its sole dependent when the chain is linear and shares a seam.
- Make shared, high-fan-out, or ownership-changing foundation work a separate foundation chunk, grouping related setup tickets where possible.
- Do not cross expand, migrate, and contract boundaries.
- Group migration batches by package or architectural affinity without hiding the final convergence edge.
- Keep convergence work separate when it depends on several parallel chunks.

Architectural boundaries outrank balancing. The operating guide is roughly 500–1500 reviewable changed lines, not a cap.

## Adapt at ticket boundaries

Give each worker an ordered candidate bundle. After every green ticket commit, compute:

- **Raw churn** — additions plus deletions.
- **Reviewable churn** — raw churn excluding generated files, lockfiles, snapshots, vendored output, and verified pure moves.

The worker returns one decision:

- `CONTINUE` — the next ticket remains cohesive and enough reasoning capacity remains.
- `SEAL_CHUNK` — review this chunk now and return the unstarted suffix.

The decision considers exploration cost, number of relevant files and seams, failed-test/debugging loops, review repair, and approximate churn. LOC is only an alert. Keep a cohesive architectural unit intact when splitting would create a broken seam or artificial handoff; finish at the next green ticket or behavioral boundary and record the overrun.

A ticket too large for one fresh worker is a ticket defect. Stop at a green behavioral boundary, preserve the work, and mark the unimplemented remainder `needs-info` for splitting. Never leave half an acceptance criterion as a nominally completed ticket.

## Closeout path

A ticket is docs-only only when all are true:

- no production code, tests, executable schema, configuration, generated API surface, or build behavior changes;
- every behavioral blocker is integrated;
- verification is limited to documentation conventions, links, formatting, examples, and factual comparison with settled behavior.

Group terminal docs-only tickets into one closeout chunk. Run one fresh worker against the integration worktree, one commit per ticket. Documentation syntax, schema, link, or build validators remain required, with coordinator fallback for worker-blocked commands. Skip TDD and a dedicated chunk review; the final whole-feature Standards and Spec review covers it.

A cleanup label never makes work docs-only. Deleting methods, contracting migrations, trimming tests, changing configuration, or running behavioral convergence remains normal implementation.

## Single-ticket mode

A focused ticket is one chunk. Run it only when all blockers are verified complete. Do not silently pull in ancestors or siblings.
