# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from ..exceptions import ConfigurationError
from .factory import ModelConfig, create_llm_model


def try_create_model(
    model_arg: str | None, api_key_arg: str | None, temperature: float
) -> BaseChatModel | None:
    """
    Configure the LLM model based on command-line arguments, .codestoryconfig, or defaults.

    Priority:
    1. Command-line arguments (--model, --api-key)
    2. .codestoryconfig file
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

    if not (isinstance(temperature, float) or isinstance(temperature, int)):
        raise ConfigurationError("Temperature must be a number.")    

    if temperature < 0 or temperature > 1:
        raise ConfigurationError("Temperature must be between 0 and 1.")

    if model_arg == "no-model" or model_arg is None:
        # explicit no model usage (will default to single grouper)
        logger.warning("No model specified. Using no logical grouping.")
        return None

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
        temperature=temperature,
    )

    # Create and return the model
    return create_llm_model(model_config)
