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
import tomllib
from dataclasses import fields
from pathlib import Path
from textwrap import shorten
from typing import Any

import typer
from colorama import Fore, Style, init

from codestory.constants import (
    CONFIG_FILENAME,
    ENV_APP_PREFIX,
    GLOBAL_CONFIG_FILE,
    LOCAL_CONFIG_FILE,
)
from codestory.core.exceptions import ConfigurationError

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
    from codestory.context import GlobalConfig

    schema = {}

    for field in fields(GlobalConfig):
        field_name = field.name
        # Get the type annotation if possible, defaulting to str
        field_type = field.type
        default_value = field.default
        constraint = GlobalConfig.constraints.get(field_name)
        description = GlobalConfig.descriptions.get(
            field_name, "No description available"
        )

        schema[field_name] = {
            "description": description,
            "default": default_value,
            "type": field_type,
            "constraint": constraint,
        }

    return schema


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if it exceeds max_length."""
    text_str = str(text)
    if len(text_str) <= max_length:
        return text_str
    return text_str[: max_length - 3] + "..."


def _write_toml_config(config_path: Path, config_data: dict) -> None:
    """Write configuration data to a TOML file.

    Args:
        config_path: Path to the config file
        config_data: Dictionary of configuration values
    """
    with open(config_path, "w") as f:
        for k, v in config_data.items():
            if isinstance(v, bool):
                f.write(f"{k} = {str(v).lower()}\n")
            elif isinstance(v, (int, float)):
                f.write(f"{k} = {v}\n")
            else:
                f.write(f"{k} = '{v}'\n")


def _load_toml_config(config_path: Path) -> dict:
    """Load configuration from a TOML file.

    Args:
        config_path: Path to the config file

    Returns:
        Dictionary of configuration values, or empty dict if file doesn't exist

    Raises:
        ConfigurationError: If the TOML file is malformed
    """
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigurationError(f"Failed to parse config at {config_path}: {e}")


def _format_value_for_display(value: Any) -> str:
    """Format a configuration value for display.

    Args:
        value: The value to format

    Returns:
        Formatted string representation of the value
    """
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    else:
        return f"'{value}'"


def _print_env_instructions(key: str, value: str, is_delete: bool = False) -> None:
    """Print instructions for setting/deleting environment variables.

    Args:
        key: Configuration key
        value: Configuration value (only used for set operations)
        is_delete: Whether this is a delete operation
    """
    env_var = f"{ENV_APP_PREFIX}{key.upper()}"

    if is_delete:
        print(
            f"{Fore.YELLOW}Info:{Style.RESET_ALL} Cannot delete environment variables through cst."
        )
        print("Please delete them through your terminal/OS:")
        print(f"  Windows (PowerShell): Remove-Item Env:\\{env_var}")
        print(f"  Windows (CMD): set {env_var}=")
        print(f"  Linux/macOS: unset {env_var}")
    else:
        print(f"{Fore.GREEN}To set this as an environment variable:{Style.RESET_ALL}")
        print(f"  Windows (PowerShell): $env:{env_var}='{value}'")
        print(f"  Windows (CMD): set {env_var}={value}")
        print(f"  Linux/macOS: export {env_var}='{value}'")


def _delete_key_from_config(config_path: Path, key: str, scope: str) -> bool:
    """Delete a specific key from a configuration file.

    Args:
        config_path: Path to the config file
        key: The key to delete
        scope: The scope name (for display purposes)

    Returns:
        True if the key was deleted, False if it wasn't found
    """
    config_data = _load_toml_config(config_path)

    if not config_data:
        print(f"{Fore.YELLOW}Info:{Style.RESET_ALL} No {scope} config file found")
        return False

    if key not in config_data:
        print(
            f"{Fore.YELLOW}Info:{Style.RESET_ALL} Key '{key}' not found in {scope} config"
        )
        return False

    del config_data[key]

    if config_data:
        _write_toml_config(config_path, config_data)
    else:
        config_path.unlink()
        print(f"Removed empty config file: {config_path}")

    print(f"{Fore.GREEN}Deleted {key} from {scope} config{Style.RESET_ALL}")
    return True


def _delete_all_from_config(config_path: Path, scope: str) -> bool:
    """Delete all keys from a configuration file.

    Args:
        config_path: Path to the config file
        scope: The scope name (for display purposes)

    Returns:
        True if config was deleted, False if file didn't exist or was already empty
    """
    config_data = _load_toml_config(config_path)

    if not config_data:
        print(
            f"{Fore.YELLOW}Info:{Style.RESET_ALL} {scope.capitalize()} config is already empty"
        )
        return False

    config_path.unlink()
    print(f"{Fore.GREEN}Deleted all config from {scope} scope{Style.RESET_ALL}")
    return True


def print_describe_options():
    schema = _get_config_schema()

    print(
        f"{Fore.WHITE}{Style.BRIGHT}Available configuration options:{Style.RESET_ALL}\n"
    )

    table_data = []
    for config_key, info in sorted(schema.items()):
        default_str = str(info["default"]) if info["default"] is not None else "None"
        description = _truncate_text(info["description"], 100)
        table_data.append(
            {
                "Key": config_key,
                "Description": description,
                "Value": default_str,
                "Source": "Options: " + str(info["constraint"]),
            }
        )

    display_config(
        table_data,
        description_field="Description",
        key_field="Key",
        value_field="Value",
        source_field="Source",
        max_value_length=80,
    )


def _check_key_exists(key: str, exit_on_fail: bool = True) -> dict:
    """Check if a config key exists.

    If not, show available options and exit.
    """
    schema = _get_config_schema()

    if key not in schema:
        print(f"{Fore.RED}Error:{Style.RESET_ALL} Unknown configuration key '{key}'\n")
        print_describe_options()
        if exit_on_fail:
            raise typer.Exit(1)

    return schema[key]


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


def set_config(key: str, value: str, scope: str) -> None:
    """Set a configuration value in the specified scope.

    Args:
        key: Configuration key to set
        value: Value to set (as string from CLI)
        scope: Scope to set the value in (local, global, or env)
    """
    field_info = _check_key_exists(key)

    if scope == "env":
        _print_env_instructions(key, value)
        return

    # Check for sensitive keys in local scope
    if scope == "local" and key in ("api_key",):
        print(
            f"{Fore.YELLOW}Warning:{Style.RESET_ALL} You are setting a sensitive key ('{key}') in local configuration."
        )
        if not typer.confirm("Are you sure you want to proceed?", default=False):
            print("Operation cancelled.")
            raise typer.Exit(0)

    # Determine config file path based on scope
    if scope == "global":
        config_path = GLOBAL_CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)
    else:  # local
        config_path = LOCAL_CONFIG_FILE
        _add_to_gitignore(CONFIG_FILENAME)

    # Load existing config
    try:
        config_data = _load_toml_config(config_path)
    except ConfigurationError as e:
        print(f"{Fore.YELLOW}Warning:{Style.RESET_ALL} {e}. Creating new config.")
        config_data = {}

    # Coerce and validate the value using the constraint
    constraint = field_info.get("constraint")
    try:
        final_value = constraint.coerce(value)
    except ConfigurationError as e:
        print(f"{Fore.RED}Error:{Style.RESET_ALL} Invalid value for {key}: {e}")
        raise typer.Exit(1)

    # Update and save
    config_data[key] = final_value
    _write_toml_config(config_path, config_data)

    # Display success message
    scope_label = "global" if scope == "global" else "local"
    display_value = _format_value_for_display(final_value)
    print(f"{Fore.GREEN}Set {key} = {display_value} ({scope_label}){Style.RESET_ALL}")
    print(f"Config file: {config_path.absolute()}")


def get_config(key: str | None, scope: str | None) -> None:
    """Get configuration value(s) from the specified scope or all scopes.

    Args:
        key: Specific key to get, or None to get all keys
        scope: Scope to search (local, global, env), or None to search all
    """
    schema = _get_config_schema()

    if key is not None:
        _check_key_exists(key)

    # Gather all sources (Priority order for display: Local > Env > Global)
    sources = []

    # Local
    if (scope is None or scope == "local") and LOCAL_CONFIG_FILE.exists():
        try:
            local_config = _load_toml_config(LOCAL_CONFIG_FILE)
            if local_config:
                sources.append(
                    ("Set from: Local Config", LOCAL_CONFIG_FILE, local_config)
                )
        except ConfigurationError:
            pass

    # Env
    if scope is None or scope == "env":
        env_config = {
            k[len(ENV_APP_PREFIX) :]: v
            for k, v in os.environ.items()
            if k.lower().startswith(ENV_APP_PREFIX.lower())
        }
        if env_config:
            sources.append(("Environment", None, env_config))

    # Global
    if (scope is None or scope == "global") and GLOBAL_CONFIG_FILE.exists():
        try:
            global_config = _load_toml_config(GLOBAL_CONFIG_FILE)
            if global_config:
                sources.append(
                    ("Set from: Global Config", GLOBAL_CONFIG_FILE, global_config)
                )
        except ConfigurationError:
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
                table_data.append(
                    {
                        "Key": key,
                        "Description": description,
                        "Value": val,
                        "Source": source_name,
                    }
                )

        # If not found in any active source, show the system default
        if not found:
            default_val = schema[key]["default"]
            val_str = str(default_val) if default_val is not None else "None"
            table_data.append(
                {
                    "Key": key,
                    "Description": description,
                    "Value": val_str,
                    "Source": "System Default (Not Set)",
                }
            )

        if found:
            print(
                f"{Fore.WHITE}{Style.BRIGHT}Configuration for key={key} displayed in order of priority:{Style.RESET_ALL}"
            )

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
                table_data.append(
                    {
                        "Key": k,
                        "Description": description,
                        "Value": str(active_val),
                        "Source": active_source,
                    }
                )
            else:
                # Fallback to default
                default_val = schema[k]["default"]
                val_str = str(default_val) if default_val is not None else "None"
                table_data.append(
                    {
                        "Key": k,
                        "Description": description,
                        "Value": val_str,
                        "Source": "Default",
                    }
                )

        display_config(table_data)


def delete_config(key: str | None, scope: str) -> None:
    """Delete configuration value(s) from the specified scope.

    Args:
        key: Specific key to delete, or None to delete all
        scope: Scope to delete from (local, global, or env)
    """
    if scope == "env":
        if key is not None:
            _print_env_instructions(key, "", is_delete=True)
        else:
            print(
                f"{Fore.YELLOW}Info:{Style.RESET_ALL} Cannot delete environment variables through cst."
            )
            print("Please delete them through your terminal/OS:")
            print(f"  Windows (PowerShell): Remove-Item Env:\\{ENV_APP_PREFIX}*")
            print(f"  Windows (CMD): set {ENV_APP_PREFIX}*=")
            print(f"  Linux/macOS: unset {ENV_APP_PREFIX}*")
        return

    config_path = GLOBAL_CONFIG_FILE if scope == "global" else LOCAL_CONFIG_FILE

    if not config_path.exists():
        print(
            f"{Fore.YELLOW}Info:{Style.RESET_ALL} No {scope} config file found at {config_path}"
        )
        return

    # Load existing config
    try:
        config_data = _load_toml_config(config_path)
    except ConfigurationError as e:
        print(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        raise typer.Exit(1)

    if not config_data:
        print(
            f"{Fore.YELLOW}Info:{Style.RESET_ALL} {scope.capitalize()} config is already empty"
        )
        return

    if key is not None:
        # Delete specific key
        if key not in config_data:
            print(
                f"{Fore.YELLOW}Info:{Style.RESET_ALL} Key '{key}' not found in {scope} config"
            )
            return

        if not typer.confirm(
            f"Are you sure you want to delete '{key}' from {scope} config?"
        ):
            print("Delete cancelled.")
            return

        del config_data[key]
        print(f"{Fore.GREEN}Deleted {key} from {scope} config{Style.RESET_ALL}")
    else:
        # Delete all keys
        keys_list = ", ".join(config_data.keys())
        if not typer.confirm(
            f"Are you sure you want to delete ALL config from {scope} scope?\n"
            f"Keys to be deleted: {keys_list}"
        ):
            print("Delete cancelled.")
            return

        config_data.clear()
        print(f"{Fore.GREEN}Deleted all config from {scope} scope{Style.RESET_ALL}")

    # Write back to file or remove if empty
    if config_data:
        _write_toml_config(config_path, config_data)
    else:
        config_path.unlink()
        print(f"Removed empty config file: {config_path}")


def deleteall_config(key: str | None) -> None:
    """Delete configuration value(s) from both global and local scopes.

    Args:
        key: Specific key to delete, or None to delete all
    """
    if key is not None:
        # Confirmation prompt for specific key across all scopes
        if not typer.confirm(
            f"Are you sure you want to delete '{key}' from BOTH global and local config?"
        ):
            print("Delete cancelled.")
            return

        print(f"\n{Fore.CYAN}Deleting from local scope:{Style.RESET_ALL}")
        if LOCAL_CONFIG_FILE.exists():
            try:
                _delete_key_from_config(LOCAL_CONFIG_FILE, key, "local")
            except ConfigurationError as e:
                print(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.YELLOW}Info:{Style.RESET_ALL} No local config file found")

        print(f"\n{Fore.CYAN}Deleting from global scope:{Style.RESET_ALL}")
        if GLOBAL_CONFIG_FILE.exists():
            try:
                _delete_key_from_config(GLOBAL_CONFIG_FILE, key, "global")
            except ConfigurationError as e:
                print(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.YELLOW}Info:{Style.RESET_ALL} No global config file found")
    else:
        # Delete all from both scopes
        if not typer.confirm(
            "Are you sure you want to delete ALL config from BOTH global and local scopes?"
        ):
            print("Delete cancelled.")
            return

        print(f"\n{Fore.CYAN}Deleting from local scope:{Style.RESET_ALL}")
        if LOCAL_CONFIG_FILE.exists():
            try:
                _delete_all_from_config(LOCAL_CONFIG_FILE, "local")
            except ConfigurationError as e:
                print(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.YELLOW}Info:{Style.RESET_ALL} No local config file found")

        print(f"\n{Fore.CYAN}Deleting from global scope:{Style.RESET_ALL}")
        if GLOBAL_CONFIG_FILE.exists():
            try:
                _delete_all_from_config(GLOBAL_CONFIG_FILE, "global")
            except ConfigurationError as e:
                print(f"{Fore.RED}Error:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.YELLOW}Info:{Style.RESET_ALL} No global config file found")


def describe_callback(ctx: typer.Context, param, value: bool):
    if not value or ctx.resilient_parsing:
        return

    print_describe_options()
    raise typer.Exit()


def run_config(
    key: str | None, value: str | None, scope: str | None, delete: bool, deleteall: bool
) -> None:
    # Check for conflicting operations
    if delete and deleteall:
        raise ConfigurationError(
            f"{Fore.RED}Error:{Style.RESET_ALL} Cannot use --delete and --deleteall together"
        )

    if deleteall:
        # DELETEALL operation
        if value is not None:
            raise ConfigurationError(
                f"{Fore.RED}Error:{Style.RESET_ALL} Cannot specify a value when deleting"
            )
        if scope is not None:
            print(
                f"{Fore.YELLOW}Warning:{Style.RESET_ALL} --scope is ignored when using --deleteall"
            )
        deleteall_config(key)
    elif delete:
        # DELETE operation
        if value is not None:
            raise ConfigurationError(
                f"{Fore.RED}Error:{Style.RESET_ALL} Cannot specify a value when deleting"
            )
        # Default to local if deleting and no scope provided
        target_scope = scope if scope is not None else "local"
        delete_config(key, target_scope)
    elif value is not None:
        # SET operation
        if key is None:
            raise ConfigurationError(
                f"{Fore.RED}Error:{Style.RESET_ALL} Key is required when setting a value"
            )

        # Default to local if setting and no scope provided
        target_scope = scope if scope is not None else "local"
        set_config(key, value, target_scope)
    else:
        # GET operation
        # If scope is None here, get_config handles searching all scopes
        get_config(key, scope)
