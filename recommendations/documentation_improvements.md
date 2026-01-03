# Improved CLI Documentation Strategy

## 1. Enhanced CLI Help

### Command Examples
```python
def commit_with_examples():
    """
    Commits changes with AI-powered messages.
    
    Examples:
        # Commit all changes interactively
        $ vibe commit
        
        # Commit specific directory with message
        $ vibe commit src/ "Refactor user authentication"
        
        # Auto-accept all suggestions
        $ vibe commit --yes
        
        # Commit single file
        $ vibe commit utils/helpers.py
    """
```

### Rich Help Formatting
```python
import typer
from rich.console import Console
from rich.table import Table

def show_enhanced_help():
    """Show enhanced help with examples and formatting."""
    console = Console()
    
    table = Table(title="Vibe Commands")
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Example", style="green")
    
    table.add_row(
        "commit", 
        "Create AI-powered commits", 
        "vibe commit src/ --yes"
    )
    table.add_row(
        "expand", 
        "Break down large commits", 
        "vibe expand abc123"
    )
    table.add_row(
        "clean", 
        "Clean up commit history", 
        "vibe clean --min-size 5"
    )
    
    console.print(table)
```

## 2. Configuration Help

### Auto-generated Config Documentation
```python
def generate_config_help():
    """Generate help for configuration options."""
    return """
Configuration File: ~/.config/vibe/config.json

{
  "ai_model": "gemini-pro",        # AI model to use
  "max_chunks": 10,                # Max chunks per commit
  "auto_yes": false,               # Skip confirmations
  "log_level": "INFO"              # Logging verbosity
}

Environment Variables:
  VIBE_API_KEY     - AI service API key
  VIBE_LOG_LEVEL   - Override log level
  VIBE_CONFIG_PATH - Custom config file path
"""

## 3. Progressive Disclosure

def command_with_progressive_help():
    """Show help progressively based on user needs."""
    
    # Basic help (default)
    basic_help = "Commit changes with AI-powered messages"
    
    # Detailed help (with --help)
    detailed_help = """
    Analyzes your git changes and creates meaningful commits using AI.
    
    The tool will:
    1. Scan for uncommitted changes
    2. Group related changes together  
    3. Generate descriptive commit messages
    4. Ask for your confirmation before committing
    
    Use --yes to skip confirmations in scripts.
    """
    
    # Expert help (with --help --verbose)
    expert_help = """
    Advanced Usage:
    - Supports partial commits by specifying target paths
    - Uses tree-sitter for syntax-aware grouping
    - Integrates with multiple AI providers
    - Maintains git history integrity
    
    Configuration: ~/.config/vibe/config.json
    Logs: ~/.local/share/VibeCommit/logs/
    """
```

## 4. User Onboarding

```python
def first_run_setup():
    """Guide users through initial setup."""
    console = Console()
    
    console.print("[bold green]Welcome to Vibe! 🎉[/bold green]")
    console.print("Let's set up your AI-powered git workflow.\n")
    
    # Check prerequisites
    if not check_git_available():
        console.print("[red]❌ Git not found. Please install git first.[/red]")
        return
    
    console.print("[green]✅ Git found[/green]")
    
    # API key setup
    if not check_api_key():
        console.print("\n[yellow]🔑 API Key Setup[/yellow]")
        console.print("Visit: https://ai-provider.com/api-keys")
        api_key = typer.prompt("Enter your API key")
        save_api_key(api_key)
    
    console.print("[green]✅ API key configured[/green]")
    
    # Quick tutorial
    console.print("\n[cyan]🚀 Quick Start[/cyan]")
    console.print("1. Make some changes to your code")
    console.print("2. Run: [bold]vibe commit[/bold]")
    console.print("3. Review and accept the AI-generated commits")
    
    console.print("\n[dim]Run 'vibe --help' anytime for more options![/dim]")
```