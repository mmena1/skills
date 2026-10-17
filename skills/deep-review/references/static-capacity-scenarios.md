# Static Capacity Scenarios

Apply "Static invocation accounting" in `protocol.md` to these synthetic native launch/notification sequences. Observe the consolidated queue and invocation entries, not a free-slot counter. These are worked scenario expectations, not observations of native execution. For each replay, compare every transition and the final accounting below; retain any divergence. Use the same cases for targeted native smoke coverage where the harness can exercise them, recording only actual native events in runtime receipts.

Notation: `rN/vN/HN` binds reservation `rN` to accepted native invocation `vN` for hypothesis `HN`. `R` is the set of reserved entries, `A` the set of running entries, and occupancy is `len(R) + len(A)`. Every accepted launch below passes through a persisted reservation before becoming running. Completed entries remain in the record even when omitted from the active sets. A completion means native termination is confirmed; the timeout exception is explicit below. Accepted order, including failed adjudications, counts each hypothesis once; refused non-starts are separate.

## Four slots and queued replacements

Use bound 4, canonical queue `H1` through `H8`, and fresh IDs. Compare the record after each event; the intermediate reservation is shown for each refill.

| Event | Queue after event | Reserved/running transitions | Occupancy after event |
| --- | --- | --- | --- |
| Accept H1 through H4 in order | H5,H6,H7,H8 | Each reservation raises occupancy by one; A=v1,v2,v3,v4 | 4 |
| Receive terminal v2/H2; v1 is also finishing | H5,H6,H7,H8 | Complete r2 only; A=v1,v3,v4 | 3 |
| Refill with H5 | H6,H7,H8 | R=r5,A=v1,v3,v4 (4), then bind v5; A=v1,v3,v4,v5 | 4 |
| Receive terminal v1/H1 | H6,H7,H8 | Complete r1 only; A=v3,v4,v5 | 3 |
| Refill with H6 | H7,H8 | R=r6,A=v3,v4,v5 (4), then bind v6; A=v3,v4,v5,v6 | 4 |
| Delayed duplicate terminal v2/H2 after replacements | H7,H8 | r2 is already completed; A=v3,v4,v5,v6 | 4 |
| Receive terminal v4/H4 and refill H7 | H8 | Complete r4; reserve r7 (4), bind v7; A=v3,v5,v6,v7 | 4 |
| Receive terminal v3/H3 and refill H8 | empty | Complete r3; reserve r8 (4), bind v8; A=v5,v6,v7,v8 | 4 |
| Terminals v8,v6,v7,v5, in that order | empty | Complete only the identified entries | 3,2,1,0 |

Expected final accounting: 8 accepted attempts in order H1 through H8, 8 completed accepted entries, 0 refusals, 0 unattempted, no occupied entries, peak 4, and no terminal overwrite. Check the alternate delivery of the first two terminals as one batch: completing r2 and r1 gives occupancy 2; reserving and accepting H5 then H6 gives 3 then 4, with the same final accounting. A launch of H7 on the delayed v2 notification is a divergence: it would reach 5.

## Additional lifecycle cases

Each row starts a separate run. `Finding`, `Disproved`, and `Needs probe` are supplied terminal results, not assumptions about reviewer reasoning.

