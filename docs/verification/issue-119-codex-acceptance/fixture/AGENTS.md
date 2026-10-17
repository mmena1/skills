# Project instructions

Runtime: Python >=3.11 (`/tmp/skills-pr130-codex-20261017/runtime/bin/python3.11`).
Setup from the repository root, offline, into a project-local `.venv`:

    /tmp/skills-pr130-codex-20261017/runtime/bin/python3.11 -m venv .venv
    .venv/bin/python -m pip install --no-index --find-links vendor --require-hashes -r requirements.lock

`requirements.lock` is authoritative; do not edit it or the manifest. Run checks from the repository root
with `.venv/bin/python -B`. Public contract: `calculate(n)` doubles `n`, so `calculate(3) == 6`;
`label(n)` returns `"<n>"`.
