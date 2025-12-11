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
import sys

import typer
from colorama import Fore, Style

from codestory.commands.config import set_config
from codestory.constants import ONBOARDING_FLAG

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


def run_embedding_grouper_setup(scope: str):
    """Configure embedding grouper with model recommendations."""
    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}=== Embedding Grouper Setup ==={Style.RESET_ALL}"
    )
    print(
        f"{Fore.YELLOW}Note: Embedding grouper uses clustering with embeddings to group related changes."
    )
    print(
        f"It makes MANY batched API calls, so local models (Ollama) are STRONGLY recommended.{Style.RESET_ALL}\n"
    )

    # Check if ollama is installed
    ollama_available = check_ollama_installed()

    if ollama_available:
        # Get available models
        available_models = get_ollama_models()

        if available_models:
            print(f"{Fore.GREEN}Available Ollama models:{Style.RESET_ALL}")
            for model in available_models:
                print(f"  - {model}")
            print()
    else:
        print(f"{Fore.YELLOW}Ollama not detected.{Style.RESET_ALL}")
        print(
            f"{Fore.WHITE}You can download Ollama from https://ollama.com{Style.RESET_ALL}"
        )
        print(
            f"{Fore.WHITE}After installing, run: ollama pull [your model]{Style.RESET_ALL}"
        )
        print(
            f"{Fore.WHITE}Then you can set this with: cst config model ollama/[your model]{Style.RESET_ALL}\n"
        )

    # Prompt for model
    print(f"{Fore.WHITE}Model format: provider/model{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}Examples: ollama/qwen2.5-coder:1.5b, openai/gpt-4o{Style.RESET_ALL}\n"
    )
    print(f"{Fore.WHITE}Recommended model: ollama/qwen2.5-coder:1.5b{Style.RESET_ALL}")

    model_string = typer.prompt("Enter model (format: provider/model)")

    # Validate format
    if "/" not in model_string and ":" not in model_string:
        print(f"{Fore.RED}Invalid format! Must be 'provider/model'{Style.RESET_ALL}")
        sys.exit(1)

    # Warn if not using Ollama
    if not model_string.lower().startswith("ollama"):
        print(
            f"\n{Fore.RED}⚠ WARNING: Embedding grouper will make MANY API calls. This can be expensive with cloud providers.{Style.RESET_ALL}\n"
        )

    # Extract provider and prompt for API key if needed
    separator = "/" if "/" in model_string else ":"
    provider = model_string.split(separator)[0].lower()

    if provider != "ollama":
        api_key = typer.prompt(f"Enter API key for {provider}", hide_input=True)
        set_config(key="api_key", value=api_key, scope=scope)

    # Set configuration
    set_config(key="model", value=model_string, scope=scope)
    set_config(key="logical_grouping_type", value="embeddings", scope=scope)

    print(
        f"\n{Fore.GREEN}✓ Embedding grouper configured with {model_string}!{Style.RESET_ALL}"
    )


def run_brute_force_llm_setup(scope: str):
    """Configure brute force LLM grouper with model recommendations."""
    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}=== Brute Force LLM Grouper Setup ==={Style.RESET_ALL}"
    )
    print(
        f"{Fore.YELLOW}Note: Brute force LLM analyzes all changes in a single pass to group them semantically."
    )
    print(
        f"It makes fewer API calls. Large cloud models are recommended for best results.{Style.RESET_ALL}\n"
    )

    # Show provider examples
    print(f"{Fore.WHITE}Popular providers (via LiteLLM):{Style.RESET_ALL}")
    print("  - openai, anthropic, gemini, google")
    print("  - groq, together, replicate, deepseek")
    print("  - cohere, mistral, perplexity, huggingface")
    print("  - ollama (local), and many more!\n")

    print(f"{Fore.WHITE}Model format: provider/model{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Examples:{Style.RESET_ALL}")
    print("  - openai/gpt-4o")
    print("  - anthropic/claude-3-5-sonnet-20241022")
    print("  - gemini/gemini-2.0-flash-exp")
    print("  - groq/llama-3.3-70b-versatile")
    print("  - ollama/qwen2.5-coder:7b\n")

    # Prompt for model
    model_string = typer.prompt("Enter model (format: provider/model)")

    # Validate format
    while "/" not in model_string:
        print(f"{Fore.RED}Invalid format! Must be 'provider/model'{Style.RESET_ALL}")
        model_string = typer.prompt("Enter model (format: provider/model)")

    provider = model_string.partition("/")[0]

    # Prompt for API key if not local provider
    if not model_string.startswith("ollama"):
        print(
            f"\n{Fore.WHITE}API key can be provided now or set via environment variables:{Style.RESET_ALL}"
        )
        print(f"  - LiteLLM format: {provider.upper()}_API_KEY")
        print("  - Or: CODESTORY_API_KEY\n")

        api_key = typer.prompt(
            f"Enter API key for {provider} (press Enter to skip if using env variables)",
            default="",
            show_default=False,
        )

        if api_key:
            set_config(key="api_key", value=api_key, scope=scope)

    # Set configuration
    set_config(key="model", value=model_string, scope=scope)
    set_config(key="logical_grouping_type", value="brute_force_llm", scope=scope)

    print(
        f"\n{Fore.GREEN}✓ Brute force LLM grouper configured with {model_string}!{Style.RESET_ALL}"
    )


def run_onboarding():
    print(f"{Fore.CYAN}{Style.BRIGHT}{CODESTORY_ASCII}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Style.BRIGHT}Welcome to CodeStory!{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}This is the first time you're running codestory. Let's get you set up!{Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}You can change any of these settings later using 'cst config'.{Style.RESET_ALL}\n"
    )

    print(f"{Fore.WHITE}{Style.BRIGHT}Press Enter to continue...{Style.RESET_ALL}")
    input()

    # Step 1: Choose grouping strategy
    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}=== Choose Grouping Strategy ==={Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}Which grouping method would you like to use?{Style.RESET_ALL}\n"
    )
    print(
        f"  1. {Fore.CYAN}Embedding Grouper{Style.RESET_ALL} - Uses clustering with embeddings"
    )
    print(
        f"     {Fore.YELLOW}Recommendation: Local models (Ollama) - makes many API calls{Style.RESET_ALL}"
    )
    print(
        f"\n  2. {Fore.CYAN}Brute Force LLM Grouper{Style.RESET_ALL} - Analyzes all changes in one pass"
    )
    print(
        f"     {Fore.YELLOW}Recommendation: Large cloud models - fewer calls, needs reasoning{Style.RESET_ALL}\n"
    )

    config_choice = typer.prompt("Enter choice (1 or 2)", type=int, default=2)

    # Ask if global or local config
    global_ = typer.confirm(
        "\nDo you want to set this as the global configuration (applies to all repos)?",
        default=True,
    )
    scope = "global" if global_ else "local"

    # Step 2: Configure chosen grouping strategy
    if config_choice == 1:
        run_embedding_grouper_setup(scope)
    else:
        run_brute_force_llm_setup(scope)

    # Final message
    print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ Configuration completed!{Style.RESET_ALL}")
    print(f"{Fore.WHITE}There are many other configuration options available.")
    print(
        f"You can view and change them at any time using: {Fore.CYAN}cst config{Style.RESET_ALL}\n"
    )

    return


def check_run_onboarding(exit_after: bool = True) -> None:
    # check a file in user config dir
    if not ONBOARDING_FLAG.exists():
        run_onboarding()
        ONBOARDING_FLAG.touch()
        if exit_after:
            raise typer.Exit(0)
        else:
            print("Now continuing with command...\n")
    else:
        return
