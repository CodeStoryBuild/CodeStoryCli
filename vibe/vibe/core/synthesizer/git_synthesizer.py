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
        Generates a dictionary of valid, cumulative unified diffs (patches) for each file
        """
        patches: Dict[bytes, bytes] = {}

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

            old_file_path = (
                GitSynthesizer.sanitize_filename(single_chunk.old_file_path)
                if single_chunk.old_file_path is not None
                else None
            )
            new_file_path = (
                GitSynthesizer.sanitize_filename(single_chunk.new_file_path)
                if single_chunk.new_file_path is not None
                else None
            )

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
                    c.old_file_path == single_chunk.old_file_path for c in file_chunks
                ), "Standard chunk old file paths dont match!"
                assert all(
                    c.new_file_path == single_chunk.new_file_path for c in file_chunks
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
                    b"diff --git a/" + new_file_path + b" b/" + new_file_path
                )
            elif single_chunk.is_file_rename:
                patch_lines.append(
                    b"diff --git a/" + old_file_path + b" b/" + new_file_path
                )
                patch_lines.append(
                    b"rename from " + old_file_path
                )
                patch_lines.append(
                    b"rename to " + new_file_path
                )
            elif single_chunk.is_file_deletion:
                # possible edge case: file deletion with multiple chunks
                if current_count < total_expected:
                    # in this case, we treat it as a standard modification
                    patch_lines.append(
                        b"diff --git a/" + old_file_path + b" b/" + old_file_path
                    )
                else:
                    # we have all deletion chunks, so we can treat it as a deletion
                    patch_lines.append(
                        b"diff --git a/" + old_file_path + b" b/" + old_file_path
                    )
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
            elif single_chunk.is_standard_modification:
                patch_lines.append(
                    b"diff --git a/" + new_file_path + b" b/" + new_file_path
                )

            old_file_header = (
                GitSynthesizer.sanitize_filename(b"a/" + old_file_path)
                if old_file_path is not None
                else DEVNULL
            )

            new_file_header = (
                GitSynthesizer.sanitize_filename(b"b/" + new_file_path)
                if new_file_path is not None
                else DEVNULL
            )

            # second part of deletion edge case
            # if we are in partial deletion state, new_file_header should act like a standard_change
            # that is it should be old_file_header
            if single_chunk.is_file_deletion and current_count < total_expected:
                new_file_header = old_file_header

            patch_lines.append(
                b"--- " + old_file_header
            )
            patch_lines.append(
                b"+++ " + new_file_header
            )

            if not multiple_chunks and not single_chunk.has_content:
                patch_lines.append(b"@@ -0,0 +0,0 @@")
            else:
                # Sort chunks by their old_start line to ensure correct order in the patch
                sorted_file_chunks = sorted(
                    file_chunks,
                    key=lambda c: c.line_anchor,
                )

                merged = GitSynthesizer.merge_continous_same_type(sorted_file_chunks)

                # if single_chunk.is_file_addition:
                #     # file additions are handled differently
                #     # since they are a new file, we need to merge all chunks into a new contigous hunk
                #     additions = []
                #     for sorted_chunk in sorted_file_chunks:
                #         additions.extend(sorted_chunk.parsed_content)

                #     hunk_header = f"@@ -{0},{0} +{1},{len(additions)} @@"
                #     patch_lines.append(hunk_header)

                #     for item in additions:
                #         patch_lines.append(f"+{item.content}")

                #     # you might hit edge case where it was an empty addition
                #     # then the newline_marker_rem might have been marked because hit_add will never be true (in diff_chunk.py::from_hunk)
                #     if single_chunk.contains_newline_fallback:
                #         patch_lines.append("\\ No newline at end of file")
                #         terminator_needed = False

                # else:
                # go over each chunk and generate the hunk headers and content
                has_newline_fallback = False

                for sorted_chunk in merged:
                    removals = [
                        p for p in sorted_chunk.parsed_content if isinstance(p, Removal)
                    ]
                    additions = [
                        p
                        for p in sorted_chunk.parsed_content
                        if isinstance(p, Addition)
                    ]

                    old_len = len(removals)
                    new_len = len(additions)

                    hunk_header = f"@@ -{sorted_chunk.old_start},{old_len} +{sorted_chunk.new_start},{new_len} @@".encode('utf-8')
                    patch_lines.append(hunk_header)

                    for removal in removals:
                        patch_lines.append(b"-" + removal.content)

                    for addition in additions:
                        patch_lines.append(b"+" + addition.content)

                    has_newline_fallback |= sorted_chunk.contains_newline_fallback

                if has_newline_fallback:
                    patch_lines.append(b"\\ No newline at end of file")

            patches[file_path] = b"\n".join(patch_lines) + b"\n"

            logger.debug(
                "Patch generation progress: cumulative_patches={count}",
                count=len(patches),
            )

        return patches

    @staticmethod
    def merge_continous_same_type(sorted_chunks: list[DiffChunk]):
        new_chunks = []
        for chunk in sorted_chunks:
            sig = 1 if chunk.pure_addition() else (-1 if chunk.pure_deletion() else 0)
            if new_chunks:
                last, last_sig = new_chunks[-1]
                if sig != 0 and sig == last_sig:
                    # both "pure the same something"
                    # check if they are continous
                    if sig == 1:
                        new_range = (
                            chunk.new_start,
                            chunk.new_start + chunk.new_len() - 1,
                        )
                        last_range = (
                            last.new_start,
                            last.new_start + last.new_len() - 1,
                        )
                    else:
                        new_range = (
                            chunk.old_start,
                            chunk.old_start + chunk.old_len() - 1,
                        )
                        last_range = (
                            last.old_start,
                            last.old_start + last.old_len() - 1,
                        )

                    last_start, last_end = last_range
                    new_start, new_end = new_range

                    if last_end + 1 == new_start:
                        # adjacent
                        new_chunk = GitSynthesizer.merge_two_single_type_chunks(
                            last, chunk
                        )
                        new_chunks[-1] = (new_chunk, sig)
                    elif last_end > new_start:
                        # overlapping, this is something that should not happen
                        logger.error(
                            f"Overlapping chunks! chunk1:{last} chunk2:{chunk}"
                        )
                    else:
                        # just a regular non-neighbor chunk
                        new_chunks.append((chunk, sig))
                else:
                    new_chunks.append((chunk, sig))
            else:
                new_chunks.append((chunk, sig))

        return [chunk for (chunk, _) in new_chunks]

    @staticmethod
    def merge_two_single_type_chunks(old: "DiffChunk", new: "DiffChunk"):
        return DiffChunk.from_parsed_content_slice(
            old_file_path=old.old_file_path,
            new_file_path=old.new_file_path,
            file_mode=old.file_mode,
            contains_newline_fallback=old.contains_newline_fallback
            or new.contains_newline_fallback,
            contains_newline_marker_rem=old.contains_newline_marker_rem,
            parsed_slice=old.parsed_content + new.parsed_content,
        )

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
                        "--unidiff-zero",
                        cwd=worktree_path,
                        stdin_content=combined_patch,
                    )
                except RuntimeError as e:
                    raise RuntimeError(
                        "FATAL: Git apply failed for combined patch stream.\n"
                        f"--- ERROR DETAILS ---\n{e}\n"
                        # f"--- PATCH CONTENT (combined) ---\n{combined_patch}\n"
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
