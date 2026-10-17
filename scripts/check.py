#!/usr/bin/env python3
"""Canonical fast repository validation. Installer tests live in test_installers.py.

`main` runs every validation group explicitly, in the order that decides which failure
is reported first. Each group lives in the module that owns its responsibility; see
scripts/repo_checks/README.md.
"""

from __future__ import annotations

import sys

from repo_checks.common import CheckFailure
from repo_checks.layout import validate_layout_and_skills
from repo_checks.native_agents import validate_generated_agents_untracked, validate_native_agents
from repo_checks.references import validate_repository_references
from repo_checks.scenarios.agent_generation import validate_agent_generation_contract, validate_deep_review_generation
from repo_checks.scenarios.deep_review import validate_deep_review
from repo_checks.scenarios.implementation import (
    validate_branch_satisfied_blockers, validate_implementation_review_routing_contract,
    validate_implementation_working_copy_contract,
)
from repo_checks.scenarios.portfolio_sync import validate_portfolio_sync
from repo_checks.scenarios.pr_handoff import validate_multi_ticket_pr_contract, validate_pr_ticket_plan
from repo_checks.scenarios.reconciliation import validate_reconciliation, validate_reconciliation_contract
from repo_checks.scenarios.tracker import (
    validate_implementation_authority_contract, validate_standalone_authority_modes,
    validate_tracker_capability_contract,
)
from repo_checks.scenarios.wizard import validate_wizard


def main() -> int:
    try:
        skill_names = validate_layout_and_skills()
        validate_repository_references()
        validate_implementation_authority_contract()
        validate_implementation_review_routing_contract()
        validate_implementation_working_copy_contract()
        validate_standalone_authority_modes()
        validate_tracker_capability_contract()
        validate_reconciliation()
        validate_reconciliation_contract()
        validate_pr_ticket_plan()
        validate_multi_ticket_pr_contract()
        validate_branch_satisfied_blockers()
        validate_native_agents()
        validate_generated_agents_untracked()
        validate_deep_review()
        validate_deep_review_generation()
        validate_agent_generation_contract()
        validate_portfolio_sync()
        validate_wizard()
    except CheckFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Repository checks passed for {len(skill_names)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
