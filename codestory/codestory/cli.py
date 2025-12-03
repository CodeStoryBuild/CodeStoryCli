"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build
 */
-----------------------------------------------------------------------------
"""

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
from pathlib import Path

import typer
from colorama import Fore, Style, init
from loguru import logger
from platformdirs import user_config_dir

from codestory.commands import clean, commit, config, fix
from codestory.context import GlobalConfig, GlobalContext
from codestory.core.config.config_loader import ConfigLoader
from codestory.core.exceptions import handle_codestory_exception
from codestory.core.logging.logging import setup_logger
from codestory.runtimeutil import (
    ensure_utf8_output,
    get_log_dir_callback,
    setup_signal_handlers,
    version_callback,
)

# Initialize colorama for cross-platform colored output
init(autoreset=True)


# create app
app = typer.Typer(
    help="codestory: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    add_completion=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="fix")(fix.main)
app.command(name="clean")(clean.main)
app.command(name="config")(config.main)

# which commands require a global context
config_command = "config"


def setup_config_args(**kwargs):
    config_args = {}

    for key, item in kwargs.items():
        if item is not None:
            config_args[key] = item

    return config_args


def run_onboarding(ctx: typer.Context):
    print(f"{Fore.WHITE}{Style.BRIGHT}Welcome to codestory!{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}{Style.BRIGHT}This is the first time you're running codestory. Let's get started!{Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You'll be asked a few questions to configure codestory.{Style.RESET_ALL}"
    )
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You can always change these settings later using the 'config' command.{Style.RESET_ALL}"
    )
    print(f"{Fore.WHITE}{Style.BRIGHT}Press Enter to continue.{Style.RESET_ALL}")
    input()
    model = typer.prompt(
        "What AI model would you like to use? Format=provider:model (e.g., openai:gpt-4)"
    )
    api_key = typer.prompt("What is your API key?")
    global_ = typer.confirm(
        "Do you want to set this as the global configuration?", default=False
    )
    config.main(ctx, key="model", value=model, scope="global" if global_ else "local")
    config.main(
        ctx, key="api_key", value=api_key, scope="global" if global_ else "local"
    )
    print(f"{Fore.WHITE}{Style.BRIGHT}Configuration completed!{Style.RESET_ALL}")
    print(
        f"{Fore.WHITE}{Style.BRIGHT}You can always change these settings and more later using the 'config' command.{Style.RESET_ALL}"
    )
    return


def check_run_onboarding(ctx: typer.Context):
    # check a file in user config dir
    onboarding_file = Path(user_config_dir("codestory")) / "onboarding_flag"
    if not onboarding_file.exists():
        run_onboarding(ctx)
        onboarding_file.touch()
        raise typer.Exit(0)
    else:
        return


@app.callback(invoke_without_command=True)
@handle_codestory_exception
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        help="Show version and exit",
    ),
    log_path: bool = typer.Option(
        False,
        "--log-dir",
        "-LD",
        callback=get_log_dir_callback,
        help="Show log path (where logs for codestory live) and exit",
    ),
    repo_path: str = typer.Option(
        ".",
        "--repo",
        help="Path to the git repository to operate on.",
    ),
    custom_config: str | None = typer.Option(
        None,
        "--custom-config",
        help="Path to a custom config file",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="AI model to use. Format provider/model (e.g., openai/gpt-4).",
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="API key for the model provider"
    ),
    temperature: float | None = typer.Option(
        None,
        "--temperature",
        help="Sampling temperature for the AI model (0.0 to 1.0).",
    ),
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging.",
    ),
    silent: bool | None = typer.Option(
        None,
        "--silent",
        "-s",
        help="Do not output any text to the console, except for prompting acceptance of changes if auto_accept is False",
    ),
    auto_accept: bool | None = typer.Option(
        None, "--yes", "-y", help="Automatically accept and commit all changes"
    ),
) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # skip --help in subcommands
    if any(arg in ctx.help_option_names for arg in ctx.args):
        return

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()

    # initial setup of logger, will be updated later if needed
    setup_logger(ctx.invoked_subcommand, debug=verbose or False, silent=silent or False)

    if ctx.invoked_subcommand == config_command:
        return

    config_args = setup_config_args(
        model=model,
        api_key=api_key,
        temperature=temperature,
        verbose=verbose,
        auto_accept=auto_accept,
        silent=silent,
    )

    local_config_path = Path("codestoryconfig.toml")
    env_prefix = "codestory_"
    global_config_path = Path(user_config_dir("codestory")) / "codestoryconfig.toml"
    custom_config_path = Path(custom_config) if custom_config else None

    config, used_configs, used_defaults = ConfigLoader.get_full_config(
        GlobalConfig,
        config_args,
        local_config_path,
        env_prefix,
        global_config_path,
        custom_config_path,
    )

    setup_logger(ctx.invoked_subcommand, debug=config.verbose, silent=config.silent)

    # if we run a command that requires a global context, check that the user has learned the onboarding process
    if not used_configs and used_defaults:
        # check if this is first run of command
        # if so, run onboarding for user
        check_run_onboarding(ctx)
        logger.debug("No configuration found. Using default values.")

    logger.debug(f"Used {used_configs} to build global context.")
    global_context = GlobalContext.from_global_config(config, Path(repo_path))
    ctx.obj = global_context


def load_env(path=".env"):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
            os.environ[key] = value
    except FileNotFoundError:
        pass


def run_app():
    """Run the application with global exception handling."""
    # force stdout to be utf8 as it can be weird with typers console.print sometimes
    ensure_utf8_output()
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()
    # load any .env files
    load_env()
    # launch cli
    app(prog_name="cst")


if __name__ == "__main__":
    run_app()
