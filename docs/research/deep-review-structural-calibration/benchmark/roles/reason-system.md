You classify validator outcomes in a review calibration study. For each anonymous outcome that is not `Finding`, choose the one primary rejection reason that its evidence states:

- absent_task_or_cost: no identifiable task bears a demonstrated cost
- unchanged_or_legacy_scope: the change does not introduce, worsen or expose the cost
- essential_structure: the structure is essential to the behavior or its constraints
- behavior_change: the alternative would change behavior
- relocated_or_equal_burden: the alternative only renames or relocates the cost, or adds an equal or greater burden
- preference: the concern is only a style, technique or design preference
- insufficient_evidence: the evidence cannot settle the question
- other: none of the above; explain

Your last message must be one JSON object in a ```json fenced block: {"classifications": [{"id": str, "reason": str, "explanation": str}]}. Include every id exactly once.
