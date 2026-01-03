import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Union, Tuple
from itertools import groupby
import shutil
import io

## Imports
from ..data.models import (
    CommitGroup,
    CommitResult,
    ChunkApplicationData,
)
from ..data.diff_chunk import DiffChunk
from ..data.c_diff_chunk import CompositeDiffChunk
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..git_interface.interface import GitInterface


class GitSynthesizer:
    """
    Builds a clean, linear Git history from a plan of commit groups.

    This implementation is optimized for both speed and memory efficiency:
    - It interacts directly with Git's object database to avoid slow worktree operations.
    - It uses batch Git commands (`cat-file --batch`, `hash-object --stdin-paths`)
      to minimize process creation overhead.
    - It uses a hybrid file-streaming approach for applying changes, ensuring
      low memory consumption even when processing very large files.
    """

    def __init__(self, git: GitInterface):
        self.git = git

    def _run_git(
        self, *args: str, env: Dict = None, stdin_content: Union[str, bytes] = None
    ) -> bytes:
        """Helper to run Git commands, always returning raw bytes."""
        if isinstance(stdin_content, str):
            stdin_content = stdin_content.encode("utf-8")

        result = self.git.run_git_binary(list(args), input_bytes=stdin_content, env=env)
        return result if result is not None else b""

    def _run_git_decoded(self, *args: str, **kwargs) -> str:
        """Helper to run Git and get a decoded, stripped string."""
        output = self._run_git(*args, **kwargs)
        return output.decode("utf-8", errors="replace").strip()

    def _get_commit_tree_hash(self, commit_ish: str) -> str:
        return self._run_git_decoded("rev-parse", f"{commit_ish}^{{tree}}")

    def _get_full_tree_listing(self, tree_hash: str) -> Dict[str, str]:
        if not tree_hash:
            return {}
        # Use NULL characters as delimiters for paths with spaces/special chars.
        ls_tree_output = self._run_git_decoded("ls-tree", "-r", "-z", tree_hash)
        if not ls_tree_output:
            return {}

        listing = {}
        entries = [entry for entry in ls_tree_output.split("\0") if entry]
        for entry in entries:
            meta, path = entry.split("\t", 1)
            _, _, blob_hash = meta.split(maxsplit=2)
            listing[path] = blob_hash
        return listing

    def _get_blob_contents_batch(self, blob_hashes: List[str]) -> Dict[str, bytes]:
        """Reads content for multiple blobs in a single Git call."""
        if not blob_hashes:
            return {}

        # The input for `cat-file --batch` is just one hash per line.
        stdin_content = "\n".join(blob_hashes).encode("utf-8")
        raw_output = self._run_git("cat-file", "--batch", stdin_content=stdin_content)

        contents = {}
        cursor = 0
        while cursor < len(raw_output):
            # Read header line: <hash> <type> <size>
            header_end = raw_output.find(b"\n", cursor)
            header = raw_output[cursor:header_end].decode("utf-8")
            cursor = header_end + 1

            blob_hash, _, size_str = header.split()
            size = int(size_str)

            # Read content bytes
            content = raw_output[cursor : cursor + size]
            contents[blob_hash] = content
            cursor += size

            # Skip the trailing newline
            if cursor < len(raw_output) and raw_output[cursor] == ord(b"\n"):
                cursor += 1

        return contents

    def _create_blobs_batch(
        self, path_to_tempfile_map: Dict[str, Path]
    ) -> Dict[str, str]:
        """Creates multiple blob objects from files on disk in a single Git call."""
        if not path_to_tempfile_map:
            return {}

        # The order of paths in stdin must match the order of hashes in stdout.
        # We use a list to preserve this order.
        ordered_temp_paths = list(path_to_tempfile_map.values())
        stdin_content = "\n".join(str(p) for p in ordered_temp_paths)

        output = self._run_git_decoded(
            "hash-object", "-w", "--stdin-paths", stdin_content=stdin_content
        )

        new_blob_hashes = output.splitlines()

        # Map the resulting hashes back to their final Git path
        path_to_blob_hash = {}
        final_paths = list(path_to_tempfile_map.keys())
        for i, final_path in enumerate(final_paths):
            path_to_blob_hash[final_path] = new_blob_hashes[i]

        return path_to_blob_hash

    def _apply_changes_hybrid(
        self,
        original_content: bytes,
        chunks_data: List[ChunkApplicationData],
    ) -> Path:
        """
        Applies chunks using an optimized method that balances speed and memory usage.

        For small/medium files (<1MB), processes in-memory using StringIO.
        For large files, uses file-streaming to keep memory usage low.

        Returns the Path to a new temporary file containing the result.
        The caller is responsible for cleaning up this file.
        """

        print(f"Using: {chunks_data}")

        # Memory threshold: 1MB - process in-memory if below this
        MEMORY_THRESHOLD = 1024 * 1024

        sorted_chunks = sorted(chunks_data, key=lambda c: c.start_line)

        # Fast path for empty original content (new files)
        if not original_content:
            new_content_file = tempfile.NamedTemporaryFile(
                mode="w", delete=False, encoding="utf-8"
            )
            try:
                for chunk in sorted_chunks:
                    for line in chunk.add_content:
                        new_content_file.write(f"{line}\n")
            finally:
                new_content_file.close()
            return Path(new_content_file.name)

        # Choose processing strategy based on size
        if len(original_content) < MEMORY_THRESHOLD:
            # In-memory processing for small/medium files
            return self._apply_changes_in_memory(original_content, sorted_chunks)
        else:
            # File-based streaming for large files
            return self._apply_changes_via_disk(original_content, sorted_chunks)

    def _apply_changes_in_memory(
        self,
        original_content: bytes,
        sorted_chunks: List[ChunkApplicationData],
    ) -> Path:
        """Process changes in-memory using StringIO for better performance."""
        original_lines = original_content.decode("utf-8").splitlines(keepends=True)
        result = io.StringIO()

        # This cursor tracks our position in the *original* file. It is 1-indexed.
        original_cursor = 1

        for chunk in sorted_chunks:
            # Write the unmodified lines between the last chunk and this one.
            # Slicing handles the start/end indices correctly.
            start_index = original_cursor - 1
            end_index = chunk.start_line - 1
            if start_index < end_index:
                result.writelines(original_lines[start_index:end_index])

            # Add the new content from the current chunk.
            for line in chunk.add_content:
                result.write(f"{line}\n")

            # Advance the cursor past the lines that were just removed by this chunk.
            original_cursor = chunk.start_line + chunk.line_count

        # After processing all chunks, write the remaining lines from the original file.
        if original_cursor - 1 < len(original_lines):
            result.writelines(original_lines[original_cursor - 1 :])

        # Write the final result to a temp file.
        new_content_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8"
        )
        try:
            new_content_file.write(result.getvalue())
        finally:
            new_content_file.close()

        return Path(new_content_file.name)

    def _apply_changes_via_disk(
        self,
        original_content: bytes,
        sorted_chunks: List[ChunkApplicationData],
    ) -> Path:
        """Process changes using disk-based streaming for large files."""
        reader = io.StringIO(original_content.decode("utf-8"))
        new_content_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, encoding="utf-8"
        )

        try:
            # This cursor tracks our position in the *original* file. It is 1-indexed.
            original_cursor = 1

            for chunk in sorted_chunks:
                # Write lines from the original file that come before this chunk.
                lines_to_write = chunk.start_line - original_cursor
                for _ in range(lines_to_write):
                    line = reader.readline()
                    if line:
                        new_content_file.write(line)

                # Add new content from the chunk.
                for line in chunk.add_content:
                    new_content_file.write(f"{line}\n")

                # Skip lines in the original file that are removed by the chunk.
                lines_to_skip = chunk.line_count
                for _ in range(lines_to_skip):
                    reader.readline()  # Read and discard

                # Update the cursor to its new position in the original file.
                original_cursor = chunk.start_line + chunk.line_count

            # Write any remaining lines from the original file after the last chunk.
            for line in reader:
                new_content_file.write(line)
        finally:
            new_content_file.close()

        return Path(new_content_file.name)

    def _build_tree_from_plan(
        self,
        base_tree_hash: str,
        base_tree_listing: Dict[str, str],
        cumulative_chunks: List[DiffChunk],
    ) -> str:
        final_tree_map = base_tree_listing.copy()

        # --- 1. Pre-process and gather data for batching ---

        chunks_by_file = {
            file_path: list(group)
            for file_path, group in groupby(
                sorted(cumulative_chunks, key=lambda c: c.file_path()),
                key=lambda c: c.file_path(),
            )
        }

        # Process rename chunks in one pass: build rename_map and collect blob hashes
        rename_map: dict[str, str] = {}
        rename_chunks: list[RenameDiffChunk] = []
        base_blobs_to_read = set()

        for chunk in cumulative_chunks:
            if isinstance(chunk, RenameDiffChunk):
                rename_map[chunk.new_file_path] = chunk.old_file_path
                rename_chunks.append(chunk)
                if base_blob_hash := base_tree_listing.get(chunk.old_file_path):
                    base_blobs_to_read.add(base_blob_hash)

        # Add blobs for standard chunks
        for file_path in chunks_by_file:
            # rename file_path points to a new file, that has not been created yet
            if file_path not in rename_map:
                if base_blob_hash := base_tree_listing.get(file_path):
                    base_blobs_to_read.add(base_blob_hash)

        # --- 2. Perform Batch Operations ---

        # BATCH READ: Get all original file contents in one go
        base_blob_contents = self._get_blob_contents_batch(list(base_blobs_to_read))

        temp_files_to_clean = []
        path_to_new_tempfile = {}
        try:
            # --- 3. Remove rename old file paths ---
            for chunk in rename_chunks:
                final_tree_map.pop(chunk.old_file_path)

            # --- 4. Process standard chunks using memory-efficient streaming ---
            for file_path, chunks in chunks_by_file.items():
                original_path = rename_map.get(file_path, file_path)
                base_blob_hash = base_tree_listing.get(original_path)
                original_content = base_blob_contents.get(base_blob_hash, b"")

                chunks_data = [
                    cd for chunk in chunks for cd in chunk.get_chunk_application_data()
                ]

                # Use streaming apply, which returns a path to a temp file
                new_content_temp_path = self._apply_changes_hybrid(
                    original_content, chunks_data
                )

                temp_files_to_clean.append(new_content_temp_path)

                # Check for deletion: file had content, now it's empty
                if original_content and new_content_temp_path.stat().st_size == 0:
                    if file_path in final_tree_map:
                        del final_tree_map[file_path]
                else:
                    path_to_new_tempfile[file_path] = new_content_temp_path

            # BATCH WRITE: Create all new blobs in one go from the temp files
            if path_to_new_tempfile:
                path_to_blob_hash_map = self._create_blobs_batch(path_to_new_tempfile)
                final_tree_map.update(path_to_blob_hash_map)

        finally:
            # --- 5. Cleanup ---
            for temp_file in temp_files_to_clean:
                if temp_file.exists():
                    temp_file.unlink()

        # --- 6. Build the Tree Object ---
        if not final_tree_map:
            return self._run_git_decoded("mktree")

        tree_structure = {}
        for full_path, blob_hash in final_tree_map.items():
            parts = full_path.split("/")
            current_level = tree_structure
            for part in parts[:-1]:
                current_level = current_level.setdefault(part, {})
            current_level[parts[-1]] = blob_hash

        return self._build_recursive_tree(tree_structure)

    def _build_recursive_tree(self, tree_structure: Dict[str, Union[str, dict]]) -> str:
        """Recursively builds Git tree objects from a nested dictionary structure."""
        mktree_input_lines = []
        for name, content in sorted(tree_structure.items()):
            if isinstance(content, str):  # Blob
                mktree_input_lines.append(f"100644 blob {content}\t{name}")
            elif isinstance(content, dict):  # Tree
                subtree_hash = self._build_recursive_tree(content)
                mktree_input_lines.append(f"040000 tree {subtree_hash}\t{name}")

        mktree_input = "\n".join(mktree_input_lines)
        return self._run_git_decoded("mktree", stdin_content=mktree_input)

    def _create_commit(self, tree_hash: str, parent_hash: str, message: str) -> str:
        return self._run_git_decoded(
            "commit-tree", tree_hash, "-p", parent_hash, "-m", message
        )

    def execute_plan(
        self, groups: List[CommitGroup], base_commit: str, branch_to_update: str
    ) -> List[CommitResult]:
        """Executes the synthesis plan to build and apply the new commit history."""

        print("1")

        results: List[CommitResult] = []
        original_base_commit_hash = self._run_git_decoded("rev-parse", base_commit)
        original_base_tree_hash = self._get_commit_tree_hash(original_base_commit_hash)

        # Cache the base tree listing once - it's the same for all commits
        base_tree_listing = self._get_full_tree_listing(original_base_tree_hash)

        last_synthetic_commit_hash = original_base_commit_hash
        cumulative_chunks: List[Union[DiffChunk]] = []

        for group in groups:

            print("2")

            try:
                cumulative_chunks.extend(group.chunks)
                new_tree_hash = self._build_tree_from_plan(
                    original_base_tree_hash, base_tree_listing, cumulative_chunks
                )

                full_message = group.commmit_message
                if group.extended_message:
                    full_message += f"\n\n{group.extended_message}"

                new_commit_hash = self._create_commit(
                    new_tree_hash, last_synthetic_commit_hash, full_message
                )
                last_synthetic_commit_hash = new_commit_hash
                results.append(CommitResult(commit_hash=new_commit_hash, group=group))

            except Exception as e:
                print(
                    f"FATAL: Synthesis failed during group '{group.group_id}'. No changes have been applied."
                )
                raise e

        print("3")

        # Atomically update the target branch to point to the new history
        final_commit_hash = last_synthetic_commit_hash
        if final_commit_hash != original_base_commit_hash:
            self._run_git(
                "update-ref", f"refs/heads/{branch_to_update}", final_commit_hash
            )

            # If we updated the current branch, we must also update the worktree to match
            current_branch = self._run_git_decoded("rev-parse", "--abbrev-ref", "HEAD")
            if current_branch == branch_to_update:
                self._run_git("reset", "--hard")

        return results
