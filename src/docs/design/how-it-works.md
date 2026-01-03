# How It Works

`codestory` transforms a set of changes (staged or unstaged) into a series of logical, atomic commits. This process involves several stages of analysis, grouping, and history rewriting.

### 1. State Snapshot
The process begins by identifying the "target state." For the `commit` command, this is a snapshot of your current working directory. For `fix` or `clean`, it is an existing commit in your history.

### 2. Diff Generation
The engine generates a diff between the base state (the parent commit) and the target state. This raw diff contains all changes that need to be processed.

### 3. Mechanical Chunking
The raw diff is decomposed into the smallest possible independent units called **mechanical chunks**. These chunks are the fundamental building blocks of the system. They are designed to be "pairwise disjoint," meaning they can be applied in any order without overlapping or conflicting at a line level.

**[Mechanical Chunking Deep Dive](./mechanical-chunking.md)**

### 4. Semantic Grouping
Mechanical chunks are then aggregated into **semantic groups** using Tree-sitter. The engine analyzes the code's structure to ensure that related changes (e.g., a function definition and its internal logic) stay together. This prevents the creation of commits that result in invalid syntax.

**[Semantic Grouping & Tree-sitter](./semantic-grouping.md)**

### 5. Filtering & Safety
Before logical grouping, the semantic groups pass through a filtering layer:
- **Relevance Filtering**: Removes changes that don't match a specified intent (if configured).
- **Secret Scanning**: Identifies and blocks groups containing potential secrets or sensitive data.
- **Syntax Validation**: Optionally ensures that each group results in valid, parsable code.

*Note: Filtering is typically skipped during `fix` and `clean` operations to preserve the integrity of existing history.*

### 6. Logical Grouping
Filtered semantic groups are further aggregated into **logical groups** using an LLM. This step identifies relationships that aren't visible in the code structure alone, such as a feature implementation and its corresponding documentation or tests.

**[Logical Grouping with AI](./logical-grouping.md)**

### 7. History Reconstruction
Finally, the logical groups are applied sequentially to create a new commit history. `codestory` uses an incremental accumulation strategy to ensure that each commit is a valid transition from the previous one, avoiding context overlaps.

**[Commit Strategy](./commit-strategy.md)**
