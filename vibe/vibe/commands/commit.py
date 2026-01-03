import typer
from vibe.core.context.commit_init import createPipeline


# Define the main commit command
def main(
    ctx: typer.Context,
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: str = typer.Argument(None, help="Message to the AI model"),
):
    """
    Commits changes with AI-powered messages.
    """
    # TODO proper repo check first
    repo_path = "."
    runner = createPipeline(repo_path, target)
    runner.run(target, message)
