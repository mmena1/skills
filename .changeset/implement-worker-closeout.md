---
"mattpocock-skills": minor
---

Make `implement` a self-contained issue worker: resolve the approved parent, enforce readiness and clean-start gates, capture a fixed review baseline, commit before review, fix blocking findings, and close the ticket through the configured tracker workflow.

Keep `code-review` explicit-only while allowing `implement` to compose its workflow directly, and extend issue-tracker templates with the lifecycle mechanics the worker needs.
