Phase: static, under a read-only contract. Writable probes are not available in this run.
Canonical hypothesis: {hypothesis_id} (original scout ID: {origin_id})
Pinned review worktree: the repository behind your list_files, read_file, search and git tools. Paths are repository-relative, and every Git command runs in that repository.
Reviewed base SHA: {base}
Reviewed head SHA: {head}
Context snapshot: `manifest`, `core-manifest` and `reviewers/validator-manifest` name no entries. Supplemental context is empty; tracked instructions in the worktree govern.
History: the repository contains exactly these two snapshot commits. Original commit history is intentionally withheld.
Access: only the four tools above are available. There are no other files, tools or network access.

Hypothesis to adjudicate:

{hypothesis}

Return exactly one static outcome (`Finding`, `Disproved`, `Unresolved` or `Needs probe`) in the contract's schema as your last message.
