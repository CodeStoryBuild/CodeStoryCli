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

import typer
from dotenv import load_dotenv
from loguru import logger
from platformdirs import user_config_dir
from rich.traceback import install
from rich import print as rprint

from dslate.commands import clean, commit, config, fix
from dslate.context import GlobalConfig, GlobalContext
from dslate.core.config.config_loader import ConfigLoader
from dslate.core.exceptions import dslateError
from dslate.core.logging.logging import setup_logger
from dslate.runtimeutil import (
    ensure_utf8_output,
    setup_signal_handlers,
    version_callback,
)

# create app
app = typer.Typer(
    help="dslate: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
    add_completion=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="fix")(fix.main)
app.command(name="clean")(clean.main)
app.command(name="config")(config.main)

# which commands require a global context
dependent_commands = ["commit", "fix", "clean"]


def setup_config_args(**kwargs):
    config_args = {}

    for key, item in kwargs.items():
        if item is not None:
            config_args[key] = item

    return config_args


def run_onboarding(ctx: typer.Context):
    rprint("[bold]Welcome to dslate![/bold]")
    rprint("[bold]This is the first time you're running dslate. Let's get started![/bold]")
    rprint("[bold]You'll be asked a few questions to configure dslate.[/bold]")
    rprint("[bold]You can always change these settings later using the 'config' command.[/bold]")
    rprint("[bold]Press Enter to continue.[/bold]")
    input()
    model = typer.prompt("What AI model would you like to use? Format=provider:model (e.g., openai:gpt-4)")
    api_key = typer.prompt("What is your API key?")
    global_ = typer.confirm("Do you want to set this as the global configuration?")
    config.main(ctx, key="model", value=model, global_scope=global_, env_scope=False)
    config.main(ctx, key="api_key", value=api_key, global_scope=global_, env_scope=False)
    rprint("[bold]Configuration completed![/bold]")
    rprint("[bold]You can always change these settings and more later using the 'config' command.[/bold]")
    return

def check_run_onboarding(ctx: typer.Context):
    # check a file in user config dir
    onboarding_file = Path(user_config_dir("dslate")) / "onboarding_flag"
    if not onboarding_file.exists():
        run_onboarding(ctx)
        onboarding_file.touch()
        raise typer.Exit(0)
    else:
        return


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        help="Show version and exit",
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
        help="AI model to use (e.g., openai:gpt-4).",
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="API key for the model provider"
    ),
    model_temperature: float | None = typer.Option(
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

    setup_logger(ctx.invoked_subcommand, debug=verbose)

    if ctx.invoked_subcommand not in dependent_commands:
        return

    config_args = setup_config_args(
        model=model,
        api_key=api_key,
        model_temperature=model_temperature,
        verbose=verbose,
        auto_accept=auto_accept,
    )

    local_config_path = Path("dslateconfig.toml")
    env_prefix = "dslate_"
    global_config_path = Path(user_config_dir("dslate")) / "dslateconfig.toml"
    custom_config_path = Path(custom_config) if custom_config else None

    config, used_configs, used_defaults = ConfigLoader.get_full_config(
        GlobalConfig,
        config_args,
        local_config_path,
        env_prefix,
        global_config_path,
        custom_config_path,
    )
    if not used_configs and used_defaults:
        # check if this is first run of command
        # if so, run onboarding for user
        check_run_onboarding(ctx)

        logger.warning("No configuration found. Using default values.")

    logger.debug(f"Used {used_configs} to build global context.")
    global_context = GlobalContext.from_global_config(config, Path(repo_path))
    ctx.obj = global_context


def run_app():
    """Run the application with global exception handling."""
    try:
        # force stdout to be utf8 as it can be weird with typers console.print sometimes
        ensure_utf8_output()
        # Set up signal handlers for graceful shutdown
        setup_signal_handlers()
        # Disable showing locals in tracebacks (way too much text)
        install(show_locals=False)
        # load any .env files
        load_dotenv()
        # launch cli
        app(prog_name="dslate")

    # except ValidationError as e:
    #     logger.error(f"[red]Validation Error:[/red] {e.message}")
    #     if e.details:
    #         logger.error(f"[dim]Details: {e.details}[/dim]")
    #     raise typer.Exit(1)

    # except GitError as e:
    #     logger.error(f"[red]Git Error:[/red] {e.message}")
    #     if e.details:
    #         logger.error(f"[dim]Details: {e.details}[/dim]")
    #     logger.error(f"Git operation failed: {e.message}")
    #     raise typer.Exit(1)

    except dslateError as e:
        logger.error(e)

    except KeyboardInterrupt:
        logger.info("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)


if __name__ == "__main__":
    run_app()
