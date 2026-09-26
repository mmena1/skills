# Review Tone Guide

This captures the established voice for inline PR review comments, drawn from this reviewer's actual comments on past PRs. Use it directly; re-sampling recent PR comments alongside generated ones dilutes the voice over time.

## Voice

- **One idea per comment.** Start with the observation or question; compliments and code summaries before the critique add noise. (Exception: a top-level PR *approval* summary can be one short warm line, e.g. "Nice fixes! Looks good now"; that's the one place a positive aside fits.)
- **Match certainty to the finding. This is the key branch:**
  - **Clear-cut / objectively verifiable** (style nits, provably-dead code, a redundant assertion, a mechanical convention like import placement) → **state it directly, as an instruction.** No hedging, no question mark. E.g. "Move this import to the top of the file." "This assertion is always true and adds noise." "This should be at the top of the class."
  - **Judgment call / tradeoff / anything requiring the author's context** (naming, architecture, threshold values, whether a rule is too broad, whether a doc's intent still holds) → **frame it as a genuine question and preserve the uncertainty.** "I think", "I don't think", "Do we care about...?", "Should we...?", and "WDYT?" are examples of the reviewer's voice, not required templates. Use them only when they fit naturally; a direct question is often enough.
  - **Suspected but not fully confirmed** (e.g. "this test looks like a duplicate of that other test") → **state the evidence, then ask the author to confirm**: "I think this test is doing the same thing as `X`, can you check?" When you haven't traced both code paths, state the evidence and ask the author to confirm before asserting removal.
- **Repeated instances of the same nit get terser each time.** The first occurrence in a file can have a full sentence ("This fully qualified import should be moved to the top of the file with the other imports."); by the third or fourth repeat in the same PR it's just "Import should be at the top of the class." Shorten repeated instances of the same nit after the first full explanation.
- **Show the reasoning before the conclusion when it's not obvious.** Pattern: state what the code currently does → state why that's a problem → state the ask. E.g. "These tests claim publisher exception scenarios, but validation fails before the publisher is reached. Existing tests already cover these validation paths. In that case, I think they can be removed."
- **Invite discussion with "WDYT?"**: use it on judgment calls where there's a real tradeoff, not on every comment. Skip it on unambiguous fixes (naming, missing doc updates, style nits), and do not add it just to make a comment sound like the examples.
- **Name concrete identifiers with backticks.** Reference the exact constant, method, class, or file being discussed (`RedisConstants.java`, `EXACT_FALLBACK_MESSAGES`, `acquireDedupLock()`) so the author doesn't have to guess what's being pointed at.
- **Call out doc/comment vs. behavior drift explicitly.** Pattern: "The Javadoc says X, but actual behavior now does Y", then say what the doc should say instead, often as a fenced snippet.
- **Give a code suggestion only when it's short and unambiguous.** Use a ` ```suggestion ` block for single/few-line diff edits, or a small fenced snippet (```java, ```md) when showing the shape of a bigger fix. For a broader refactor (e.g. "extract these into shared setup"), it's fine to give the full replacement code directly and state it as a recommendation rather than a question. That's still a judgment call on approach, but the fix itself is concrete enough to just show. Keep the fix explanation short when the code makes it self-evident.
- **Point to the shared/canonical place things belong.** "Shouldn't this be in `RedisConstants.java`?" / "I think these prefixes should also be documented on `redis-key-conventions.md`". This favors consolidating into existing conventions over introducing new ones.
- **Keep it short.** Most comments are 1-3 sentences. Even the longer ones with a code suggestion stay to a single point.

## Keep comments human

The rules above define the reviewer's judgment and certainty. After drafting, do one editing pass for voice. Do not change the finding or make uncertain evidence sound more certain just to make the prose stronger.

- Write the comment you would actually leave for a teammate, not a miniature review report.
- Do not restate the diff. Start at the concern.
- Be concrete. Name the behavior, identifier, or failure mode instead of saying something is "cleaner", "more robust", or "more maintainable".
- Prefer plain words and active voice.
- Cut generic review filler such as "consider", "it may be worth", "this could potentially", "to improve maintainability", and "best practice" when the specific reason can be stated instead.
- Do not mechanically reuse signature phrases. "I think", "Should we...?", "Do we care about...?", and "WDYT?" are available when they fit, not required markers of a judgment call.
- Fragments and contractions are fine when they sound natural. Do not polish a two-line PR comment into formal prose.
- If a sentence could be pasted unchanged onto dozens of unrelated PRs, rewrite it with the actual code and consequence.
- Before presenting the comment, ask: "Would this obviously read as generated text?" If so, simplify it.

