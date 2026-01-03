import typer
from vibe.core.pipeline.runner import AIGitPipeline

# Define the main commit command
def main(
    ctx: typer.Context,
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: str = typer.Argument(None, help="Message to the AI model"),
):
    """
    Commits changes with AI-powered messages.
    """
    runner: AIGitPipeline = ctx.obj["runner"]
    runner.run(target, message)
