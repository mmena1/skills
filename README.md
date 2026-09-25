# skills

A personal-first collection of portable agent skills for deliberate software work. Each skill is a small workflow that keeps the human in control: the collection helps with framing, design, implementation, review, diagnosis, and communication without taking ownership of the whole development process.

The canonical behavior and detailed documentation for a skill live together in its `SKILL.md`. The workflows are written to be harness-agnostic. Small native metadata files are included only where a harness needs them to preserve invocation behavior or present the skill in its UI.

## Installation

Clone the repository, then run the installer for your platform:

```bash
git clone https://github.com/mmena1/skills.git
cd skills
./install.sh
```

```powershell
git clone https://github.com/mmena1/skills.git
Set-Location skills
./install.ps1
```

With no harness option, the installer detects configured Codex and Devin installations and installs all stable skills into their canonical locations:

- Codex: `~/.agents/skills/<skill>`
- Devin: `~/.config/devin/skills/<skill>`

Select a harness explicitly with `--codex`, `--devin`, or `--all` on Unix-like shells, and `-Codex`, `-Devin`, or `-All` in PowerShell. `all` means both supported harnesses. It does not include experimental skills.

Add `--experimental` or `-Experimental` to install the experimental collection as well. Harness selection and experimental selection are independent, so commands such as `./install.sh --codex --experimental` and `./install.ps1 -All -Experimental` are valid.

The installer uses symbolic links on Unix, macOS, and WSL where possible. Git Bash and native Windows PowerShell use directory junctions. If the environment cannot create a link safely, the installer copies the skill and warns that it must be rerun after repository updates. Existing unrelated destinations are backed up, not deleted.

## Updating

Linked and junctioned skills reflect repository edits immediately. After pulling changes, rerun the installer to add, remove, or refresh installed skills safely:

```bash
git pull
./install.sh
```

```powershell
git pull
./install.ps1
```

## Stable and experimental skills

Stable skills live directly under [`skills/`](./skills/). Experimental skills live under [`skills/experimental/`](./skills/experimental/) and are excluded from the default installation. The experimental collection starts empty; ideas that have not been deliberately adopted remain in Git history rather than in a current-tree graveyard.

## Skill catalog

User-invoked skills are not selected autonomously. A user may invoke them directly, and an already user-authorized workflow may explicitly compose a named user-only dependency when its documented contract requires that step. Model-invoked skills may also be selected automatically when a request matches their description.

### User-invoked

- [`code-review`](./skills/code-review/SKILL.md): Review a diff against repository standards and its originating issue or spec.
- [`design-review`](./skills/design-review/SKILL.md): Check a spec's proposed modules for shallow seams before ticket breakdown.
- [`evaluate-model`](./skills/evaluate-model/SKILL.md): Recommend a model, reasoning effort, and session boundary for an upcoming task, then stop.
- [`grill-me`](./skills/grill-me/SKILL.md): Sharpen a plan or design through a relentless interview.
- [`grill-with-docs`](./skills/grill-with-docs/SKILL.md): Grill a design while building its domain documentation.
- [`handoff-doc`](./skills/handoff-doc/SKILL.md): Compact a conversation into a portable handoff document.
- [`implement`](./skills/implement/SKILL.md): Implement one approved issue through verification, review, commit, and closeout.
- [`improve-codebase-architecture`](./skills/improve-codebase-architecture/SKILL.md): Find and explore opportunities to deepen codebase modules.
- [`reconcile`](./skills/reconcile/SKILL.md): Recompute an implementation frontier after a ticket resolves.
- [`setup-skills`](./skills/setup-skills/SKILL.md): Configure a target repository for the issue, triage, and domain-document workflows used by these skills.
- [`teach`](./skills/teach/SKILL.md): Teach a concept through a stateful workspace.
- [`to-questionnaire`](./skills/to-questionnaire/SKILL.md): Turn a decision gap into a questionnaire for the person who can resolve it.
- [`to-spec`](./skills/to-spec/SKILL.md): Turn the current conversation into a specification without repeating the interview.
- [`to-tickets`](./skills/to-tickets/SKILL.md): Break a plan into tracer-bullet tickets with explicit blocking edges.
- [`triage`](./skills/triage/SKILL.md): Move issues and external pull requests through explicit triage roles.
- [`wait-what`](./skills/wait-what/SKILL.md): Re-pitch the last answer with simpler language and missing context.
- [`wayfinder`](./skills/wayfinder/SKILL.md): Map a large effort as decision tickets and resolve the path incrementally.
- [`write-pr`](./skills/write-pr/SKILL.md): Prepare and open a repository-aware pull request.

