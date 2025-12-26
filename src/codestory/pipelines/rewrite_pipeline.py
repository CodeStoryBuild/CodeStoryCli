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

from colorama import Fore, Style

from codestory.core.data.commit_group import CommitGroup
from codestory.core.git_commands.git_commands import GitCommands
from codestory.core.logging.utils import time_block
from codestory.core.synthesizer.git_synthesizer import GitSynthesizer


def print_patch_cleanly(patch_content: str, max_lines: int = 120):
    """
    Displays a patch/diff content cleanly using direct Colorama styling.
    """
    # Direct mapping to Colorama styles
    styles = {
        "diff_header": Fore.BLUE,
        "between_diff": Fore.WHITE + Style.BRIGHT,
        "header_removed": Fore.RED + Style.BRIGHT,
        "header_added": Fore.GREEN + Style.BRIGHT,
        "hunk": Fore.BLUE,
        "removed": Fore.RED,
        "added": Fore.GREEN,
        "context": Fore.WHITE + Style.DIM,
    }

    # Iterate through the patch content line by line
    between_diff_and_hunk = False

    for line in patch_content.splitlines()[:max_lines]:
        style_key = "context"  # default

        # Check up to the first ten characters (optimizes for large lines)
        prefix = line[:10]

        if prefix.startswith("diff --git"):
            style_key = "diff_header"
            between_diff_and_hunk = True
        elif prefix.startswith("---"):
            style_key = "header_removed"
            between_diff_and_hunk = False
        elif prefix.startswith("+++"):
            style_key = "header_added"
            between_diff_and_hunk = False
        elif prefix.startswith("@@"):
            style_key = "hunk"
        elif prefix.startswith("-"):
            style_key = "removed"
        elif prefix.startswith("+"):
            style_key = "added"
        elif between_diff_and_hunk:
            # lines after diff header, before first hunk (e.g., file mode lines)
            style_key = "between_diff"

        # we print (not logger) because this is a required output, the user needs to know what changes to accept/reject

        # Apply style directly
        print(f"{styles[style_key]}{line}{Style.RESET_ALL}")

    if len(patch_content.splitlines()) > max_lines:
        print(f"{Fore.YELLOW}(Diff truncated){Style.RESET_ALL}\n")


class RewritePipeline:
    """
    Final stage of the pipeline: synthesizes git commits from commit groups.

    This class is now simplified to only handle the synthesis step, as the
    diff generation, context management, grouping, filtering, and user
    interaction are handled by DiffContext, GroupingContext, and CMDUserFilter.
    """

    def __init__(
        self,
        git_commands: GitCommands,
    ):
        self.git_commands = git_commands
        self.synthesizer = GitSynthesizer(git_commands)

    def run(self, base_commit_hash: str, final_groups: list[CommitGroup]) -> str | None:
        """
        Execute the synthesizer to create git commits from the final groups.

        Args:
            base_commit_hash: The commit to build on top of
            final_groups: The commit groups to synthesize into git commits

        Returns:
            The hash of the last created commit, or None if no commits were created
        """
        from loguru import logger

        if not final_groups:
            logger.debug("No groups to synthesize")
            return None

        with time_block("Executing Synthesizer Pipeline"):
            new_commit_hash = self.synthesizer.execute_plan(
                final_groups, base_commit_hash
            )

        return new_commit_hash
