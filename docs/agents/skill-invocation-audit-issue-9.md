# Issue #9 invocation audit

All 28 stable skills were reviewed against their individual purpose: 18 are user-invoked and 10 are model-invoked. The [catalog](../../README.md#skill-catalog) names each skill in its group. `scripts/check.py` now treats those groups as a reviewed roster, so adding a stable skill requires an explicit classification.

## Deterministic policy results

| Harness | User-only example: `design-review` | Model-invoked example: `diagnosing-bugs` |
| --- | --- | --- |
| Codex | `policy.allow_implicit_invocation: false`; explicit use remains available | Policy omitted, so implicit selection and explicit use remain available |
| Devin CLI | `triggers: [user]` | `triggers` omitted; Devin's default enables both `user` and `model` |
| Claude Code | `disable-model-invocation: true` | Model invocation enabled by omission; explicit use remains available |

Model-invoked skills originally declared `triggers: [user, model]`, and `codebase-design` and `writing-for-agents` set Claude's `user-invocable: false` as reference-only skills. A follow-up removed both. The explicit Devin triggers matched Devin's documented default, so they were redundant. Hiding the two reference skills from direct invocation was judged unnecessary, so all 10 model-invoked skills are now directly invocable in every harness. The checker now requires model-invoked skills to omit `triggers` and rejects `user-invocable` on any stable skill.

The canonical checker passed for all 28 skills. Mutation checks rejected a missing or extra Devin trigger, a contradictory Codex policy, a user-only Claude toggle, a missing model trigger, and incorrect Claude slash visibility. A separate red-green check first showed that moving Codex's `allow_implicit_invocation: false` from `policy` into `interface` passed the old checker; the updated checker rejects that move. Representative installed Codex junctions for `design-review` and `codebase-design` point to this checkout, and their `SKILL.md` hashes match the source.

These are metadata and installation results. In the current Codex task, the user explicitly invoked the user-only `implement` skill, and the available-skill catalog exposes `diagnosing-bugs` and `codebase-design` as model-invoked skills while omitting `design-review` from automatic discovery. A partial Claude Code runtime smoke was run on 2026-09-25 with Claude Code 2.1.282. The installed skills under `~/.claude/skills` are junctions to this checkout, and the `SKILL.md` hashes for `design-review`, `diagnosing-bugs`, `codebase-design`, and `writing-for-agents` match their sources.

| Prompt | Observed Claude Code trace |
| --- | --- |
| `/design-review` with no spec reference | Loaded `design-review` and asked for an exact issue, URL, or local path. No spec was changed. |
| `Without naming any skill, diagnose this reproducible bug...` followed by the minimal `total_positive` example | No `diagnosing-bugs` invocation appeared in the session trace; Claude answered directly. |
| `/diagnosing-bugs` on the same example | Explicit invocation started the diagnosis workflow. It proposed a throwaway repro harness; the run was interrupted and its temp file removed. No repository files changed. |
| `I am designing a new shared library for skill metadata validation...` | Automatically loaded `codebase-design`. |
| `I have a spec ... review the proposed modules for shallow seams...` | Automatically loaded `codebase-design`; `design-review` did not load. |
| Typed `/codebase-design` in the interactive `/` command menu (2.1.282) | The autocomplete suggested `codebase-design` even though its frontmatter has `user-invocable: false`. This did not reproduce in the 2.1.283 recheck below. |

A headless recheck was run on 2026-09-25 with Claude Code 2.1.283 from a scratch directory outside the repository, using `claude -p "/<skill>" --output-format stream-json --verbose --permission-mode plan`. The Claude Code desktop session on the same installation was also inspected.

| Check | Observed Claude Code 2.1.283 trace |
| --- | --- |
| Session `init` event | `slash_commands` and `skills` list all 18 user-invoked skills and the 8 directly invocable model-invoked skills. `codebase-design` and `writing-for-agents` are absent. |
| `/design-review` with no spec reference | Loaded `design-review` and asked for an issue number, issue URL, or local spec path. No files changed. |
| `/codebase-design` | The command did not run: zero turns, no model request, and an empty result. This matches the documented `user-invocable: false` behavior. |
| Model-visible skill listing in a desktop session | Lists exactly the 10 model-invoked skills, including `codebase-design` and `writing-for-agents`. None of the 18 user-invoked skills appear, including `design-review`. |

Both Claude trace tables were recorded while `codebase-design` and `writing-for-agents` still set `user-invocable: false`. After the follow-up removal, `/codebase-design` is expected to run like any other model-invoked skill. The 2.1.283 results matched the Claude Code controls in place at the time. The interactive `/` menu was not rechecked on 2.1.283, so the 2.1.282 autocomplete observation remains unexplained but is no longer reproduced. Claude automatic selection is demonstrated for `codebase-design` but not for `diagnosing-bugs`.

The Devin runtime prompt smoke was skipped at the user's direction, and the CLI installed for setup was removed. Codex has not had a separate fresh-session routing trace. The cross-harness criterion therefore remains incomplete. Use the [manual procedure](../../README.md#invocation-verification) in each available harness and record its invocation trace. A single prompt can demonstrate routing, but it cannot prove probabilistic selection will always occur.

The field placement and defaults follow the [Codex](https://learn.chatgpt.com/docs/build-skills), [Devin CLI](https://docs.devin.ai/cli/extensibility/skills/overview), and [Claude Code](https://code.claude.com/docs/en/skills) references. Claude documents that it ignores unrecognized frontmatter fields; Devin documents the shared `.agents` skill layout. Devin parser acceptance and the cross-harness runtime criterion still need the manual check.
