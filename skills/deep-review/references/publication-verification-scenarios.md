# Publication Verification Scenarios

Use when changing the submission outcome or read-back verification rules in `pr-review-comments.md`. Each scenario is a synthetic API state, not evidence from a real PR. Apply the rules to the state and compare the result with the expected row. The approved payload for every scenario is the same two comments unless a row states a different payload:

- A: `src/a.py`, `side: RIGHT`, `line: 10`, body `Guard the empty list.`
- B: `src/b.py`, `side: RIGHT`, `start_side: RIGHT`, `start_line: 20`, `line: 24`, body `Close the handle on error.`

Every row ends with zero additional review or comment POSTs. A verification outcome other than `verified` never causes one.

## Read-back verification

| Scenario | PR-wide read-back state | Verification outcome |
| --- | --- | --- |
| Matching review | Both comments carry the review ID with equal body, path, side, line, and B's range fields | `verified` |
| Omitted line and side | Both comments carry the review ID and equal bodies and paths, but `line` and `side` are absent from each | `verification incomplete`, not `mismatch` |
| Omitted range start | B carries `line: 24` and the body, but `start_line` and `start_side` are absent | `verification incomplete` |
| Different anchor | A reports `line: 11`, every field present | `mismatch` |
| Different body | B reports `Close the file on error.`, every field present | `mismatch` |
| Whitespace drift | A's approved body begins with four spaces (an indented Markdown code block) and the received body has them removed, every field present | `mismatch`; only line-ending normalization is excused |
| Line endings only | B's received body differs from the approved body only by `\r\n` versus `\n` | `verified` for B |
| Different comment set | The review has A and a comment on `src/c.py` instead of B | `mismatch` |
| Extra comment | The review has A, B, and a third comment | `mismatch` |
| Missing comment, confirmed | The review has only A on two reads | `mismatch` |
| Count matches, body differs | The review has two comments and the right count, but one body differs | `mismatch` |
| Valid range comment | B reports `start_line: 20`, `start_side: RIGHT`, `line: 24`, `side: RIGHT` | `verified` for B |
| Outdated anchor | A reports `line: null` and `original_line: 10` | `verified` for A |
| Pagination | A payload of 150 comments spans two pages and all pages are read | Compared as one set: `verified` or `mismatch` as the rows above |
| Page failure | The second of two pages fails or the body is unreadable | `verification incomplete` |
| Other reviews' comments | The PR has comments from other reviews and an older review by the same account, besides the submitted review's comments | Only comments with the submitted review ID count; the outcome follows the rows above |
| Head moved during submission, bound | The PR head changes after step 9; the POST carried `commit_id` equal to the pinned head SHA and the review reports that `commit_id` | Compared against the pinned head SHA, so `verified` for the reviewed commit when the comments match; the head change is reported as stale for current-gate use |
| Review at a different commit | The review reports a `commit_id`, or comments an `original_commit_id`, other than the pinned head SHA | `mismatch` recorded as stale with both SHAs; reported as published but unverified; no further POST |
| Missing commit | The review or its comments omit `commit_id` and `original_commit_id` | `verification incomplete` |
| No review ID | The success response lacks an ID and reconciliation found no unique match | `verification incomplete`, submission `ambiguous` |

## Submission

| Scenario | Submission state | Required behavior |
| --- | --- | --- |
| Success, read-back incomplete | `submitted`, then a read-back failure | Report the review as published and the verification as `verification incomplete`; do not submit again |
| Success, mismatch | `submitted`, then `mismatch` | Report the published review and the differences; do not submit again, edit, or resolve anything |
| Timeout | The POST times out | `ambiguous`; reconcile with read-only calls only |
| Dropped connection | The connection closes before a response | `ambiguous`; reconcile with read-only calls only |
| Success without review ID | A 2xx response with no review ID | `ambiguous`; reconcile with read-only calls only |
| Unique match on reconciliation | Exactly one review by this account at the pinned head within the submission window exists and verifies against the payload | `submitted` with the found review ID |
| No match, complete read | Retrieval completes and finds no matching review | Stays `ambiguous`; record the evidence and require explicit human action |
| Two candidates | Two reviews by this account fit the window and head, even if only one verifies against the payload | Stays `ambiguous`; require explicit human action |
| Lone candidate that differs | One review fits the account, window, and head but does not verify | Stays `ambiguous`; record the differences and require explicit human action |
| Transient reconciliation failure | A read fails, then succeeds on a bounded retry | Continue with the successful read; the failure is recorded |
| Persistent reconciliation failure | Retries are exhausted | Stays `ambiguous`; require explicit human action |
| Definitive rejection | A 4xx response states that no review was created | `rejected`; report it and do not replay automatically |

## Verification record

Assess these scenarios by applying the instructions, not by asserting generated wording. Static checks in `scripts/check.py` confirm that the contract clauses and this scenario catalog are present; they cannot prove that a coordinator avoids a duplicate POST at runtime. Confirm runtime behavior in a natural publication or a targeted smoke run, and report publication paths not observed as unobserved rather than passing.
