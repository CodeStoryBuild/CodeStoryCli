import os
import typer
import inquirer
from rich.console import Console
from dotenv import load_dotenv
from vibe.core.chunker.max_line_chunker import MaxLineChunker
from vibe.core.chunker.predicate_chunker import PredicateChunker
from vibe.core.grouper.gemini_grouper import GeminiGrouper
from vibe.core.grouper.single_grouper import SingleGrouper
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.pipeline.runner import AIGitPipeline

load_dotenv()

console = Console()
app = typer.Typer(help="Commit changes with AI-powered messages")
git = SubprocessGitInterface(".")

def is_whitespace_line(line: str) -> bool:
    return line.strip() == ""

chk = PredicateChunker(is_whitespace_line)
# chk = MaxLineChunker(2)

grp = SingleGrouper()
# grp = GeminiGrouper(os.getenv("GEMINIAPIKEY"))

runner = AIGitPipeline(git, chk, grp)

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
