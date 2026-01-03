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

import asyncio
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
    Supports sync and async invocation with batched parallel calls.
    """

    def __init__(self, config: ModelConfig):
        import httpx

        self.config = config
        self.provider, self.model_name = self._parse_model_string(config.model_string)
        self.api_key = config.api_key or self._get_env_key()

        # Shared sync client for connection pooling
        self.client = httpx.Client(timeout=60.0)

        # Async client created lazily to avoid event loop issues
        self._async_client = None  # type: httpx.AsyncClient | None

        # Persistent event loop for sync batch calls
        self._loop = None

    def _get_async_client(self):
        import httpx

        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=60.0)
        return self._async_client

    def _get_loop(self):
        """Get or create a persistent event loop for sync batch calls."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def close(self):
        """Close the synchronous client and event loop."""
        self.client.close()
        if self._loop and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

    async def aclose(self):
        """Close the asynchronous client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def _parse_model_string(self, model_string: str) -> tuple[str, str]:
        """Parses 'provider:model' string."""
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

    # --- Unified Invocation Methods ---

    def invoke(self, messages: str | list[dict[str, str]]) -> str:
        """Unified sync invoke method. Returns the content string."""
        import httpx

        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        logger.debug(f"Invoking {self.provider}:{self.model_name} (sync)")

        try:
            url, headers, payload = self._prepare_request(messages)
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return self._parse_response(response)

        except httpx.HTTPStatusError as e:
            logger.error(f"API Error ({e.response.status_code}): {e.response.text}")
            raise ConfigurationError(
                f"{self.provider} API failed: {e.response.text}"
            ) from e
        except Exception as e:
            logger.exception("LLM Request failed")
            raise e

    async def async_invoke(self, messages: str | list[dict[str, str]]) -> str:
        """Unified async invoke method. Returns the content string."""
        import httpx

        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        logger.debug(f"Invoking {self.provider}:{self.model_name} (async)")

        try:
            client = self._get_async_client()
            url, headers, payload = self._prepare_request(messages)
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return self._parse_response(response)

        except httpx.HTTPStatusError as e:
            logger.error(f"API Error ({e.response.status_code}): {e.response.text}")
            raise ConfigurationError(
                f"{self.provider} API failed: {e.response.text}"
            ) from e
        except Exception as e:
            logger.exception("LLM Request failed")
            raise e

    async def async_invoke_batch(
        self,
        batch: list[str | list[dict[str, str]]],
        max_concurrent: int = 10,
        sleep_between_tasks: float = -1,
    ) -> list[str]:
        """Run a batch of invocations in parallel and return list of responses."""
        if self.provider == "ollama" and max_concurrent > 3:
            logger.debug(
                "When using ollama, max_concurrent will be lowered to a maximum of 3"
            )
            max_concurrent = 3

        semaphore = asyncio.Semaphore(max_concurrent)

        async def sem_task(item):
            async with semaphore:
                if sleep_between_tasks > 0:
                    await asyncio.sleep(sleep_between_tasks)

                return await self.async_invoke(item)

        tasks = [sem_task(item) for item in batch]
        results = await asyncio.gather(*tasks)
        return results

    def invoke_batch(
        self, batch: list[str | list[dict[str, str]]], max_concurrent: int = 10
    ) -> list[str]:
        """
        Synchronous convenience wrapper for batched calls.
        Safe for multiple calls in a CLI by reusing a persistent event loop.
        """
        loop = self._get_loop()
        return loop.run_until_complete(self.async_invoke_batch(batch, max_concurrent))

    def _prepare_request(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, dict, dict]:
        """
        Routes to specific provider logic to generate URL, Headers, and JSON Payload.
        Returns: (url, headers, payload)
        """
        if self.provider == "openai":
            return self._prepare_openai(messages)
        elif self.provider == "anthropic":
            return self._prepare_anthropic(messages)
        elif self.provider in ["gemini", "google"]:
            return self._prepare_gemini(messages)
        elif self.provider == "ollama":
            return self._prepare_ollama(messages)
        else:
            raise ConfigurationError(f"Unsupported provider: {self.provider}")

    def _parse_response(self, response) -> str:
        """Routes response JSON parsing to specific provider logic."""
        if self.provider == "openai":
            return response.json()["choices"][0]["message"]["content"]
        elif self.provider == "anthropic":
            return response.json()["content"][0]["text"]
        elif self.provider in ["gemini", "google"]:
            return self._parse_gemini_response(response)
        elif self.provider == "ollama":
            return response.json()["message"]["content"]
        return ""

    # --- Provider Specific Implementations ---

    def _prepare_openai(self, messages: list[dict[str, str]]):
        if not self.api_key:
            raise ConfigurationError("Missing OPENAI_API_KEY")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens:
            payload["max_completion_tokens"] = self.config.max_tokens

        return url, headers, payload

    def _prepare_anthropic(self, messages: list[dict[str, str]]):
        if not self.api_key:
            raise ConfigurationError("Missing ANTHROPIC_API_KEY")

        system_prompt = None
        filtered_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                filtered_messages.append(m)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": filtered_messages,
            "max_tokens": self.config.max_tokens or 1024,
            "temperature": self.config.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        return url, headers, payload

    def _prepare_gemini(self, messages: list[dict[str, str]]):
        if not self.api_key:
            raise ConfigurationError("Missing GEMINI_API_KEY")

        gemini_contents = []
        system_instruction = None

        for m in messages:
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
                continue
            role = "model" if m["role"] == "assistant" else "user"
            gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {}  # API key is in URL
        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens or 1024,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        return url, headers, payload

    def _parse_gemini_response(self, response) -> str:
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            logger.error(f"Gemini response structure unexpected: {response.text}")
            raise ConfigurationError(
                "Gemini refused to generate content (likely safety filter)."
            )

    def _prepare_ollama(self, messages: list[dict[str, str]]):
        base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        url = f"{base_url}/api/chat"
        headers = {}
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "keep_alive": -1,
            "options": {"temperature": self.config.temperature},
        }
        return url, headers, payload
