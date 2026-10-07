---
name: setup-skills
description: "Configure or migrate a target repository for these engineering skills: set up its issue tracker workflow, triage label vocabulary, and domain doc layout."
disable-model-invocation: true
triggers:
  - user
---

# Setup Skills

Configure the target repository after this skill collection has been installed. This workflow is not an installation mechanism.

Scaffold the per-repository configuration that the engineering skills assume:

- **Issue tracker**: where issues live and how implementation readiness, parent lookup, claiming, resolution, reconciliation, and frontier promotion work (GitHub by default; local markdown is also supported out of the box)
- **Triage labels**: the strings used for the five canonical triage roles
- **Domain docs**: where `GLOSSARY.md` (or the legacy `CONTEXT.md` name) and ADRs live, and the consumer rules for reading them

This is a prompt-driven skill, not a deterministic script. Explore, present what you found, confirm with the user, then write.

## Required implementation-workflow capabilities

This is the one canonical list of capabilities a complete `docs/agents/issue-tracker.md` defines. It is the union of what `/to-tickets`, `/implement`, and `/reconcile` require from the tracker. The exploration check and the post-write validation both use this list, so check every entry each time; never stop at the first gap.

- **Implementation-ready state**: the label or status that marks an open, unblocked, unclaimed implementation ticket as executable.
- **Planned/non-ready state**: the explicit state, or the explicit absence of the ready state, that every blocked or otherwise non-executable ticket has.
- **Direct parent or spec lookup**: how to follow a ticket to its governing parent or spec and read its approval.
- **Canonical blocker checks**: which blocker references are canonical (native dependencies or exact `Blocked by` references, and the fallback when native data is unavailable) and the rule that every blocker must be resolved.
- **Direct dependent discovery**: how to enumerate the resolved trigger's direct open downstream dependents through canonical dependency references, independently of ready markers or titles, with native data taking precedence over fallback text.
- **Affected reconciliation scopes**: how to resolve each dependent's own authority, select the trigger's normal scope and each valid dependent's scope, deduplicate those scopes, and confine readiness mutations to them without recursive dependency traversal. Retain the full trusted standalone set when that scope is selected; parent-only trackers never gain standalone authority. Preserve mapped non-agent triage states in every selected scope.
- **Claim and assignment semantics**: how a ticket is claimed or assigned so it leaves the frontier.
- **Resolution and resolved-state verification**: how a ticket is resolved, and how a later step verifies the resolved state before acting on it.
- **Deterministic child/sibling enumeration and ordering**: how to enumerate every implementation child or sibling of a parent, and the order to use.
- **Idempotent ready-state mutation**: how readiness is set or removed, changing only states that differ, so a rerun with unchanged tracker state makes no writes.
- **Frontier promotion**: when unblocked, unclaimed tickets are promoted to ready and blocked or claimed tickets are demoted.
- **`/reconcile` contract**: how `/reconcile <ticket-ref>` validates a resolved trigger and recomputes every independently validated affected frontier, reports authority failures, and makes no writes for an open trigger.

## Process

### 1. Explore

Look at the current repo to understand its starting state. Read whatever exists; don't assume:

- `git remote -v` and `.git/config`: is this a GitHub repo? Which one?
- Supported instruction files at the repository root, especially `AGENTS.md` and `CLAUDE.md`: which already exist, and does one already contain an `## Agent skills` section?
- `GLOSSARY.md` and `GLOSSARY-MAP.md` at the repo root, and the legacy `CONTEXT.md` and `CONTEXT-MAP.md` they replace (including per-context legacy files that a map points to)
- `docs/adr/` and any `src/*/docs/adr/` directories
- `docs/agents/`: does this skill's prior output already exist?
- `.scratch/`: a sign that a local-markdown issue tracker convention is already in use
- Is the `triage` skill installed? (a `triage` skill folder alongside this one, or `triage` in your available skills.) This decides whether Section B runs at all.
- Monorepo signals: a `pnpm-workspace.yaml`, a `workspaces` field in `package.json`, or a populated `packages/*` with its own `src/`. These are present only in a genuinely large multi-package repo; their absence means single-context, which is almost every repo.

When `docs/agents/issue-tracker.md` already exists, identify its tracker choice, custom state names, commands, fallbacks, and user-authored notes. Then check it against every entry in the required implementation-workflow capabilities above, not only the first gap you notice, and record the complete set of missing capabilities. Finally, classify its standalone authority mode, judged by what the file states in its own vocabulary:

- **Parent-only (current)**: the file states that standalone authority is unsupported, or that every implementation ticket has or requires a parent/spec. This is a complete, current contract. It needs no Agent Brief rule; never propose one for it.
- **Standalone-capable (current)**: the file defines the complete Agent Brief rule: completeness, trusted sources and their verification, precedence, and fail-closed parent handling.
- **Retired (stale)**: the file defines the retired record contract, recognizable by a required `## Standalone implementation authority` comment and its upstream approval values.
- **Incomplete (stale)**: the file claims standalone support for parentless tickets without the complete Agent Brief rule.
- **Undeclared (stale)**: the file states neither mode.
- **Ambiguous (stale)**: the file states both modes.

