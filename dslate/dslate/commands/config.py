# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
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


from pathlib import Path
from typing import Literal
from rich import print
import tomli
import typer
from loguru import logger
from platformdirs import user_config_dir
from rich.console import Console
from rich.table import Table

from dslate.context import GlobalConfig

console = Console()


def _get_config_schema() -> dict:
    """Get the schema of available config options from GlobalConfig."""
    schema = {}

    for field_name, field_info in GlobalConfig.model_fields.items():
        # Get default value
        default_value = field_info.default

        # Get description from Field metadata
        description = field_info.description or "No description available"

        schema[field_name] = {"description": description, "default": default_value}

    return schema


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if it exceeds max_length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _check_key_exists(key: str) -> None:
    """Check if a config key exists. If not, show available options and exit."""
    schema = _get_config_schema()

    if key not in schema:
        console.print(f"[red]Error:[/red] Unknown configuration key '{key}'\n")
        console.print("[bold]Available configuration options:[/bold]\n")

        table = Table(show_header=True, header_style="bold cyan", show_lines=True)
        table.add_column("Key", style="cyan")
        table.add_column("Description", style="yellow")
        table.add_column("Default", style="green")

        for config_key, info in sorted(schema.items()):
            default_str = (
                str(info["default"]) if info["default"] is not None else "None"
            )
            description = _truncate_text(info["description"], 60)
            table.add_row(config_key, description, default_str)

        console.print(table)
        raise typer.Exit(1)


def _help_callback(ctx: typer.Context, param, value: bool):
    # Typer/Click help callback: show help and exit when --help is provided
    if not value or ctx.resilient_parsing:
        return
    typer.echo(ctx.get_help())
    raise typer.Exit()


def _add_to_gitignore(config_filename: str) -> None:
    """Add config file to .gitignore if it exists, otherwise print warning."""
    gitignore_path = Path(".gitignore")

    if gitignore_path.exists():
        # Read existing .gitignore
        gitignore_content = gitignore_path.read_text()

        # Check if config file is already in .gitignore
        if config_filename not in gitignore_content:
            # Add config file to .gitignore
            with gitignore_path.open("a") as f:
                # Add newline if file doesn't end with one
                if gitignore_content and not gitignore_content.endswith("\n"):
                    f.write("\n")
                f.write(f"{config_filename}\n")
            print(f"Added {config_filename} to .gitignore")
    else:
        print(
            f"[yellow]Warning:[/yellow] .gitignore not found. "
            f"Please consider adding {config_filename} to your .gitignore file, you may commit your api keys by accident."
        )


def _set_config(key: str, value: str, scope: str) -> None:
    """Set a configuration value in the specified scope."""
    # Validate that the key exists
    _check_key_exists(key)

    config_filename = "dslateconfig.toml"

    if scope == "env":
        # For environment variables, just print instructions
        env_var = f"dslate_{key}"
        console.print(f"[green]To set this as an environment variable:[/green]")
        console.print(f"  Windows (PowerShell): $env:{env_var}='{value}'")
        console.print(f"  Windows (CMD): set {env_var}={value}")
        console.print(f"  Linux/macOS: export {env_var}='{value}'")
        return

    # Determine config file path based on scope
    if scope == "global":
        config_path = Path(user_config_dir("dslate")) / config_filename
        config_path.parent.mkdir(parents=True, exist_ok=True)
    else:  # local
        config_path = Path(config_filename)
        # Add to .gitignore for local configs
        _add_to_gitignore(config_filename)

    # Load existing config or create new one
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                config_data = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            print(f"Failed to parse existing config: {e}. Creating new config.")

    # Update the value
    config_data[key] = value

    # Write back to file
    with open(config_path, "w") as f:
        # Simple TOML writer for flat key-value pairs
        for k, v in config_data.items():
            # Handle different types
            if isinstance(v, bool):
                f.write(f"{k} = {str(v).lower()}\n")
            elif isinstance(v, (int, float)):
                f.write(f"{k} = {v}\n")
            else:
                # String values need quotes
                f.write(f'{k} = "{v}"\n')

    scope_label = "global" if scope == "global" else "local"
    print(f"[green]Set {key} = {value} ({scope_label})[/green]")
    print(f"Config file: {config_path.absolute()}")


