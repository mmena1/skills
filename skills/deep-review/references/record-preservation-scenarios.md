# Record Preservation Regression Scenarios

Use when changing preservation timing, the preservation closeout, the receipt rows for record preservation, or the cleanup order in `protocol.md`. Apply the instructions to these controlled inputs and compare the observable record directory, run directory, and closeout with the expected results. These are scenario checks, not native runtime evidence. Do not implement a simulated preservation harness and count its decisions as coordinator behavior.

## Observation seams and common checks

The seams are the run directory, the record directory under the record root, the live and archived `run-state.json`, and the coordinator's preservation closeout. A hypothetical answer cannot prove an actual write restriction, copy outcome, or native agent behavior.

For every case, check:

- **Snapshot immutability**: the live run state is not changed after its copy starts, the archived run state and report are byte-equal to what was copied, and neither carries a predicted or backfilled preservation success. Its preservation rows are `NOT EXERCISED` with the intended record directory as evidence.
- **Copy ordering**: actual scratch and worktree cleanup outcomes are recorded before preservation, the optional report and publication receipt are copied before the run state, and the run state is copied last.
- **Byte integrity**: every copied file is compared byte for byte with its source before the run directory is removed, and an existing record directory is never overwritten.
- **Truthful closeout**: success is claimed only after verification and names the record path. The closeout distinguishes the archived snapshot from what was observed afterward. Unobserved paths stay `NOT EXERCISED` and no row infers a `PASS`.
- **Retention**: the run directory is removed only when worktree cleanup and preservation are both verified. Review outcomes, report, publication, and worktree cleanup are unchanged by any preservation outcome.

## Cases

| Scenario | Controlled input | Expected observation |
| --- | --- | --- |
| Successful preservation | Worktree cleanup succeeded. The record directory does not exist and every copy succeeds with equal bytes. | The record holds `run-state.json` last, with the report and publication receipt when produced. The archived snapshot names the intended directory and `not yet observed`. The closeout names the record path and verified byte equality, the run directory is removed, and the closeout rows are `PASS` only for observed paths. |
| Existing record directory | A directory already exists at the intended record path. | Nothing is overwritten or merged. Preservation fails before any copy, the failure is recorded in the retained run state because no snapshot exists yet, and the closeout reports the existing path and the retained run directory. |
| Denied write | The write restriction or authorization refuses the first copy into the Git common directory. | Outcomes, report, publication, and worktree cleanup are unchanged. The failure is recorded in the retained run state, since no run state was archived. The closeout reports that records were not preserved, why, and the exact retained run directory. Nothing claims success, and the preservation rows stay `NOT EXERCISED` or `FAIL` only as observed. |
| Partial copy | The report copies, then a later copy fails. In one variant the publication receipt copy fails before the run-state copy starts. In the other the run-state copy itself fails and leaves a partial file. | Before the run-state copy starts, no run state is archived, so the failure is recorded in the retained run state and the record directory has no `run-state.json`. Once the run-state copy has started, the live run state and any partial archived file are left unchanged and the failure is reported in the closeout only. A partial `run-state.json` is never a trusted record. Either way the closeout names the partial record directory and the retained run directory and claims no success. |
| Verification failure | All copies finish, but the byte comparison of one file, such as the report, differs from its source. | The live and archived run state stay unchanged, and nothing is backfilled to describe the mismatch. The closeout reports the mismatch, names the unverified record directory, claims no success, and the run directory is retained with its records. |
| Interruption | The session is interrupted during or after the run-state copy, before verification completes. | Only the closeout can report the interruption, never a snapshot. It claims no success, names the partial or unverified record directory and the retained run directory, and leaves unobserved rows `NOT EXERCISED`. A partial `run-state.json` is not a trusted record, and discovery skips an unreadable one with its reason. An interruption before the run-state copy starts follows the earlier failure path instead. |
| Failed worktree cleanup followed by preservation | Worktree removal failed or was interrupted, leaving a worktree path and its Git registration. | The snapshot records the actual failed cleanup outcome and exact leftovers. Preservation still runs, was not delayed by cleanup, and did not reverse it. The closeout reports the verified record path and the cleanup leftovers separately. The run directory is retained because worktree cleanup is unverified, even when preservation was verified. |

## Native smoke procedure

Observe a real coordinator run or a targeted smoke run on a disposable repository, and inspect the record directory, the live and archived run state, and the closeout, not only the coordinator's narrative. Cover the cases through bounded scenarios and add native cases where important gaps remain. If a harness or permission is unavailable, record the limitation and keep the affected rows `NOT EXERCISED`. These checks do not replace the independent native runtime verification gate, and static guards in `scripts/check.py` establish contract presence and detect clause removal, not runtime compliance.
