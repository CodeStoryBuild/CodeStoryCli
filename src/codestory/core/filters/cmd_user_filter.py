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
from tqdm import tqdm

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.patch.git_patch_generator import GitPatchGenerator
from codestory.core.diff.patch.semantic_patch_generator import SemanticPatchGenerator
from codestory.core.diff.pipeline.filter import Filter
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class CMDUserFilter(Filter):
    """Command-line user filter for reviewing and accepting/rejecting commit groups.

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
        file_manager: FileManager,
        use_semantic_diff: bool,
        silent: bool = False,
    ):
        self.auto_accept = auto_accept
        self.ask_for_commit_message = ask_for_commit_message
        self.can_partially_reject_changes = can_partially_reject_changes
        self.file_manager = file_manager
        self.use_semantic_diff = use_semantic_diff
        self.silent = silent

    def filter(
        self, groups: list[AtomicContainer]
    ) -> tuple[list[AtomicContainer], list[AtomicContainer]]:
        """Filter commit groups through user interaction."""
        # Prepare pretty diffs for each proposed group
        if not groups:
            return [], []

        all_affected_files = set()
        if self.use_semantic_diff:
            display_patch_map = SemanticPatchGenerator(
                groups,
                self.file_manager,
                context_lines=2,
            ).get_patches(groups)
        else:
            display_patch_map = GitPatchGenerator(
                groups,
                self.file_manager,
            ).get_patches(groups)

        accepted_groups: list[AtomicContainer] = []
        user_rejected_groups: list[AtomicContainer] = []

        for idx, group in enumerate(groups):
            num = idx + 1

            if isinstance(group, CommitGroup):
                commit_message = group.commit_message
                logger.info(
                    "\n------------- Proposed commit #{num}: {message} -------------",
                    num=num,
                    message=commit_message,
                )
            else:
                logger.info(
                    "\n------------- Proposed change #{num} -------------",
                    num=num,
                )

            affected_files = group.canonical_paths()
            all_affected_files.update(affected_files)

            files_preview = b", ".join(sorted(affected_files))
            logger.info(
                "Files: {files}\n",
                files=files_preview.decode("utf-8", errors="replace"),
            )

            # Log the diff for this group at debug level
            diff_text = display_patch_map.get(idx, "") or "(no diff)"

            if not (self.silent and self.auto_accept):
                with tqdm.external_write_mode():
                    print(f"Diff for #{num}:")
                    if diff_text != "(no diff)":
                        if self.use_semantic_diff:
                            CMDUserFilter.print_patch_cleanly_semantic(
                                diff_text, max_lines=120
                            )
                        else:
                            CMDUserFilter.print_patch_cleanly(diff_text, max_lines=120)
                    else:
                        print(f"{Fore.YELLOW}(no diff){Style.RESET_ALL}")

            logger.debug(
                "Group preview: idx={idx} chunks={chunk_count} files={files}",
                idx=idx,
                chunk_count=len(group.get_atomic_chunks()),
                files=len(affected_files),
            )

            # Acceptance/modification of groups:
            if not self.auto_accept:
                if self.ask_for_commit_message:
                    if self.can_partially_reject_changes:
                        with tqdm.external_write_mode():
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
                        with tqdm.external_write_mode():
                            custom_message = typer.prompt(
                                "Would you like to optionally override this commit message with a custom message?",
                                default="",
                                type=str,
                            ).strip()

                    if custom_message:
                        group = CommitGroup(group, commit_message=custom_message)

                    accepted_groups.append(group)
                else:
                    if self.can_partially_reject_changes:
                        with tqdm.external_write_mode():
                            keep = typer.confirm("Do you want to commit this change?")
                        if keep:
                            accepted_groups.append(group)
                        else:
                            user_rejected_groups.append(group)
                    else:
                        accepted_groups.append(group)
            else:
                accepted_groups.append(group)

        num_acc = len(accepted_groups)
        if num_acc == 0:
            logger.info("No changes applied")
            logger.info("User did not accept any commits")
            return [], []

        if self.auto_accept:
            apply_final = True
            logger.info(f"Auto-confirm: Accepted {num_acc} proposed groups")
        else:
            with tqdm.external_write_mode():
                apply_final = typer.confirm(
                    f"Accept {num_acc} proposed groups?",
                )

        if not apply_final:
            logger.info("No changes applied")
            logger.info("User declined applying commits")
            return [], groups

        logger.debug(
            "Num accepted groups: {groups}",
            groups=num_acc,
        )
        return accepted_groups, user_rejected_groups

    @staticmethod
    def print_patch_cleanly(patch_content: str, max_lines: int = 120):
        """Displays a patch/diff content cleanly using direct Colorama styling."""
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

        print("--- Begin Patch ---")

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
        print("---  End Patch  ---")

    @staticmethod
    def print_patch_cleanly_semantic(patch_content: str, max_lines: int = 120):
        """Displays a semantic patch content cleanly using direct Colorama styling."""
        styles = {
            "h": Fore.BLUE,
            "rem": Fore.RED,
            "add": Fore.GREEN,
            "ctx": Fore.WHITE + Style.DIM,
        }

        print("--- Begin Semantic Patch ---")

        for line in patch_content.splitlines()[:max_lines]:
            style_key = "ctx"  # default

            # Semantic format is [tag] message
            if line.startswith("[h]"):
                style_key = "h"
            elif line.startswith("[rem]"):
                style_key = "rem"
            elif line.startswith("[add]"):
                style_key = "add"
            elif line.startswith("[ctx]"):
                style_key = "ctx"

            # Apply style directly
            print(f"{styles[style_key]}{line}{Style.RESET_ALL}")

        if len(patch_content.splitlines()) > max_lines:
            print(f"{Fore.YELLOW}(Diff truncated){Style.RESET_ALL}\n")
        print("---  End Semantic Patch  ---")
