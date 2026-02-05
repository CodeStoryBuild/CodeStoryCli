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

import subprocess

import typer

from codestory.commands.config import set_config
from codestory.constants import (
    DEFAULT_EMBEDDING_MODEL,
    LOCAL_PROVIDERS,
    ONBOARDING_FLAG,
    get_cloud_providers,
)
from codestory.core.ui.theme import themed
from codestory.runtimeutil import confirm_strict

CODESTORY_ASCII = r"""
  ___  __  ____  ____    ____  ____  __  ____  _  _
 / __)/  \(    \(  __)  / ___)(_  _)/  \(  _ \( \/ )
( (__(  O )) D ( ) _)   \___ \  )( (  O ))   / )  /
 \___)\__/(____/(____)  (____/ (__) \__/(__\_)(__/
"""


def check_ollama_installed() -> bool:
    """Check if ollama is installed and accessible."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_ollama_models() -> list[str]:
    """Get list of available ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            models = [line.split()[0] for line in lines if line.strip()]
            return models
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def run_model_setup(scope: str):
    print(f"\n{themed('primary', '=== Model Setup ===')}")

    # Inform about supported providers
    local = sorted(LOCAL_PROVIDERS)
    cloud = sorted(get_cloud_providers())

    print(f"{themed('primary', 'Supported providers:')}")

    def _print_grouped(title: str, items: list[str], color_key: str):
        if not items:
            return
        print(f"  {themed(color_key, f'{title}:')}")
        # print up to 3 providers per line
        for i in range(0, len(items), 3):
            chunk = items[i : i + 3]
            print(f"    - {', '.join(chunk)}")

    _print_grouped("Local providers", local, "success")
    _print_grouped("Cloud providers", cloud, "primary")

    # Show expected format
    print()
    print(themed("primary", "Model format: provider:model"))
    print(
        themed("primary", "Examples: ollama:qwen2.5-coder:1.5b, openai:gpt-4o") + "\n"
    )

    # Prompt for model
    model_string = typer.prompt(
        themed("primary", "Enter model (format: ")
        + themed("label", "provider:model")
        + themed("primary", ")"),
    ).strip()
    while ":" not in model_string:
        print(themed("error", "Invalid format! Must be 'provider:model'"))
        model_string = typer.prompt(
            themed("primary", "Enter model (format: ")
            + themed("label", "provider:model")
            + themed("primary", ")")
        ).strip()

    set_config(key="model", value=model_string, scope=scope, quiet=True)

    provider = model_string.split(":")[0].lower()
    need_api_key = provider in get_cloud_providers()

    if need_api_key:
        # If provider is not local, ask for an optional API key and explain env var options
        print()
        print(
            themed(
                "primary",
                "This provider requires an API key, you may enter it now (optional).",
            )
        )
        print(
            themed(
                "primary", "You can also set the API key via environment variables: "
            )
            + themed("info", "CODESTORY_API_KEY")
            + themed("primary", " or the provider-specific standard var (e.g. ")
            + themed("info", provider.upper() + "_API_KEY")
            + themed("primary", ").")
        )
        api_key = typer.prompt(
            f"Enter API key for {provider} (leave blank to use environment variables)",
            hide_input=True,
            default="",
        ).strip()

        if api_key:
            set_config(key="api_key", value=api_key, scope=scope, quiet=True)
            need_set_api_key = False
        else:
            print(
                themed(
                    "warn",
                    "No API key provided. Please make sure to set as an environment variable.",
                )
            )
            need_set_api_key = True
    else:
        need_set_api_key = False

    print(f"\n{themed('success', f'✓ Model configured: {model_string}')}")
    if need_set_api_key:
        print(
            themed(
                "warn",
                "Codestory will exit for you to set your api key as an environment variable",
            )
        )
        print(
            themed("primary", "You can set the API key via environment variables: ")
            + themed("info", "CODESTORY_API_KEY")
            + themed("primary", " or the provider-specific standard var (e.g. ")
            + themed("info", provider.upper() + "_API_KEY")
            + themed("primary", ").")
        )
        print(
            themed(
                "primary",
                "After setting the environment variable, please rerun the codestory command.",
            )
        )

    return need_set_api_key


def run_embedding_setup(scope: str):
    print(f"\n{themed('primary', '=== Embedding Model Setup ===')}")

    try:
        from fastembed import TextEmbedding

        supported_models = [m["model"] for m in TextEmbedding.list_supported_models()]
    except Exception:
        supported_models = []

    if not confirm_strict(
        f"{themed('primary', 'Do you want to specify a custom embedding model? (Default: ')}"
        f"{themed('label', DEFAULT_EMBEDDING_MODEL)}{themed('primary', ')')}",
    ):
        return

    if supported_models:
        print(f"\n{themed('primary', 'Supported embedding models:')}")
        # print up to 2 models per line to keep it readable
        for i in range(0, len(supported_models), 2):
            chunk = supported_models[i : i + 2]
            print(f"    - {', '.join(chunk)}")

    print(
        f"\n{themed('primary', 'You can choose one from the list above or enter a custom model name.')}"
    )

    while True:
        model = typer.prompt(
            f"{themed('primary', 'Enter embedding model')}",
            default=DEFAULT_EMBEDDING_MODEL,
        ).strip()

        if not model:
            model = DEFAULT_EMBEDDING_MODEL
            break

        if model == DEFAULT_EMBEDDING_MODEL or model in supported_models:
            break

        print(f"{themed('warn', 'Invalid model!')}")

    set_config(key="custom_embedding_model", value=model, scope=scope, quiet=True)
    print(f"\n{themed('success', f'✓ Embedding model configured: {model}')}")


def run_onboarding():
    print(f"{themed('primary', CODESTORY_ASCII)}")
    print(
        f"{themed('primary', 'Welcome to CodeStory!')}\n"
        f"{themed('primary', '- We will help you configure your preferred AI model.')}\n"
        f"{themed('primary', '- These settings can be changed later using ')}{themed('label', 'cst config')}{themed('primary', '.')}\n"
    )

    confirm_strict(f"{themed('primary', 'Ready to start?')}", abort=True)

    # Ask if global or local config
    global_ = confirm_strict(
        "\nDo you want to set this as the global configuration (applies to all repos)?",
    )
    scope = "global" if global_ else "local"

    # Configure embedding grouper
    need_api_key = run_model_setup(scope)
    run_embedding_setup(scope)

    # Final message
    print(f"\n{themed('success', '✓ Configuration completed!')}")
    print(
        f"{themed('primary', 'There are many other configuration options available.')}"
    )
    print(
        f"You can view and change them at any time using: {themed('label', 'cst config')}\n"
    )

    return need_api_key


def check_run_onboarding(can_continue: bool) -> bool:
    # check a file in user config dir
    if not ONBOARDING_FLAG.exists():
        continue_ = run_onboarding()
        ONBOARDING_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ONBOARDING_FLAG.touch()
        if not continue_:
            raise typer.Exit(0)
        elif can_continue:
            print("Now continuing with command...\n")
        return True
    else:
        return False


def set_ran_onboarding():
    if not ONBOARDING_FLAG.exists():
        ONBOARDING_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ONBOARDING_FLAG.touch()