An older contract that refreshes only the trigger's normal scope is missing affected reconciliation scopes even if it already has a `/reconcile` paragraph. Direct dependent discovery and the expanded reconciliation contract must migrate together. Check native discovery and fallback precedence, each dependent's own approval or complete trusted Agent Brief, scope deduplication, held triage states in both branches, read versus mutation boundaries, direct-only traversal, deterministic frontiers, and idempotence. A dependency never supplies parent authority.

### 2. Present findings and ask

Summarise what's present and what's missing. Then take the sections in order. One section, one answer, then the next.

Lead each section with the recommended answer so the user can accept it in a word. Give a one-line explainer only when the choice genuinely branches; skip the section entirely when exploration already settled it (Section B when `triage` isn't installed, Section C when there's no monorepo).

**Section A: Issue tracker.**

> Explainer: The "issue tracker" is where issues live for this repo. Skills like `to-tickets`, `triage`, and `to-spec` read from and write to it. They need to know whether to call `gh issue create`, write a markdown file under `.scratch/`, or follow some other workflow you describe. Pick the place you actually track work for this repo.

Default posture: these skills were designed for GitHub. If a `git remote` points at GitHub, propose that. Otherwise (or if the user prefers), offer:

- **GitHub**: issues live in the repo's GitHub Issues (uses the `gh` CLI)
- **Local markdown**: issues live as files under `.scratch/<feature>/` in this repo (good for solo projects or repos without a remote)
- **Other** (Jira, Linear, etc.): ask the user to describe the workflow in one paragraph; the skill will record it as freeform prose

Record the choice in `docs/agents/issue-tracker.md`. The GitHub template carries a "PRs as a request surface" flag, defaulted **off**. Leave it off and don't raise it: a user who wants external PRs in the triage queue can flip the flag in the file later.

If an existing tracker file already makes the choice clear, treat this as a migration instead of configuration. Preserve the tracker choice and every customization, show additions for every missing capability and any standalone authority replacement, and do not ask the user to choose the tracker again.

**Section B: Triage label vocabulary.** Skip this section entirely if the `triage` skill isn't installed (exploration told you), since an uninstalled skill needs no labels.

If it is installed, ask exactly one question:

> Do you want to keep the default triage labels? (recommended: **yes**)

The defaults are the five canonical roles, each label string equal to its name: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. On **yes**, write them as-is. Only if the user says no, usually because their tracker already uses other names (e.g. `bug:triage` for `needs-triage`), collect the overrides so `triage` applies existing labels instead of creating duplicates.

**Section C: Domain docs.** Default to **single-context** (one `GLOSSARY.md` + `docs/adr/` at the repo root). This fits almost every repo; write it without asking.

Offer **multi-context** (a root `GLOSSARY-MAP.md` pointing to per-context `GLOSSARY.md` files) only when exploration found monorepo signals. Then confirm which layout they want.

**Glossary migration.** When exploration found a legacy `CONTEXT.md` or `CONTEXT-MAP.md`, offer a content-preserving rename to the matching `GLOSSARY` name, and wait for confirmation before touching anything. Do not create a parallel glossary, and do not use symlinks.

- Rename each legacy file in place with `git mv` (or a plain rename outside Git), keeping its content unchanged. For a `CONTEXT-MAP.md`, rename every per-context `CONTEXT.md` file it points to as well, then update only the file links inside the map so they name the renamed files.
- If a `GLOSSARY` file already exists beside its legacy twin, do not merge or overwrite either. Show both, report the duplicate, and let the user decide.
- Update every reference in the files this skill wrote (the `## Agent skills` block and `docs/agents/domain.md`) to the new names, leaving the rest of those files unchanged. Report other references to the legacy names that this skill did not write, such as prose in other docs, without editing them.
- If the user declines, change nothing. The skills still read the legacy files.

### 3. Confirm and edit

Show the user a draft of:

