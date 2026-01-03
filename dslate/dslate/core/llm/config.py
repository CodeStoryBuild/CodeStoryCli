
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from ..exceptions import ConfigurationError
from .factory import ModelConfig, create_llm_model


def try_create_model(
    model_arg: str | None, api_key_arg: str | None
) -> BaseChatModel | None:
    """
    Configure the LLM model based on command-line arguments, .dslateconfig, or defaults.

    Priority:
    1. Command-line arguments (--model, --api-key)
    2. .dslateconfig file
    3. Environment variables (via factory defaults)
    4. Fallback to gemini-2.0-flash-exp

    Args:
        model_arg: Model specification from --model flag (provider:model-name)
        api_key_arg: API key from --api-key flag

    Returns:
        Configured BaseChatModel or None if configuration fails
    """
    provider = None
    model_name = None
    api_key = api_key_arg

    # Parse --model argument (format: provider:model-name)
    if model_arg:
        if ":" in model_arg:
            provider, model_name = model_arg.split(":", 1)
        else:
            # If no provider specified, try to infer from model name
            model_lower = model_arg.lower()
            if "gpt" in model_lower or "o1" in model_lower or "chatgpt" in model_lower:
                provider = "openai"
                model_name = model_arg
            elif "gemini" in model_lower:
                provider = "gemini"
                model_name = model_arg
            elif "claude" in model_lower:
                provider = "anthropic"
                model_name = model_arg
            else:
                raise ConfigurationError(
                    f"Cannot infer provider from model '{model_arg}'. "
                    f"Please use format: provider:model-name (e.g., openai:gpt-4)"
                )

    # Create model configuration
    model_config = ModelConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=0.7,
    )

    # Create and return the model
    try:
        return create_llm_model(model_config)
    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        return None
