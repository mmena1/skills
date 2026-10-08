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

Run the canonical repository check routinely, and always after changing skills, metadata, installers, or repository structure:

```text
python scripts/check.py
```

It is the fast check and finishes in seconds. It validates skill frontmatter and invocation metadata, stale internal references, the flat layout, the implementation authority contract, the tracker capability contract, native agent rendering and the rule that generated agents stay untracked, and deep-review invariants. It does not run the installers. It needs a Git checkout, because it verifies that generated agent files stay untracked and ignored.

Run the installer integration suite after changing `install.sh`, `install.ps1`, the installer tests, or native agent installation:

```text
python scripts/test_installers.py
```

It is slower, taking minutes on Windows. It runs `install.sh` through Bash on every platform and `install.ps1` through PowerShell on Windows, in isolated home directories, and checks harness selection, stable and experimental selection, links, junctions, copy fallback, reconciliation, unrelated-destination backup, native agent installation, and legacy deep-review migration.

CI runs both commands as separate jobs on Ubuntu and macOS.

A skill that ships native reviewer agents declares them in `harnesses/roles.toml` (see ADR-0001). That manifest and the reviewer bodies it embeds are the only committed source. The agent files under `harnesses/<harness>/` are generated, gitignored install artifacts: never commit or hand-edit them. The installers regenerate them, and `python scripts/generate_agents.py` regenerates them locally after you change a manifest or body.

Also run `git diff --check` before committing.

## Installation and updates

- `install.sh` is the Unix, macOS, WSL, and Git Bash entry point.
- `install.ps1` is the native Windows PowerShell entry point.
- Bare invocation detects supported configured harnesses and installs stable skills only.
- Harness selection and experimental selection are independent. `all` selects all supported harness destinations, not all stability tiers.
- Installers may replace only destinations they can recognize as managed by this repository. Back up unrelated existing destinations before installing. The one exception is migration from the former standalone `mmena1/deep-review` repository: installers also replace exactly the installations its installer wrote, recognized as the README describes, and reconciliation removes those under names this repository no longer installs.
- Codex native reviewer agents always use marked regular-file copies because Codex refuses symlinked role configuration files at launch. Rerun the installer after repository updates to regenerate and refresh them. For skills and other native agents, prefer symbolic links on Unix, macOS, and WSL. Use directory junctions for directories on Windows, including Git Bash. Claude Code single-file agents use Windows symbolic links when the account may create them. A copy fallback must warn that the installer needs to be rerun after repository updates.

After pulling repository changes, rerun the appropriate installer so new, removed, renamed, or copied skills are reconciled and native agents are regenerated. The installers need Python 3.11 or newer when a selected skill ships native agents, and fail before changing any destination when it is unavailable.

## Agent skills

### Issue tracker

Issues and specs live in this repository's GitHub Issues; use `gh` for tracker operations. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical triage roles with matching GitHub labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Use the single-context layout with root `GLOSSARY.md` and ADRs in `docs/adr/`. See `docs/agents/domain.md`.
