# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import sys
from pathlib import Path
from typing import Literal

import typer
from colorama import init

from codestory.commands.config import describe_callback
from codestory.constants import APP_NAME
from codestory.core.config.config_loader import ConfigLoader
from codestory.core.exceptions import ValidationError, handle_codestory_exception
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_interface import GitInterface
from codestory.core.logging.logging import setup_logger
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.validation import (
    validate_branch,
    validate_default_branch,
    validate_git_repository,
)
from codestory.onboarding import check_run_onboarding, set_ran_onboarding
from codestory.runtimeutil import (
    ensure_utf8_output,
    get_log_dir_callback,
    get_supported_languages_callback,
    get_supported_providers_callback,
    setup_signal_handlers,
    version_callback,
)

# which commands do not require a global context
no_context_commands = {"config"}
# if you have a broken config, the config command should stil allow you to fix it (or check)
config_override_command = "config"

# Initialize colorama (colored output in terminal)
init(autoreset=True)

# main cli app
app = typer.Typer(
    help=f"{APP_NAME}: Give your project a good story worth reading",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    add_completion=False,
)


# Main cli commands
@app.command(name="commit")
def main_commit(
    ctx: typer.Context,
    target: list[str] | None = typer.Argument(
        None, help="Path(s) to file or directory to commit (supports git pathspecs)."
    ),
    message: str | None = typer.Option(
        None,
        "-m",
        help="Context or instructions for the AI to generate the commit message",
    ),
    intent: str | None = typer.Option(
        None,
        "--intent",
        help="Intent or purpose for the commit, used for relevance filtering.",
    ),
    fail_on_syntax_errors: bool = typer.Option(
        False,
        "--fail-on-syntax-errors",
        help="Fail the commit if syntax errors are detected in the changes.",
    ),
) -> None:
    """Commit current changes into small logical commits. (If you wish to modify
    existing history, use codestory fix or codestory clean)

    Examples:
        # Commit all changes interactively
        cst commit

        # Commit specific directory with message
        cst commit src/  -m "Make 2 commits, one for refactor, one for feature A..."

        # Commit changes with an intent filter enabled
        cst commit --intent "refactor abc into a class"
    """
    from codestory.commands.commit import run_commit

    global_context = ctx.obj
    description = f"Committing {target}" if target else "Committing all changes"
    with (
        handle_codestory_exception(),
        ProgressBarManager.set_pbar(
            description=description, silent=global_context.config.silent
        ),
    ):
        if global_context.config.relevance_filtering and intent is None:
            raise ValidationError(
                "--intent must be provided when relevance filter is active. "
                "You can provide an intent like --intent \"refactor xyz\", or disable filtering with 'cst config relevance_filtering false'"
            )

        if not global_context.config.relevance_filtering and intent is not None:
            from loguru import logger

            logger.warning(
                "You are using the --intent option, but have not enabled the relevance filter! Check 'cst config relevance_filter_level'"
            )

        if run_commit(
            ctx.obj,
            target,
            message,
            intent,
            fail_on_syntax_errors,
        ):
            raise typer.Exit(0)
        else:
            raise typer.Exit(1)


@app.command(name="fix")
def main_fix(
    ctx: typer.Context,
    commit_hash: str = typer.Argument(
        None, help="Hash of the end commit to split or fix"
    ),
    message: str | None = typer.Option(
        None,
        "-m",
        help="Context or instructions for the AI to generate the commit message",
    ),
    start_commit: str = typer.Option(
        None,
        "--start",
        help="Hash of the start commit, non inclusive (optional). If not provided, uses end commit's parent.",
    ),
) -> None:
    """Turn a past commit or range of commits into small logical commits.

    Examples:
        # Fix a specific commit (--start will be parent of def456)
        cst fix def456

        # Fix a range of commits from start to end
        cst fix def456 --start abc123
    """
    from codestory.commands.fix import run_fix

    global_context = ctx.obj
    if start_commit:
        description = f"Fixing {start_commit[:7]} -> {commit_hash[:7]}"
    else:
        description = f"Fixing {commit_hash[:7]}"
    with (
        handle_codestory_exception(),
        ProgressBarManager.set_pbar(
            description=description, silent=global_context.config.silent
        ),
    ):
        if run_fix(ctx.obj, commit_hash, start_commit, message):
            raise typer.Exit(0)
        else:
            raise typer.Exit(1)


