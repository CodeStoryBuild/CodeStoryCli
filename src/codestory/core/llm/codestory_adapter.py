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
import logging
import os
from dataclasses import dataclass

import litellm
from loguru import logger

from codestory.core.exceptions import LLMInitError

# Disable LiteLLM logging at module level to prevent any logging worker errors
os.environ["LITELLM_LOG"] = "CRITICAL"
litellm.success_callback = []
litellm.failure_callback = []
litellm.completion_call_details_callback = []
litellm.callbacks = []
litellm.logging = False
litellm.set_verbose = False
litellm.suppress_debug_info = True
litellm.drop_params = True


logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM Proxy").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM Router").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM API").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)


@dataclass
class ModelConfig:
    """
    Configuration for the LLM Adapter.
    model_string format: "provider/model_name" (e.g. "openai/gpt-4o")
    """

    model_string: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class CodeStoryAdapter:
    """
    A unified interface for calling LLM APIs using LiteLLM.
    Supports sync and async invocation with batched parallel calls.
    Supports all LiteLLM providers via the provider/model format.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.model_string = config.model_string
        self._loop = None

    def close(self):
        """Cleanup method to properly close the event loop."""
        # Close the persistent event loop if it exists
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

    # --- Unified Invocation Methods ---

    def invoke(self, messages: str | list[dict[str, str]]) -> str:
        """Unified sync invoke method. Returns the content string."""
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        logger.debug(f"Invoking {self.model_string} (sync)")

        try:
            response = litellm.completion(
                model=self.model_string,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )
            return response.choices[0].message.content

        except litellm.AuthenticationError as e:
            provider = self.model_string.partition("/")[0]
            raise LLMInitError(
                f"Authentication failed for {provider}. "
                f"Please check your API key is set correctly. "
                f"Error: {str(e)}"
            )
        except litellm.NotFoundError as e:
            raise LLMInitError(
                f"Model {self.model_string} not found. "
                f"Please check the model name is correct. "
                f"Error: {str(e)}"
            )
        except litellm.RateLimitError as e:
            raise LLMInitError(
                f"Rate limit exceeded for {self.model_string}. "
                f"Please try again later. "
                f"Error: {str(e)}"
            )
        except litellm.APIConnectionError as e:
            raise LLMInitError(
                f"Failed to connect to API for {self.model_string}. "
                f"Please check your internet connection. "
                f"Error: {str(e)}"
            )
        except Exception as e:
            raise LLMInitError(f"LLM request failed for {self.model_string}: {str(e)}")

    async def async_invoke(self, messages: str | list[dict[str, str]]) -> str:
        """Unified async invoke method. Returns the content string."""
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        logger.debug(f"Invoking {self.model_string} (async)")

        try:
            response = await litellm.acompletion(
                model=self.model_string,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )
            return response.choices[0].message.content

        except litellm.AuthenticationError as e:
            provider = self.model_string.split("/")[0]
            raise LLMInitError(
                f"Authentication failed for {provider}. "
                f"Please check your API key is set correctly. "
                f"Error: {str(e)}"
            ) from e
        except litellm.NotFoundError as e:
            raise LLMInitError(
                f"Model {self.model_string} not found. "
                f"Please check the model name is correct. "
                f"Error: {str(e)}"
            ) from e
        except litellm.RateLimitError as e:
            raise LLMInitError(
                f"Rate limit exceeded for {self.model_string}. "
                f"Please try again later. "
                f"Error: {str(e)}"
            ) from e
        except litellm.APIConnectionError as e:
            raise LLMInitError(
                f"Failed to connect to API for {self.model_string}. "
                f"Please check your internet connection. "
                f"Error: {str(e)}"
            ) from e
        except Exception as e:
            raise LLMInitError(
                f"LLM request failed for {self.model_string}: {str(e)}"
            ) from e

    async def async_invoke_batch(
        self,
        batch: list[str | list[dict[str, str]]],
        max_concurrent: int = 10,
        sleep_between_tasks: float = -1,
    ) -> list[str]:
        """Run a batch of invocations in parallel and return list of responses."""
        # Lower concurrency for local models
        if self.model_string.startswith("ollama/") and max_concurrent > 3:
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

        tasks = [asyncio.create_task(sem_task(item)) for item in batch]

        # Use wait with FIRST_EXCEPTION to fail fast on any error
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        # Check if any task raised an exception
        for task in done:
            if task.exception() is not None:
                # Cancel all pending tasks
                for pending_task in pending:
                    pending_task.cancel()
                # Raise the first exception found
                raise task.exception()

        # If no exceptions, wait for all tasks to complete
        if pending:
            done, _ = await asyncio.wait(pending)

        # Collect all results
        return [task.result() for task in tasks]

    def invoke_batch(
        self, batch: list[str | list[dict[str, str]]], max_concurrent: int = 10
    ) -> list[str]:
        """
        Synchronous convenience wrapper for batched calls.
        Reuses the same event loop to avoid conflicts with litellm's logging worker.
        """
        # No running loop - create or reuse a persistent loop
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        return self._loop.run_until_complete(
            self.async_invoke_batch(batch, max_concurrent)
        )
