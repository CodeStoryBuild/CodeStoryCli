import subprocess
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Union
from itertools import groupby

## Imports
from ..data.models import (
    CommitGroup,
    Addition,
    Removal,
    CommitResult,
    ChunkApplicationData,
)
from ..data.s_diff_chunk import StandardDiffChunk
from ..data.r_diff_chunk import RenameDiffChunk
from ..git_interface.interface import GitInterface


class GitSynthesizer:
    """
    Builds a clean, linear Git history from a plan of commit groups.
    Directly manipulates Git's object database for atomic operations.
    """

    def __init__(self, git: GitInterface):
        self.git = git

    def _run_git(
        self, *args: str, env: Dict = None, stdin_content: Union[str, bytes] = None
    ) -> str:
        # Pass bytes directly to avoid newline conversion.
        if isinstance(stdin_content, str):
            stdin_content = stdin_content.encode("utf-8")

        # Always run in binary mode for stdin and decode output manually.
        output_bytes = self.git.run_git_binary(
            list(args), input_bytes=stdin_content, env=env
        )
        return output_bytes.decode("utf-8").strip()

    def _get_commit_tree_hash(self, commit_ish: str) -> str:
        return self._run_git("rev-parse", f"{commit_ish}^{{tree}}")

    def _get_full_tree_listing(self, tree_hash: str) -> Dict[str, str]:
        if not tree_hash:
            return {}
        # Use NULL characters as delimiters for paths with spaces/special chars.
        ls_tree_output = self._run_git("ls-tree", "-r", "-z", tree_hash)
        if not ls_tree_output:
            return {}

        listing = {}
        # Split by NULL character, filter out empty strings
        entries = [entry for entry in ls_tree_output.split("\0") if entry]
        for entry in entries:
            # Format is: <mode> <type> <hash>\t<path>
            meta, path = entry.split("\t", 1)
            _, _, blob_hash = meta.split(maxsplit=2)
            listing[path] = blob_hash
        return listing

    def _get_blob_content_as_lines(self, blob_hash: str) -> List[str]:
        if not blob_hash:
            return []
        content = self._run_git("cat-file", "-p", blob_hash)
        return content.splitlines()

    def _create_blob(self, content: str) -> str:
        return self._run_git("hash-object", "-w", "--stdin", stdin_content=content)

    def _apply_chunks_to_lines(
        self, original_lines: List[str], chunks_data: List[ChunkApplicationData]
    ) -> str:
        """
        Applies a set of disjoint chunks to an original set of lines.
        Builds a new list of lines for correct coordinate handling.
        """
        if not chunks_data:
            # If there are no changes, join the original lines.
            result = "\n".join(original_lines)
            if original_lines:  # Add trailing newline if original was not empty
                result += "\n"
            return result

        # Sort chunks by starting line number
        sorted_chunks = sorted(chunks_data, key=lambda c: c.start_line)

        print(f"{sorted_chunks=}")

        result_lines = []
        # Use a cursor to track position in original_lines
        original_cursor = 0

        for chunk in sorted_chunks:
            # Convert start_line to 0-indexed
            start_index = chunk.start_line - 1

            # Copy lines before chunk
            lines_before_chunk = original_lines[original_cursor:start_index]
            result_lines.extend(lines_before_chunk)
            print(
                f"Applying chunk: {chunk=} Copied lines before: {lines_before_chunk=}"
            )

            # Add chunk content
            result_lines.extend(chunk.add_content)
            print(f"Added chunk content. Current result: {result_lines=}")

            # Move cursor past removed lines
            original_cursor = start_index + chunk.line_count
            print(f"Moved cursor to {original_cursor=}")

        # Add remaining lines
        remaining_lines = original_lines[original_cursor:]
        result_lines.extend(remaining_lines)
        print(f"Added remaining lines: {remaining_lines=}")

        result = "\n".join(result_lines)
        # Add final newline for non-empty text files
        if result:
            result += "\n"
        return result

    def _build_tree_from_plan(
        self,
        base_tree_hash: str,
        cumulative_chunks: List[Union[StandardDiffChunk, RenameDiffChunk]],
    ) -> str:
        # Start with flat map of {path: blob_hash} from base tree
        final_tree_map = self._get_full_tree_listing(base_tree_hash)

        # Handle renames first
        for chunk in cumulative_chunks:
            if isinstance(chunk, RenameDiffChunk):
                # Get the original content blob
                original_blob_hash = final_tree_map.pop(chunk.old_file_path, None)
                if original_blob_hash is None:
                    # Handle case where the file to be renamed doesn't exist (edge case)
                    continue

                original_lines = self._get_blob_content_as_lines(original_blob_hash)

                # Apply the modifications stored inside the chunk
                new_content = self._apply_chunks_to_lines(
                    original_lines, chunk.application_data
                )

                # Create a new blob for the modified content
                new_blob_hash = self._create_blob(new_content)

                # Place the new blob at the new file path
                final_tree_map[chunk.new_file_path] = new_blob_hash

        # Group standard chunks by file path
        standard_chunks = [
            c for c in cumulative_chunks if isinstance(c, StandardDiffChunk)
        ]
        chunks_by_file = {
            file_path: list(group)
            for file_path, group in groupby(
                sorted(standard_chunks, key=lambda c: c.file_path),
                key=lambda c: c.file_path,
            )
        }

        # This is used to get original content for a file that might have been renamed.
        # It maps new_path -> old_path.
        rename_map = {
            c.new_file_path: c.old_file_path
            for c in cumulative_chunks
            if isinstance(c, RenameDiffChunk)
        }
        base_tree_listing = self._get_full_tree_listing(base_tree_hash)

        # 4. For each file with changes, calculate its new content and update the flat map.
        for file_path, chunks in chunks_by_file.items():
            original_path = rename_map.get(file_path, file_path)
            base_blob_hash = base_tree_listing.get(original_path)
            original_lines = (
                self._get_blob_content_as_lines(base_blob_hash)
                if base_blob_hash
                else []
            )

            # With our contiguity guarantee, we can now process chunks correctly
            # Each chunk has contiguous removals starting at old_start and contiguous additions starting at new_start
            chunks_data = []

            for chunk in chunks:
                removals = [
                    item for item in chunk.parsed_content if isinstance(item, Removal)
                ]
                additions = [
                    item for item in chunk.parsed_content if isinstance(item, Addition)
                ]

                # If a chunk has both removals and additions, it's a "replace" operation.
                # The anchor point for applying the change is always the start of the removal.
                if removals and additions:
                    chunks_data.append(
                        ChunkApplicationData(
                            start_line=chunk.old_start,
                            line_count=len(removals),
                            add_content=[item.content for item in additions],
                        )
                    )
                # If it only has removals, it's a pure deletion.
                elif removals:
                    chunks_data.append(
                        ChunkApplicationData(
                            start_line=chunk.old_start,
                            line_count=len(removals),
                            add_content=[],
                        )
                    )
                # If it only has additions, it's a pure addition.
                elif additions:
                    chunks_data.append(
                        ChunkApplicationData(
                            start_line=chunk.old_start + 1,
                            line_count=0,
                            add_content=[item.content for item in additions],
                        )
                    )

            print(f"{chunks_data=}")

            new_content = self._apply_chunks_to_lines(original_lines, chunks_data)

            is_deletion = not new_content and original_lines
            if is_deletion:
                if file_path in final_tree_map:
                    del final_tree_map[file_path]
            else:
                new_blob_hash = self._create_blob(new_content)
                final_tree_map[file_path] = new_blob_hash

        # 5. Convert the final flat map into a nested dictionary structure.
        tree_structure = {}
        if not final_tree_map:
            return self._run_git("mktree")  # Handle case of an empty repo

        for full_path, blob_hash in final_tree_map.items():
            parts = full_path.split("/")
            current_level = tree_structure
            for part in parts[:-1]:  # Iterate through directories
                current_level = current_level.setdefault(part, {})
            current_level[parts[-1]] = blob_hash

        # 6. Recursively build the tree objects from the nested structure.
        return self._build_recursive_tree(tree_structure)

    def _build_recursive_tree(self, tree_structure: Dict[str, Union[str, dict]]) -> str:
        """
        Recursively builds Git tree objects from a nested dictionary structure.
        """
        mktree_input_lines = []

        for name, content in sorted(tree_structure.items()):
            if isinstance(content, str):  # File (blob)
                mktree_input_lines.append(f"100644 blob {content}\t{name}")
            elif isinstance(content, dict):  # Subdirectory (tree)
                subtree_hash = self._build_recursive_tree(content)
                mktree_input_lines.append(f"040000 tree {subtree_hash}\t{name}")

        mktree_input = "\n".join(mktree_input_lines)
        return self._run_git("mktree", stdin_content=mktree_input)

    def _create_commit(self, tree_hash: str, parent_hash: str, message: str) -> str:
        return self._run_git("commit-tree", tree_hash, "-p", parent_hash, "-m", message)

    def execute_plan(
        self, groups: List[CommitGroup], base_commit: str, branch_to_update: str
    ) -> List[CommitResult]:
        results: List[CommitResult] = []
        original_base_commit_hash = self._run_git("rev-parse", base_commit)
        last_synthetic_commit_hash = original_base_commit_hash
        cumulative_chunks: List[Union[StandardDiffChunk, RenameDiffChunk]] = []

        for group in groups:
            try:
                cumulative_chunks.extend(group.chunks)
                new_tree_hash = self._build_tree_from_plan(
                    original_base_commit_hash, cumulative_chunks
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
                # A simple safety measure: if synthesis fails, don't update the branch.
                print(
                    f"FATAL: Synthesis failed during group '{group.group_id}'. No changes have been applied."
                )
                raise e

        final_commit_hash = last_synthetic_commit_hash
        if final_commit_hash != original_base_commit_hash:
            self._run_git(
                "update-ref", f"refs/heads/{branch_to_update}", final_commit_hash
            )
            self._run_git("reset", "--hard", branch_to_update)
            self._run_git("clean", "-fd")

        return results
