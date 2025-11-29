# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
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

import os
import tomllib
from dataclasses import fields
from pathlib import Path
from textwrap import shorten
from typing import Any, Literal

import typer
from colorama import Fore, Style, init
from platformdirs import user_config_dir

from ..context import GlobalConfig

# Initialize colorama
init(autoreset=True)


def display_config(
    data: list[dict],
    description_field: str = "Description",
    key_field: str = "Key",
    value_field: str = "Value",
    source_field: str = "Source",
    max_value_length: int = 50,
) -> None:
    """
    Display config data in a two-line format:
    Key: Description
      Value (Source)
    """
    for item in data:
        key = str(item.get(key_field, ""))
        description = str(item.get(description_field, ""))
        value = str(item.get(value_field, ""))
        source = str(item.get(source_field, ""))

        # Truncate value if too long
        value_display = shorten(value, width=max_value_length, placeholder="...")

        # Line 1: Key + Description
        print(
            f"{Fore.CYAN}{Style.BRIGHT}{key}{Style.RESET_ALL}: "
            f"{Fore.WHITE}{description}{Style.RESET_ALL}"
        )
        # Line 2: Value + Source (Indented)
        print(
            f"  {Fore.GREEN}{value_display}{Style.RESET_ALL} "
            f"{Fore.YELLOW}({source}){Style.RESET_ALL}"
        )
        print()  # Spacer