| Case | Synthetic events | Expected transitions and final accounting |
| --- | --- | --- |
| Delayed first terminal notification | Bound 4, accept H1 through H4, queue H5,H6. v2 terminates physically but its first notification is delayed; receive v1, refill H5, then receive v2 and refill H6; finish the rest. | Until identified, v2 still occupies its entry. Occupancy is 4,3,4,3,4, then drains; peak 4, accepted order H1 through H6, 6 unique completed attempts, no unattempted. A delayed first notification completes v2 only, never replacement v5. |
| Duplicate terminal with conflicting result | Bound 1, queue H1,H2. v1/H1 returns Finding; refill H2 as v2. Receive v1 again as Disproved, then finish v2. | Duplicate leaves occupancy 1 and H1's Finding unchanged, retains a conflict diagnostic, and does not relaunch H2. Final: 2 accepted/completed, peak 1, no unattempted. |
| Failure and confirmed timeout | Bound 2, queue H1 through H4. v1 fails; accept H3 as v3. v2 times out with native termination confirmed; accept H4 as v4. v3 returns Needs probe; v4 returns Disproved. | Occupancy alternates 2,1,2,1,2,1,0. Final: 4 unique accepted attempts H1 through H4, 2 outcomes and 2 terminal failures, peak 2, no unattempted. Run incomplete, preserved evidence, no writable probe despite H3's result. |
| Timeout before native termination | Bound 1, queue H1,H2. v1 times out while still running; native wait/cancellation later confirms termination; then accept and complete H2. | At timeout occupancy stays 1 and H2 stays queued. Confirmed termination completes v1 once; only then reserve H2. Final: 2 accepted/completed, peak 1, incomplete, no writable probe. If termination cannot be confirmed, retain v1 occupied, report H2 unattempted, and stop without claiming drainage. |
| Refusal while another invocation runs | Retryable-backpressure contract, bound 2, queue H1,H2,H3. Accept H1 as v1; reserve H2 as r2; native launch is refused. Wait for v1's first terminal transition, then accept H2 as r3/v2 and H3 as r4/v3; finish both. | Before refusal R=r2,A=v1 (2); after refusal r2 is completed/not started, A=v1 (1), queue H2,H3. No immediate retry. Final: 3 unique accepted attempts H1,H2,H3, 4 completed reservation entries, 1 non-start, peak 2, no unattempted. Refusal is not an adjudication failure. |
| Duplicate cannot lift backpressure | Retryable-backpressure contract, bound 2. Complete H1, keep H2/v2 running, then refuse reserved H3. Receive duplicate H1 terminal; later receive v2's first terminal. | Duplicate leaves H3 at the queue head and dispatch paused despite a free slot. Only v2's first terminal lifts the pause. Accept/finish H3 once. Final: 3 accepted/completed attempts, 1 separate non-start, peak at most 2. |
| Refusal with none able to free a slot | Retryable-backpressure contract, bound 1, queue H1,H2. Reserve H1/r1; native launch refuses before any invocation starts. | r1 becomes completed/not started, occupancy 0, queue H1,H2, 0 accepted attempts, 1 refusal, 2 unattempted due to review failure; stop incomplete without retry or writable probing. |
| Ambiguous admission or unknown identity | Bound 1, queue H1,H2. H1/r1 has no definitive admission response; a terminal notification names unknown native ID vx. | r1 remains reserved (occupancy 1); queue H2. No second launch or inferred release. Resolve vx through native evidence before binding/completing r1; if that fails, stop incomplete, preserve r1 and the unknown-ID diagnostic, and report H1's attempt status unknown and H2 unattempted. |
| Completion before acknowledgment | Bound 1, reserve H1/r1; receive native terminal v1 before its launch acknowledgment, then obtain native binding evidence. | Resolve r1/v1/H1 first, record acceptance and its terminal result once, then refill. A later acknowledgment or terminal duplicate cannot reactivate r1. With H2 then completed, final: 2 accepted/completed, peak 1, queue empty. |
| Zero hypotheses | Successful scouts produce none. | No validator state or launches, 0 attempts, validation skipped; no fabricated invocation evidence. |
| Single slot | Bound 1, queue H1,H2,H3. Each accepted invocation finishes before the next reservation. | Accepted order H1,H2,H3, 3 unique completed attempts, peak 1, no unattempted; capacity alone leaves the run complete. |

## Evidence boundary

Scenario review verifies the specified state transitions and arithmetic, not the harness's execution of instructions. Native smoke evidence must name the harness/version, skill commit, bound/source, accepted native IDs, reservation and terminal transitions, observed peak occupancy, final queue and failures, and the cases actually encountered. Unobserved paths stay NOT EXERCISED. Never rewrite a historical FAIL using these expectations or a replay result.
