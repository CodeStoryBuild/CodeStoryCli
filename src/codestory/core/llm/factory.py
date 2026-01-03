# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import os
from dataclasses import dataclass

from loguru import logger

from codestory.core.exceptions import ConfigurationError


@dataclass
class ModelConfig:
    """
    Configuration for the LLM Adapter.
    model_string format: "provider:model_name" (e.g. "openai:gpt-4o")
    """

    model_string: str
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class CodeStoryAdapter:
    """
    A unified, lightweight interface for calling LLM APIs.
    Zero heavy dependencies (only httpx).
    """

    def __init__(self, config: ModelConfig):
        import httpx

        self.config = config
        self.provider, self.model_name = self._parse_model_string(config.model_string)
        self.api_key = config.api_key or self._get_env_key()

        # Shared client for connection pooling
        self.client = httpx.Client(timeout=60.0)

    def _parse_model_string(self, model_string: str) -> tuple[str, str]:
        """
        Parses 'provider:model' string.
        """
        if ":" not in model_string:
            raise ConfigurationError(f"Invalid model: {model_string}!")

        provider, model = model_string.split(":", 1)
        return provider.lower(), model

    def _get_env_key(self) -> str | None:
        """Fetch API key from environment based on provider."""
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        env_var = key_map.get(self.provider)
        return os.getenv(env_var) if env_var else None

    def invoke(self, messages: str | list[dict[str, str]]) -> str:
        """
        Unified invoke method. Returns the content string.
        """
        import httpx

        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        logger.debug(f"Invoking {self.provider}:{self.model_name}")

        try:
            if self.provider == "openai":
                return self._call_openai(messages)
            elif self.provider == "anthropic":
                return self._call_anthropic(messages)
            elif self.provider in ["gemini", "google"]:
                return self._call_gemini(messages)
            elif self.provider == "ollama":
                return self._call_ollama(messages)
            else:
                raise ConfigurationError(f"Unsupported provider: {self.provider}")
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error ({e.response.status_code}): {e.response.text}")
            raise ConfigurationError(
                f"{self.provider} API failed: {e.response.text}"
            ) from e
        except Exception as e:
            logger.exception("LLM Request failed")
            raise e

    # --- Provider Implementations ---

    def _call_openai(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise ConfigurationError("Missing OPENAI_API_KEY")

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens:
            payload["max_completion_tokens"] = self.config.max_tokens

        response = self.client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _call_anthropic(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise ConfigurationError("Missing ANTHROPIC_API_KEY")

        # Anthropic: System prompt is a top-level parameter
        system_prompt = None
        filtered_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                filtered_messages.append(m)

        payload = {
            "model": self.model_name,
            "messages": filtered_messages,
            "max_tokens": self.config.max_tokens or 1024,
            "temperature": self.config.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    def _call_gemini(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise ConfigurationError("Missing GEMINI_API_KEY")

        # Gemini: Map standard messages to "contents" and "parts"
        gemini_contents = []
        system_instruction = None

        for m in messages:
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
                continue

            role = "model" if m["role"] == "assistant" else "user"
            gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens or 1024,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        response = self.client.post(url, json=payload)
        response.raise_for_status()
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            # Handle cases where safety filters block the response
            logger.error(f"Gemini response structure unexpected: {response.text}")
            raise ConfigurationError(
                "Gemini refused to generate content (likely safety filter)."
            )

    def _call_ollama(self, messages: list[dict[str, str]]) -> str:
        base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # Using Ollama's /api/chat endpoint
        response = self.client.post(
            f"{base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.config.temperature},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
