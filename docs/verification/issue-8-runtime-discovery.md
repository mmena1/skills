# Issue #8 runtime discovery check

## Deterministic check

On 2026-09-24, `python scripts/check.py` passed on Windows for all 28 stable skills. The canonical check exercises the Git Bash and PowerShell installers in isolated home directories. It verifies the shared Codex and Devin destination, Claude's personal destination, automatic and explicit selection, one shared installation under `--all` / `-All`, experimental selection, and removal of repository-managed legacy Devin entries while preserving unrelated content.

The test verifies files and links at the paths documented by each runtime. It does not launch the runtimes.

## Runtime discovery

Codex desktop exposed `evaluate-model` in this session, and its global entry is a junction to the canonical repository skill at `C:\code\skills\skills\evaluate-model`; its `SKILL.md` is present. Devin CLI was not available on this host.

On 2026-09-25, after rebasing onto `main`, Claude Code 2.1.283 was checked while signed in. All 28 entries in `~/.claude/skills` are junctions to the repository, and the unrelated `synced` folder there was left in place. A fresh print-mode session (`claude -p --output-format stream-json --verbose`) listed all 28 stable skills in its `init` event under both `skills` and `slash_commands`, so each one is reachable from the `/` menu. In a separate Claude Code session in this repository, only the 10 model-invoked skills were offered for automatic selection, and the 18 user-invoked skills were withheld as `disable-model-invocation: true` requires.

Both installers were also run with `--claude` / `-Claude` in isolated home directories that contained an unrelated `synced` folder and an existing `evaluate-model` directory. Each run installed 28 links, preserved the unrelated folder, backed up the existing directory once, did not add a backup on a second run, and did not create `~/.agents`. With only `~/.claude` present, automatic detection in both installers installed into `~/.claude/skills` alone.

Smallest remaining manual procedure for Devin CLI:

1. Run `./install.sh --devin` or `./install.ps1 -Devin` from this repository.
2. Start a fresh Devin CLI session.
3. Confirm that `evaluate-model` appears in Devin's available skills.

For Codex, confirm `evaluate-model` appears in the skill picker after installation. Codex documents `~/.agents/skills` as its global skill location and follows symlinked skill folders. Devin documents the same global location and supports the `.agents` skills standard. Claude Code documents `~/.claude/skills` as its personal skill location and follows symlinked skill folders.

References: [Codex local skills](https://learn.chatgpt.com/docs/build-skills), [Devin CLI skills](https://docs.devin.ai/cli/extensibility/skills/overview#where-skills-live), and [Claude Code skills](https://code.claude.com/docs/en/skills).
