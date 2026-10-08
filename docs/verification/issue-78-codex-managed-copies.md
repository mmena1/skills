# Issue #78 Codex managed-copy verification

Authority: the [latest trusted Agent Brief](https://github.com/mmena1/skills/issues/78#issuecomment-6070992320). Baseline: `3e9ea4d725f61eaa97264f36d7bf625a68fa3ec3`. Verified on 2026-10-08.

## Native Codex smoke

CLI: `codex-cli 0.160.0`, `/home/martin/.local/bin/codex`. Runtime: Linux x86_64 on WSL2, kernel `6.18.33.2-microsoft-standard-WSL2`. This is Linux CLI evidence, not Windows-native Codex evidence.

Two installations used distinct isolated `HOME` values and matching `CODEX_HOME=$HOME/.codex`: one default `bash install.sh --codex`, one with `SKILLS_INSTALLER_FORCE_COPY=1`. All seven installed role files were regular files, byte-identical to their generated sources, with managed markers naming those sources. The default installer printed no link-failure warning. Forced-copy warnings applied to skill directory fallbacks; intentional Codex agent copies printed none.

Each installation ran `codex exec --json --color never --skip-git-repo-check -C <isolated-workspace> -o <final.md> -` with the recorded prompt. The coordinator preserved the user's model `gpt-6.1-sol` and effort `high`. It discovered all seven native types and launched each once by exact `agent_type`, using `fork_turns=none` and no model or effort overrides. The child message requested only READY and prohibited tools and review work. All fourteen child sessions completed with READY. Both CLI runs exited 0, with zero `failed to apply role to config` warnings.

The tables below come from child `session_meta` and `turn_context` records, with READY verified from each child's `task_complete` event. Model and effort claims are runtime records, not static configuration or agent self-reports.

### default

Parent session: `01a11ddf-27da-7d31-8e41-a28d1e97b471`.

| Native role | Child session | Recorded model | Effort | Reply |
|---|---|---|---|---|
| `deep-review-scout-bugs` | `01a11ddf-3e72-7b30-88da-b870697d8f62` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-scout-conventions` | `01a11ddf-4695-79a3-9086-a93d8c2ced54` | `gpt-6-luna` | `high` | READY |
| `deep-review-scout-history` | `01a11ddf-4f3c-7dd0-b24e-083f91d1a56d` | `gpt-6-luna` | `high` | READY |
| `deep-review-scout-docs` | `01a11ddf-5841-73c0-a75f-cb1b920898fd` | `gpt-6-luna` | `high` | READY |
| `deep-review-structural` | `01a11ddf-60b5-7db1-ac9a-28b1e1d20920` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-validator-static` | `01a11ddf-6c26-7690-8eb2-d7915904de7b` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-validator-probe` | `01a11ddf-961c-7280-bc11-977fa34a2a20` | `gpt-6-luna` | `high` | READY |

### force-copy

Parent session: `01a11ddf-c679-76a2-bb99-9a1cc1631d53`.

| Native role | Child session | Recorded model | Effort | Reply |
|---|---|---|---|---|
| `deep-review-scout-bugs` | `01a11ddf-dc98-7513-8681-29119c4b70e2` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-scout-conventions` | `01a11ddf-e5ce-72d3-9593-0163936bb563` | `gpt-6-luna` | `high` | READY |
| `deep-review-scout-history` | `01a11ddf-eeab-7472-81eb-7a1626657245` | `gpt-6-luna` | `high` | READY |
| `deep-review-scout-docs` | `01a11ddf-f99a-75c1-8f3a-bb150cc00196` | `gpt-6-luna` | `high` | READY |
| `deep-review-structural` | `01a11de0-0172-7ad1-b8e6-61395583fb20` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-validator-static` | `01a11de0-09d8-7830-b953-4a0476e36122` | `gpt-6.1-sol` | `high` | READY |
| `deep-review-validator-probe` | `01a11de0-5a6d-72b3-8673-f4c54d6affae` | `gpt-6-luna` | `high` | READY |

## Evidence and limits

Raw commands, prompt, installer output, CLI events and stderr, parent and child rollouts, `metadata.json`, `runtime-summary.json`, normal-configuration snapshots, and `SHA256SUMS` are retained locally under `/home/martin/.codex/2026-10-08-issue-78-wvaet8pc/`. Copied authentication files were removed after both runs. `normal-before.json` and `normal-after.json` match, covering the usual Linux and Windows Codex configurations and installed agent contents and link targets.

The CLI exposed no close-agent tool. Completed children allowed the final role to launch; the forced-copy coordinator additionally interrupted completed children. This smoke verifies native role loading, session creation, pinned model and effort, and readiness only. It does not rerun the broader issue #71 review matrix or establish sandbox enforcement.

Tested installer bytes:

- `install.sh`: `f5c2c66392272917c5931ec8671d0a8969375ca57cbc29b360a3d39e29166d13`
- `install.ps1`: `0257a4bdd86c784c738864b5795db003cd3fa5028b6cb2beeae76a2fa88795ee`

## Installer checks and platform coverage

- Linux/WSL2: `python3 scripts/check.py`, `python3 scripts/test_installers.py`, and `git diff --check` passed. The integration suite exercises Bash, all harnesses, Codex copy and managed-link upgrade assertions, copy refresh, idempotency, retirement with marker removal, unrelated-content backup and preservation, and legacy deep-review migration.
- Windows 11 (`Windows-11-10.0.26200-SP0`): the full `python.exe scripts/test_installers.py` suite passed with native Python 3.14.7, Git Bash 5.3.15 (`x86_64-pc-cygwin`, `C:\Program Files\Git\bin\bash.exe`), and Windows PowerShell 5.1.26100.9444. Both installer entry points were exercised in isolated test homes. The separate native PowerShell Codex copy, managed-link upgrade, no-warning, refresh, idempotency, and unrelated-content probe also passed.
- The Windows runner restored the normal machine/user PATH and machine PATHEXT for its process and set `SKILLS_INSTALLER_PYTHON` to the native Python executable. This was necessary because the original WSL-launched native process inherited Linux environment values. No system environment settings were changed. The successful command wrapper and log are `/mnt/c/Users/marti/AppData/Local/Temp/skills-issue78-windows-i40wwkxf/native-suite.ps1` and `/mnt/c/Users/marti/AppData/Local/Temp/skills-issue78-windows-i40wwkxf/native-integration.log`; `native-verification.json` records versions and installer hashes.
- Windows file-symlink creation was unavailable (`Administrator privilege required for this operation.`). The existing suite uses hard links for Windows file-link fixtures, including the added upgrade test; Unix fixtures use symbolic links. A Windows account permitted to create file symlinks, and an actual Windows symbolic-link upgrade, were not exercised. The copy-only branch is independent of link privileges.
- macOS: not exercised locally. The shared Bash test cases are available to the existing macOS CI job.
- Windows-native Codex runtime: not exercised. The native launch results above use the Linux binary under WSL2.
