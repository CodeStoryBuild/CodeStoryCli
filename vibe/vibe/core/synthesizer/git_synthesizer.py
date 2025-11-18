# vibe/core/synthesizer/synthesizer.py

import os
import tempfile
from itertools import groupby
from pathlib import Path

from loguru import logger

from ..commands.git_const import DEVNULL
from ..data.diff_chunk import DiffChunk
from ..data.line_changes import Addition, Removal
from ..data.models import CommitGroup, CommitResult
from ..git_interface.interface import GitInterface


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
        cwd: str | Path | None = None,
        env: dict | None = None,
        stdin_content: str | bytes | None = None,
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
    def _validate_chunks_are_disjoint(chunks: list[DiffChunk]) -> bool:
        """Validate that all chunks are pairwise disjoint in old file coordinates.
        
        This is a critical invariant: chunks must not overlap in the old file
        for them to be safely applied in any order.
        
        Returns True if all chunks are disjoint, raises RuntimeError otherwise.
        """
        from itertools import groupby

        # Group by file
        sorted_chunks = sorted(chunks, key=lambda c: c.canonical_path())
        for file_path, file_chunks_iter in groupby(sorted_chunks, key=lambda c: c.canonical_path()):
            file_chunks = list(file_chunks_iter)

            # Sort by old_start within each file
            file_chunks.sort(key=lambda c: c.old_start or 0)

            # Check each adjacent pair for overlap
            for i in range(len(file_chunks) - 1):
                chunk_a = file_chunks[i]
                chunk_b = file_chunks[i + 1]

                if not chunk_a.is_disjoint_from(chunk_b):
                    raise RuntimeError(
                        f"INVARIANT VIOLATION: Chunks are not disjoint!\n"
                        f"File: {file_path}\n"
                        f"Chunk A: old_start={chunk_a.old_start}, old_len={chunk_a.old_len()}\n"
                        f"Chunk B: old_start={chunk_b.old_start}, old_len={chunk_b.old_len()}\n"
                        f"These chunks overlap in old file coordinates!"
                    )

        return True

    @staticmethod
    def _calculate_hunk_starts(
        file_change_type: str,
        old_start: int,
        is_pure_addition: bool,
        cumulative_offset: int
    ) -> tuple[int, int]:
        """
        Calculate the old_start and new_start for a hunk header based on file change type.
        
        Args:
            file_change_type: One of "added", "deleted", "modified", "renamed"
            old_start: The old_start from the chunk (in old file coordinates)
            is_pure_addition: Whether this is a pure addition (old_len == 0)
            cumulative_offset: Cumulative net lines added so far
            
        Returns:
            Tuple of (hunk_old_start, hunk_new_start) for the @@ header
        """
        if file_change_type == "added":
            # File addition: old side is always -0,0
            hunk_old_start = 0
            # new_start adjustment: +1 unless already at line 1
            hunk_new_start = old_start + cumulative_offset + (1 if old_start != 1 else 0)
        elif file_change_type == "deleted":
            # File deletion: new side is always +0,0
            hunk_old_start = old_start
            hunk_new_start = 0
        elif is_pure_addition:
            # Pure addition (not a new file): @@ -N,0 +M,len @@
            hunk_old_start = old_start
            # new_start adjustment: +1 unless already at line 1
            hunk_new_start = old_start + cumulative_offset + (1 if old_start != 1 else 0)
        else:
            # Deletion, modification, or rename: @@ -N,len +M,len @@
            hunk_old_start = old_start
            hunk_new_start = old_start + cumulative_offset

        return (hunk_old_start, hunk_new_start)

    @staticmethod
    def _generate_unified_diff(
        chunks: list[DiffChunk], total_chunks_per_file: dict[bytes, int]
    ) -> dict[bytes, bytes]:
        """
        Generates a dictionary of valid, cumulative unified diffs (patches) for each file.
        This method is stateful and correctly recalculates hunk headers for subsets of chunks.
        """
        # CRITICAL VALIDATION: Ensure chunks are disjoint before generating patches
        GitSynthesizer._validate_chunks_are_disjoint(chunks)

        patches: dict[bytes, bytes] = {}

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

            # we need all chunks to mark as deletion
            file_deletion = single_chunk.is_file_deletion and current_count >= total_expected
            file_addition = single_chunk.is_file_addition
            standard_modification = single_chunk.is_standard_modification or (single_chunk.is_file_deletion and current_count < total_expected)
            file_rename = single_chunk.is_file_rename

            # Determine file change type for hunk calculation
            if file_addition:
                file_change_type = "added"
            elif file_deletion:
                file_change_type = "deleted"
            elif file_rename:
                file_change_type = "renamed"
            else:
                file_change_type = "modified"

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

            if standard_modification:
                if single_chunk.is_file_deletion:
                    # use old file and "pretend its a modification as we dont have all deletion chunks yet"
                    patch_lines.append(
                        b"diff --git a/" + old_file_path + b" b/" + old_file_path
                    )
                else:
                    patch_lines.append(
                        b"diff --git a/" + new_file_path + b" b/" + new_file_path
                    )
            elif file_rename:
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + new_file_path
                )
                patch_lines.append(b"rename from " + old_file_path)
                patch_lines.append(b"rename to " + new_file_path)
            elif file_deletion:
                # Treat partial deletions as a modification for the header
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + old_file_path
                )
                patch_lines.append(
                    b"deleted file mode " + (single_chunk.file_mode or b"100644")
                )
            elif file_addition:
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
                # Sort chunks by their sort key (old_start, then abs_new_line)
                # This maintains correct ordering even for chunks at the same old_start
                sorted_file_chunks = sorted(file_chunks, key=lambda c: c.get_sort_key())
                # you must merge chunks to get valid patches
                sorted_file_chunks = GitSynthesizer.merge_chunks(sorted_file_chunks)

                # CRITICAL: new_start is calculated HERE and ONLY HERE!
                # We calculate it based on old_start + cumulative_offset.
                #
                # The cumulative_offset tracks how many net lines have been added
                # (additions - deletions) by all prior chunks in this file.
                #
                # For each chunk:
                # - old_start tells us where the change occurs in the old file
                # - new_start = old_start + cumulative_offset (where it lands in new file)

                cumulative_offset = 0  # Net lines added so far (additions - deletions)

                for chunk in sorted_file_chunks:
                    if not chunk.has_content:
                        continue

                    old_len = chunk.old_len()
                    new_len = chunk.new_len()
                    is_pure_addition = (old_len == 0)

                    # Use the helper function to calculate hunk starts
                    hunk_old_start, hunk_new_start = GitSynthesizer._calculate_hunk_starts(
                        file_change_type=file_change_type,
                        old_start=chunk.old_start,
                        is_pure_addition=is_pure_addition,
                        cumulative_offset=cumulative_offset
                    )

                    hunk_header = f"@@ -{hunk_old_start},{old_len} +{hunk_new_start},{new_len} @@".encode()
                    patch_lines.append(hunk_header)

                    for item in chunk.parsed_content:
                        if isinstance(item, Removal):
                            patch_lines.append(b"-" + item.content)
                        elif isinstance(item, Addition):
                            patch_lines.append(b"+" + item.content)

                    # Update cumulative offset for next chunk
                    cumulative_offset += new_len - old_len

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

        Since we ONLY have old_start (no new_start), we check contiguity
        based on old file coordinates only.
        
        Chunks are contiguous if their old_start + old_len touch or overlap.
        """
        # Check for contiguity on the "old file" side
        last_old_end = (last_chunk.old_start or 0) + last_chunk.old_len()
        current_old_start = current_chunk.old_start or 0

        return last_old_end >= current_old_start

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
        chunks_for_commit: list[DiffChunk],
        total_chunks_per_file: dict[bytes, int],
    ) -> str:
        """
        Creates a new Git tree object by applying a specific set of changes
        to a base commit.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            worktree_path = Path(temp_dir) / "synth_worktree"
            worktree_created = False

            try:
                # create the worktree off of our base commit
                self._run_git_binary(
                    "worktree", "add", "--detach", str(worktree_path), base_commit_hash
                )
                worktree_created = True

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
                            "--verbose",
                            cwd=worktree_path,
                            stdin_content=combined_patch,
                        )
                        print(combined_patch)
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

                return new_tree_hash

            finally:
                # Clean up the worktree before TemporaryDirectory cleanup
                # This prevents orphaned worktree references in git
                if worktree_created:
                    try:
                        self._run_git_binary(
                            "worktree", "remove", "--force", str(worktree_path)
                        )
                    except RuntimeError:
                        # If worktree removal fails, log it but let temp_dir cleanup proceed
                        logger.warning(
                            "Failed to remove worktree, will be cleaned up with temp directory"
                        )

    def _create_commit(self, tree_hash: str, parent_hash: str, message: str) -> str:
        return self._run_git_decoded(
            "commit-tree", tree_hash, "-p", parent_hash, "-m", message
        )

    # vibe/core/synthesizer/synthesizer.py

    def execute_plan(
        self, groups: list[CommitGroup], base_commit: str, branch_to_update: str
    ) -> list[CommitResult]:
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

        results: list[CommitResult] = []

        # 1. Establish the constant starting point for all tree builds.
        original_base_commit_hash = self._run_git_decoded("rev-parse", base_commit)

        # 2. These variables will track the evolving state of our NEW commit chain.
        last_synthetic_commit_hash = original_base_commit_hash
        cumulative_chunks: list[DiffChunk] = []

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
                primitive_chunks: list[DiffChunk] = []
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
