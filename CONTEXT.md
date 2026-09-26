# Skills

A standalone collection of portable agent workflows. Stable skills live directly under `skills/`; optional experimental skills live under `skills/experimental/`. The `setup-skills` workflow configures a target repository for the shared issue-tracker, triage, and domain-document contracts after the collection has been installed.

## Language

**Issue tracker**:
The tool that hosts a repository's issues: GitHub Issues, Linear, a local `.scratch/` markdown convention, or similar. Skills such as `to-tickets`, `to-spec`, and `triage` read from and write to it.
_Avoid_: backlog manager, backlog backend, issue host

**Issue**:
A single tracked unit of work inside an **Issue tracker**: a bug, task, spec, or slice produced by `to-tickets`.
_Avoid_: ticket (use only when quoting external systems that call them tickets, or for a **Decision ticket**, below)

**Decision ticket**:
A `wayfinder` unit: a child **Issue** of a `wayfinder:map` holding a question whose resolution is a decision, not a slice of a build to execute. The **decision** qualifier keeps it distinct from an implementation ticket; `wayfinder` introduces the term, then uses "ticket."

**Triage role**:
A canonical state-machine label applied to an **Issue** during triage, such as `needs-triage` or `ready-for-agent`. Each role maps to a real label string in the **Issue tracker** through `docs/agents/triage-labels.md` in the configured target repository.

**Deep review**:
The strict PR-gate review workflow owned by the `deep-review` skill: parallel read-only scouts propose hypotheses and independent validators adjudicate them. Its own vocabulary (Hypothesis, Finding, Unresolved, review run, publication boundary, and so on) lives in that skill's glossary, not here.
_Avoid_: code review (that is the lighter `code-review` skill)

**Native reviewer agent**:
A harness-specific agent definition that a skill ships so the harness can launch a named role with its own model, tools, and sandbox. Only skills whose protocol requires distinct roles ship them.

## Relationships

- An **Issue tracker** holds many **Issues**.
- An **Issue** carries one **Triage role** at a time.
- A **Decision ticket** is an **Issue** and a child of a `wayfinder:map`.
