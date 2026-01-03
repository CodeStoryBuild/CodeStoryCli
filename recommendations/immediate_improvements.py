"""
Immediate improvements that can be made to the vibe CLI codebase.
"""

# 1. Add version flag to CLI
# In cli.py, add:

import importlib.metadata

def version_callback(value: bool):
    if value:
        try:
            version = importlib.metadata.version("vibe")
            typer.echo(f"vibe version {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("vibe version: development")
        raise typer.Exit()

# Add to app definition:
app = typer.Typer(
    help="✨ vibe: an AI-powered abstraction layer above Git",
    pretty_exceptions_show_locals=False,
)

@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, 
        help="Show version and exit"
    )
):
    pass


# 2. Improve error messages in commands
# Replace generic "if not ok: raise typer.Exit(1)" with specific messages

def improved_expand_main(...):
    try:
        ok = service.expand_commit(commit_hash, console=console, auto_yes=yes)
        if not ok:
            console.print("[red]Failed to expand commit. Check logs for details.[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error expanding commit:[/red] {e}")
        logger.exception("Expand command failed")
        raise typer.Exit(1)


# 3. Add input validation decorators
from functools import wraps

def validate_git_repo(func):
    """Decorator to ensure we're in a git repository."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not GitCommands.is_git_repository():
            console = Console()
            console.print("[red]Error:[/red] Not in a git repository")
            raise typer.Exit(1)
        return func(*args, **kwargs)
    return wrapper

# Use like:
@validate_git_repo
def commit_main(...):
    # Command logic


# 4. Improve configuration loading
# Add to a new config.py module:

@dataclass
class Config:
    ai_provider: str = "gemini"
    log_level: str = "INFO"
    max_chunks: int = 10
    
    @classmethod
    def load(cls) -> 'Config':
        config_path = Path.home() / ".config" / "vibe" / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            return cls(**data)
        return cls()


# 5. Add consistent return types
# Instead of returning bool/None inconsistently:

from typing import Result, Success, Failure  # or create custom types

class OperationResult:
    def __init__(self, success: bool, message: str = "", data: Any = None):
        self.success = success
        self.message = message  
        self.data = data
    
    @classmethod
    def success(cls, message: str = "", data: Any = None):
        return cls(True, message, data)
    
    @classmethod  
    def failure(cls, message: str):
        return cls(False, message)


# 6. Add proper logging context
# Instead of simple logger.info(), use structured logging:

logger.info(
    "Pipeline execution completed",
    success=True,
    duration_ms=execution_time,
    chunks_processed=len(chunks),
    commits_created=len(results),
    files_affected=len(affected_files)
)


# 7. Add signal handling for graceful shutdown
import signal
import sys

def setup_signal_handlers():
    def signal_handler(sig, frame):
        console = Console()
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Call in main CLI setup