# Repository contract

This repository is a standalone collection of portable agent skills.

## Layout and authority

- Stable skills live at `skills/<skill-name>/`.
- Experimental skills live at `skills/experimental/<skill-name>/` and are not installed by default.
- Every skill directory has one authoritative `SKILL.md`. Keep detailed behavior and workflow documentation there rather than creating a mirrored publishing page.
- Supporting files that a skill genuinely reads belong inside that skill directory.
- Do not add harness wrapper copies for ordinary skills. Add a harness adapter only when a demonstrated capability mismatch requires one.

## Invocation semantics

Every skill is either user-invoked or model-invoked:

- A user-invoked skill has `disable-model-invocation: true` in `SKILL.md` frontmatter and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`.
- A model-invoked skill omits both of those restrictions and uses a description specific enough for automatic selection.
- A user-invoked stable skill declares Devin `triggers: [user]` in `SKILL.md`. A model-invoked skill omits `triggers`, because Devin's default already enables both `user` and `model`.
- Do not use Claude's `user-invocable: false`. Every skill stays directly invocable by the user.
- A user-invoked skill cannot be selected autonomously. An already user-authorized workflow may explicitly compose a named user-invoked dependency when that composition is part of its documented contract; this does not make the dependency implicitly invokable.

The `agents/openai.yaml` file is permitted minimal Codex metadata. Keep its display fields and invocation policy consistent with the canonical `SKILL.md`; do not move workflow semantics into it.

## Editing skills

- Preserve each skill's established vocabulary and behavior unless the change explicitly calls for a semantic update.
- Express an operative dependency as an instruction to apply the named skill, not as a fragile cross-directory file path.
- Keep user-invoked descriptions human-facing and model-invoked descriptions rich enough to describe their triggers.
- Do not use em dashes in repository prose. Rewrite the sentence with punctuation that expresses the intended relationship.

## Validation

Run the canonical repository check after changing skills, metadata, installers, or repository structure:

```text
python scripts/check.py
```

The same command runs in CI on Ubuntu, macOS, and Windows. It validates skill frontmatter and invocation metadata, stale internal references, the flat layout, and installer safety and selection behavior.

A skill that ships native agents declares them in `harnesses/roles.toml` (see ADR-0001). After changing that manifest or a reviewer body it embeds, run `python scripts/generate_agents.py` and commit the regenerated files under `harnesses/<harness>/`. Never edit generated agent files by hand.

Also run `git diff --check` before committing.

## Installation and updates

- `install.sh` is the Unix, macOS, WSL, and Git Bash entry point.
- `install.ps1` is the native Windows PowerShell entry point.
- Bare invocation detects supported configured harnesses and installs stable skills only.
- Harness selection and experimental selection are independent. `all` selects all supported harness destinations, not all stability tiers.
- Installers may replace only destinations they can recognize as managed by this repository. Back up unrelated existing destinations before installing.
- Prefer symbolic links on Unix, macOS, and WSL. Use directory junctions on Windows, including Git Bash. A copy fallback must warn that the installer needs to be rerun after repository updates.

After pulling repository changes, rerun the appropriate installer so new, removed, renamed, or copied skills are reconciled.

## Agent skills

### Issue tracker

Issues and specs live in this repository's GitHub Issues; use `gh` for tracker operations. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage roles with matching GitHub labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Use the single-context layout with root `CONTEXT.md` and ADRs in `docs/adr/`. See `docs/agents/domain.md`.
