# Why Codestory CLI?

Git is a powerful tool, but the reality of software development often involves jumping between different tasks. We frequently bundle unrelated fixes, features, and refactors into a single set of changes. This makes the resulting history difficult to read and maintain for everyone on the team.

## The Problem: The "Mega-Commit"

When multiple logical changes are squashed into one commit, they become:

- **Hard to Review**: Reviewers must keep track of several unrelated contexts at once.

- **Impossible to Bisect**: If a bug is introduced, `git bisect` can only tell you it's somewhere in the giant commit, but not which specific change caused it.

- **Difficult to Revert**: You can't undo a single experimental feature without also losing the critical bug fix that was committed alongside it.

## The Solution: Atomic Commits

Codestory CLI is built on the belief that **your commit history should be clean, no matter how messy your work process was.**

It goes beyond simple commit message generation. Codestory CLI **re-architects your history** by decomposing your changes into their fundamental units and organizing them into logical, atomic steps.

### A New Standard for AI-Assisted Git

Most AI commit tools simply summarize a large diff. Codestory CLI actually **restructures the work itself** while maintaining absolute technical integrity.

- **Index-Only Operations**: We never disrupt your working directory. Codestory CLI creates a snapshot of your state and performs its analysis in isolation, keeping your active development safe.

- **Fully Sandboxed**: All analysis and grouping happens in a temporary Git environment. This ensures your repository's object database stays clean and free of intermediate noise.

- **Fully Atomic**: Your branch is only updated if the entire pipeline succeeds. If the AI doesn't produce a valid result, your history remains untouched.

- **Mechanical Safety**: Our algorithms ensure that every change can be safely applied or reverted at a granular level.

- **Semantic Awareness**: By using tree-sitter, Codestory CLI understands the structure of your code (functions, classes, etc.), ensuring that related logical blocks stay together.

- **Human in the Loop**: You are always in control. Codestory CLI handles the heavy lifting of granular staging (`git add -p`), allowing you to review and approve every commit before it's finalized.

## Our Philosophy

1. **History is a Feature**: A clean, readable Git log is a primary asset that helps teams move faster.

2. **Speed is Essential**: Developer tools should be fast and stay out of the way.

3. **No Magic Without Review**: Every decision made by the system must be transparent and reviewable by a human.

4. **Git-Native**: We don't replace the Git workflows you know; we enhance them.
