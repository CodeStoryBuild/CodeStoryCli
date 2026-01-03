import typer
from rich.traceback import install
from dotenv import load_dotenv
import sys
import importlib.metadata

from vibe.commands import commit
from vibe.commands import expand
from vibe.commands import clean

# Disable showing locals in tracebacks (way too much text)
install(show_locals=False)
load_dotenv()

# force utf-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# create app
app = typer.Typer(
    help="✨ vibe: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
)

# attach commands
app.command(name="commit")(commit.main)
app.command(name="expand")(expand.main)
app.command(name="clean")(clean.main)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Global setup callback. Initialize shared objects here.
    """
    # default behavior
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    # start app
    app(prog_name="vibe")
