"""
Security and configuration best practices for vibe CLI.
"""
import os
import keyring
from pathlib import Path
from typing import Optional, Dict, Any
import json
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet


@dataclass
class VibeConfig:
    """Type-safe configuration with defaults."""
    ai_model: str = "gemini-pro"
    max_chunks_per_group: int = 10
    auto_yes: bool = False
    log_level: str = "INFO"
    timeout_seconds: int = 30
    max_file_size_mb: int = 10
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.max_chunks_per_group <= 0:
            raise ValueError("max_chunks_per_group must be positive")
        
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_log_levels:
            raise ValueError(f"log_level must be one of {valid_log_levels}")


class SecureConfigManager:
    """Secure configuration management with keyring integration."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "vibe"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Securely retrieve API key from system keyring."""
        try:
            return keyring.get_password("vibe-cli", service)
        except keyring.errors.KeyringError:
            return None
    
    def set_api_key(self, service: str, api_key: str) -> None:
        """Securely store API key in system keyring."""
        try:
            keyring.set_password("vibe-cli", service, api_key)
        except keyring.errors.KeyringError as e:
            raise RuntimeError(f"Failed to store API key: {e}")
    
    def load_config(self) -> VibeConfig:
        """Load and validate configuration."""
        if not self.config_file.exists():
            config = VibeConfig()
            self.save_config(config)
            return config
        
        try:
            with open(self.config_file) as f:
                data = json.load(f)
            
            # Filter unknown fields for forward compatibility
            known_fields = {f.name for f in VibeConfig.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in known_fields}
            
            config = VibeConfig(**filtered_data)
            config.validate()
            return config
            
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise RuntimeError(f"Invalid configuration file: {e}")
    
    def save_config(self, config: VibeConfig) -> None:
        """Save configuration to file."""
        config.validate()
        
        # Set restrictive permissions (user only)
        self.config_file.touch(mode=0o600, exist_ok=True)
        
        with open(self.config_file, 'w') as f:
            json.dump(asdict(config), f, indent=2)


class EnvironmentManager:
    """Manage environment variables and security."""
    
    @staticmethod
    def get_safe_env(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with logging (excluding secrets)."""
        value = os.environ.get(key, default)
        
        # Don't log API keys or other secrets
        if any(secret in key.lower() for secret in ['key', 'token', 'secret', 'password']):
            logger.debug(f"Environment variable {key}: {'SET' if value else 'NOT SET'}")
        else:
            logger.debug(f"Environment variable {key}: {value}")
        
        return value
    
    @staticmethod
    def validate_git_environment() -> bool:
        """Validate git is available and properly configured."""
        try:
            result = subprocess.run(
                ["git", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode != 0:
                return False
            
            # Check if we're in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
            
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


# Example usage in CLI
def secure_cli_setup() -> tuple[VibeConfig, str]:
    """Set up CLI with secure configuration."""
    config_manager = SecureConfigManager()
    
    # Load configuration
    try:
        config = config_manager.load_config()
    except RuntimeError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)
    
    # Get API key securely
    api_key = config_manager.get_api_key("gemini")
    if not api_key:
        api_key = typer.prompt(
            "Enter your Gemini API key", 
            hide_input=True
        )
        config_manager.set_api_key("gemini", api_key)
    
    # Validate environment
    if not EnvironmentManager.validate_git_environment():
        typer.echo("Git not available or not in a git repository", err=True)
        raise typer.Exit(1)
    
    return config, api_key


# Input sanitization
def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent issues."""
    if not isinstance(user_input, str):
        raise TypeError("Input must be a string")
    
    # Basic length check
    if len(user_input) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")
    
    # Remove null bytes and control characters (except newlines/tabs)
    sanitized = ''.join(
        char for char in user_input 
        if char.isprintable() or char in '\n\t'
    )
    
    return sanitized.strip()