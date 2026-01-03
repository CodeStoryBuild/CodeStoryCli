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


import typer
from colorama import Fore, Style
from loguru import logger

from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.diff_generation.git_diff_generator import GitDiffGenerator
from codestory.core.diff_generation.semantic_diff_generator import SemanticDiffGenerator
from codestory.core.logging.utils import describe_chunk
from codestory.core.semantic_grouper.context_manager import ContextManager


class CMDUserFilter:
    """
    Command-line user filter for reviewing and accepting/rejecting commit groups.

    Handles the interactive user experience for:
    1. Displaying proposed commit groups with diffs
    2. Allowing users to accept, reject, or modify commit messages
    3. Confirming final commit application
    """

    def __init__(
        self,
        auto_accept: bool,
        ask_for_commit_message: bool,
        can_partially_reject_changes: bool,
        silent: bool = False,
        context_manager: ContextManager | None = None,
    ):
        self.auto_accept = auto_accept
        self.ask_for_commit_message = ask_for_commit_message
        self.can_partially_reject_changes = can_partially_reject_changes
        self.silent = silent
        self.context_manager = context_manager

    def filter(self, groups: list[CommitGroup]) -> list[CommitGroup]:
        """Filter commit groups through user interaction."""
        # Prepare pretty diffs for each proposed group
        if not groups:
            return []

        all_affected_files = set()
        if self.context_manager is not None:
            display_patch_map = SemanticDiffGenerator(
                groups, context_manager=self.context_manager
            ).get_patches(groups)
        else:
            display_patch_map = GitDiffGenerator(groups).get_patches(groups)

        accepted_groups = []
        user_rejected_groups = []

        for idx, group in enumerate(groups):
            num = idx + 1
            logger.info(
                "\n------------- Proposed commit #{num}: {message} -------------",
                num=num,
                message=group.commit_message,
            )

            if group.extended_message:
                logger.info(
                    "Extended message: {message}",
                    message=group.extended_message,
                )

            affected_files = set()
            for chunk in group.chunks:
                if isinstance(chunk, ImmutableChunk):
                    affected_files.add(
                        chunk.canonical_path.decode("utf-8", errors="replace")
                    )
                else:
                    for diff_chunk in chunk.get_chunks():
                        if diff_chunk.is_file_rename:
                            old_path = diff_chunk.old_file_path.decode(
                                "utf-8", errors="replace"
                            )
                            new_path = diff_chunk.new_file_path.decode(
                                "utf-8", errors="replace"
                            )
                            affected_files.add(f"{old_path} -> {new_path}")
                        else:
                            path = diff_chunk.canonical_path()
                            affected_files.add(path.decode("utf-8", errors="replace"))

            all_affected_files.update(affected_files)

            files_preview = ", ".join(sorted(affected_files))
            if len(files_preview) > 120:
                files_preview = files_preview[:117] + "..."
            logger.info("Files: {files}\n", files=files_preview)

            # Log the diff for this group at debug level
            diff_text = display_patch_map.get(idx, "") or "(no diff)"

            if not (self.silent and self.auto_accept):
                print(f"Diff for #{num}:")
                if diff_text != "(no diff)":
                    CMDUserFilter.print_patch_cleanly(diff_text, max_lines=120)
                else:
                    print(f"{Fore.YELLOW}(no diff){Style.RESET_ALL}")

            logger.debug(
                "Group preview: idx={idx} chunks={chunk_count} files={files}",
                idx=idx,
                chunk_count=len(group.chunks),
                files=len(affected_files),
            )

            # Acceptance/modification of groups:
            if not self.auto_accept:
                if self.ask_for_commit_message:
                    if self.can_partially_reject_changes:
                        custom_message = typer.prompt(
                            "Would you like to optionally override this commit message with a custom message? (type N/n if you wish to reject this change)",
                            default="",
                            type=str,
                        ).strip()
                        # possible rejection of group
                        if custom_message.lower() == "n":
                            user_rejected_groups.append(group)
                            continue
                    else:
                        custom_message = typer.prompt(
                            "Would you like to optionally override this commit message with a custom message?",
                            default="",
                            type=str,
                        ).strip()

                    if custom_message:
                        # TODO how should we handle extended message
                        group = CommitGroup(group.chunks, commit_message=custom_message)

                    accepted_groups.append(group)
                else:
                    if self.can_partially_reject_changes:
                        keep = typer.confirm("Do you want to commit this change?")
                        if keep:
                            accepted_groups.append(group)
                        else:
                            user_rejected_groups.append(group)
                    else:
                        accepted_groups.append(group)
            else:
                accepted_groups.append(group)

        if user_rejected_groups:
            logger.info(
                f"Rejected {len(user_rejected_groups)} commits due to user input"
            )
            logger.info("---------- affected chunks ----------")
            for group in user_rejected_groups:
                logger.info(describe_chunk(group))
            logger.info("These chunks will simply stay as uncommitted changes\n")

        num_acc = len(accepted_groups)
        if num_acc == 0:
            logger.info("No changes applied")
            logger.info("User did not accept any commits")
            return []

        if self.auto_accept:
            apply_final = True
            logger.info(f"Auto-confirm: Applying {num_acc} proposed commits")
        else:
            apply_final = typer.confirm(
                f"Apply {num_acc} proposed commits?",
            )

        if not apply_final:
            logger.info("No changes applied")
            logger.info("User declined applying commits")
            return []

        logger.debug(
            "Num accepted groups: {groups}",
            groups=num_acc,
        )
        return accepted_groups

    @staticmethod
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

            # we print because this is a required output, the user needs to know what changes to accept/reject

            # Apply style directly
            print(f"{styles[style_key]}{line}{Style.RESET_ALL}")

        if len(patch_content.splitlines()) > max_lines:
            print(f"{Fore.YELLOW}(Diff truncated){Style.RESET_ALL}\n")
