import importlib.metadata
import signal
import sys
from typing import Optional

import typer
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger
from rich.console import Console
from rich.traceback import install

from vibe.commands import clean, commit, expand
from vibe.core.config import VibeConfig, load_config
from vibe.core.exceptions import VibeError
from vibe.core.llm import ModelConfig, create_llm_model

# Disable showing locals in tracebacks (way too much text)
install(show_locals=False)
load_dotenv()

# force utf-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        try:
            version = importlib.metadata.version("vibe")
            typer.echo(f"vibe version {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("vibe version: development")
        raise typer.Exit()


def setup_signal_handlers():
    """Set up graceful shutdown on Ctrl+C."""

    def signal_handler(sig, frame):
        console = Console()
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)  # Standard exit code for Ctrl+C

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)


# create app
app = typer.Typer(
    help="✨ vibe: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
    add_completion=False,  # Disable completion for now
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="expand")(expand.main)
app.command(name="clean")(clean.main)


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
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (format: provider:model-name, e.g., openai:gpt-4, gemini:gemini-2.0-flash-exp)",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="API key for the model provider"
    ),
) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()

    # Initialize context object for sharing between commands
    if ctx.obj is None:
        ctx.obj = {}

    # Configure model
    try:
        llm_model = _configure_model(model, api_key)
        ctx.obj["model"] = llm_model
        if llm_model:
            logger.debug("LLM model configured successfully")
    except Exception as e:
        console = Console()
        console.print(f"[yellow]Warning: Failed to configure model: {e}[/yellow]")
        console.print("[dim]Falling back to default model[/dim]")
        ctx.obj["model"] = None

    # default behavior
    if ctx.invoked_subcommand is None:
        console = Console()
        console.print(ctx.get_help())
        console.print("\n[dim]Run 'vibe --help' for more information.[/dim]")
        raise typer.Exit()


def _configure_model(
    model_arg: Optional[str], api_key_arg: Optional[str]
) -> Optional[BaseChatModel]:
    """
    Configure the LLM model based on command-line arguments, .vibeconfig, or defaults.

    Priority:
    1. Command-line arguments (--model, --api-key)
    2. .vibeconfig file
    3. Environment variables (via factory defaults)
    4. Fallback to gemini-2.0-flash-exp

    Args:
        model_arg: Model specification from --model flag (provider:model-name)
        api_key_arg: API key from --api-key flag

    Returns:
        Configured BaseChatModel or None if configuration fails
    """
    provider = None
    model_name = None
    api_key = api_key_arg

    # Parse --model argument (format: provider:model-name)
    if model_arg:
        if ":" in model_arg:
            provider, model_name = model_arg.split(":", 1)
        else:
            # If no provider specified, try to infer from model name
            model_lower = model_arg.lower()
            if "gpt" in model_lower or "o1" in model_lower or "chatgpt" in model_lower:
                provider = "openai"
                model_name = model_arg
            elif "gemini" in model_lower:
                provider = "gemini"
                model_name = model_arg
            elif "claude" in model_lower:
                provider = "anthropic"
                model_name = model_arg
            else:
                raise ValueError(
                    f"Cannot infer provider from model '{model_arg}'. "
                    f"Please use format: provider:model-name (e.g., openai:gpt-4)"
                )

    # If not provided via CLI, check .vibeconfig
    if not provider or not model_name:
        config = load_config()
        if config:
            provider = provider or config.model_provider
            model_name = model_name or config.model_name
            api_key = api_key or config.api_key

    # If still not configured, use default
    if not provider or not model_name:
        logger.info("No model specified, using default: gemini:gemini-2.0-flash-exp")
        provider = "gemini"
        model_name = "gemini-2.0-flash-exp"

    # Create model configuration
    model_config = ModelConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=0.7,
    )

    # Create and return the model
    try:
        return create_llm_model(model_config)
    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        # Try fallback to default Gemini model
        try:
            logger.info("Attempting fallback to gemini-2.0-flash-exp")
            fallback_config = ModelConfig(
                provider="gemini",
                model_name="gemini-2.0-flash-exp",
                api_key=None,  # Will use environment variable
                temperature=0.7,
            )
            return create_llm_model(fallback_config)
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            raise ValueError(
                f"Failed to configure model: {e}. Fallback also failed: {fallback_error}"
            )


def run_app():
    """Run the application with global exception handling."""
    try:
        app(prog_name="vibe")
    except VibeError as e:
        console = Console()
        console.print(f"[red]Error:[/red] {e.message}")
        if e.details:
            console.print(f"[dim]{e.details}[/dim]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console = Console()
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(130)


if __name__ == "__main__":
    run_app()
