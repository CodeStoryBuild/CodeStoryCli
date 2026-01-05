# Usage Guide

Codestory CLI (`cst`) is designed to fit seamlessly into your existing Git workflow. It helps you keep your history clean and documented by analyzing your work and proposing logical, atomic commits.

The CLI follows a simple, standard pattern:

`cst [global options] <command> [command options]`

## Common Workflows

### 1. Committing Your Current Work

The `commit` command is likely where you'll spend most of your time. It analyzes your uncommitted changes and suggests how to group them into meaningful commits.

```bash
# Interactively review and commit all current changes
cst commit

# Focus on a specific area of your project
cst commit src/ui/

# Provide a hint to guide the AI's commit messages
cst commit -m "Implement the new billing dashboard"

# Use intentional filtering to capture specific types of work
# (Note: This depends on your relevance filtering settings)
cst commit --intent "fix visual regressions and update readme"
```

### 2. Refining Recent History

If you've already made a large commit and realized it would be better as several smaller steps, use the `fix` command.

```bash
# Break down your most recent commit
cst fix HEAD

# Split any specific commit from your history
cst fix abc1234
```

### 3. Repository Maintenance with `clean`

The `clean` command helps you improve the quality of a series of recent commits. It walks through your history and attempts to decompose "mega-commits" into smaller, logical units.

**Safety Note**: Since this command rewrites history, it's best to run it on a new branch.

```bash
# Cleanup history starting from the current branch tip
cst clean

# Start cleaning from a specific point, ignoring smaller commits
cst clean --start abc1234 --min-size 10
```

## On-the-Fly Overrides

You can temporarily change any setting by passing it as a global option before the command.

### AI & Model Settings

```bash
# Try a different model for a specific task
cst --model "openai:gpt-4o" commit

# Adjust the 'creativity' of the commit generation
cst --temperature 0.3 commit
```

### Precision & Filtering

```bash
# Enable strict filtering to focus on specific work
cst --relevance-filtering true --relevance-filter-similarity-threshold 0.8 commit --intent "refactor"

# Increase the aggression of the secret scanner
cst --secret-scanner-aggression strict commit
```

## Managing Your Settings

Use `cst config` to view and modify your persistent preferences. You can store settings globally for all your projects or locally within a single repository.

```bash
# Set your preferred model for all projects
cst config model "anthropic:claude-3-5-sonnet-20240620" --scope global

# Save a project-specific API key
cst config api_key "sk-..."

# View your active configuration across all sources
cst config
```

## Pro Tip

- **Extending Language Support**: Working with a newer or custom language? You can provide your own tree-sitter definitions using `--custom-language-config`.
