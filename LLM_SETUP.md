# Multi-LLM Support for Vibe

## Overview

Vibe now supports multiple LLM providers through LangChain, allowing you to choose the best model for your needs.

## Supported Providers

- **OpenAI** (`openai`) - GPT-4, GPT-3.5-turbo, etc.
- **Google Gemini** (`gemini`) - Gemini 2.0 Flash, Gemini Pro, etc.
- **Anthropic** (`anthropic` or `claude`) - Claude 3.5 Sonnet, Claude 3 Opus, etc.
- **Azure OpenAI** (`azure`) - Azure-hosted OpenAI models
- **Ollama** (`ollama`) - Local open-source models

## Usage

### Command-line Arguments

Use the `--model` and `--api-key` flags at the root level (before the subcommand):

```bash
# OpenAI GPT-4
vibe --model openai:gpt-4 --api-key sk-... commit

# Google Gemini 2.0 Flash
vibe --model gemini:gemini-2.0-flash-exp commit

# Anthropic Claude 3.5 Sonnet
vibe --model anthropic:claude-3-5-sonnet-20241022 expand abc123

# Ollama (local)
vibe --model ollama:llama3.2 commit
```

### Configuration File (.vibeconfig)

Create a `.vibeconfig` file in your project root or any parent directory:

```json
{
  "model_provider": "gemini",
  "model_name": "gemini-2.0-flash-exp",
  "api_key": "your-api-key-here",
  "temperature": 0.7
}
```

**Note:** For security, it's recommended to use environment variables for API keys instead of storing them in .vibeconfig.

### Environment Variables

Set provider-specific environment variables:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Google Gemini
export GOOGLE_API_KEY=...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI
export AZURE_OPENAI_ENDPOINT=https://...
export AZURE_OPENAI_API_KEY=...

# Ollama
export OLLAMA_BASE_URL=http://localhost:11434
```

## Priority Order

Vibe uses the following priority for configuration:

1. **Command-line arguments** (`--model`, `--api-key`)
2. **.vibeconfig file** (searched from current directory up to root)
3. **Environment variables** (provider-specific)
4. **Default fallback** (Gemini 2.0 Flash Exp)

## Model Format

The `--model` argument accepts two formats:

1. **Full format:** `provider:model-name`
   - Example: `openai:gpt-4`, `gemini:gemini-2.0-flash-exp`

2. **Model name only:** Vibe will attempt to infer the provider
   - Example: `gpt-4` → OpenAI, `gemini-2.0-flash-exp` → Gemini

## Examples

### Using OpenAI GPT-4

```bash
# Via command line
vibe --model openai:gpt-4 commit src/

# Via .vibeconfig
cat > .vibeconfig << EOF
{
  "model_provider": "openai",
  "model_name": "gpt-4"
}
EOF
export OPENAI_API_KEY=sk-...
vibe commit src/
```

### Using Anthropic Claude

```bash
# Via command line
vibe --model claude:claude-3-5-sonnet-20241022 --api-key sk-ant-... expand abc123

# Via environment
export ANTHROPIC_API_KEY=sk-ant-...
vibe --model anthropic:claude-3-5-sonnet-20241022 expand abc123
```

### Using Local Ollama

```bash
# Start ollama server first
ollama serve

# Use with vibe
vibe --model ollama:llama3.2 commit
```

### Using Default (Gemini)

```bash
# Just set API key
export GOOGLE_API_KEY=...

# Vibe will use Gemini 2.0 Flash Exp by default
vibe commit
```

## Installing Dependencies

Install all provider dependencies:

```bash
pip install langchain-openai langchain-anthropic langchain-ollama
```

Or install only what you need:

```bash
# OpenAI only
pip install langchain-openai

# Anthropic only
pip install langchain-anthropic

# Ollama only
pip install langchain-ollama
```

Google Gemini support (`langchain-google-genai`) is already included in the base installation.

## Troubleshooting

### Missing Provider Package

If you see an error like "langchain-openai is not installed", install the required package:

```bash
pip install langchain-openai
```

### API Key Not Found

Ensure your API key is set via one of these methods:
1. `--api-key` command-line argument
2. `.vibeconfig` file
3. Provider-specific environment variable

### Model Not Working

Check that:
1. The model name is correct for the provider
2. You have access to the model with your API key
3. The provider package is installed

## Additional Notes

- The `--model` and `--api-key` arguments must come **before** the subcommand (`commit`, `expand`, etc.)
- If no model is configured, Vibe falls back to Gemini 2.0 Flash Exp
- API keys in .vibeconfig should be kept secure (add to .gitignore)
- Temperature and max_tokens can be configured in .vibeconfig or via the factory
