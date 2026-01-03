import typer
import inquirer
from rich.console import Console
from rich.panel import Panel
from vibe.core.git_interface.LocalGitInterface import LocalGitInterface
from vibe.core.pipeline.runner import AIGitPipeline

console = Console()
app = typer.Typer(help="Commit changes with AI-powered messages")
git = LocalGitInterface(".")

runner = AIGitPipeline(git, None, None, None, None)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: str = typer.Argument(
        ".", 
        help="The target path to check for changes."
    )
):
    """
    Commits changes with AI-powered messages. This is the main command.
    """
    # This block only executes if no subcommand is explicitly called.
    if ctx.invoked_subcommand is None:
        runner.run(target)
    else:
        typer.echo(ctx.get_help())
        raise typer.Exit()
