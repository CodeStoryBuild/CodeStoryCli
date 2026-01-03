from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from platformdirs import user_config_dir

from loguru import logger
from rich.console import Console
from rich.traceback import install

from vibe.commands import clean, commit, expand
from vibe.core.exceptions import GitError, ValidationError, VibeError
from vibe.core.validation import validate_git_repository
from vibe.core.logging.logging import setup_logger


from vibe.core.config.config_loader import ConfigLoader
from vibe.runtimeutil import ensure_utf8_output, setup_signal_handlers, version_callback
from vibe.context import GlobalConfig, GlobalContext


# create app
app = typer.Typer(
    help="✨ vibe: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
    add_completion=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="expand")(expand.main)
app.command(name="clean")(clean.main)


def setup_config_args(**kwargs):
    config_args = {}

    for key, item in kwargs.items():
        if item is not None:
            config_args[key] = item

    return config_args


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
        help="Where should operations be made?",
    ),
    custom_config: Optional[str] = typer.Option(
        None,
        "--custom-config",
        help="Path to a custom config file",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Model to use (format: provider:model-name, e.g., openai:gpt-4, gemini:gemini-2.5-flash)",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="API key for the model provider"
    ),
    model_temperature: float = typer.Option(
        0.7, "--temperature", help="What temperature to use when creating the AI model"
    ),
    verbose: Optional[bool] = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Be extra verbose",
    ),
    auto_accept: Optional[bool] = typer.Option(
        False, "--yes", "-y", help="Automatically accept and commit all changes"
    ),
) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # default behavior
    if ctx.invoked_subcommand is None:
        logger.info(ctx.get_help())
        print("\n[dim]Run 'vibe --help' for more information.[/dim]")
        raise typer.Exit()

    setup_logger(ctx.invoked_subcommand)

    config_args = setup_config_args(
        model=model,
        api_key=api_key,
        model_temperature=model_temperature,
        verbose=verbose,
        auto_accept=auto_accept,
    )

    local_config_path = Path("vibeconfig.toml")
    env_prefix = "VIBE_"
    global_config_path = Path(user_config_dir("Vibe")) / "vibeconfig.toml"

    config, used_configs = ConfigLoader.get_full_config(
        GlobalConfig,
        config_args,
        local_config_path,
        env_prefix,
        global_config_path,
        custom_config,
    )
    logger.info(f"Used {used_configs} to build global context.")
    global_context = GlobalContext.from_global_config(config, Path(repo_path))
    ctx.obj = global_context

    validate_git_repository(global_context.git_interface)


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
        app(prog_name="vibe")

    except ValidationError as e:
        logger.error(f"[red]Validation Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        raise typer.Exit(1)

    except GitError as e:
        logger.error(f"[red]Git Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"Git operation failed: {e.message}")
        raise typer.Exit(1)

    except VibeError as e:
        logger.error(f"[red]Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"Vibe operation failed: {e.message}")
        raise typer.Exit(1)

    except KeyboardInterrupt:
        logger.info("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)


if __name__ == "__main__":
    run_app()
