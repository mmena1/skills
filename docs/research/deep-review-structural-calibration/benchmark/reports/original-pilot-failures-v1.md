# Issue 89 original pilot failures, offline report v1

**EXPLORATORY retrospective.** This report describes retained original failure receipts. It does not rescore either pilot, rewrite any result, establish recall, or replace the original FAIL gates.

## Reproduction and integrity

Input archive is retained on the operator host at `/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/takeover-snapshot-b481487ca52ce86f/preexisting-evidence.tar.gz` (SHA-256 `82d329db655a752c0a8fb8a779f390d9cbfb053a7789f5814eb27f92d5cabf51`). The reproducer checks this archive hash before extraction and checks the individual original gate receipt hashes. Absolute session paths printed inside gate details are historical strings only; the reproducer never follows them. All inspected files come from the immutable archive. Run it with:

```bash
python3 /path/to/reproduce_pilot_failures.py --snapshot /path/to/preexisting-evidence.tar.gz --output original-pilot-failures-v1.md
```

Pilot 1 gate SHA-256: `470a7b01fa7e31dda2bdb00dbbef3288bf36e550568f29ddff706a07776970ec`. Pilot 2 gate SHA-256: `657affb52c44809c81fc80c0de2a7cd3e23269c8130dbde53a3c4faf19c20eb7`. Original files are read from archive members and are not modified.

## Pilot 1

Original verdict: **FAIL**, recorded at `2026-10-10T12:29:20.115616+00:00`. The original gate failed these checks:

- `no-leakage`: ["/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/attempts/adjudication-attempt1/label-S05-2/attempt-1", "/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/attempts/adjudication-attempt1/label-S12-1/attempt-1", "/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/attempts/adjudication-attempt1/label-S12-1/attempt-2", "/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/attempts/adjudication-attempt1/label-S12-2/attempt-1", "/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/attempts/adjudication-attempt1/label-S12-2/attempt-2", "/home/martin/.local/share/skills-research/structural-calibration-benchmark-20261009/sessions/shakedown/20261009T200135-nudge-default"]
- `disposition-accounting-within-cap`: {"cap": 12, "dispositions": {"R-57995fe5": "Disproved", "R-6b4bacd4": "Disproved", "R-76904262": "Finding", "R-84664351": "Finding", "R-997a0331": "Disproved", "R-b4800d18": "Finding", "R-ca85afb1": null}, "unique": 7}

The retained receipt records eight completed scout sessions and seven unique hypotheses, all within the validator cap. Six validator dispositions parsed. Replay `R-ca85afb1` returned `**Finding: the match-eligibility rule is now split between `meta_context.py` and the spine, at a cost lower than the hypothesis claims (low severity).**`; the v1 outcome parser did not recognize that bold label with a colon, so disposition accounting failed. The no-leakage failure listed five retained superseded adjudication sessions and one shakedown refusal outside the evidence used by the pilot. The challenge gate passed. These are descriptions of the original gate and result text, not a new gate computation.

Actual retained session usage: `{"cache_creation_input_tokens": 442053, "cache_read_input_tokens": 1464986, "input_tokens": 216, "output_tokens": 77254, "requests": 108, "sessions": 28}`.

## Pilot 2

Original verdict: **FAIL**, recorded at `2026-10-10T12:37:20.022909+00:00`. The original gate failed these checks:

- `validator-conformance`: {"P1": "pass", "P2": "pass", "P3": "pass", "P4": "pass", "P5": "pass", "X1": "execution failure", "Y1": "pass", "Z1": "pass"}
- `assessments-complete`: "3/7"

All eight scouts completed with paired settings. Seven hypotheses were replayed within the cap. The scoped leakage check passed. Challenge X1 had status `completed` but no parsed disposition. Its first output line was:

> Disproved: `CarrierRates.quote` does real pricing work, so it is not a pass-through to the rate table.

This supported output form was not recognized by the parser, so the validator conformance gate failed. The pilot gate also recorded only three of seven hypotheses with completed assessments.

The retained pilot API logs contain 10 HTTP 429 response(s), including provider `rate_limit_error` responses saying the account's rate limit would be exceeded. The original evaluator then created attempt 2 for affected evaluator sessions, which also received quota errors. This left assessments, novelty audits and rejection classifications incomplete. No later sessions can recover the lost quota within this attempt.

Actual retained session usage: `{"cache_creation_input_tokens": 292453, "cache_read_input_tokens": 1632831, "input_tokens": 206, "output_tokens": 71550, "requests": 113, "sessions": 36}`. This is observed per-session request and token accounting. The provider-side quota was not measured exactly.

## Scientific status and acceptance

Both pilot attempts remain operational **FAIL** receipts. The isolated scout outputs and validator evidence are retained, but incomplete matching, novelty auditing, rejection classification and validator disposition accounting prevent a scientifically complete pilot assessment. Neither pilot supports a recall estimate or a treatment comparison. The preregistered full experiment of sixty scout invocations was not run. Issue 89's acceptance requirement for an audited passing pilot and completed full comparison therefore remains incomplete.
