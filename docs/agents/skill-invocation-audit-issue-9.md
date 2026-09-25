# Issue #9 invocation audit

All 28 stable skills were reviewed against their individual purpose: 18 are user-invoked and 10 are model-invoked. The [catalog](../../README.md#skill-catalog) names each skill in its group. `scripts/check.py` now treats those groups as a reviewed roster, so adding a stable skill requires an explicit classification.

## Deterministic policy results

| Harness | User-only example: `design-review` | Model-invoked example: `diagnosing-bugs` | Reference example: `codebase-design` |
| --- | --- | --- | --- |
| Codex | `policy.allow_implicit_invocation: false`; explicit use remains available | Policy omitted, so implicit selection and explicit use remain available | Policy omitted; explicit use remains available |
| Devin CLI | `triggers: [user]` | `triggers: [user, model]` | `triggers: [user, model]` |
| Claude Code | `disable-model-invocation: true` | Model invocation enabled by omission; explicit use remains available | `user-invocable: false` hides the slash command while model invocation remains enabled |

The canonical checker passed for all 28 skills. Mutation checks rejected a missing or extra Devin trigger, a contradictory Codex policy, a user-only Claude toggle, a missing model trigger, and incorrect Claude slash visibility. A separate red-green check first showed that moving Codex's `allow_implicit_invocation: false` from `policy` into `interface` passed the old checker; the updated checker rejects that move. Representative installed Codex junctions for `design-review` and `codebase-design` point to this checkout, and their `SKILL.md` hashes match the source.

These are metadata and installation results. In the current Codex task, the user explicitly invoked the user-only `implement` skill, and the available-skill catalog exposes `diagnosing-bugs` and `codebase-design` as model-invoked skills while omitting `design-review` from automatic discovery. Live prompt selection remains a runtime smoke check: Codex CLI 0.155.0-alpha.16.4 is installed, Claude Code 2.1.282 is installed but has no active session authentication, and Devin CLI is unavailable here. No separate model-driven invocation trace was produced for the three examples. Use the [manual procedure](../../README.md#invocation-verification) in a fresh session with each available harness and record its invocation trace. A single prompt can demonstrate routing, but it cannot prove probabilistic selection will always occur.

The field placement and defaults follow the [Codex](https://learn.chatgpt.com/docs/build-skills), [Devin CLI](https://docs.devin.ai/cli/extensibility/skills/overview), and [Claude Code](https://code.claude.com/docs/en/skills) references. Claude documents that it ignores unrecognized frontmatter fields; Devin documents the shared `.agents` skill layout. Runtime parser acceptance in Devin still needs the manual check because its CLI is unavailable in this environment.
