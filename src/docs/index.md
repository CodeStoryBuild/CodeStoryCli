# CodeStory CLI

codestory is a high-level interface layered on top of Git that helps you produce clean, logical commit histories without manually staging and composing many small commits.

This page is a technical landing for the CLI: what it does, how it works, and the guarantees it provides. It is not a replacement for Git — it is a workflow tool that programmatically constructs commit history while leaving your working tree untouched.

## What problem it solves

Developers often accumulate large, multi-file changes and commit them as a single blob with an opaque message. That makes bisects, rollbacks, and code review harder.

codestory reads your working changes or existing commits and constructs a linearized sequence of atomic, logically grouped commits. It reduces cognitive debt by converting a large unstructured change into smaller, semantically meaningful steps.

## How it works (technical overview)

- **Read-only with respect to source files**: codestory never modifies source files in your working directory. It constructs and manipulates Git index objects (virtual indexes) to build the desired history, then writes a sequence of commits into your repository.
- **Semantic grouping**: Source files are analyzed with language-aware parsers (AST-level) using Tree-sitter to ensure syntactically coupled edits remain together. Tree-sitter queries define the language semantics, allowing codestory to identify and group semantically dependent changes. This prevents splitting code in a way that would break compilation or tests.
- **High-level analysis with models**: For logical relationships that static analysis cannot infer (documentation linked to code, cross-file design intent), codestory employs configurable model providers to detect logical dependencies and relevance.
- **Commit linearization**: Changes are split into minimal logical units and ordered to form a linear history that best represents the development story.

## Safety and guarantees

- **No source mutation**: The file contents in your working directory remain unchanged. All history edits are implemented via Git objects and index manipulation.
- **Atomic changes**: Commands are transactional. If a rewrite cannot be completed safely, codestory aborts and leaves the repository state unchanged.
- **Secrets and filters**: The commit pipeline supports filters that identify and exclude exposed secrets before constructing commits. A relevance filter can drop unrelated files when you provide an intent for the change.

## Extensibility and language support

codestory is language-agnostic by design. New language support generally requires only a small JSON file that defines the language semantics used by the semantic grouper (roughly 10–20 lines for common languages). The grouping engine uses these definitions plus AST analysis to keep semantically-dependent edits together.

## Model providers (BYOK)

You can configure model providers via your environment or configuration files. Supported providers include cloud services (OpenAI, Anthropic, Google) and local runtimes (Ollama). The architecture is provider-agnostic: you supply credentials or local endpoints and codestory will use them for high-level analysis tasks.

## Typical workflow (examples)

1. Make a set of edits across files while implementing a feature.
2. Run `codestory commit` (optionally supply an intent or model selection).
3. Review the proposed commit sequence and messages, then accept and push.

Common options you will find useful:

- Provide an intent or summary to guide relevance filtering.
- Enable secret detection to avoid committing credentials.
- Choose a model provider for higher-quality logical grouping.

## When to use which command

- Use `commit` when you have local, unstaged/unstaged changes you want split into logical commits.
- Use `fix` to repair or refine a single commit or a contiguous range that already exists in history.
- Use `clean` when you want to perform a broad rewrite across many commits (for repo-wide hygiene).

## Integration notes

- After codestory rewrites history, the repository is a normal Git repository: you may push, rebase, or merge as you would normally.
- Because history can be rewritten, coordinate with collaborators when operating on shared branches.

## License and contribution

codestory is licensed under GPLv2, following the same license principles as Git. The project is designed to be extensible; contributions that add language configs, filters, or provider integrations are welcome.

## Cli Reference

For detailed CLI reference, see [reference/root.md](reference/root.md).
