## What it does

`implement` takes one approved [ticket](https://www.aihero.dev/ai-coding-dictionary/ticket) or [spec](https://www.aihero.dev/ai-coding-dictionary/spec) from resolution through committed, reviewed implementation and tracker closeout. For a ticket, the ticket owns scope and acceptance criteria while its directly referenced approved parent owns architecture and public test seams.

The defining constraint is one worker, one ticket. It will make ordinary local implementation choices from existing patterns, but it stops instead of inventing a missing product decision, changing approved architecture, crossing an external gate, or pulling later tickets forward.

## When to reach for it

You invoke this by typing `/implement <issue-or-spec>`, and the agent will not reach for it on its own. An orchestrator can later dispatch the same explicit invocation to an isolated worker.

| The work is | Reach for |
| --- | --- |
| One open, unblocked, implementation-ready ticket | `/implement <ticket-ref>` |
| One small approved spec | `/implement <spec-ref>` |
| A larger approved spec | [to-tickets](https://aihero.dev/skills-to-tickets) first, then one `/implement` worker per ticket |
| An unresolved plan or architecture | [grill-with-docs](https://aihero.dev/skills-grill-with-docs), [to-spec](https://aihero.dev/skills-to-spec), and [design-review](https://aihero.dev/skills-design-review) first |
| A concrete behavior with no issue workflow | [tdd](https://aihero.dev/skills-tdd) directly |
| Existing committed work that only needs review | [code-review](https://aihero.dev/skills-code-review) directly |

## Prerequisites

Ticket-driven work needs `docs/agents/issue-tracker.md`, created by [setup-matt-pocock-skills](https://aihero.dev/skills-setup-matt-pocock-skills). That file names the ready state and the tracker-specific parent, blocker, claim, resolution, and frontier operations.

The worker also requires a clean starting worktree unless you explicitly approve the exact dirty state. It records the current `HEAD` SHA before editing and keeps that SHA as the review baseline for the entire run.

## Authority and stop conditions

The ticket is deliberately not the only document read. A fresh worker resolves the ticket, follows its direct parent or spec reference, then reads repository instructions, `CONTEXT.md`, and relevant ADRs. This gives it two distinct authorities:

| Source | Controls |
| --- | --- |
| Requested ticket | Delivery scope, acceptance criteria, blockers |
| Approved parent or spec | Architecture, settled decisions, public seams |
| Repository instructions and ADRs | Local engineering rules and prior hard-to-reverse decisions |

Routine private design choices do not trigger another planning round. A material contradiction between these authorities does. The worker leaves the ticket open and reports the exact conflict, impossible criterion, product decision, or external gate instead of guessing.

## Fixed-point closeout

The implementation is committed before review. That sequencing is essential because `code-review` examines `<baseline>...HEAD`; uncommitted work is absent from that diff.

`implement` explicitly composes `code-review` with the captured SHA and the source bundle. Both skills remain explicit-only, so this does not turn code review into a spontaneous background behavior. Blocking findings are fixed, verified, committed, and reviewed again from the same original baseline. Advisory smell findings do not create an endless cleanup loop.

Only after acceptance criteria, required verification, and review pass does the worker close the ticket and refresh the configured frontier. It never pushes, merges, or opens a pull request without separate authorization.

## Pre-agreed seams

A public seam written into the approved ticket or spec is already agreed for the nested [tdd](https://aihero.dev/skills-tdd) loop. The worker records it and starts red-green work without asking the user to approve the same seam again.

The user is asked only when implementation materially needs a new or changed public seam. This keeps `/tdd`'s confirmation rule intact while allowing an approved issue to run unattended.

## Common questions

**Why did it stop before claiming my ticket?**

Claiming is the first tracker write. The worker first proves that the issue is open, unblocked, in the configured ready state, and starts from a clean worktree. A failed gate is a stop unless you explicitly override it.

**Why did it stop after it had already committed code?**

Review can expose a contradiction that implementation did not make visible. In that case the existing commits are reported, the ticket stays open, and the worker does not turn a product or architecture decision into an improvised fix.

**Does it run typechecking and linting?**

It runs the targeted and full checks the repository or ticket actually configures. It does not install or introduce a typechecker, linter, test runner, or other tool just because a generic implementation checklist names one.

**Can several workers run in parallel?**

Yes, when an orchestrator gives each worker an isolated checkout or worktree and one frontier ticket. Several workers must not share one working directory, index, or `HEAD`.

**Can it open a pull request?**

Only after a separate instruction authorizes that external action. A normal run stops with local commits and an updated ticket.

## It's working if

- The worker names the ticket, approved parent, and exact starting SHA before editing.
- Claiming happens only after ready, blocker, and cleanliness checks pass.
- Tests use approved public seams without repeating a settled question.
- The first review sees committed changes in `<baseline>...HEAD`.
- Every blocking finding is followed by a fix commit and another review from the same baseline.
- Success leaves a clean worktree, a closed ticket, and a refreshed frontier, with no push, merge, or pull request.

## Where it fits

`implement` is the issue worker near the end of the main chain:

```txt
grill-with-docs -> to-spec -> design-review -> to-tickets -> implement -> code-review
```

[to-tickets](https://aihero.dev/skills-to-tickets) produces the bounded ticket and blocking edges; [tdd](https://aihero.dev/skills-tdd) drives behavior through approved seams; [code-review](https://aihero.dev/skills-code-review) checks the committed diff against standards and its originating sources. [ask-matt](https://aihero.dev/skills-ask-matt) routes the whole set.
