"""
Example of improved error handling patterns for the vibe CLI.
"""
from typing import Optional
import typer
from rich.console import Console
from loguru import logger


# Custom exception hierarchy
class VibeError(Exception):
    """Base exception for all vibe-related errors."""
    pass


class GitError(VibeError):
    """Git operation errors."""
    pass


class ConfigError(VibeError):
    """Configuration-related errors."""
    pass


class ValidationError(VibeError):
    """Input validation errors."""
    pass


# Example of proper error handling in CLI commands
def improved_commit_command(
    target: str = typer.Argument(".", help="The target path to check for changes."),
    message: Optional[str] = typer.Argument(None, help="Message to the AI model"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """
    Commits changes with AI-powered messages.
    """
    console = Console()
    
    try:
        # Validate inputs
        if not Path(target).exists():
            raise ValidationError(f"Target path '{target}' does not exist")
        
        # Setup logger with error handling
        setup_logger("commit", console)
        
        # Create and run pipeline with proper error propagation
        runner = createPipeline(".", target, console, auto_yes=yes)
        result = runner.run(target, message, auto_yes=yes)
        
        if not result:
            raise GitError("Pipeline execution failed")
            
    except ValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitError as e:
        console.print(f"[red]Git Error:[/red] {e}")
        logger.error(f"Git operation failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        logger.exception("Unexpected error in commit command")
        raise typer.Exit(1)


# Example of proper exception handling in core modules
class ImprovedGitInterface:
    def run_git_text(self, args: list[str], **kwargs) -> str:
        """Run git command with proper error handling."""
        try:
            # Git operation logic here
            result = subprocess.run(["git"] + args, capture_output=True, text=True, **kwargs)
            
            if result.returncode != 0:
                raise GitError(f"Git command failed: {result.stderr.strip()}")
                
            return result.stdout
            
        except FileNotFoundError:
            raise GitError("Git is not installed or not in PATH")
        except subprocess.SubprocessError as e:
            raise GitError(f"Git subprocess error: {e}")