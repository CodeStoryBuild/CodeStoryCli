# Mechanical Chunking

Mechanical chunking is the process of decomposing a large Git diff into the smallest possible independent units of change. This is the foundation upon which all higher-level semantic and logical analysis is built.

## The Hunk Limitation

In standard Git, the most granular unit of change is a **hunk**. A hunk is a contiguous block of changes within a file. However, Git's default hunk generation is often too coarse. For example, if you add multiple functions to a new file, Git treats the entire file as a single hunk.

To enable precise history rewriting, Codestory CLI must be able to manipulate these changes at a much finer level.

## Decomposition Strategy

Codestory CLI analyzes each Git hunk and attempts to split it into smaller, independent pieces. This allows the engine to:

1.  **Isolate Changes**: Separate unrelated modifications that happen to be near each other.

2.  **Reorder Safely**: Move changes between different logical commits.

3.  **Filter Precisely**: Exclude specific lines (like debug logs) without rejecting the entire file change.

## The Pairwise Disjoint Rule

The most critical constraint in mechanical chunking is that all resulting chunks must be **pairwise disjoint**. This means:

- No two chunks can modify the same line of code.

- The sum of all chunks must exactly equal the original diff.

- Each chunk must be "mechanically valid," meaning it contains enough context to be applied independently using standard patching tools.

## Configuration

Users can control the granularity of this process through the `chunking_level` configuration:

- `none`: No additional chunking beyond standard Git hunks.

- `full_files`: Only split hunks that represent entire file additions or deletions.

- `all_files`: Aggressively attempt to split all hunks into the smallest possible units.

## Why It Matters

By ensuring that chunks are independent and disjoint, Codestory CLI guarantees that any combination of these chunks can be applied to the codebase without causing merge conflicts or line-offset errors. This mechanical robustness is what makes complex history transformations safe.

**[Next: Semantic Grouping](./semantic-grouping.md)**
