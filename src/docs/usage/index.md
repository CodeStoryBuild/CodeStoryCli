# Usage Guide

`codestory` (`cst`) helps you maintain a clean, logical git history. It works by analyzing your changes and splitting them into meaningful commits.

The CLI follows a standard pattern:
`cst [global options] <command> [command options]`

## Core Workflows

### 1. Committing New Changes
The `commit` command is your daily driver. It looks at your current working directory and stages changes into logical groups.

```bash
# Interactively review and commit all changes
cst commit

# Focus on a specific directory
cst commit src/core/

# Provide a hint to the AI for better commit messages
cst commit -m "Refactor the database connection pool"

# Use an intent filter to only capture specific types of changes
# (Requires relevance filtering to be enabled in config)
cst commit --intent "fix typos and documentation"
```

### 2. Fixing Past Commits
If you've already made a "mega-commit" and want to split it up after the fact, use `fix`.

```bash
# Split the most recent commit
cst fix HEAD

# Split a specific commit in your history
cst fix abc1234
```

### 3. Cleaning Repository History
The `clean` command is for deep maintenance. It iterates through your history and attempts to split every commit it encounters until it hits a merge commit.

```bash
# Start cleaning from the current HEAD
cst clean

# Start from a specific point in history
cst clean abc1234 --min-size 5
```

## Global Overrides

You can override any configuration value on the fly by passing it as a global option before the command.

### AI & Model Selection
```bash
# Use a specific model for a one-off task
cst --model "openai/gpt-4o" commit

# Lower temperature for more deterministic messages
cst --temperature 0 commit
```

### Filtering & Precision
```bash
# Increase relevance filtering for a cleaner result
cst --relevance-filter-level strict commit --intent "refactor"

# Aggressively scan for secrets before committing
cst --secret-scanner-aggression strict commit
```

## Configuration Management

Use `cst config` to manage your persistent settings. Settings can be stored at the repository level (`local`) or user level (`global`).

```bash
# Set your preferred model globally
cst config model "anthropic/claude-3-5-sonnet-20240620" --scope global

# Set an API key for the current project (scope will default to local if --scope is not specified)
cst config api_key "sk-..."

# View your active configuration (merges local, global, and env vars if --scope is not specified)
cst config
```

## Pro Tip
- **Custom Languages**: If you're using a niche language, you can provide your own Tree-sitter queries via `--custom-language-config`.
