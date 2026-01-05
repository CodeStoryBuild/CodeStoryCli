# Logical Grouping

Logical grouping is the final stage of change analysis, where Codestory CLI uses Large Language Models (LLMs) to identify relationships that are not visible through static code analysis alone.

## Why Logical Grouping?
Static analysis (semantic grouping) is excellent for finding links within source code, but it cannot easily connect:

- **Code and Documentation**: A change in a `.py` file and a corresponding update in a `.md` file.

- **Code and Tests**: A new feature and its integration tests in a separate directory.

- **Cross-Language Changes**: A frontend change in TypeScript and a backend change in Go.

Logical grouping bridges these gaps by analyzing the *intent* and *context* of the changes.

## The Role of LLMs
Codestory CLI uses LLMs for **analysis (interpolation)** rather than **generation (extrapolation)**. Instead of asking the model to "invent" code, we provide it with the existing codebase state and the proposed changes. The model's task is to:

1.  **Analyze Relationships**: Determine if two semantic groups are part of the same logical task.

2.  **Summarize Intent**: Generate a concise, meaningful commit message for each logical group.

By focusing on summarization and relationship analysis, the engine achieves high accuracy and consistency.

## Intent Filtering
When the `relevance_filtering` is enabled, the logical grouping engine can also filter changes based on a user-provided intent message (`--intent`). This allows you to focus on specific tasks (e.g., "refactor auth") while ignoring unrelated changes (e.g., "fix typos").

## Supported Providers
Codestory CLI supports a wide range of LLM providers via `aisuite`:

- **Cloud**: OpenAI, Anthropic, Google, Azure, AWS, Mistral, DeepSeek, Groq, etc.

- **Local**: Ollama, LM Studio.

For a full list of supported providers and how to configure them, see [Supported Providers & Languages](../reference/supported.md).

**[Next: Commit Strategy](./commit-strategy.md)**