## Examples (paraphrased from real comments)

These examples demonstrate judgment, brevity, and level of certainty. Do not copy their sentence structure or recurring phrases unless they naturally fit the finding.

Judgment calls (hedged, framed as questions):

> Shouldn't this prefix be in `RedisConstants.java`?

> Same with these prefixes, I think you could move them to the `RedisConstants` file and reuse them on the tests as well.

> Do you think `"i cannot"` is a bit too broad here? A valid answer could start with something like "I cannot overstate..." and we'd end up hiding sources even though the response is substantive.

> This says the method doesn't rely on exact phrase matching, but we now have `EXACT_FALLBACK_MESSAGES.contains(normalized)` below. Should we update this Javadoc to mention that it uses both exact matches and heuristic checks?

> I don't think there's actually a static initialization circular dependency here, since `PromptTemplate` doesn't reference `ResponseValidationUtil`. Could we either reference the `PromptTemplate` constants directly here or move the shared fallback strings to a constants class? WDYT?

> Do we care about import order? I think it's a bit inconsistent, but I don't think this matters much.

Clear-cut (stated directly, imperative):

> This is redundant, `assertThrows` either returns a non-null exception or fails the test; it cannot return null. This assertion is always true and adds noise.

> This fully qualified import, should not be inline, please move it to the top of the file where all imports are.

> Import should be at the top of the class. *(same nit, later occurrence, terser)*

Suspected-duplicate / needs-author-confirmation:

> I think this test is doing the same thing as `handleAgentReply_MissingAgentId`, can you check?

> These tests claim publisher exception scenarios, but validation fails before the publisher is reached. Existing tests already cover these validation paths. In that case, I think they can be removed.

Concrete refactor recommendation with code:

> Four anthropic_* tests repeat the same local mock declarations and WebClient stubbing chain. You should create class level mocks and a setup method to avoid too much repetition:
> ```java
> @Mock
> private WebClient.RequestBodyUriSpec anthropicUriSpec;
> // ...
> private void setupAnthropicWebClientMocks() { ... }
> ```

Fix with a short suggestion block:

> On Redis connection failure, the exception is swallowed and false is returned. `AgentMessageSubscriber.acquireDedupLock()` treats any non-true as duplicate and returns false, so the Pub/Sub message is dropped. I think it should return null instead:
> ```java
> public Boolean setIfAbsent(String key, String value, Duration ttl) {
>     return executeWithErrorHandling(...);
> }
> ```

When the user explicitly requests a top-level approval summary:

> Nice fixes! Looks good now

## Mapping Action to comment style

Each finding's `Action` determines the comment voice:

- **Action: fix-now** → Use the **clear-cut** voice. State the fix directly as an instruction. Include a ` ```suggestion ` block when the change is a few lines or fewer. Do not hedge or ask permission.
- **Action: discuss** → Use the **judgment-call** voice. Frame the finding as a genuine question and preserve uncertainty. Do not mechanically add "I think", "Should we...?", or "WDYT?"; use the phrasing that sounds natural for the specific concern.
- **Action: follow-up** → Explain why the issue is out of scope for this PR and describe the follow-up scope in one sentence. The tone is informative, not blocking.

## Applying this to generated review comments

When drafting inline comments from consolidated findings:

1. Omit the internal report's severity, evidence, and validation fields from an inline comment.
2. Classify the outcome as Finding or a user-selected Unresolved question. Use the matching pattern above.
3. State Findings directly. Preserve the uncertainty of an Unresolved question rather than presenting it as established fact.
4. Include a code block only when the fix is short and unambiguous; otherwise describe the change in one sentence.
5. If the same nit applies to multiple locations, state it fully once and shorten later comments.
6. Run the final comment through **Keep comments human** without changing the finding's certainty or meaning.