@app.command(name="clean")
def main_clean(
    ctx: typer.Context,
    ignore: list[str] | None = typer.Option(
        None,
        "--ignore",
        help="Commit hashes or prefixes to ignore.",
    ),
    min_size: int | None = typer.Option(
        None,
        "--min-size",
        help="Minimum change size (lines) to process.",
    ),
    start_from: str | None = typer.Option(
        None,
        "--start",
        help="Where to start cleaning from (inclusive). Defaults to earliest possible commit.",
    ),
    end_at: str | None = typer.Option(
        None,
        "--end",
        help="Where to end cleaning at. (inclusive). Defaults to HEAD.",
    ),
    unpushed: bool = typer.Option(
        False,
        "--unpushed",
        help="Only clean commits that have not been pushed to the upstream branch.",
    ),
) -> None:
    """Fix your entire repository starting from the latest commit.

    Note: This command will stop at the first merge commit encountered.
    Merge commits cannot be rewritten and will mark the boundary of the clean operation.

    Examples:
        # Clean starting from the latest commit
        cst clean

        # Clean starting from a specific commit with a minimum line count of 5
        cst clean abc123 --min-size 5

        # Clean while ignoring certain commits
        cst clean --ignore def456 --ignore ghi789

        # Clean only unpushed commits
        cst clean --unpushed
    """
    from codestory.commands.clean import run_clean

    global_context = ctx.obj
    if start_from and end_at:
        description = f"Cleaning {start_from[:7]} to {end_at[:7]}"
    elif start_from:
        description = f"Cleaning {start_from[:7]} to HEAD"
    elif end_at:
        description = f"Cleaning up to {end_at[:7]}"
    elif unpushed:
        description = "Cleaning unpushed commits"
    else:
        description = "Cleaning all possible commits"

    with (
        handle_codestory_exception(),
        ProgressBarManager.set_pbar(
            description=description, silent=global_context.config.silent
        ),
    ):
        if run_clean(ctx.obj, ignore, min_size, start_from, end_at, unpushed):
            raise typer.Exit(0)
        else:
            raise typer.Exit(1)


@app.command(name="config")
def main_config(
    ctx: typer.Context,
    describe: bool = typer.Option(
        False,
        "--describe",
        callback=describe_callback,
        is_eager=True,
        help="Describe available configuration options and exit.",
    ),
    key: str | None = typer.Argument(None, help="Configuration key to get or set."),
    value: str | None = typer.Argument(
        None, help="Value to set (omit to get current value)."
    ),
    scope: Literal["local", "global", "env"] = typer.Option(
        None,
        "--scope",
        help="Select which scope to modify. Defaults to local for setting/deleting, all for getting.",
    ),
    delete: bool = typer.Option(
        False,
        "--delete",
        help="Delete configuration. Deletes all config in scope if no key specified, or specific key if provided.",
    ),
    deleteall: bool = typer.Option(
        False,
        "--deleteall",
        help="Delete configuration from both global and local scopes.",
    ),
) -> None:
    """Manage global and local codestory configurations.

    Priority order: program arguments > custom config > local config > environment variables > global config

    Examples:
        # Get a configuration value
        cst config model

        # Set a local configuration value
        cst config model "gemini/gemini-2.0-flash"

        # Set a global configuration value
        cst config model "openai/gpt-4" --scope global

        # Show all configuration
        cst config

        # Delete a specific key from local config
        cst config model --delete

        # Delete all config from global scope
        cst config --delete --scope global

        # Delete a key from both global and local scopes
        cst config model --deleteall

        # Delete all config from both scopes
        cst config --deleteall
    """
    from codestory.commands.config import run_config

    with handle_codestory_exception():
        run_config(key, value, scope, delete, deleteall)


def load_global_config(custom_config_path: str, **input_args):
    # input args are the "runtime overrides" for configs
    from codestory.context import GlobalConfig

    config_args = {}

    for key, item in input_args.items():
        if item is not None:
            config_args[key] = item

    return ConfigLoader.get_full_config(
        GlobalConfig,
        config_args,
        custom_config_path=Path(custom_config_path)
        if custom_config_path is not None
        else None,
    )


