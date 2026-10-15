---
name: retro
description: Review a completed session for evidence-backed improvements to the environment around future agents.
disable-model-invocation: true
triggers:
  - user
---

# Retro

Turn friction in a coding session into a bounded set of concrete improvements to the environment around future agents. Use the current session unless the user names another session.

## Read the session

Use the conversation and available session artifacts, including tool results, failed checks, review exchanges, and user corrections. For a named session, use the harness's available read-only retrieval mechanism or a user-provided transcript. If the session is inaccessible, ask for an accessible transcript or excerpt. State material coverage gaps and base conclusions only on the evidence available.

Consider friction in each of these areas; they are a rubric, not a quota:

- Implementation problems.
- Review problems.
- Skill or protocol problems.
- Harness-specific behavior.
- Repository guardrails and deterministic checks.
- Information access and navigation.
- Tool and quota efficiency.
- Repeated no-ops or wasted work.

Look for the environment condition that made the friction likely, rather than simply proposing to fix the code produced in the session. Distinguish observed failures from inferred causes; state uncertainty when the evidence does not establish the cause. Merge candidates that address the same underlying problem.

## Propose improvements

Return at most seven candidates in chat, ranked by expected payoff from avoided recurrence, likely impact, and implementation cost. Return fewer, including none, when the session does not support more useful candidates. This is a short set of improvements, not a repository rewrite plan.

For each candidate, include:

- **Problem and evidence:** the concrete session event and its consequence, citing a turn, tool result, command/error, artifact path, or link that lets the user locate it. Do not invent evidence or repeat secrets from logs.
- **Fix location:** choose one primary home: repository code or configuration, skill instructions, reviewer guidance, harness setup, or documentation. Name the relevant file, tool, or setting when known.
- **Proposed change:** a bounded action that addresses the evidenced problem. Prefer a deterministic check for mechanical recurring failures. Put genuine judgment calls in reviewer or workflow guidance instead of pretending a mechanical rule can decide them.
- **Expected effect:** what future work would improve and why this change should help.

Choose the fix location from the cause: missing enforcement belongs in repository code or configuration; workflow decisions in skill instructions; review judgment in reviewer guidance; runtime or permission friction in harness setup; missing facts or navigation in documentation. A harness-specific candidate is valid, but use the target session's evidence and environment rather than assuming a particular harness, tracker, or repository layout.

## Boundaries

This skill examines the agent environment. It does not review the session's code for correctness or quality; that belongs to `implementation-review` or `deep-review`. It does not produce a continuity handoff; that belongs to `handoff-doc`. Naming these workflows does not invoke them.

Keep the retrospective read-only apart from separately approved tracker publication below. Do not implement candidates or modify repository code, configuration, skills, guidance, or harness setup during the retrospective. Recommendations do not authorize those changes.

## Publish only approved candidates

The default result stays in chat. Before publishing a candidate, read the target repository's configured issue-tracker workflow, present its exact proposed issue title and body and the destination, and obtain explicit approval for that candidate. Approval of one candidate does not authorize any other candidate. A general request for a retrospective does not authorize publication.

Use the configured tracker workflow to publish only the approved candidate and report its identifier or link. If the tracker configuration is missing or the destination is ambiguous, keep the proposal in chat and ask for the missing information before publication. Report a failed publication without claiming success or automatically creating a duplicate.
