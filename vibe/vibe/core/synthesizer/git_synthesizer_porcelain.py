# vibe/core/synthesizer/synthesizer.py

import tempfile
from pathlib import Path
from typing import List, Dict, Union, Optional
from itertools import groupby
import os

from ..git_interface.interface import GitInterface
from ..data.models import CommitGroup, CommitResult
from ..data.diff_chunk import DiffChunk
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.c_diff_chunk import CompositeDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..data.empty_file_chunk import EmptyFileAdditionChunk
from ..data.file_deletion_chunk import FileDeletionChunk
from ..data.models import Addition, Removal


class GitSynthesizer:
    """
    Builds a clean, linear Git history from a plan of commit groups,
    using a provided GitInterface for all Git operations.
    """

    def __init__(self, git: GitInterface):
        self.git = git

    def _run_git(
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
        Helper to run Git and get a decoded string. It relies on _run_git for execution.
        """
        output_bytes = self._run_git(*args, **kwargs)
        return output_bytes.decode("utf-8", errors="replace").strip()

    def _generate_unified_diff(
        self, chunks: List[Union[StandardDiffChunk]]
    ) -> Dict[str, str]:
        """
        Generates a dictionary of valid, cumulative unified diffs (patches)
        for each file, correctly handling line number offsets for disjoint hunks.
        """
        patches: Dict[str, str] = {}

        sorted_chunks = sorted(chunks, key=lambda c: c.file_path())

        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.file_path()
        ):
            file_chunks = list(file_chunks_iter)

            patch_lines = []

            is_file_addition = any(c.is_file_addition for c in file_chunks)
            is_file_deletion = any(c.is_file_deletion for c in file_chunks)

            # Generate appropriate patch headers based on file operation metadata
            if is_file_addition:
                patch_lines.append(f"--- /dev/null")
                patch_lines.append(f"+++ b/{file_path}")
            elif is_file_deletion:
                patch_lines.append(f"--- a/{file_path}")
                patch_lines.append(f"+++ /dev/null")
            else:
                # Regular modification
                patch_lines.append(f"--- a/{file_path}")
                patch_lines.append(f"+++ b/{file_path}")

            sorted_file_chunks = sorted(
                [
                    c
                    for c in file_chunks
                    if isinstance(c, StandardDiffChunk) and len(c.parsed_content) > 0
                ],
                key=lambda c: c.old_start,
            )

            for chunk in sorted_file_chunks:
                removals = [p for p in chunk.parsed_content if isinstance(p, Removal)]
                additions = [p for p in chunk.parsed_content if isinstance(p, Addition)]

                old_len = len(removals)
                new_len = len(additions)

                hunk_header = (
                    f"@@ -{chunk.old_start},{old_len} +{chunk.new_start},{new_len} @@"
                )
                patch_lines.append(hunk_header)

                for item in chunk.parsed_content:
                    if isinstance(item, Removal):
                        patch_lines.append(f"-{item.content}")
                    elif isinstance(item, Addition):
                        patch_lines.append(f"+{item.content}")

            if len(sorted_file_chunks) > 0:
                patches[file_path] = "\n".join(patch_lines) + "\n"

        return patches

    def _build_tree_from_changes(
        self, base_commit_hash: str, chunks_for_commit: List[DiffChunk]
    ) -> str:
        """
        Creates a new Git tree object by applying a specific set of changes
        to a base commit.

        Processes chunks in order:
        1. Standard patches (StandardDiffChunk with content)
        2. Renames (RenameDiffChunk)
        3. Empty file additions (EmptyFileAdditionChunk)
        4. File deletions (FileDeletionChunk)
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir) / "synth_worktree"

            try:
                self._run_git(
                    "worktree", "add", "--detach", str(worktree_path), base_commit_hash
                )

                # Flatten composite chunks into primitives
                primitive_chunks: List[DiffChunk] = []
                for chunk in chunks_for_commit:
                    if isinstance(chunk, CompositeDiffChunk):
                        primitive_chunks.extend(chunk.chunks)
                    else:
                        primitive_chunks.append(chunk)

                # Separate chunks by type
                standard_chunks = [
                    c for c in primitive_chunks if isinstance(c, StandardDiffChunk)
                ]
                rename_chunks = [
                    c for c in primitive_chunks if isinstance(c, RenameDiffChunk)
                ]
                empty_file_chunks = [
                    c for c in primitive_chunks if isinstance(c, EmptyFileAdditionChunk)
                ]
                deletion_chunks = [
                    c for c in primitive_chunks if isinstance(c, FileDeletionChunk)
                ]

                patches = self._generate_unified_diff(standard_chunks)
                for file_path, patch_content in patches.items():
                    if not patch_content.strip():
                        continue

                    try:
                        self._run_git(
                            "apply",
                            "--recount",
                            "--unidiff-zero",
                            cwd=worktree_path,
                            stdin_content=patch_content,
                        )

                    except RuntimeError as e:
                        file_content = ""
                        target_file = worktree_path / file_path
                        if target_file.exists():
                            file_content = target_file.read_text()
                        raise RuntimeError(
                            f"FATAL: Git apply failed for '{file_path}'.\n"
                            f"--- ERROR DETAILS ---\n{e}\n"
                            f"--- PATCH CONTENT ---\n{patch_content}\n"
                            f"--- CURRENT FILE CONTENT ---\n{file_content}\n"
                        )

                for r_chunk in rename_chunks:
                    # Build valid Git rename patch
                    patch_lines = [
                        f"diff --git a/{r_chunk.old_file_path} b/{r_chunk.new_file_path}",
                        # "similarity index 100%",
                        f"rename from {r_chunk.old_file_path}",
                        f"rename to {r_chunk.new_file_path}",
                        f"--- a/{r_chunk.old_file_path}",
                        f"+++ b/{r_chunk.new_file_path}",
                    ]

                    # If the rename also includes content edits, append them
                    if r_chunk.patch_content.strip():
                        patch_lines.append(r_chunk.patch_content.strip())

                    patch_str = "\n".join(patch_lines) + "\n"

                    self._run_git(
                        "apply",
                        "--index",
                        "--recount",
                        "--unidiff-zero",
                        cwd=worktree_path,
                        stdin_content=patch_str,
                    )

                # Step 3: Add empty files
                for empty_chunk in empty_file_chunks:
                    file_path = empty_chunk.file_path()
                    target_file = worktree_path / file_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.touch()

                    if empty_chunk.file_mode is not None:
                        target_file.chmod(int(empty_chunk.file_mode, 8))

                # Step 4: Delete files
                for deletion_chunk in deletion_chunks:
                    try:
                        self._run_git(
                            "rm", "-f", deletion_chunk.file_path(), cwd=worktree_path
                        )
                    except (RuntimeError, ValueError):
                        # File might have been already removed, continue
                        pass

                # --- THE ISOLATED INDEX FIX ---
                # 1. Define a path for a temporary index file INSIDE the worktree.
                temp_index_path = worktree_path / ".git_temporary_index"

                # 2. Clean up any existing lock file to prevent "File exists" errors
                temp_index_lock_path = Path(str(temp_index_path) + ".lock")
                if temp_index_lock_path.exists():
                    temp_index_lock_path.unlink()

                # 3. Create a modified environment that tells Git to use this index.
                env = os.environ.copy()
                env["GIT_INDEX_FILE"] = str(temp_index_path)

                # 4. Run 'git add' with this environment. It will now write to the temp index.
                self._run_git("add", "-A", ".", cwd=worktree_path, env=env)

                # 5. Run 'write-tree' with the SAME environment. It will read from the temp index.
                new_tree_hash = self._run_git_decoded(
                    "write-tree", cwd=worktree_path, env=env
                )

                return new_tree_hash

            finally:
                self._run_git("worktree", "remove", "--force", str(worktree_path))

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

                # 4. Build a new tree from scratch.
                #    - ALWAYS start from the original base commit's state.
                #    - ALWAYS apply the full set of accumulated changes.
                #    This is the key to the stateless, cumulative rebuild.
                new_tree_hash = self._build_tree_from_changes(
                    original_base_commit_hash, cumulative_chunks
                )

                # 5. Create the new commit, chaining it to the previous one we made.
                full_message = group.commmit_message
                if group.extended_message:
                    full_message += f"\n\n{group.extended_message}"

                new_commit_hash = self._create_commit(
                    new_tree_hash, last_synthetic_commit_hash, full_message
                )

                # 6. The commit we just made becomes the parent for the NEXT loop iteration.
                last_synthetic_commit_hash = new_commit_hash
                results.append(CommitResult(commit_hash=new_commit_hash, group=group))

            except Exception as e:
                print(
                    f"FATAL: Synthesis failed during group '{group.group_id}'. No changes have been applied."
                )
                import traceback

                traceback.print_exc()
                raise e

        # 7. After the loop, the last commit we created is the new head of our chain.
        final_commit_hash = last_synthetic_commit_hash
        if final_commit_hash != original_base_commit_hash:
            # Update the branch ref dynamically
            self._run_git(
                "update-ref", f"refs/heads/{current_branch}", final_commit_hash
            )
            # Update the working directory to reflect the new branch state
            self._run_git("reset", "--hard", final_commit_hash)

        return results