def _get_config(key: str | None, scope: str | None) -> None:
    """Get configuration value(s) from the specified scope or all scopes."""
    config_filename = "dslateconfig.toml"

    # Define all config sources
    sources = []

    if scope is None or scope == "local":
        local_path = Path(config_filename)
        if local_path.exists():
            try:
                with open(local_path, "rb") as f:
                    local_config = tomli.load(f)
                    sources.append(("Local", local_path, local_config))
            except tomli.TOMLDecodeError:
                pass

    if scope is None or scope == "env":
        # Check environment variables with dslate_ prefix
        import os

        env_config = {}
        for k, v in os.environ.items():
            if k.lower().startswith("dslate_"):
                key_clean = k[7:]  # Remove "dslate_" prefix
                env_config[key_clean] = v
        if env_config:
            sources.append(("Environment", None, env_config))

    if scope is None or scope == "global":
        global_path = Path(user_config_dir("dslate")) / config_filename
        if global_path.exists():
            try:
                with open(global_path, "rb") as f:
                    global_config = tomli.load(f)
                    sources.append(("Global", global_path, global_config))
            except tomli.TOMLDecodeError:
                pass

    if not sources:
        scope_m = f"in scope:{scope if scope else 'all'}"
        if key:
            print(f"[yellow]No configuration found for key:{key} {scope_m}[/yellow]")
        else:
            print(f"[yellow]No configuration file found {scope_m}[/yellow]")

        return

    # If a specific key is requested
    if key:
        # Validate that the key exists
        _check_key_exists(key)

        # Show value from each source
        table = Table(title=f"Configuration: {key}", show_lines=True)
        table.add_column("Source", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Location", style="dim")

        found = False
        for source_name, source_path, config_data in sources:
            if key in config_data:
                found = True
                location = str(source_path) if source_path else "Environment Variables"
                value_str = _truncate_text(str(config_data[key]), 50)
                table.add_row(source_name, value_str, location)

        if found:
            console.print(table)
            # Show which value takes precedence
            active_value = sources[0][2].get(key) if key in sources[0][2] else None
            if active_value and len(sources) > 1:
                console.print(
                    f"\n[bold]Active value:[/bold] {active_value} (from {sources[0][0]})"
                )
        else:
            print(f"[yellow]Key '{key}' not found in any configuration[/yellow]")
    else:
        # Show all config values including available options
        schema = _get_config_schema()

        # Collect all set keys from sources
        set_keys = set()
        for _, _, config_data in sources:
            set_keys.update(config_data.keys())

        table = Table(title="Configuration Options", show_lines=True)
        table.add_column("Key", style="cyan")
        table.add_column("Description", style="yellow")
        # add header depending on if any values have been set
        if not set_keys:
            table.add_column("Default", style="green")
        elif len(schema.keys()) == len(set_keys):
            table.add_column("Value", style="green")
        else:
            table.add_column("Value/Default", style="green")
        table.add_column("Source", style="magenta")

        # Show all available config options
        for k in sorted(schema.keys()):
            description = schema[k]["description"]
            # Truncate description for better table formatting
            description_short = _truncate_text(description, 60)

            # Check if this key is set in any source
            if k in set_keys:
                # Find the active value from the highest priority source
                for source_name, _, config_data in sources:
                    if k in config_data:
                        value_str = _truncate_text(str(config_data[k]), 40)
                        table.add_row(k, description_short, value_str, source_name)
                        break
            else:
                # Show default value if not set
                default_value = schema[k]["default"]
                default_str = (
                    str(default_value) if default_value is not None else "[dim]No-Default[/dim]"
                )
                default_str = _truncate_text(default_str, 40)
                table.add_row(k, description_short, default_str, "[dim](not set)[/dim]")

        console.print(table)


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
        help="Select which scope to modify, defaults to  local",
    ),
) -> None:
    """
    Manage global and local dslate configurations. 
    
    Priority order: program arguments > custom config > local config > environment variables > global config

    Examples:

        # Get a configuration value

        dslate config model

        # Set a local configuration value

        dslate config model "gemini:gemini-2.0-flash"

        # Set a global configuration value

        dslate config model "openai:gpt-4" --scope global

        # Get environment variable api_key

        dslate config api_key --scope env

        # Show all configuration

        dslate config
    """
    explicit_set = scope is not None
    if scope is None:
        scope = "local"

    # Determine operation
    if value is not None:
        # Set operation
        if key is None:
            print("[red]Error:[/red] Key is required when setting a value")
            raise typer.Exit(1)
        _set_config(key, value, scope)
    else:
        # Get operation
        # If no scope flags are provided, show from all scopes
        _get_config(key, None if not explicit_set else scope)
