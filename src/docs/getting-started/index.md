# Getting Started

Codestory CLI (`cst`) helps you turn complex code changes into clean, atomic Git history. Whether you're working on a solo project or part of a large team, `cst` ensures your progress is documented in logical steps.

## 1. Installation

Get the latest version of Codestory CLI by following the download instructions for your platform:

**[Download & Installation Guide](https://cli.codestory.build/getting-started/)**

## 2. Onboarding

After installation, simply run `cst` in your terminal to begin the interactive setup.

```bash
cst
```

The onboarding flow will help you:

1. **Choose Configuration Scope**: Store settings globally for all your projects or locally within a specific repository.

2. **Select an AI Model**: Connect to your preferred provider (Anthropic, OpenAI, Ollama, etc.).

3. **Configure API Keys**: Securely set up your credentials.

## 3. Core Workflows

### Clean Up Your Working Directory

If you've been coding for a while and have a mix of changes ready to commit:

```bash
cst commit
```

Codestory CLI analyzes your changes, groups them by intent, and guides you through creating a series of clean, atomic commits.

### Refactor a Recent Commit

If you've already committed a large block of work and want to break it down into smaller, more readable pieces:

```bash
cst fix <COMMIT_HASH>
```

### Clean Up Your Repository History

If you have a complex history that you'd like to clean up:

```bash
cst clean
```

## Next Steps

- **[Usage Guide](../usage/index.md)**: Explore advanced commands like `clean` and `fix`.

- **[Architecture](../design/how-it-works.md)**: See how the engine uses Tree-sitter and LLMs to understand your code.

- **[Configuration](../configuration/index.md)**: Adjust filtering, models, and safety settings.
