# Configuration

Codestory CLI uses a hierarchical configuration system to give you fine-grained control over how it operates. You can configure everything from which AI model to use to how aggressively it should scan for secrets.

## Configuration Scopes

Config options are loaded in the following priority (highest to lowest):

1.  **Command Line Arguments**: Explicit flags like `--model openai:gpt-4` or `--custom-config path/to/config.toml`.

2.  **Custom Config File**: Specified via `--custom-config`.

3.  **Local Config**: A `codestoryconfig.toml` file in your project's root directory.

4.  **Environment Variables**: Prefix `CODESTORY_` followed by the key name (e.g., `CODESTORY_MODEL`).

5.  **Global Config**: A system-wide configuration file located in your OS-specific config directory (e.g., `~/.config/codestory/` on Linux, `AppData/Local/codestory/` on Windows).

### Custom Config File

You can specify a specific configuration file to use for a single command using the `--custom-config` global option:

```bash
cst --custom-config ./my-config.toml commit
```

This will take precedence over local and global configuration files.

## Managing Configuration

Use the `cst config` command to view and modify your settings.

### Viewing Settings

- `cst config`: Show all active configuration values and their sources.

- `cst config <key>`: Show the value for a specific setting.

- `cst config --describe`: List all available configuration options and their descriptions.

### Changing Settings

- `cst config model "openai:gpt-4"`: Set a local project-level value.

- `cst config model "ollama:qwen2.5-coder" --scope global`: Set a system-wide value.

- `cst config --delete model`: Remove a local configuration override.

- `cst config --deleteall`: Clear all local and global configurations.

## Available Options

Below are the key configuration options available in Codestory CLI:

| Key | Description | Default |
|-----|-------------|---------|
| `model` | LLM model (format: provider:model, e.g., openai:gpt-4) | `no-model` |
| `api_key` | API key for the LLM provider | `None` |
| `api_base` | Custom API base URL for the LLM provider (optional) | `None` |
| `temperature` | Temperature for LLM responses (0.0-1.0) | `0` |
| `max_tokens` | Maximum tokens to send per llm request | `4096` |
| `relevance_filtering` | Whether to filter changes by relevance to your intent (`cst commit` only) | `false` |
| `relevance_filter_similarity_threshold` | How similar do changes have to be to your intent to be included | `0.75` |
| `secret_scanner_aggression` | How aggressively to scan for secrets (`safe`, `standard`, `strict`, `none`) | `safe` |
| `fallback_grouping_strategy` | Strategy for grouping changes that were not able to be analyzed | `all_together` |
| `chunking_level` | Which type of changes should be chunked further into smaller pieces | `all_files` |
| `verbose` | Enable verbose logging output | `false` |
| `auto_accept` | Automatically accept all prompts without user confirmation | `false` |
| `silent` | Do not output any text to the console, except for prompting acceptance | `false` |
| `ask_for_commit_message` | Allow manual commit message overrides | `false` |
| `display_diff_type` | Type of diff to display (semantic or git) | `semantic` |
| `custom_language_config` | Path to custom language configuration JSON file | `None` |
| `batching_strategy` | Strategy for batching LLM requests (auto, requests, prompt) | `auto` |
| `custom_embedding_model` | FastEmbed supported text embedding model | `None` |
| `cluster_strictness` | Strictness of clustering logical groups together (0-1) | `0.5` |
| `num_retries` | How many times to retry failed LLM calls (0-10) | `3` |
| `no_log_files` | Disable logging to files, only output to console | `false` |

> Pro Tip: Use `cst config --describe` in your terminal to see the most up-to-date list of all experimental and advanced configuration flags.
