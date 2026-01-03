import typer
from rich.console import Console
from rich.traceback import install
from dotenv import load_dotenv


from vibe.core.chunker.simple_chunker import SimpleChunker
from vibe.core.chunker.atomic_chunker import AtomicChunker
from vibe.core.grouper.random_size_grouper import RandomSizeGrouper
from vibe.core.grouper.single_grouper import SingleGrouper
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.pipeline.runner import AIGitPipeline

from vibe.commands import commit
from vibe.commands import expand

# Disable showing locals in tracebacks (way too much text)
install(show_locals=False)
load_dotenv()

# create app
app = typer.Typer(
    help="✨ vibe: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="expand")(expand.main)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Global setup callback. Initialize shared objects here.
    """
    # default behavior
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    # start app
    app()
