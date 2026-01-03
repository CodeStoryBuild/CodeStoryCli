import os
import typer
import inquirer
from rich.console import Console
from dotenv import load_dotenv
from vibe.core.chunker.simple_chunker import SimpleChunker
from vibe.core.chunker.predicate_chunker import PredicateChunker
from vibe.core.chunker.max_line_chunker import MaxLineChunker
from vibe.core.grouper.langchain_grouper import LangChainGrouper
from vibe.core.grouper.random_size_grouper import RandomSizeGrouper
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.pipeline.runner import AIGitPipeline

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

console = Console()
app = typer.Typer(help="Commit changes with AI-powered messages")
git = SubprocessGitInterface(".")


def is_whitespace_line(line: str) -> bool:
    return line.strip() == ""


# chk = PredicateChunker(is_whitespace_line)
chk = SimpleChunker()
# chk = MaxLineChunker(1)

# grp = LangChainGrouper(ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINIAPIKEY")))
grp = RandomSizeGrouper(2)

runner = AIGitPipeline(git, chk, grp)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: str = typer.Argument(None, help="Message to the AI model"),
):
    """
    Commits changes with AI-powered messages. This is the main command.
    """
    # This block only executes if no subcommand is explicitly called.
    if ctx.invoked_subcommand is None:
        runner.run(target, message)
    else:
        typer.echo(ctx.get_help())
        raise typer.Exit()
