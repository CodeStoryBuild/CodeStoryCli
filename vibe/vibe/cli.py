import importlib.metadata
import signal
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.traceback import install

from vibe.commands import clean, commit, expand
from vibe.core.exceptions import VibeError

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
    if hasattr(signal, 'SIGTERM'):
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
        False, "--version", "-V",
        callback=version_callback,
        help="Show version and exit"
    ),
) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # default behavior
    if ctx.invoked_subcommand is None:
        console = Console()
        console.print(ctx.get_help())
        console.print("\n[dim]Run 'vibe --help' for more information.[/dim]")
        raise typer.Exit()


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
