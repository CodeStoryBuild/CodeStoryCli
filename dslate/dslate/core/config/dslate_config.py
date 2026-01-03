"""Configuration file handling for dslate."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class dslateConfig:
    """Configuration for dslate application."""

    model_provider: Optional[str] = None  # e.g., "openai", "gemini", "anthropic"
    model_name: Optional[str] = None  # e.g., "gpt-4", "gemini-2.5-flash"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "dslateConfig":
        """Create config from dictionary."""
        return cls(
            model_provider=data.get("model_provider"),
            model_name=data.get("model_name"),
            api_key=data.get("api_key"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
        )


def find_config_file(start_path: str = ".") -> Optional[Path]:
    """
    Find .dslateconfig file by searching up the directory tree from start_path.

    Args:
        start_path: Path to start searching from (defaults to current directory)

    Returns:
        Path to .dslateconfig if found, None otherwise
    """
    current = Path(start_path).resolve()

    # Search up to root directory
    while True:
        config_path = current / ".dslateconfig"
        if config_path.exists():
            logger.debug(f"Found .dslateconfig at {config_path}")
            return config_path

        # Check if we've reached the root
        parent = current.parent
        if parent == current:
            break
        current = parent

    logger.debug("No .dslateconfig file found")
    return None


def load_config(start_path: str = ".") -> Optional[dslateConfig]:
    """
    Load configuration from .dslateconfig file.

    Args:
        start_path: Path to start searching for config file

    Returns:
        dslateConfig if file found and valid, None otherwise
    """
    config_path = find_config_file(start_path)
    if not config_path:
        return None

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return dslateConfig.from_dict(data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in .dslateconfig: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading .dslateconfig: {e}")
        return None


def save_config(config: dslateConfig, path: str = ".dslateconfig") -> bool:
    """
    Save configuration to .dslateconfig file.

    Args:
        config: dslateConfig to save
        path: Path where to save the config file

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        logger.info(f"Saved configuration to {path}")
        return True
    except Exception as e:
        logger.error(f"Error saving .dslateconfig: {e}")
        return False


def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a specific configuration value, checking .dslateconfig then environment variables.

    Args:
        key: Configuration key to retrieve
        default: Default value if not found

    Returns:
        Configuration value or default
    """
    # First check .dslateconfig
    config = load_config()
    if config:
        value = getattr(config, key, None)
        if value is not None:
            return value

    # Then check environment variables (uppercase with dslate_ prefix)
    env_key = f"dslate_{key.upper()}"
    env_value = os.getenv(env_key)
    if env_value:
        return env_value

    return default
