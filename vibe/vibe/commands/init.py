import typer
from rich.panel import Panel
from rich.console import Console

console = Console()
app = typer.Typer(help="Initialize vibe in a repository")


@app.command()
def repo():
    """Initialize vibe for the current repo"""
    # Detect Git repo and create config
    console.print(Panel("✨ vibe initialized in current repository", style="green"))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Show help if no subcommand is provided"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
