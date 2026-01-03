
import typer
from loguru import logger
from rich.console import Console

from vibe.core.context.commit_init import createPipeline
from vibe.core.exceptions import GitError, ValidationError, VibeError
from vibe.core.logging.logging import setup_logger
from vibe.core.validation import (
    sanitize_user_input,
    validate_git_repository,
    validate_message_length,
    validate_target_path,
)


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
    
    Examples:
        # Commit all changes interactively
        vibe commit
        
        # Commit specific directory with message
        vibe commit src/ "Refactor user authentication"
        
        # Auto-accept all suggestions
        vibe commit --yes
    """
    console = Console()

    try:
        # Validate inputs
        validate_git_repository(".")
        validated_target = validate_target_path(target)
        validated_message = validate_message_length(message)

        # Sanitize message if provided
        if validated_message:
            validated_message = sanitize_user_input(validated_message)

        # Setup logging
        setup_logger("commit", console)

        logger.info(
            "Commit command started",
            target=str(validated_target),
            has_message=validated_message is not None,
            auto_yes=yes
        )

        # Create and run pipeline
        repo_path = "."
        runner = createPipeline(repo_path, str(validated_target), console, auto_yes=yes)

        result = runner.run(str(validated_target), validated_message, auto_yes=yes)

        if not result:
            console.print("[yellow]No commits were created[/yellow]")
            raise typer.Exit(0)

        logger.info(
            "Commit command completed successfully",
            commits_created=len(result) if isinstance(result, list) else 0
        )

    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e.message}")
        if e.details:
            console.print(f"[dim]Details: {e.details}[/dim]")
        raise typer.Exit(1)

    except GitError as e:
        console.print(f"[red]Git Error:[/red] {e.message}")
        if e.details:
            console.print(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"Git operation failed: {e.message}")
        raise typer.Exit(1)

    except VibeError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.details:
            console.print(f"[dim]Details: {e.details}[/dim]")
        logger.error(f"Vibe operation failed: {e.message}")
        raise typer.Exit(1)
        