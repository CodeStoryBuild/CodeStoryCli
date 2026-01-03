# Commit Strategy: Incremental Accumulation

Once changes are organized into logical groups, `codestory` must apply them to the repository to create a new history. This is not as simple as applying patches sequentially, due to the risk of overlapping contexts and line-offset conflicts.

## The Challenge: Context Overlap
Consider two logical groups, `G1` and `G2`, both modifying the same file.
- `G1` contains a change at the top of the file.
- `G2` contains a change at the bottom of the file.

If you apply `G1` and commit it, the file's state changes. When you then try to apply `G2`'s original patch to this new state, the line numbers may no longer match, or the surrounding context may have shifted, leading to patch failures.

## The Solution: Incremental Accumulation
To solve this, `codestory` uses an **incremental accumulation strategy**. Instead of applying each group's patch to the *previous* commit's state, it applies an accumulated set of changes to the *original* base state.

### How It Works:
1.  **Commit 1**: Apply changes from `G1` to the **Base State**.
2.  **Commit 2**: Apply changes from **G1 + G2** to the **Base State**.
3.  **Commit 3**: Apply changes from **G1 + G2 + G3** to the **Base State**.

By comparing the state of **Commit N** with **Commit N-1**, we get exactly the changes intended for **Group N**, but applied in a way that is guaranteed to be mechanically consistent with all preceding changes.

## History Rewriting
After all accumulated states are created, `codestory` uses Git's low-level plumbing to:
1.  Chain these states into a linear history.
2.  Update the current branch pointer to the new head.
3.  Clean up any temporary references used during the process.

This strategy ensures that the final history is clean, atomic, and perfectly reflects the logical grouping determined in earlier stages.

**[Back to Introduction](../index.md)**