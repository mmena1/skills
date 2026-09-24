# Issue #8 runtime discovery check

## Deterministic check

On 2026-09-24, `python scripts/check.py` passed on Windows for all 28 stable skills. The canonical check exercises the Git Bash and PowerShell installers in isolated home directories. It verifies the shared Codex and Devin destination, Claude's personal destination, automatic and explicit selection, one shared installation under `--all` / `-All`, experimental selection, and removal of repository-managed legacy Devin entries while preserving unrelated content.

The test verifies files and links at the paths documented by each runtime. It does not launch the runtimes.

## Runtime discovery

Codex desktop exposed `evaluate-model` in this session, and its global entry is a junction to the canonical repository skill at `C:\code\skills\skills\evaluate-model`; its `SKILL.md` is present. Devin CLI and Claude Code executables were not available on this host, so their runtime discovery was not observed.

Smallest manual procedure for Devin CLI and Claude Code:

1. Run `./install.sh --all` or `./install.ps1 -All` from this repository.
2. Start a fresh Devin CLI session and a fresh Claude Code session.
3. Confirm that `evaluate-model` appears in Devin's available skills and Claude Code's `/` skill menu.

For Codex, confirm `evaluate-model` appears in the skill picker after installation. Codex documents `~/.agents/skills` as its global skill location and follows symlinked skill folders. Devin documents the same global location and supports the `.agents` skills standard. Claude Code documents `~/.claude/skills` as its personal skill location and follows symlinked skill folders.

References: [Codex local skills](https://learn.chatgpt.com/docs/build-skills), [Devin CLI skills](https://docs.devin.ai/cli/extensibility/skills/overview#where-skills-live), and [Claude Code skills](https://code.claude.com/docs/en/skills).
