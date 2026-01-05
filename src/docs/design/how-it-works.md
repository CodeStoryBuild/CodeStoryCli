# How It Works

Codestory CLI transforms a set of changes (staged or unstaged) into a series of logical, atomic commits. This process involves several stages of analysis, grouping, and history rewriting.

### 1. State Snapshot (Index-Only)

The process begins by identifying the "target state." Codestory CLI creates a temporary, dangling commit (snapshot) of your current working directory. This is an **index-only** operation: we read your state to analyze it, but we don't touch your actual files until the final commit is ready. This ensures that even if you keep typing while `cst` is running, your working directory remains yours.

### 2. Sandboxed Environment

All subsequent analysis takes place within a **Git Sandbox**. We use temporary object directories (`GIT_OBJECT_DIRECTORY`) to prevent "loose objects" and intermediate states from cluttering your `.git` folder.

### 3. Diff Generation

The engine generates a diff between the base state (the parent commit) and the target state. This raw diff contains all changes that need to be processed.

### 4. Mechanical Chunking

The raw diff is decomposed into the smallest possible independent units called **mechanical chunks**. These chunks are the fundamental building blocks of the system. They are designed to be "pairwise disjoint," meaning they can be applied in any order without overlapping or conflicting at a line level.

**[Mechanical Chunking Deep Dive](./mechanical-chunking.md)**

### 5. Semantic Grouping

Mechanical chunks are then aggregated into **semantic groups** using tree-sitter. The engine analyzes the code's structure to ensure that related changes (e.g., a function definition and its internal logic) stay together. This prevents the creation of commits that result in invalid syntax.

**[Semantic Grouping & tree-sitter](./semantic-grouping.md)**

### 6. Filtering & Safety

Before logical grouping, the semantic groups pass through a filtering layer:

- **Relevance Filtering**: Removes changes that don't match a specified intent (if configured).

- **Secret Scanning**: Identifies and blocks groups containing potential secrets or sensitive data.

- **Syntax Validation**: Optionally ensures that each group results in valid, parsable code.

*Note: Filtering is typically skipped during `fix` and `clean` operations to preserve the integrity of existing history.*

### 7. Logical Grouping

Filtered semantic groups are further aggregated into **logical groups** using an LLM. This step identifies relationships that aren't visible in the code structure alone, such as a feature implementation and its corresponding documentation or tests.

**[Logical Grouping with AI](./logical-grouping.md)**

### 8. History Reconstruction

Finally, the logical groups are applied sequentially to create a new commit history. Codestory CLI uses an incremental accumulation strategy to ensure that each commit is a valid transition from the previous one, avoiding context overlaps.

**[Commit Strategy](./commit-strategy.md)**