- The `## Agent skills` block to add to the selected existing instruction file, or to `AGENTS.md` when none exists (see step 4 for selection rules)
- The contents of `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, and `docs/agents/triage-labels.md` (the last only when `triage` is installed)
- Any glossary migration renames and reference updates, as a list of old and new paths

Let them edit before writing.

For a migration, show only the proposed changes to `docs/agents/issue-tracker.md` as a diff before any edit. One diff adds every missing capability from the exploration check. When the file defines the retired standalone record contract, the diff replaces only its standalone authority wording (the authority rule, the record and its verification text) and its `/reconcile` contract and standalone reconciliation wording with the Agent Brief equivalents from the matching seed template, adapted to the file's vocabulary. When its standalone authority is incomplete, the diff adds the missing Agent Brief wording from the matching seed template. When it is undeclared, the diff adds the matching seed template's standalone authority statement; for an Other tracker, ask the user whether parentless implementation tickets are supported first. When it is ambiguous, ask the user which mode applies, and the diff removes the other mode's wording. Do not re-propose configuration that already exists. When nothing is missing and the file already states a current standalone authority mode, parent-only or standalone-capable, report that it is already up to date and make no edits.

### 4. Write

**Pick the file to edit:**

- Preserve an existing supported instruction file. If exactly one of `AGENTS.md` or `CLAUDE.md` exists, edit that file.
- If both exist and one already contains the `## Agent skills` block, update that file.
- If both exist without the block, use `AGENTS.md` as the cross-harness default.
- If neither exists, create `AGENTS.md`.

Do not create or prefer `CLAUDE.md` merely because of historical harness behavior. Do not replace an existing supported instruction file with a new one.

In tracker migration mode, edit only `docs/agents/issue-tracker.md`, and only the missing implementation-workflow capabilities plus any stale standalone authority wording: the retired standalone record's authority and `/reconcile` wording, an incomplete Agent Brief rule, an undeclared mode, or the losing side of an ambiguous one. Leave the instruction file, domain configuration, triage labels, and every existing tracker customization unchanged unless the user separately asks to reconfigure them. A confirmed glossary migration (Section C) is such a request, limited to the renames and name updates it lists.

If an `## Agent skills` block already exists in the chosen file, update its contents in-place rather than appending a duplicate. Don't overwrite user edits to the surrounding sections.

The block:

```markdown
## Agent skills

### Issue tracker

[one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`.

### Triage labels

[one-line summary of the label vocabulary]. See `docs/agents/triage-labels.md`.

### Domain docs

[one-line summary of layout: "single-context" or "multi-context"]. See `docs/agents/domain.md`.
```

Include the `### Triage labels` sub-block, and write `docs/agents/triage-labels.md`, only when `triage` is installed and Section B ran. When it isn't, both are omitted.

Then write the docs files using the seed templates in this skill folder as a starting point:

- [issue-tracker-github.md](./issue-tracker-github.md): GitHub issue tracker
- [issue-tracker-local.md](./issue-tracker-local.md): local-markdown issue tracker
- [triage-labels.md](./triage-labels.md): label mapping (only if `triage` is installed)
- [domain.md](./domain.md): domain doc consumer rules + layout

For "other" issue trackers, write `docs/agents/issue-tracker.md` from scratch using the user's description.
Define every entry in the required implementation-workflow capabilities above. Also state its standalone authority mode: parent-only, or standalone-capable with the complete Agent Brief rule from the GitHub seed adapted to that tracker. Tracker-specific commands and state names belong in that file so `/implement` and `/reconcile` do not need tracker-specific branches.

For a migration, edit the existing tracker file in place. Add only missing implementation-workflow capabilities and replace or add only stale standalone authority wording, adapting both to its existing tracker choice and vocabulary. Preserve every existing customization and unrelated line; never replace the file with a seed template.

When direct dependent discovery or affected reconciliation scopes are missing, add their tracker-specific operations and update the existing `/reconcile` and resolution/frontier wording needed to use them in the same migration diff. Preserve commands, custom state names, fallback conventions, notes, and the configured authority mode. A parent-only tracker still rejects parentless dependents; do not add an Agent Brief rule or standalone support. Show this complete diff in step 3 before writing, then recheck every capability and the authority mode after the edit.

### 5. Validate

After writing `docs/agents/issue-tracker.md`, re-read the file from disk and validate it against every entry in the required implementation-workflow capabilities. Judge each capability by what the file defines in its own vocabulary, not by matching the seed template's wording.

Also classify its standalone authority mode again. A parent-only or standalone-capable mode is valid; a retired, incomplete, undeclared, or ambiguous mode is a remaining gap.

Validate the expanded reconciliation behavior as well as capability presence: direct-dependent discovery and the existing `/reconcile` contract must agree on native/fallback precedence, dependent authority, selected-scope boundaries, held states in both authority branches, and readiness-only idempotent mutations. A new discovery paragraph beside an unchanged trigger-only reconciliation contract is still incomplete.

If any capability is still missing, report the setup or migration as incomplete and name each remaining missing capability. Never report it as complete while a gap remains.

When the file was already up to date and no edit was made, the exploration check is this validation.

### 6. Done

Only after validation passes, tell the user the setup or migration is complete and which engineering skills will now read from these files. Mention they can edit `docs/agents/*.md` directly later; re-run this skill when a downstream skill reports that an older configuration is missing a required contract, or when they want to switch issue trackers or restart from scratch.
