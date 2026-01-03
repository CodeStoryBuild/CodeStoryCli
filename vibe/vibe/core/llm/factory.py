"""Factory for creating LangChain LLM instances."""

import os
from dataclasses import dataclass
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""

    provider: str  # e.g., "openai", "gemini", "anthropic"
    model_name: str  # e.g., "gpt-4", "gemini-2.5-flash", "claude-3-5-sonnet"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


def create_llm_model(config: ModelConfig) -> BaseChatModel:
    """
    Create a LangChain chat model based on the provided configuration.

    Args:
        config: ModelConfig with provider, model_name, and optional api_key

    Returns:
        BaseChatModel instance configured for the specified provider

    Raises:
        ValueError: If the provider is unsupported or configuration is invalid
        ImportError: If required provider package is not installed
    """
    provider = config.provider.lower()
    api_key = config.api_key

    logger.info(
        f"Creating LLM model: provider={provider}, model={config.model_name}"
    )

    # OpenAI
    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is not installed. "
                "Install it with: pip install langchain-openai"
            )

        # Use provided API key or fall back to environment variable
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OpenAI API key not provided and OPENAI_API_KEY environment variable not set"
                )

        return ChatOpenAI(
            model=config.model_name,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    # Google Gemini
    elif provider == "gemini" or provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Install it with: pip install langchain-google-genai"
            )

        # Use provided API key or fall back to environment variable
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "Google API key not provided and GOOGLE_API_KEY environment variable not set"
                )

        return ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=api_key,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )

    # Anthropic Claude
    elif provider == "anthropic" or provider == "claude":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is not installed. "
                "Install it with: pip install langchain-anthropic"
            )

        # Use provided API key or fall back to environment variable
        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "Anthropic API key not provided and ANTHROPIC_API_KEY environment variable not set"
                )

        return ChatAnthropic(
            model=config.model_name,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    # Azure OpenAI
    elif provider == "azure" or provider == "azure-openai":
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is not installed. "
                "Install it with: pip install langchain-openai"
            )

        # Azure requires additional environment variables
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not azure_endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable not set"
            )

        if not api_key:
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "Azure OpenAI API key not provided and AZURE_OPENAI_API_KEY environment variable not set"
                )

        return AzureChatOpenAI(
            azure_deployment=config.model_name,
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    # Ollama (local models)
    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "langchain-ollama is not installed. "
                "Install it with: pip install langchain-ollama"
            )

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        return ChatOllama(
            model=config.model_name,
            base_url=base_url,
            temperature=config.temperature,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: openai, gemini, anthropic, azure, ollama"
        )


def get_default_model() -> ModelConfig:
    """
    Get the default model configuration (Gemini 2.5 Flash).

    Returns:
        ModelConfig for the default model
    """
    return ModelConfig(
        provider="gemini",
        model_name="gemini-2.0-flash-exp",
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.7,
    )
