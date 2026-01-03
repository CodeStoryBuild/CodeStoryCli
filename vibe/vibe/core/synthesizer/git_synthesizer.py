# vibe/core/synthesizer/synthesizer.py

import tempfile
from pathlib import Path
from typing import List, Dict, Union, Optional
from itertools import groupby
import os

from loguru import logger

from ..git_interface.interface import GitInterface
from ..data.models import CommitGroup, CommitResult
from ..data.diff_chunk import DiffChunk
from ..data.line_changes import Addition, Removal
from ..data.composite_diff_chunk import CompositeDiffChunk
from ..commands.git_const import DEVNULL


class GitSynthesizer:
    """
    Builds a clean, linear Git history from a plan of commit groups,
    using a provided GitInterface for all Git operations.
    """

    def __init__(self, git: GitInterface):
        self.git = git

    def _run_git_binary(
        self,
        *args: str,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict] = None,
        stdin_content: Optional[Union[str, bytes]] = None,
    ) -> bytes:
        """
        Helper to run Git commands via the binary interface.
        """
        input_data = None
        if isinstance(stdin_content, str):
            input_data = stdin_content.encode("utf-8")
        elif isinstance(stdin_content, bytes):
            input_data = stdin_content

        result = self.git.run_git_binary(
            args=list(args), input_bytes=input_data, env=env, cwd=cwd
        )

        if result is None:
            raise RuntimeError(f"Git command failed: {' '.join(args)}")

        return result

    def _run_git_decoded(self, *args: str, **kwargs) -> str:
        """
        Helper to run Git and get a decoded string. It relies on _run_git_binary for execution.
        """
        output_bytes = self._run_git_binary(*args, **kwargs)
        return output_bytes.decode("utf-8", errors="replace").strip()

    def _generate_unified_diff(
        self, chunks: List[DiffChunk], total_chunks_per_file: Dict[str, int]
    ) -> Dict[str, str]:
        """
        Generates a dictionary of valid, cumulative unified diffs (patches) for each file
        """
        patches: Dict[str, str] = {}

        # group chunks by file
        sorted_chunks = sorted(chunks, key=lambda c: c.canonical_path())

        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks: list[DiffChunk] = list(file_chunks_iter)

            if len(file_chunks) == 0:
                logger.warning(
                    "No chunks found for file: {file_path}", file_path=file_path
                )
                continue

            current_count = len(file_chunks)
            total_expected = total_chunks_per_file.get(file_path, current_count)

            patch_lines = []

            # single chunk for metadata extraction
            single_chunk: DiffChunk = file_chunks[0]

            old_file_path = single_chunk.old_file_path
            new_file_path = single_chunk.new_file_path

            multiple_chunks = len(file_chunks) > 1

            # start by generating patch header
            # multiple chunks means it must be standard chunks
            # a single chunk can be different types
            if multiple_chunks:
                # TMP: check that if there are multiple chunks, its split content
                assert all(
                    c.has_content for c in file_chunks
                ), "Standard chunk does not have content!"
                assert all(
                    c.old_file_path == old_file_path for c in file_chunks
                ), "Standard chunk old file paths dont match!"
                assert all(
                    c.new_file_path == new_file_path for c in file_chunks
                ), "Standard chunk new file paths dont match!"
                assert all(
                    c.is_file_addition == single_chunk.is_file_addition
                    for c in file_chunks
                ), "Standard chunk file addition flags dont match!"
                assert all(
                    c.is_file_deletion == single_chunk.is_file_deletion
                    for c in file_chunks
                ), "Standard chunk file deletion flags dont match!"
                assert all(
                    c.is_file_rename == single_chunk.is_file_rename for c in file_chunks
                ), "Standard chunk file rename flags dont match!"

            if single_chunk.is_standard_modification:
                patch_lines.append(
                    "diff --git a/{file_path} b/{file_path}".format(
                        file_path=new_file_path,
                    )
                )
            elif single_chunk.is_file_rename:
                patch_lines.append(
                    "diff --git a/{old_path} b/{new_path}".format(
                        old_path=old_file_path, new_path=new_file_path
                    )
                )
                patch_lines.append(
                    "rename from {old_path}".format(old_path=old_file_path)
                )
                patch_lines.append(
                    "rename to {new_path}".format(new_path=new_file_path)
                )
            elif single_chunk.is_file_deletion:
                # possible edge case: file deletion with multiple chunks
                if current_count < total_expected:
                    # in this case, we treat it as a standard modification
                    patch_lines.append(
                        "diff --git a/{file_path} b/{file_path}".format(
                            file_path=old_file_path,
                        )
                    )
                else:
                    # we have all deletion chunks, so we can treat it as a deletion
                    patch_lines.append(
                        "diff --git a/{file_path} b/{file_path}".format(
                            file_path=old_file_path,
                        )
                    )
                    patch_lines.append(
                        "deleted file mode {mode}".format(
                            mode=single_chunk.file_mode or "100644"
                        )
                    )
            elif single_chunk.is_file_addition:
                patch_lines.append(
                    "diff --git a/{file_path} b/{file_path}".format(
                        file_path=new_file_path,
                    )
                )
                patch_lines.append(
                    "new file mode {mode}".format(
                        mode=single_chunk.file_mode or "100644"
                    )
                )
            elif single_chunk.is_standard_modification:
                patch_lines.append(
                    "diff --git a/{file_path} b/{file_path}".format(
                        file_path=new_file_path,
                    )
                )

            old_file_header = (
                f"a/{old_file_path}" if old_file_path is not None else DEVNULL
            )

            new_file_header = (
                f"b/{new_file_path}" if new_file_path is not None else DEVNULL
            )

            # second part of deletion edge case
            # if we are in partial deletion state, new_file_header should act like a standard_change
            # that is it should be old_file_header
            if single_chunk.is_file_deletion and current_count < total_expected:
                new_file_header = old_file_header

            patch_lines.append(
                "--- {old_file_header}".format(old_file_header=old_file_header)
            )
            patch_lines.append(
                "+++ {new_file_header}".format(new_file_header=new_file_header)
            )

            terminator_needed = True

            if not multiple_chunks and not single_chunk.has_content:
                patch_lines.append("@@ -0,0 +0,0 @@")
            else:
                # Sort chunks by their old_start line to ensure correct order in the patch
                sorted_file_chunks = sorted(
                    file_chunks,
                    key=lambda c: c.line_anchor,
                )

                if single_chunk.is_file_addition:
                    # file additions are handled differently
                    # since they are a new file, we need to merge all chunks into a new contigous hunk
                    additions = []
                    for sorted_chunk in sorted_file_chunks:
                        additions.extend(sorted_chunk.parsed_content)

                    hunk_header = f"@@ -{0},{0} +{1},{len(additions)} @@"
                    patch_lines.append(hunk_header)

                    for item in additions:
                        patch_lines.append(f"+{item.content}")

                else:
                    # go over each chunk and generate the hunk headers and content
                    for sorted_chunk in sorted_file_chunks:
                        removals = [
                            p
                            for p in sorted_chunk.parsed_content
                            if isinstance(p, Removal)
                        ]
                        additions = [
                            p
                            for p in sorted_chunk.parsed_content
                            if isinstance(p, Addition)
                        ]

                        old_len = len(removals)
                        new_len = len(additions)

                        hunk_header = f"@@ -{sorted_chunk.old_start},{old_len} +{sorted_chunk.new_start},{new_len} @@"
                        patch_lines.append(hunk_header)

                        for item in sorted_chunk.parsed_content:
                            if isinstance(item, Removal):
                                patch_lines.append(f"-{item.content}")
                            elif isinstance(item, Addition):
                                if item.content == "\\ No newline at end of file":
                                    # special terminator patch
                                    patch_lines.append(f"{item.content}")
                                    terminator_needed = False
                                else:
                                    patch_lines.append(f"+{item.content}")

            patches[file_path] = "\n".join(patch_lines) + (
                "\n" if terminator_needed else ""
            )

            print(f"{patches=}")

        return patches

    def _build_tree_from_changes(
        self,
        base_commit_hash: str,
        chunks_for_commit: List[DiffChunk],
        total_chunks_per_file: Dict[str, int],
    ) -> str:
        """
        Creates a new Git tree object by applying a specific set of changes
        to a base commit.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir) / "synth_worktree"

            try:
                # create the worktree off of our base commit
                self._run_git_binary(
                    "worktree", "add", "--detach", str(worktree_path), base_commit_hash
                )

                patches = self._generate_unified_diff(
                    chunks_for_commit, total_chunks_per_file
                )
                for file_path, patch_content in patches.items():
                    if not patch_content.strip():
                        logger.warning(f"Skipping empty patch for file: {file_path}")
                        continue

                    try:
                        self._run_git_binary(
                            "apply",
                            "--index",
                            "--recount",
                            "--unidiff-zero",
                            cwd=worktree_path,
                            stdin_content=patch_content,
                        )

                    except RuntimeError as e:
                        raise RuntimeError(
                            f"FATAL: Git apply failed for '{file_path}'.\n"
                            f"--- ERROR DETAILS ---\n{e}\n"
                            f"--- PATCH CONTENT ---\n{patch_content}\n"
                        )

                # 1. Define a path for a temporary index file INSIDE the worktree.
                temp_index_path = Path(temp_dir) / ".git_temporary_index"

                # 2. Clean up any existing index files for the temp index.
                # 2. Clean up any existing lock files for the temp index.
                temp_index_lock_path = Path(str(temp_index_path) + ".lock")
                if temp_index_lock_path.exists():
                    temp_index_lock_path.unlink()

                # 3. Create a modified environment that tells Git to use this index.
                env = os.environ.copy()
                env["GIT_INDEX_FILE"] = str(temp_index_path)

                # 5. Run 'git add' with this environment. It will now write to the temp index.
                self._run_git_binary("add", "-A", ".", cwd=worktree_path, env=env)

                # 6. Run 'write-tree' with the SAME environment. It will read from the temp index.
                new_tree_hash = self._run_git_decoded(
                    "write-tree", cwd=worktree_path, env=env
                )

                return new_tree_hash

            finally:
                self._run_git_binary(
                    "worktree", "remove", "--force", str(worktree_path)
                )

    def _create_commit(self, tree_hash: str, parent_hash: str, message: str) -> str:
        return self._run_git_decoded(
            "commit-tree", tree_hash, "-p", parent_hash, "-m", message
        )

    # vibe/core/synthesizer/synthesizer.py

    def execute_plan(
        self, groups: List[CommitGroup], base_commit: str, branch_to_update: str
    ) -> List[CommitResult]:
        """
        Executes the synthesis plan. For each group, it creates a new commit
        by applying the CUMULATIVE set of changes from all processed groups
        to the ORIGINAL base commit. This ensures each commit build is isolated
        and stateless.
        """

        # Build a global map of total chunk counts per file
        # this will be used for file deletions where you want to adjust the patch header if not all deletion chunks are present
        all_chunks = []
        for group in groups:
            for chunk in group.chunks:
                all_chunks.extend(chunk.get_chunks())

        total_chunks_per_file = {}
        for file_path, file_chunks_iter in groupby(
            sorted(all_chunks, key=lambda c: c.canonical_path()),
            key=lambda c: c.canonical_path(),
        ):
            total_chunks_per_file[file_path] = len(list(file_chunks_iter))

        results: List[CommitResult] = []

        # 1. Establish the constant starting point for all tree builds.
        original_base_commit_hash = self._run_git_decoded("rev-parse", base_commit)

        # 2. These variables will track the evolving state of our NEW commit chain.
        last_synthetic_commit_hash = original_base_commit_hash
        cumulative_chunks: List[DiffChunk] = []

        # Determine if we are on a branch or detached HEAD for the final update.
        current_branch = self._run_git_decoded("rev-parse", "--abbrev-ref", "HEAD")

        for group in groups:
            try:
                # 3. Accumulate the chunks from the current group.
                cumulative_chunks.extend(group.chunks)

                # Flatten composite chunks into primitives
                primitive_chunks: List[DiffChunk] = []
                for chunk in cumulative_chunks:
                    primitive_chunks.extend(chunk.get_chunks())

                # 4. Build a new tree from scratch.
                #    - ALWAYS start from the original base commit's state.
                #    - ALWAYS apply the full set of accumulated changes.
                #    This is the key to the stateless, cumulative rebuild.
                new_tree_hash = self._build_tree_from_changes(
                    original_base_commit_hash, primitive_chunks, total_chunks_per_file
                )

                # 5. Create the new commit, chaining it to the previous one we made.
                full_message = group.commit_message
                if group.extended_message:
                    full_message += f"\n\n{group.extended_message}"

                new_commit_hash = self._create_commit(
                    new_tree_hash, last_synthetic_commit_hash, full_message
                )

                # 6. The commit we just made becomes the parent for the NEXT loop iteration.
                last_synthetic_commit_hash = new_commit_hash
                results.append(CommitResult(commit_hash=new_commit_hash, group=group))

            except Exception as e:
                raise RuntimeError(
                    e,
                    f"FATAL: Synthesis failed during group '{group.group_id}'. No changes have been applied.",
                )

        # 7. After the loop, the last commit we created is the new head of our chain.
        final_commit_hash = last_synthetic_commit_hash
        if final_commit_hash != original_base_commit_hash:
            # Update the branch ref dynamically
            self._run_git_binary(
                "update-ref", f"refs/heads/{current_branch}", final_commit_hash
            )
            # Update the working directory to reflect the new branch state
            self._run_git_binary("reset", "--hard", final_commit_hash)

        return results
