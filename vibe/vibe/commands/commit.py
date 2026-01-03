import typer
import inquirer
from rich.console import Console
from rich.panel import Panel
from vibe.core.git_interface.LocalGitInterface import LocalGitInterface

console = Console()
app = typer.Typer(help="Commit changes with AI-powered messages")
git = LocalGitInterface(".")

def extractChunks(target: str):
    """
    Extracts the file differences for a given target.
    
    Args:
        target: The path to check for changes.
    
    Returns:
        A list of file differences.
    """
    file_diffs = git.get_working_diff(target=target)
    return file_diffs

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
        unstage = inquirer.confirm("Would you like to unstage all changes?", default=False)
        
        if unstage:
            git.track_untracked(target)
        
        # The extractChunks function is now called directly from the main function.
        print("\n".join(map(str, extractChunks(target))))
    else:
        typer.echo(ctx.get_help())
        raise typer.Exit()
