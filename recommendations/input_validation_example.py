"""
Example of improved input validation and type safety for vibe CLI.
"""
import re
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console


def validate_commit_hash(value: str) -> str:
    """Validate and normalize commit hash."""
    if not value:
        raise typer.BadParameter("Commit hash cannot be empty")
    
    # Git accepts partial hashes (4-40 chars, hex only)
    if not re.match(r'^[a-fA-F0-9]{4,40}$', value):
        raise typer.BadParameter("Invalid commit hash format")
    
    return value.lower()


def validate_target_path(value: str) -> Path:
    """Validate target path exists and is accessible."""
    path = Path(value)
    
    if not path.exists():
        raise typer.BadParameter(f"Target path '{value}' does not exist")
    
    if not path.is_dir() and not path.is_file():
        raise typer.BadParameter(f"Target '{value}' is not a valid file or directory")
    
    return path


def validate_message_length(value: Optional[str]) -> Optional[str]:
    """Validate commit message length."""
    if value is None:
        return None
    
    if len(value.strip()) == 0:
        raise typer.BadParameter("Commit message cannot be empty")
    
    if len(value) > 1000:  # Reasonable limit
        raise typer.BadParameter("Commit message too long (max 1000 characters)")
    
    return value.strip()


# Usage in CLI commands with proper type annotations
def improved_expand_command(
    commit_hash: Annotated[str, typer.Argument(callback=validate_commit_hash)] = ...,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Expand a past commit into smaller logical commits safely."""
    console = Console()
    # Command logic here...


def improved_commit_command(
    target: Annotated[str, typer.Argument(callback=validate_target_path)] = ".",
    message: Annotated[Optional[str], typer.Argument(callback=validate_message_length)] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Commits changes with AI-powered messages."""
    console = Console()
    # Command logic here...


# Example of improved data models with validation
from dataclasses import dataclass
from typing import List


@dataclass
class ValidatedCommitGroup:
    """A collection of DiffChunks with validation."""
    
    chunks: List["Chunk"]
    group_id: str
    commit_message: str
    extended_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate data after initialization."""
        if not self.chunks:
            raise ValueError("CommitGroup must contain at least one chunk")
        
        if not self.group_id.strip():
            raise ValueError("CommitGroup must have a valid group_id")
        
        if not self.commit_message.strip():
            raise ValueError("CommitGroup must have a commit message")
        
        if len(self.commit_message) > 72:  # Git convention
            raise ValueError("Commit message subject line should be ≤ 72 characters")


# Example of configuration validation
import json
from pathlib import Path


def validate_config_file(config_path: Path) -> dict:
    """Validate and load configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    
    # Validate required fields
    required_fields = ["languages", "queries"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field '{field}' in configuration")
    
    return config