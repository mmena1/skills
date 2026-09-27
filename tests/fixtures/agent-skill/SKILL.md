---
name: agent-skill
description: Test fixture that ships native reviewer agents. It is not installed as part of the collection.
---

# Agent skill fixture

This fixture proves the native reviewer agent capability. `python scripts/check.py` regenerates its agent files and compares them with the committed copies. `python scripts/test_installers.py` installs it in isolated home directories to exercise both installers.

Roles are declared in `harnesses/roles.toml`. Each generated agent is named `agent-skill-<role>` on every harness.
