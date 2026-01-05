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

import os
import shutil
import tempfile

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.patch.git_patch_generator import GitPatchGenerator
from codestory.core.exceptions import SynthesizerError
from codestory.core.git.git_commands import GitCommands
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class GitSynthesizer:
    """Builds a clean, linear Git history from a plan of commit groups by manipulating
    the Git Index directly, avoiding worktree/filesystem overhead."""

    def __init__(self, git_commands: GitCommands, file_manager: FileManager):
        self.git_commands = git_commands
        self.file_manager = file_manager

    def _build_tree_index_only(
        self,
        template_index_path: str,
        atomic_groups: list[CommitGroup],
        patch_generator: GitPatchGenerator,
    ) -> str:
        """Creates a new Git tree object by applying changes directly to a temporary Git
        Index.

        This avoids creating any files on the filesystem.
        """

        # 1. Create a temp file to serve as the isolated Git Index
        # We use delete=False and close it immediately so we can pass the path to Git
        # (Windows prevents opening a file twice if strictly locked, this avoids that)
        temp_index_fd, temp_index_path = tempfile.mkstemp(prefix="codestory_index_")
        os.close(temp_index_fd)

        # Copy the template index to the new temporary index
        shutil.copy2(template_index_path, temp_index_path)

        # 2. Create an environment that forces Git to use this specific index file
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = temp_index_path

        try:
            # 3. Generate the combined patch
            patches = patch_generator.generate_diff(atomic_groups)

            if patches:
                ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
                combined_patch = b"".join(patch for _, patch in ordered_items)

                try:
                    # 5. Apply patch to the INDEX only (--cached)
                    # --cached: modifies the index, ignores working dir
                    # --unidiff-zero: allows patches with 0 context lines (common in AI diffs)
                    applied = self.git_commands.apply(
                        combined_patch,
                        [
                            "--cached",
                            "--whitespace=nowarn",
                            "--unidiff-zero",
                            "--verbose",
                        ],
                        env=env,
                    )
                    if not applied:
                        raise SynthesizerError("Git apply returned False")
                except Exception as e:
                    raise SynthesizerError(
                        f"FATAL: Git apply failed for combined patch stream.\n"
                        f"--- ERROR DETAILS ---\n{e}\n"
                    ) from e

            # 6. Write the index state to a Tree Object in the Git database
            new_tree_hash = self.git_commands.write_tree(env=env)
            if not new_tree_hash:
                raise SynthesizerError("Failed to write-tree from temporary index.")

            return new_tree_hash

        finally:
            # Cleanup the temporary index file
            if os.path.exists(temp_index_path):
                os.unlink(temp_index_path)

    def _create_commit(self, tree_hash: str, parent_hash: str, message: str) -> str:
        res = self.git_commands.commit_tree(tree_hash, [parent_hash], message)
        if not res:
            raise SynthesizerError("Failed to create commit object.")
        return res

    def execute_plan(
        self,
        all_chunks: list[AtomicContainer],
        final_commit_groups: list[CommitGroup],
        base_commit: str,
    ) -> str:
        """Executes the synthesis plan using pure Git plumbing.

        Returns the hash of the final commit.
        """
        from loguru import logger

        patch_generator = GitPatchGenerator(all_chunks, file_manager=self.file_manager)

        original_base_commit_hash = self.git_commands.get_commit_hash(base_commit)

        # Create a template index populated with the base commit
        template_fd, template_index_path = tempfile.mkstemp(
            prefix="codestory_template_index_"
        )
        os.close(template_fd)
        # Git read-tree fails if the index file exists but is empty (0 bytes).
        if os.path.exists(template_index_path):
            os.unlink(template_index_path)

        try:
            # Populate the template index once
            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = template_index_path
            read_success = self.git_commands.read_tree(
                original_base_commit_hash, env=env
            )
            if not read_success:
                raise SynthesizerError(
                    f"Failed to populate template index from base commit {original_base_commit_hash}"
                )

            # Track state
            last_synthetic_commit_hash = original_base_commit_hash

            logger.debug(
                "Execute plan (Index-Only): groups={groups} base={base}",
                groups=len(final_commit_groups),
                base=original_base_commit_hash,
            )

            total = len(final_commit_groups)
            pbar = ProgressBarManager.get_pbar()

            cumulative_groups: list[CommitGroup] = []

            for i, group in enumerate(final_commit_groups):
                try:
                    # 1. Accumulate chunks
                    # We rebuild from the original base every time using all chunks
                    cumulative_groups.append(group)

                    # 2. Build the Tree (In Memory / Index)
                    new_tree_hash = self._build_tree_index_only(
                        template_index_path,
                        cumulative_groups,
                        patch_generator,
                    )

                    # 3. Create the Commit
                    full_message = group.commit_message

                    new_commit_hash = self._create_commit(
                        new_tree_hash, last_synthetic_commit_hash, full_message
                    )

                    if pbar is not None:
                        msg = group.commit_message
                        if len(msg) > 60:
                            msg = msg[:57] + "..."
                        pbar.set_postfix(
                            {
                                "phase": f"creating commits {i + 1}/{total}",
                                "msg": msg,
                            }
                        )
                    else:
                        logger.success(
                            f"Commit created: {new_commit_hash[:8]} | Msg: {group.commit_message} | Progress: {i + 1}/{total}"
                        )

                    # 4. Update parent for next loop
                    last_synthetic_commit_hash = new_commit_hash

                except Exception as e:
                    raise SynthesizerError(
                        f"FATAL: Synthesis failed during group #{i + 1}. No changes applied. {e}"
                    ) from e

            final_commit_hash = last_synthetic_commit_hash

            return final_commit_hash

        finally:
            # Cleanup the template index file
            if os.path.exists(template_index_path):
                os.unlink(template_index_path)
