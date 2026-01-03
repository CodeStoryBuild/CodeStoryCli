from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel

from .factory import ModelConfig, create_llm_model
from ..config.vibe_config import load_config
from loguru import logger


def try_create_model(
    model_arg: Optional[str], api_key_arg: Optional[str]
) -> Optional[BaseChatModel]:
    """
    Configure the LLM model based on command-line arguments, .vibeconfig, or defaults.

    Priority:
    1. Command-line arguments (--model, --api-key)
    2. .vibeconfig file
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
                raise ValueError(
                    f"Cannot infer provider from model '{model_arg}'. "
                    f"Please use format: provider:model-name (e.g., openai:gpt-4)"
                )

    # If not provided via CLI, check .vibeconfig
    if not provider or not model_name:
        config = load_config()
        if config:
            provider = provider or config.model_provider
            model_name = model_name or config.model_name
            api_key = api_key or config.api_key

    # If still not configured, use default
    if not provider or not model_name:
        logger.info("No model specified, using default: gemini:gemini-2.0-flash-exp")
        provider = "gemini"
        model_name = "gemini-2.0-flash-exp"

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
        # Try fallback to default Gemini model
        try:
            logger.info("Attempting fallback to gemini-2.0-flash-exp")
            fallback_config = ModelConfig(
                provider="gemini",
                model_name="gemini-2.0-flash-exp",
                api_key=None,  # Will use environment variable
                temperature=0.7,
            )
            return create_llm_model(fallback_config)
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            raise ValueError(
                f"Failed to configure model: {e}. Fallback also failed: {fallback_error}"
            )
