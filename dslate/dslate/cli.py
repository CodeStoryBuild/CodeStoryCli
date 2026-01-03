
from pathlib import Path

import typer
from dotenv import load_dotenv
from loguru import logger
from platformdirs import user_config_dir
from rich.traceback import install

from dslate.commands import clean, commit, fix
from dslate.context import GlobalConfig, GlobalContext
from dslate.core.config.config_loader import ConfigLoader
from dslate.core.exceptions import GitError, ValidationError, dslateError
from dslate.core.logging.logging import setup_logger
from dslate.runtimeutil import (
    ensure_utf8_output,
    setup_signal_handlers,
    version_callback,
)

# create app
app = typer.Typer(
    help="✨ dslate: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
    add_completion=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="fix")(fix.main)
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
    model_temperature: float = typer.Option(
        0.7,
        "--temperature",
        help="Sampling temperature for the AI model (0.0 to 1.0).",
    ),
    verbose: bool | None = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging.",
    ),
    auto_accept: bool | None = typer.Option(
        False, "--yes", "-y", help="Automatically accept and commit all changes"
    ),
) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # skip --help in subcommands
    if ctx.help_option_names:
        return

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()
    else:
        setup_logger(ctx.invoked_subcommand, debug=verbose)

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

        config, used_configs = ConfigLoader.get_full_config(
            GlobalConfig,
            config_args,
            local_config_path,
            env_prefix,
            global_config_path,
            custom_config_path,
        )
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

    except ValidationError as e:
        logger.error(f"[red]Validation Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        raise typer.Exit(1) from e

    except GitError as e:
        logger.error(f"[red]Git Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"Git operation failed: {e.message}")
        raise typer.Exit(1) from e

    except dslateError as e:
        logger.error(f"[red]Error:[/red] {e.message}")
        if e.details:
            logger.error(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"dslate operation failed: {e.message}")
        raise typer.Exit(1) from e

    except KeyboardInterrupt:
        logger.info("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130) from None


if __name__ == "__main__":
    run_app()
