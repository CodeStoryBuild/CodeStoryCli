from typing import Callable

import typer
import inquirer
from rich.console import Console
from loguru import logger

from vibe.core.expand.service import ExpandService
from vibe.core.logging.logging import setup_logger
from vibe.core.validation import (
    validate_commit_hash,
    validate_git_repository
)
from vibe.core.exceptions import VibeError, GitError, ValidationError


def main(
    ctx: typer.Context,
    commit_hash: str = typer.Argument(..., help="Commit hash to expand"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically accept rewrite confirmation (non-interactive).",
    ),
) -> None:
    """Expand a past commit into smaller logical commits safely.
    
    Examples:
        # Expand a specific commit
        vibe expand abc123
        
        # Expand with auto-confirmation
        vibe expand abc123 --yes
    """
    console = Console()
    
    try:
        # Validate inputs
        validate_git_repository(".")
        validated_hash = validate_commit_hash(commit_hash)
        
        # Setup logging
        setup_logger("expand", console)
        
        logger.info(
            "Expand command started",
            commit_hash=validated_hash,
            auto_yes=yes
        )
        
        # Execute expansion
        service = ExpandService(".")
        success = service.expand_commit(validated_hash, console=console, auto_yes=yes)
        
        if not success:
            console.print("[red]Failed to expand commit[/red]")
            logger.error("Expand operation failed")
            raise typer.Exit(1)
        
        logger.info("Expand command completed successfully")
        console.print("[green]Commit expanded successfully![/green]")
        
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
        logger.error(f"Expand operation failed: {e.message}")
        raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}")
        logger.exception("Unexpected error in expand command")
        raise typer.Exit(1)