def create_global_callback():
    """Dynamically creates the main callback function with GlobalConfig parameters.

    This allows the CLI arguments to be automatically synced with
    GlobalConfig fields.
    """
    from codestory.context import GlobalConfig, GlobalContext

    # Get dynamic parameters from GlobalConfig
    cli_params = GlobalConfig.get_cli_params()

    # Define the callback function with dynamic signature
    def callback(
        ctx: typer.Context,
        version: bool = typer.Option(
            False,
            "--version",
            "-V",
            callback=version_callback,
            help="Show version and exit",
        ),
        log_path: bool = typer.Option(
            False,
            "--log-dir",
            "-LD",
            callback=get_log_dir_callback,
            help="Show log path (where logs for codestory live) and exit",
        ),
        supported_languages: bool = typer.Option(
            False,
            "--supported-languages",
            "-SL",
            callback=get_supported_languages_callback,
            help="Show languages that support semantic analysis and grouping, then exit",
        ),
        supported_providers: bool = typer.Option(
            False,
            "--supported-providers",
            "-SP",
            callback=get_supported_providers_callback,
            help="Show all supported model providers you can use for logical grouping. Set using 'codestory config model provider:model'",
        ),
        repo_path: str = typer.Option(
            None,
            "--repo",
            help="Path to the git repository to operate on. Defaults to current directory.",
        ),
        branch: str | None = typer.Option(
            None,
            "--branch",
            help="Branch to operate on. Defaults to current branch.",
        ),
        custom_config: str | None = typer.Option(
            None,
            "--custom-config",
            help="Path to a custom config file",
        ),
        **kwargs,  # Dynamic GlobalConfig params injected here
    ) -> None:
        """Global setup callback.

        Initialize global context/config used by commands
        """
        with handle_codestory_exception():
            # conditions to not create global context
            if ctx.invoked_subcommand is None:
                if not check_run_onboarding(can_continue=False):
                    print(ctx.get_help())

                raise typer.Exit()

            # skip --help in subcommands
            if any(arg in ctx.help_option_names for arg in sys.argv):
                return

            if ctx.invoked_subcommand == config_override_command:
                # dont try to load config
                return

            if ctx.invoked_subcommand in no_context_commands:
                return

            config, used_config_sources, used_default = load_global_config(
                custom_config,
                **kwargs,  # Pass all dynamic config args
            )

            # if we run a command that requires a global context, check that the user has learned the onboarding process
            if not used_config_sources and used_default:
                # we only used defaults (so no user set config)
                check_run_onboarding(can_continue=True)

                # reload any possible set configs through onboarding
                config, used_config_sources, used_default = load_global_config(
                    custom_config,
                    **kwargs,
                )
            else:
                # the user likely knows what they are doing
                set_ran_onboarding()

            # Set custom language config override if provided
            if config.custom_language_config is not None:
                from codestory.core.semantic_analysis.mappers.query_manager import (
                    QueryManager,
                )

                QueryManager.set_override(config.custom_language_config)

            setup_logger(
                ctx.invoked_subcommand,
                debug=config.verbose,
                silent=config.silent,
                no_log_files=config.no_log_files,
            )

            if config.model == "no-model":
                from loguru import logger

                logger.warning(
                    "Logical grouping is disabled as no model has been configured. To set a model please check 'cst config model'."
                )

            # Initialize git interface and commands to resolve branch

            resolved_repo_path = Path(repo_path) if repo_path is not None else Path(".")
            git_interface = GitInterface(resolved_repo_path)
            git_commands = GitCommands(git_interface)

            validate_git_repository(
                git_commands
            )  # fail immediately if we arent in a valid git repo as we expect one

            if branch:
                validate_branch(git_commands, branch)
                current_branch = branch
            else:
                validate_default_branch(git_commands)
                # Get current branch (already validated we are on one by validate_default_branch)
                current_branch = (git_commands.get_show_current_branch() or "").strip()

            global_context = GlobalContext(
                repo_path=resolved_repo_path,
                git_interface=git_interface,
                git_commands=git_commands,
                config=config,
                current_branch=current_branch,
            )

            # Set up signal handlers with context for proper cleanup
            setup_signal_handlers(global_context)

            ctx.obj = global_context

    # Dynamically add GlobalConfig parameters to function signature
    # This is necessary for typer to recognize them
    import inspect

    sig = inspect.signature(callback)
    params = list(sig.parameters.values())

    # Remove **kwargs and add actual dynamic parameters
    params = [p for p in params if p.name != "kwargs"]
    for param_name, (param_type, param_default) in cli_params.items():
        params.append(
            inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=param_default,
                annotation=param_type,
            )
        )

    callback.__signature__ = sig.replace(parameters=params)
    return callback


# Register the dynamically created callback
main = create_global_callback()
app.callback(invoke_without_command=True)(main)


def run_app():
    """Run the application with global exception handling."""
    # force stdout to be utf8
    ensure_utf8_output()
    # launch cli
    app(prog_name="cst")


if __name__ == "__main__":
    run_app()
