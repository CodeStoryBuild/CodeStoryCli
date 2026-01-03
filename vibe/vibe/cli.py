import typer
from rich.console import Console

# Import the main functions directly from the command modules
from vibe.commands import init
from vibe.commands.commit import main as commit_main

app = typer.Typer(help="✨ vibe: an AI-powered abstraction layer above Git")
console = Console()

# Register init as a subcommand
app.add_typer(init.app, name="init")

# Register the commit function as a direct command
app.command(name="commit")(commit_main)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Show help if no subcommand is provided"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

if __name__ == "__main__":
    app()
