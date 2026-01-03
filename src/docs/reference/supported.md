# Supported Providers & Languages

`codestory` leverages `aisuite` for model connectivity and `tree-sitter` for code analysis.

## Model Providers

The following providers are supported via `aisuite`. Configure them using `cst config model "<provider>:<model>"`.

For the most up to date list, you can run:
``` bash
cst -SP
```

| Provider | Key | Link |
| :--- | :--- | :--- |
| **Anthropic** | `anthropic` | [anthropic.com](https://anthropic.com/) |
| **AWS** | `aws` | [aws.amazon.com/bedrock](https://aws.amazon.com/bedrock/) |
| **Azure** | `azure` | [azure.microsoft.com](https://azure.microsoft.com/en-us/products/ai-foundry/models) |
| **Cerebras** | `cerebras` | [cerebras.net](https://cerebras.net/) |
| **CentML** | `centml` | [centml.ai](https://centml.ai/) |
| **Cohere** | `cohere` | [cohere.com](https://cohere.com/) |
| **DeepSeek** | `deepseek` | [deepseek.com](https://deepseek.com/) |
| **Fireworks** | `fireworks` | [fireworks.ai](https://fireworks.ai/) |
| **Featherless** | `featherless` | [featherless.ai](https://featherless.ai/) |
| **Google** | `googlegenai` | [ai.google.dev](https://ai.google.dev/) |
| **Groq** | `groq` | [groq.com](https://groq.com/) |
| **Hugging Face** | `huggingface` | [huggingface.co](https://huggingface.co/) |
| **Inception** | `inception` | [inceptionlabs.ai](https://inceptionlabs.ai/) |
| **LM Studio** | `lmstudio` | [lmstudio.ai](https://lmstudio.ai/) |
| **Mistral** | `mistral` | [mistral.ai](https://mistral.ai/) |
| **Nebius** | `nebius` | [nebius.com](https://nebius.com/) |
| **Ollama** | `ollama` | [ollama.ai](https://ollama.com/) |
| **OpenRouter** | `openrouter` | [openrouter.ai](https://openrouter.ai/) |
| **OpenAI** | `openai` | [openai.com](https://openai.com/) |
| **SambaNova** | `sambanova` | [sambanova.ai](https://sambanova.ai/) |
| **Together** | `together` | [together.ai](https://together.ai/) |
| **WatsonX** | `watsonx` | [ibm.com/products/watsonx-ai](https://www.ibm.com/products/watsonx-ai) |
| **xAI** | `xai` | [x.ai](https://x.ai/) |

### Configuration Example
```bash
# Set your model
cst config model "openai:gpt-4o"

# Set your API key
cst config api_key "sk-..."
```


## Supported Languages

`codestory` provides deep semantic analysis for the many languages out of the box. Here are some common ones:
- **C-Family**: `cpp`, `csharp`,
- **Web**: `javascript`, `typescript`, `php`
- **Systems**: `rust`, `go`, `swift`
- **Scripting**: `python`, `ruby`, `lua`
- **Functional**: `elixir`, `haskell`, `ocaml`, `erlang`, `clojure`
- **Mobile/Other**: `kotlin`, `java`, `scala`, `dart`, `r`

For the most up to date list, you can run:
``` bash
cst -SL
```

