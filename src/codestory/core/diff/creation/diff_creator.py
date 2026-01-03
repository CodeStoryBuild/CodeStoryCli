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

import re

from codestory.core.diff.creation.hunk_wrapper import HunkWrapper
from codestory.core.diff.creation.immutable_hunk_wrapper import ImmutableHunkWrapper
from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.immutable_diff_chunk import ImmutableDiffChunk
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.git.git_interface import GitInterface


class DiffCreator:
    def __init__(self, git: GitInterface):
        self.git = git

    # Precompile diff regexes for performance
    _MODE_RE = re.compile(
        rb"^(?:new file mode|deleted file mode|old mode|new mode) (\d{6})$"
    )
    _INDEX_RE = re.compile(rb"^index [0-9a-f]{7,}\.\.[0-9a-f]{7,}(?: (\d{6}))?$")
    _RENAME_FROM_RE = re.compile(rb"^rename from (.+)$")
    _RENAME_TO_RE = re.compile(rb"^rename to (.+)$")
    _OLD_PATH_RE = re.compile(rb"^--- (?:(?:a/)?(.+)|/dev/null)$")
    _NEW_PATH_RE = re.compile(rb"^\+\+\+ (?:(?:b/)?(.+)|/dev/null)$")
    _A_B_PATHS_RE = re.compile(rb"^diff --git a/(.+?) b/(.+)")

    def get_processed_working_diff(
        self,
        base_hash: str,
        new_hash: str,
        target: str | list[str] | None = None,
    ) -> list[AtomicDiffChunk]:
        """Parses the git diff once and converts each hunk directly into an atomic
        StandardDiffChunk object (StandardDiffChunk) or ImmutableDiffChunk for
        binary/unparsable files.

        Returns a unified list containing both StandardDiffChunk and
        ImmutableDiffChunk objects.
        """
        hunks = self.get_full_working_diff(base_hash, new_hash, target)
        return self.convert_hunks(hunks, base_hash, new_hash)

    def convert_hunks(
        self,
        hunks: list[HunkWrapper | ImmutableHunkWrapper],
        base_hash: str,
        new_hash: str,
    ) -> list[AtomicDiffChunk]:
        chunks: list[AtomicDiffChunk] = []
        for hunk in hunks:
            if isinstance(hunk, ImmutableHunkWrapper):
                chunks.append(
                    self.immutable_diff_chunk_from_hunk(hunk, base_hash, new_hash)
                )
            else:
                chunks.append(self.diff_chunk_from_hunk(hunk, base_hash, new_hash))

        return chunks

    def get_full_working_diff(
        self,
        base_hash: str,
        new_hash: str,
        target: str | list[str] | None = None,
        similarity: int = 50,
    ) -> list[HunkWrapper | ImmutableHunkWrapper]:
        """Generates a list of raw hunks, correctly parsing rename-and-modify diffs.

        This is the authoritative source of diff information.
        """
        if isinstance(target, str):
            targets = [target]
        elif target is None:
            targets = []
        else:
            targets = target

        path_args = ["--"] + targets
        diff_output_bytes = self.git.run_git_binary_out(
            [
                "diff",
                base_hash,
                new_hash,
                "--binary",
                "--unified=0",
                f"-M{similarity}",
            ]
            + path_args
        )
        binary_files = self._get_binary_files(base_hash, new_hash)
        return self._parse_hunks_with_renames(diff_output_bytes, binary_files)

    def _get_binary_files(self, base: str, new: str) -> set[bytes]:
        """Generates a set of file paths that are identified as binary by `git diff
        --numstat`."""
        binary_files: set[bytes] = set()
        cmd = ["diff", "--numstat", base, new]
        numstat_output = self.git.run_git_binary_out(cmd)
        if numstat_output is None:
            return binary_files

        if not numstat_output:
            return binary_files

        for line in numstat_output.splitlines():
            parts = line.split(b"\t")
            if len(parts) == 3 and parts[0] == b"-" and parts[1] == b"-":
                path_part = parts[2]
                if b" => " in path_part:
                    # Handle rename syntax `old => new` or `prefix/{old=>new}/suffix`
                    # by extracting the new path.
                    pre, _, post = path_part.partition(b"{")
                    if post:
                        rename_part, _, suffix = post.partition(b"}")
                        _, _, new_name = rename_part.partition(b" => ")
                        binary_files.add(pre + new_name + suffix)
                    else:
                        _, _, new_path = path_part.partition(b" => ")
                        binary_files.add(new_path)
                else:
                    binary_files.add(path_part)
        return binary_files

    def _is_binary_or_unparsable(
        self,
        diff_lines: list[bytes],
        file_mode: bytes | None,
        file_path: bytes | None,
        binary_files_from_numstat: set[bytes],
    ) -> bool:
        """Detects if a diff block is for a binary file, submodule, symlink, or other
        format that cannot be represented by standard hunk chunks."""
        # 1. Check against the set of binary files from `git diff --numstat`.
        if file_path and file_path in binary_files_from_numstat:
            return True

        # 2. File modes for submodules (160000) and symlinks (120000) are unparsable.
        if file_mode in {b"160000", b"120000"}:
            return True

        # 3. Check for explicit statements in the diff output as a fallback.
        for line in diff_lines:
            if line.startswith(b"Binary files ") or b"Subproject commit" in line:
                return True
        return False

    def _parse_hunks_with_renames(
        self, diff_output: bytes | None, binary_files: set[bytes]
    ) -> list[HunkWrapper | ImmutableHunkWrapper]:
        """Parses a unified diff output, detects binary/unparsable files, and creates
        appropriate HunkWrapper or ImmutableHunkWrapper objects."""
        hunks: list[HunkWrapper | ImmutableHunkWrapper] = []
        if not diff_output:
            return hunks

        file_blocks = diff_output.split(b"\ndiff --git ")

        for block in file_blocks:
            if not block.strip():
                continue

            # the first block will still have a diff --git, otherwise we need to add one
            if not block.startswith(b"diff --git "):
                block = b"diff --git " + block

            lines = block.splitlines()
            if not lines:
                continue

            old_path, new_path, file_mode = self._parse_file_metadata(lines)

            if old_path is None and new_path is None:
                raise ValueError(
                    "Both old and new file paths are None! Invalid /dev/null parsing!"
                )
            elif not old_path and not new_path:
                raise ValueError("Could not parse file paths from diff block!")

            path_to_check = new_path if new_path is not None else old_path

            if self._is_binary_or_unparsable(
                lines, file_mode, path_to_check, binary_files
            ):
                # add back the "diff -git"
                hunks.append(
                    ImmutableHunkWrapper(
                        old_file_path=old_path, new_file_path=new_path, file_patch=block
                    )
                )
                continue

            hunk_start_indices = [
                i for i, line in enumerate(lines) if line.startswith(b"@@ ")
            ]

            if not hunk_start_indices:
                hunks.append(
                    HunkWrapper.create_empty_content(
                        new_file_path=new_path,
                        old_file_path=old_path,
                        file_mode=file_mode,
                    )
                )
            else:
                for i, start_idx in enumerate(hunk_start_indices):
                    end_idx = (
                        hunk_start_indices[i + 1]
                        if i + 1 < len(hunk_start_indices)
                        else len(lines)
                    )
                    hunk_header = lines[start_idx]
                    hunk_body_lines = lines[start_idx + 1 : end_idx]

                    old_start, old_len, new_start, new_len = self._parse_hunk_start(
                        hunk_header
                    )

                    hunks.append(
                        HunkWrapper(
                            new_file_path=new_path,
                            old_file_path=old_path,
                            file_mode=file_mode,
                            hunk_lines=hunk_body_lines,
                            old_start=old_start,
                            new_start=new_start,
                            old_len=old_len,
                            new_len=new_len,
                        )
                    )
        return hunks

    def _parse_file_metadata(self, lines: list[bytes]) -> tuple:
        """Extracts file operation metadata from a diff block by unifying the logic
        around the '---' and '+++' file path lines.

        Returns a dictionary with file paths, operation flags, and mode
        information.
        """
        old_path, new_path = b"", b""
        file_mode = None

        # 1. First pass: Extract primary data (paths and mode)
        for line in lines:
            # Check for file mode (new, deleted, old, new)
            mode_match = self._MODE_RE.match(line)
            if mode_match:
                # We only need one mode; Git diffs can show old and new.
                # The one on the 'new file mode' or 'deleted file mode' line is most relevant.
                if file_mode is None or b"file mode" in line:
                    file_mode = mode_match.group(1)
                continue

            old_path_match = self._OLD_PATH_RE.match(line)
            if old_path_match:
                if line.strip() == b"--- /dev/null":
                    old_path = None
                else:
                    old_path = old_path_match.group(1)
                continue

            new_path_match = self._NEW_PATH_RE.match(line)
            if new_path_match:
                if line.strip() == b"+++ /dev/null":
                    new_path = None
                else:
                    new_path = new_path_match.group(1)
                continue

        # fallback for cases like:
        # a/src/api/__init__.py b/src/api/__init__.py
        # new file mode 100644
        # index 0000000..e69de29
        # no --- or +++ lines
        if not old_path and not new_path:
            # Use regex to robustly extract a/ and b/ paths from the first line
            path_a, path_b = None, None
            m = self._A_B_PATHS_RE.match(lines[0])
            if not m:
                return (None, None, file_mode)  # Unrecognized format
            path_a = m.group(1)
            path_b = m.group(2)

            # Use other metadata clues from the block to determine the operation
            block_text = b"\n".join(lines)
            if b"new file mode" in block_text:
                # This is an empty file addition.
                return (None, path_b, file_mode)
            elif b"deleted file mode" in block_text:
                # This is an empty file deletion (less common, but possible).
                return (path_a, None, file_mode)
            elif b"rename from" in block_text:
                # This is a pure rename with no content change.
                return (path_a, path_b, file_mode)
            else:
                # Could be a pure mode change.
                return (path_a, path_b, file_mode)

        return (old_path, new_path, file_mode)

    def _create_no_content_hunk(self, file_metadata: dict) -> HunkWrapper:
        """Create a HunkWrapper for files with no content changes (pure operations)."""
        if file_metadata["is_rename"]:
            # Pure rename (no content change)
            return HunkWrapper.create_empty_rename(
                new_file_path=file_metadata["canonical_path"],
                old_file_path=file_metadata["old_path"],
                file_mode=file_metadata["file_mode"],
            )
        elif file_metadata["is_file_addition"]:
            # Empty new file (no content)
            return HunkWrapper.create_empty_addition(
                new_file_path=file_metadata["canonical_path"],
                file_mode=file_metadata["file_mode"],
            )
        elif file_metadata["is_file_deletion"]:
            # File deletion (deleted file mode)
            return HunkWrapper.create_empty_deletion(
                old_file_path=file_metadata["canonical_path"],
                file_mode=file_metadata["file_mode"],
            )

        else:
            raise ValueError("Cannot create no-content hunk for unknown operation.")

    def _parse_hunk_start(self, header_line: bytes) -> tuple[int, int, int, int]:
        """
        Extract old_start, old_len, new_start, new_len from @@ -x,y +a,b @@ header
        Returns: (old_start, old_len, new_start, new_len)
        """
        import re

        match = re.search(rb"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header_line)
        if match:
            old_start = int(match.group(1))
            old_len = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_len = int(match.group(4)) if match.group(4) else 1
            return old_start, old_len, new_start, new_len
        return 0, 0, 0, 0

    def diff_chunk_from_hunk(
        self, hunk: HunkWrapper, base_hash: str, new_hash: str
    ) -> StandardDiffChunk:
        """Construct a StandardDiffChunk from a single, parsed HunkWrapper. This is the
        standard factory for this class.

        CRITICAL: We store BOTH coordinate systems:
        - old_line: Position in old file (used for patch generation)
        - abs_new_line: Absolute position in new file from original diff
          (ONLY used for semantic grouping, never for patch generation)
        """
        parsed_content: list[Addition | Removal] = []
        current_old_line = hunk.old_start
        current_new_line = hunk.new_start

        contains_newline_fallback = False

        for line in hunk.hunk_lines:
            sanitized_content = StandardDiffChunk._sanitize_patch_content(line[1:])
            if line.startswith(b"+"):
                # For additions:
                # - old_line: where in old file this addition occurs (line before insertion)
                # - abs_new_line: absolute position in new file (from original diff)
                parsed_content.append(
                    Addition(
                        old_line=current_old_line,
                        abs_new_line=current_new_line,
                        content=sanitized_content,
                    )
                )
                current_new_line += 1
            elif line.startswith(b"-"):
                # For removals:
                # - old_line: the line being removed from old file
                # - abs_new_line: where this removal "lands" in new file
                parsed_content.append(
                    Removal(
                        old_line=current_old_line,
                        abs_new_line=current_new_line,
                        content=sanitized_content,
                    )
                )
                current_old_line += 1
            elif line.strip() == b"\\ No newline at end of file":
                if parsed_content:
                    parsed_content[-1].newline_marker = True
                else:
                    contains_newline_fallback = True

        return StandardDiffChunk(
            base_hash=base_hash,
            new_hash=new_hash,
            old_file_path=hunk.old_file_path,
            new_file_path=hunk.new_file_path,
            file_mode=hunk.file_mode,
            contains_newline_fallback=contains_newline_fallback,
            parsed_content=parsed_content,
            old_start=hunk.old_start,
        )

    def immutable_diff_chunk_from_hunk(
        self, hunk: ImmutableHunkWrapper, base_hash: str, new_hash: str
    ) -> ImmutableDiffChunk:
        """Construct an ImmutableDiffChunk from a single, parsed ImmutableHunkWrapper.

        This is the standard factory for this class.
        """
        return ImmutableDiffChunk(
            base_hash=base_hash,
            new_hash=new_hash,
            old_file_path=hunk.old_file_path,
            new_file_path=hunk.new_file_path,
            file_patch=hunk.file_patch,
        )