def _get_config_schema() -> dict[str, dict[str, Any]]:
    """Get the schema of available config options from GlobalConfig."""
    # Descriptions for each config field
    descriptions = {
        "model": "LLM model (format: provider:model, e.g., openai:gpt-4)",
        "api_key": "API key for the LLM provider",
        "temperature": "Temperature for LLM responses (0.0-1.0)",
        "aggresiveness": "How aggressively to split commits smaller",
        "verbose": "Enable verbose logging output",
        "auto_accept": "Automatically accept all prompts without user confirmation",
        "silent": "Do not output any text to the console, except for prompting acceptance",
    }

    schema = {}
    for field in fields(GlobalConfig):
        field_name = field.name
        # Get the type annotation if possible, defaulting to str
        field_type = field.type
        default_value = field.default
        description = descriptions.get(field_name, "No description available")
        
        schema[field_name] = {
            "description": description, 
            "default": default_value,
            "type": field_type
        }

    return schema


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if it exceeds max_length."""
    text_str = str(text)
    if len(text_str) <= max_length:
        return text_str
    return text_str[: max_length - 3] + "..."


def _check_key_exists(key: str) -> dict:
    """Check if a config key exists. If not, show available options and exit."""
    schema = _get_config_schema()

    if key not in schema:
        print(f"{Fore.RED}Error:{Style.RESET_ALL} Unknown configuration key '{key}'\n")
        print(f"{Fore.WHITE}{Style.BRIGHT}Available configuration options:{Style.RESET_ALL}\n")

        table_data = []
        for config_key, info in sorted(schema.items()):
            default_str = str(info["default"]) if info["default"] is not None else "None"
            description = _truncate_text(info["description"], 60)
            table_data.append({
                "Key": config_key,
                "Description": description,
                "Value": default_str,
                "Source": "Default"
            })

        display_config(
            table_data, 
            description_field="Description", 
            key_field="Key", 
            value_field="Value", 
            source_field="Source", 
            max_value_length=80
        )
        raise typer.Exit(1)
    
    return schema[key]


def _help_callback(ctx: typer.Context, param, value: bool):
    """Typer/Click help callback: show help and exit when --help is provided"""
    if not value or ctx.resilient_parsing:
        return
    typer.echo(ctx.get_help())
    raise typer.Exit()


def _add_to_gitignore(config_filename: str) -> None:
    """Add config file to .gitignore if it exists, otherwise print warning."""
    gitignore_path = Path(".gitignore")

    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text()
        if config_filename not in gitignore_content:
            with gitignore_path.open("a") as f:
                if gitignore_content and not gitignore_content.endswith("\n"):
                    f.write("\n")
                f.write(f"{config_filename}\n")
            print(f"Added {config_filename} to .gitignore")
    else:
        print(
            f"{Fore.YELLOW}Warning:{Style.RESET_ALL} .gitignore not found. "
            f"Please consider adding {config_filename} to your .gitignore file to avoid committing API keys."
        )


def _set_config(key: str, value: str, scope: str) -> None:
    """Set a configuration value in the specified scope."""
    field_info = _check_key_exists(key)

    config_filename = "codestoryconfig.toml"

    if scope == "env":
        env_var = f"codestory_{key}"
        print(f"{Fore.GREEN}To set this as an environment variable:{Style.RESET_ALL}")
        print(f"  Windows (PowerShell): $env:{env_var}='{value}'")
        print(f"  Windows (CMD): set {env_var}={value}")
        print(f"  Linux/macOS: export {env_var}='{value}'")
        return

    # Determine config file path based on scope
    if scope == "global":
        config_path = Path(user_config_dir("codestory")) / config_filename
        config_path.parent.mkdir(parents=True, exist_ok=True)
    else:  # local
        config_path = Path(config_filename)
        _add_to_gitignore(config_filename)

    # Load existing config
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                config_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"Failed to parse existing config: {e}. Creating new config.")

    # Type Conversion
    # Inputs from CLI are always strings, but TOML supports types.
    # We check the GlobalConfig type annotation to convert properly.
    target_type = field_info.get("type", str)
    final_value = value

    if target_type == bool or target_type == bool | None:
        if value.lower() in ("true", "1", "yes", "on"):
            final_value = True
        elif value.lower() in ("false", "0", "no", "off"):
            final_value = False
    elif target_type == int or target_type == int | None:
        try:
            final_value = int(value)
        except ValueError:
            pass # Keep as string if it fails, or raise error

    # Update the value
    config_data[key] = final_value

    # Write back to file (Simple TOML serialization)
    with open(config_path, "w") as f:
        for k, v in config_data.items():
            if isinstance(v, bool):
                f.write(f"{k} = {str(v).lower()}\n")
            elif isinstance(v, (int, float)):
                f.write(f"{k} = {v}\n")
            else:
                f.write(f'{k} = "{v}"\n')

    scope_label = "global" if scope == "global" else "local"
    print(f"{Fore.GREEN}Set {key} = {final_value} ({scope_label}){Style.RESET_ALL}")
    print(f"Config file: {config_path.absolute()}")


def _get_config(key: str | None, scope: str | None) -> None:
    """Get configuration value(s) from the specified scope or all scopes."""
    config_filename = "codestoryconfig.toml"
    schema = _get_config_schema()

    if key is not None:
        _check_key_exists(key)

    # 1. Gather all sources
    # Priority order for display: Local > Env > Global
    sources = []

    # Local
    if scope is None or scope == "local":
        local_path = Path(config_filename)
        if local_path.exists():
            try:
                with open(local_path, "rb") as f:
                    local_config = tomllib.load(f)
                    sources.append(("Local Config", local_path, local_config))
            except tomllib.TOMLDecodeError:
                pass

    # Env
    if scope is None or scope == "env":
        env_config = {k[10:]: v for k, v in os.environ.items() if k.lower().startswith("codestory_")}
        if env_config:
            sources.append(("Environment", None, env_config))

    # Global
    if scope is None or scope == "global":
        global_path = Path(user_config_dir("codestory")) / config_filename
        if global_path.exists():
            try:
                with open(global_path, "rb") as f:
                    global_config = tomllib.load(f)
                    sources.append(("Global Config", global_path, global_config))
            except tomllib.TOMLDecodeError:
                pass

    # 2. Display Logic
    table_data = []

    if key:
        # User requested a specific key
        found = False
        description = schema[key]["description"]
        
        # Check explicit sources
        for source_name, _, config_data in sources:
            if key in config_data:
                found = True
                val = _truncate_text(str(config_data[key]), 60)
                table_data.append({
                    "Key": key, 
                    "Description": description, 
                    "Value": val, 
                    "Source": source_name
                })
        
        # If not found in any active source, show the system default
        if not found:
            default_val = schema[key]["default"]
            val_str = str(default_val) if default_val is not None else "None"
            table_data.append({
                "Key": key,
                "Description": description,
                "Value": val_str,
                "Source": "System Default (Not Set)"
            })
        
        display_config(table_data)

    else:
        # List all keys
        for k in sorted(schema.keys()):
            description = schema[k]["description"]
            
            # Find the active value (first match in priority: Local -> Env -> Global)
            active_val = None
            active_source = None
            
            for source_name, _, config_data in sources:
                if k in config_data:
                    active_val = config_data[k]
                    active_source = source_name
                    break
            
            if active_val is not None:
                table_data.append({
                    "Key": k, 
                    "Description": description, 
                    "Value": str(active_val), 
                    "Source": active_source
                })
            else:
                # Fallback to default
                default_val = schema[k]["default"]
                val_str = str(default_val) if default_val is not None else "None"
                table_data.append({
                    "Key": k, 
                    "Description": description, 
                    "Value": val_str, 
                    "Source": f"Default"
                })

        display_config(table_data)


def main(
    ctx: typer.Context,
    help: bool = typer.Option(
        False,
        "--help",
        callback=_help_callback,
        is_eager=True,
        help="Show this message and exit.",
    ),
    key: str | None = typer.Argument(None, help="Configuration key to get or set."),
    value: str | None = typer.Argument(
        None, help="Value to set (omit to get current value)."
    ),
    scope: Literal["local", "global", "env"] = typer.Option(
        None,
        "--scope",
        help="Select which scope to modify. Defaults to local for setting, all for getting.",
    ),
) -> None:
    """
    Manage global and local codestory configurations.

    Priority order: program arguments > custom config > local config > environment variables > global config

    Examples:
        # Get a configuration value
        codestory config model

        # Set a local configuration value
        codestory config model "gemini:gemini-2.0-flash"

        # Set a global configuration value
        codestory config model "openai:gpt-4" --scope global

        # Show all configuration
        codestory config
    """
    
    # Determine operation
    if value is not None:
        # SET operation
        if key is None:
            print(f"{Fore.RED}Error:{Style.RESET_ALL} Key is required when setting a value")
            raise typer.Exit(1)
        
        # Default to local if setting and no scope provided
        target_scope = scope if scope is not None else "local"
        _set_config(key, value, target_scope)
    else:
        # GET operation
        # If scope is None here, _get_config handles searching all scopes
        _get_config(key, scope)