### Model-invoked

- [`codebase-design`](./skills/codebase-design/SKILL.md): Shared vocabulary and discipline for deep-module design.
- [`diagnosing-bugs`](./skills/diagnosing-bugs/SKILL.md): A diagnosis loop for hard bugs and performance regressions.
- [`domain-modeling`](./skills/domain-modeling/SKILL.md): Build and sharpen project terminology, context documents, and ADRs.
- [`grilling`](./skills/grilling/SKILL.md): The reusable decision-tree interview discipline.
- [`prototype`](./skills/prototype/SKILL.md): Build throwaway code that answers a design question.
- [`research`](./skills/research/SKILL.md): Investigate a question against primary sources and capture cited findings.
- [`resolving-merge-conflicts`](./skills/resolving-merge-conflicts/SKILL.md): Resolve an in-progress merge or rebase by preserving intent.
- [`tdd`](./skills/tdd/SKILL.md): Test-driven development through a red-green-refactor loop.
- [`wizard`](./skills/wizard/SKILL.md): Generate an interactive shell wizard for steps only a human can perform.
- [`writing-for-agents`](./skills/writing-for-agents/SKILL.md): Write predictable skills and instruction documents for agents.

## Invocation verification

The catalog above records the reviewed classification of every stable skill. `SKILL.md` holds the Claude and Devin controls, while `agents/openai.yaml` holds Codex's invocation policy. `python scripts/check.py` checks the complete stable-skill roster and rejects missing or contradictory controls. Claude's `user-invocable: false` field hides reference-only skills from the slash menu and prevents a typed `/name` from running them, while keeping them available to the model. Claude Code 2.1.283 matched that behavior for `codebase-design`; see the [Issue #9 audit](./docs/agents/skill-invocation-audit-issue-9.md) for the trace. All other model-invoked skills remain directly invocable by the user.

After installing updated skills, use a fresh session in each available harness for a runtime smoke check:

1. Invoke `design-review` explicitly (`$design-review` in Codex, `/design-review` in Devin or Claude) without a spec reference. It should load and ask for an exact reference without changing a spec.
2. Ask for help diagnosing a reproducible bug without naming a skill. Check the invocation trace for automatic selection of `diagnosing-bugs`. In a separate turn, invoke it directly (`$diagnosing-bugs` in Codex or `/diagnosing-bugs` in Devin or Claude) on the same bug.
3. Ask for a design review without naming a skill. Check the invocation trace: `design-review` must not load automatically. In Claude, verify that `codebase-design` is absent from the slash menu and does not run when `/codebase-design` is typed, but can still be selected by the model for module-design work.

Prompt-based selection is probabilistic; the metadata check is the deterministic policy gate. Record the harness version, installed skill path, prompt, and invocation trace for runtime checks. If a harness is unavailable, retain these steps for its next installation. The controls follow [Codex](https://learn.chatgpt.com/docs/build-skills), [Devin CLI](https://docs.devin.ai/cli/extensibility/skills/overview), and [Claude Code](https://code.claude.com/docs/en/skills) documentation.

## Provenance and license

This repository originated as a fork of [`mattpocock/skills`](https://github.com/mattpocock/skills) and later diverged substantially into an independent collection. The original MIT copyright and permission notice are preserved in [`LICENSE`](./LICENSE); modifications and new work remain available under the same license.
