import typer
from rich.console import Console
from loguru import logger

from vibe.core.context.commit_init import createPipeline
from vibe.core.logging.logging import setup_logger


# Define the main commit command
def main(
    ctx: typer.Context,
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: str | None = typer.Argument(None, help="Message to the AI model"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically accept all prompts (non-interactive).",
    ),
) -> None:
    """
    Commits changes with AI-powered messages.
    """
    # TODO proper repo check first
    console = Console()
    setup_logger("commit", console)

    logger.info(
        "Commit command invoked: target={target} message_present={mp}",
        target=target,
        mp=message is not None,
    )

    repo_path = "."
    runner = createPipeline(repo_path, target, console, auto_yes=yes)
    runner.run(target, message, auto_yes=yes)
