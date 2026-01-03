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

    @staticmethod
    def sanitize_filename(filename: bytes) -> bytes:
        """
        Sanitize a filename for use in git patch headers.

        - Escapes spaces with backslashes.
        - Removes any trailing tabs.
        - Leaves other characters unchanged.
        """
        return filename.rstrip(b"\t").strip()  # remove trailing tabs

    @staticmethod
    def _generate_unified_diff(
        chunks: List[DiffChunk], total_chunks_per_file: Dict[bytes, int]
    ) -> Dict[bytes, bytes]:
        """
        Generates a dictionary of valid, cumulative unified diffs (patches) for each file.
        This method is stateful and correctly recalculates hunk headers for subsets of chunks.
        """
        patches: Dict[bytes, bytes] = {}

        sorted_chunks = sorted(chunks, key=lambda c: c.canonical_path())

        for file_path, file_chunks_iter in groupby(
            sorted_chunks, key=lambda c: c.canonical_path()
        ):
            file_chunks: list[DiffChunk] = list(file_chunks_iter)

            if not file_chunks:
                continue

            current_count = len(file_chunks)
            total_expected = total_chunks_per_file.get(file_path, current_count)
            patch_lines = []
            single_chunk = file_chunks[0]

            old_file_path = (
                GitSynthesizer.sanitize_filename(single_chunk.old_file_path)
                if single_chunk.old_file_path
                else None
            )
            new_file_path = (
                GitSynthesizer.sanitize_filename(single_chunk.new_file_path)
                if single_chunk.new_file_path
                else None
            )

            if single_chunk.is_standard_modification:
                patch_lines.append(
                    b"diff --git a/" + new_file_path + b" b/" + new_file_path
                )
            elif single_chunk.is_file_rename:
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + new_file_path
                )
                patch_lines.append(b"rename from " + old_file_path)
                patch_lines.append(b"rename to " + new_file_path)
            elif single_chunk.is_file_deletion:
                # Treat partial deletions as a modification for the header
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + old_file_path
                )
                if current_count >= total_expected:
                    patch_lines.append(
                        b"deleted file mode " + (single_chunk.file_mode or b"100644")
                    )
            elif single_chunk.is_file_addition:
                patch_lines.append(
                    b"diff --git a/" + new_file_path + b" b/" + new_file_path
                )
                patch_lines.append(
                    b"new file mode " + (single_chunk.file_mode or b"100644")
                )

            old_file_header = b"a/" + old_file_path if old_file_path else DEVNULL
            new_file_header = b"b/" + new_file_path if new_file_path else DEVNULL
            if single_chunk.is_file_deletion and current_count < total_expected:
                new_file_header = old_file_header

            patch_lines.append(b"--- " + old_file_header)
            patch_lines.append(b"+++ " + new_file_header)

            if not any(c.has_content for c in file_chunks):
                patch_lines.append(b"@@ -0,0 +0,0 @@")
            else:
                # Sort chunks by their original line anchor to process them in order.
                sorted_file_chunks = sorted(file_chunks, key=lambda c: c.line_anchor)
                merged = GitSynthesizer.merge_chunks(sorted_file_chunks)

                # These counters track the end of the *last* hunk we wrote to the patch.
                last_hunk_end_old = 0
                last_hunk_end_new = 0

                for chunk in merged:
                    if not chunk.has_content:
                        continue

                    old_len = chunk.old_len()
                    new_len = chunk.new_len()

                    # The `old_start` is always relative to the original file, so it's our stable anchor.
                    # The `new_start` must be recalculated based on the state of the patch so far.
                    # The number of unchanged lines between the last hunk and this one is the key.
                    # This gap is calculated from the old file's perspective.
                    gap_since_last_hunk = chunk.old_start - last_hunk_end_old

                    # The new start line is where the last hunk ended in the new file, plus the gap.
                    recalculated_new_start = last_hunk_end_new + gap_since_last_hunk

                    hunk_header = f"@@ -{chunk.old_start},{old_len} +{recalculated_new_start},{new_len} @@".encode(
                        "utf-8"
                    )
                    patch_lines.append(hunk_header)

                    for item in chunk.parsed_content:
                        if isinstance(item, Removal):
                            patch_lines.append(b"-" + item.content)
                        elif isinstance(item, Addition):
                            patch_lines.append(b"+" + item.content)

                    # Update the trackers for the next iteration.
                    last_hunk_end_old = chunk.old_start + old_len
                    last_hunk_end_new = recalculated_new_start + new_len

                # Handle the no-newline marker for the last chunk in the file
                if (
                    sorted_file_chunks
                    and sorted_file_chunks[-1].contains_newline_marker
                ):
                    patch_lines.append(b"\\ No newline at end of file")

            file_patch = b"\n".join(patch_lines) + b"\n"
            patches[file_path] = file_patch

        return patches

    @staticmethod
    def _is_contiguous(last_chunk: "DiffChunk", current_chunk: "DiffChunk") -> bool:
        """
        Determines if two DiffChunks are contiguous and can be merged.

        Chunks are considered contiguous if their line number ranges are adjacent
        on EITHER the old file side OR the new file side. This correctly handles
        all cases: pure additions, pure deletions, and mixed modifications
        being adjacent to other chunk types.
        """
        # Check for contiguity on the "new file" (additions) side
        can_merge_on_new = (
            last_chunk.new_len() > 0
            and current_chunk.new_len() > 0
            and (last_chunk.new_start + last_chunk.new_len()) == current_chunk.new_start
        )

        # Check for contiguity on the "old file" (removals) side
        can_merge_on_old = (
            last_chunk.old_len() > 0
            and current_chunk.old_len() > 0
            and (last_chunk.old_start + last_chunk.old_len()) == current_chunk.old_start
        )

        # A special case for a pure removal followed immediately by a pure addition
        # e.g., @@ -5,1 +4,0 @@ followed by @@ -4,0 +5,1 @@
        # These are contiguous if the new_start of the addition matches the old_start
        # of the deletion.
        is_adjacent_replace = (
            last_chunk.pure_deletion()
            and current_chunk.pure_addition()
            and last_chunk.old_start == current_chunk.new_start
        )

        return can_merge_on_new or can_merge_on_old or is_adjacent_replace

    @staticmethod
    def merge_chunks(sorted_chunks: list["DiffChunk"]) -> list["DiffChunk"]:
        """
        Merges a list of sorted, atomic DiffChunks into the smallest possible
        list of larger, valid DiffChunks.

        This acts as the inverse of the `split_into_atomic_chunks` method. It
        first groups adjacent chunks and then merges each group into a single
        new chunk using the `from_parsed_content_slice` factory.
        """
        if not sorted_chunks:
            return []

        # Step 1: Group all contiguous chunks together.
        groups = []
        current_group = [sorted_chunks[0]]
        for i in range(1, len(sorted_chunks)):
            last_chunk = current_group[-1]
            current_chunk = sorted_chunks[i]

            if GitSynthesizer._is_contiguous(last_chunk, current_chunk):
                current_group.append(current_chunk)
            else:
                groups.append(current_group)
                current_group = [current_chunk]
        groups.append(current_group)

        # Step 2: Merge each group into a single new DiffChunk.
        final_chunks = []
        for group in groups:
            if len(group) == 1:
                # No merging needed for groups of one.
                final_chunks.append(group[0])
                continue

            # Flatten the content from all chunks in the group.
            # It's crucial that removals come before additions for from_parsed_content_slice.
            merged_parsed_content = []
            removals = []
            additions = []

            # Also combine the newline markers.
            contains_newline_fallback = False
            contains_newline_marker = False

            for chunk in group:
                removals.extend(
                    [c for c in chunk.parsed_content if isinstance(c, Removal)]
                )
                additions.extend(
                    [c for c in chunk.parsed_content if isinstance(c, Addition)]
                )
                contains_newline_fallback |= chunk.contains_newline_fallback
                contains_newline_marker |= chunk.contains_newline_marker

            merged_parsed_content.extend(removals)
            merged_parsed_content.extend(additions)

            # Let the factory method do the hard work of creating the new valid chunk.
            merged_chunk = DiffChunk.from_parsed_content_slice(
                old_file_path=group[0].old_file_path,
                new_file_path=group[0].new_file_path,
                file_mode=group[0].file_mode,
                contains_newline_fallback=contains_newline_fallback,
                contains_newline_marker=contains_newline_marker,
                parsed_slice=merged_parsed_content,
            )
            final_chunks.append(merged_chunk)

        return final_chunks

    def _build_tree_from_changes(
        self,
        base_commit_hash: str,
        chunks_for_commit: List[DiffChunk],
        total_chunks_per_file: Dict[bytes, int],
    ) -> str:
        """
        Creates a new Git tree object by applying a specific set of changes
        to a base commit.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir) / "synth_worktree"

            # create the worktree off of our base commit
            self._run_git_binary(
                "worktree", "add", "--detach", str(worktree_path), base_commit_hash
            )

            patches = GitSynthesizer._generate_unified_diff(
                chunks_for_commit, total_chunks_per_file
            )
            logger.info(
                "Tree build patch set summary: files={files} total_lines={lines}",
                files=len(patches),
                lines=sum(len(p.splitlines()) for p in patches.values()),
            )
            # Batch apply: concatenate all file patches into a single patch stream
            # This reduces process overhead and applies atomically.
            if patches:
                # Keep ordering deterministic by sorting file paths
                ordered_items = sorted(patches.items(), key=lambda kv: kv[0])
                combined_patch = b"".join(patch for _, patch in ordered_items)

                try:
                    logger.debug(
                        "Applying combined patch stream: files={files}",
                        files=len(ordered_items),
                    )
                    self._run_git_binary(
                        "apply",
                        "--index",
                        "--recount",
                        "--whitespace=nowarn",
                        "--unidiff-zero",
                        cwd=worktree_path,
                        stdin_content=combined_patch,
                    )
                except RuntimeError as e:
                    raise RuntimeError(
                        "FATAL: Git apply failed for combined patch stream.\n"
                        f"--- ERROR DETAILS ---\n{e}\n"
                        f"--- PATCH CONTENT (combined) ---\n{combined_patch}\n"
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
            logger.info(
                "Tree object created: tree_hash={tree}",
                tree=new_tree_hash,
            )

            # Clean up the worktree before returning
            try:
                self._run_git_binary(
                    "worktree", "remove", "--force", str(worktree_path)
                )
            except RuntimeError:
                # If worktree removal fails, it will be cleaned up when temp_dir is removed
                logger.warning(
                    "Failed to remove worktree, will be cleaned up with temp directory"
                )

            return new_tree_hash

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

        logger.info(
            "Execute plan summary: groups={groups} base_commit={base} branch_to_update={branch}",
            groups=len(groups),
            base=original_base_commit_hash,
            branch=current_branch,
        )
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
                logger.info(
                    "Commit created: commit_hash={commit} parent={parent} chunks_cumulative={chunks} message_preview={preview}",
                    commit=new_commit_hash,
                    parent=last_synthetic_commit_hash,
                    chunks=len(primitive_chunks),
                    preview=(
                        (full_message[:80] + "…")
                        if len(full_message) > 80
                        else full_message
                    ),
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
            logger.info(
                "Branch updated: branch={branch} new_head={head} commits_created={count}",
                branch=current_branch,
                head=final_commit_hash,
                count=len(results),
            )

        return results
