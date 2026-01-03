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

from dataclasses import dataclass, field

from codestory.core.data.chunk import Chunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.exceptions import SyntaxErrorDetected
from codestory.core.file_reader.file_parser import FileParser, ParsedFile
from codestory.core.file_reader.git_file_reader import GitFileReader
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_grouper.comment_mapper import CommentMap, CommentMapper
from codestory.core.semantic_grouper.query_manager import QueryManager
from codestory.core.semantic_grouper.scope_mapper import ScopeMap, ScopeMapper
from codestory.core.semantic_grouper.symbol_extractor import SymbolExtractor
from codestory.core.semantic_grouper.symbol_mapper import SymbolMap, SymbolMapper


@dataclass(frozen=True)
class AnalysisContext:
    """Contains the analysis context for a specific file version."""

    file_path: bytes
    detected_language: str
    content_bytes: bytes
    line_ranges: list[tuple[int, int]]
    scope_map: ScopeMap
    symbol_map: SymbolMap
    comment_map: CommentMap
    symbols: set[str]
    is_old_version: bool


@dataclass(frozen=True)
class SharedContext:
    """Contains shared context between all files of the same type"""

    defined_symbols: set[str]


@dataclass
class ContextManager:
    """
    Data container for analysis contexts.

    This is a pure data class containing the computed analysis results.
    Use ContextManagerBuilder to construct instances.

    Fields:
        _context_cache: Mapping from (file_path, is_old_version) to AnalysisContext
        _shared_context_cache: Mapping from (language, is_old_version) to SharedContext
        base_commit: The base commit hash
        patched_commit: The patched commit hash
    """

    _context_cache: dict[tuple[bytes, bool], AnalysisContext] = field(
        default_factory=dict
    )
    _shared_context_cache: dict[tuple[str, bool], SharedContext] = field(
        default_factory=dict
    )
    base_commit: str = ""
    patched_commit: str = ""
    _old_file_content_map: dict[bytes, bytes] | None = field(default=None, repr=False)

    @property
    def old_file_content_map(self) -> dict[bytes, bytes]:
        """
        Get a map of file_path -> old file content bytes.

        This is lazily built from the context cache and cached for reuse.
        Used by SemanticDiffGenerator and JsonDiffGenerator.
        """
        if self._old_file_content_map is None:
            content_map: dict[bytes, bytes] = {}
            for (file_path, is_old_version), ctx in self._context_cache.items():
                if is_old_version and ctx.content_bytes:
                    content_map[file_path] = ctx.content_bytes
            # Store in the private field (dataclass allows mutation)
            object.__setattr__(self, "_old_file_content_map", content_map)
        return self._old_file_content_map

    def get_context(
        self, file_path: bytes, is_old_version: bool
    ) -> AnalysisContext | None:
        """
        Get analysis context for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version

        Returns:
            AnalysisContext if available, None if not found or not required
        """
        return self._context_cache.get((file_path, is_old_version))

    def get_available_contexts(self) -> list[AnalysisContext]:
        """
        Get all available analysis contexts.

        Returns:
            List of all successfully built AnalysisContext objects
        """
        return list(self._context_cache.values())

    def has_context(self, file_path: bytes, is_old_version: bool) -> bool:
        """
        Check if context is available for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version

        Returns:
            True if context is available, False otherwise
        """
        return (file_path, is_old_version) in self._context_cache

    def get_file_paths(self) -> set[bytes]:
        """
        Get all unique file paths that have contexts.

        Returns:
            Set of file paths that have at least one context (old or new)
        """
        return {file_path for file_path, _ in self._context_cache}


class ContextManagerBuilder:
    """
    Builds a ContextManager from chunks and file reader.

    This class encapsulates all the transient builder logic:
    - File parsing with tree-sitter
    - Scope/symbol/comment mapping
    - Context construction

    Usage:
        builder = ContextManagerBuilder(chunks, file_reader, base, patched)
        context_manager = builder.build()
    """

    def __init__(
        self,
        chunks: list[Chunk],
        file_reader: GitFileReader,
        base_commit: str,
        patched_commit: str,
        fail_on_syntax_errors: bool = False,
    ):
        self.file_reader = file_reader
        self.base_commit = base_commit
        self.patched_commit = patched_commit
        self.diff_chunks = [
            diff_chunk for chunk in chunks for diff_chunk in chunk.get_chunks()
        ]
        self.fail_on_syntax_errors = fail_on_syntax_errors

        # Initialize mappers
        self.query_manager = QueryManager.get_instance()
        self.scope_mapper = ScopeMapper(self.query_manager)
        self.symbol_mapper = SymbolMapper(self.query_manager)
        self.symbol_extractor = SymbolExtractor(self.query_manager)
        self.comment_mapper = CommentMapper(self.query_manager)

        # Internal state for building
        self._shared_context_cache: dict[tuple[str, bool], SharedContext] = {}
        self._context_cache: dict[tuple[bytes, bool], AnalysisContext] = {}
        self._required_contexts: dict[tuple[bytes, bool], list[tuple[int, int]]] = {}
        self._parsed_files: dict[tuple[bytes, bool], ParsedFile] = {}

    def build(self) -> ContextManager:
        """
        Build and return a ContextManager with all computed contexts.

        Returns:
            ContextManager instance containing all analysis contexts
        """
        # Determine which file versions need to be analyzed
        self._analyze_required_contexts()

        ProgressBarManager.get_pbar()

        self._generate_parsed_files()

        # First, build shared context
        self._build_shared_contexts()

        # Then, build all required contexts (dependent on shared context)
        self._build_all_contexts()

        # Log a summary of built contexts
        self._log_context_summary()

        # Return data-only ContextManager
        return ContextManager(
            _context_cache=self._context_cache,
            _shared_context_cache=self._shared_context_cache,
            base_commit=self.base_commit,
            patched_commit=self.patched_commit,
        )

    def _log_context_summary(self) -> None:
        from loguru import logger

        total_required = len(self._required_contexts.keys())
        total_built = len(self._context_cache)
        files_with_context = {fp for fp, _ in self._context_cache}
        languages: dict[str, int] = {}
        for ctx in self._context_cache.values():
            lang = ctx.detected_language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1

        missing = set(self._required_contexts.keys()) - set(self._context_cache.keys())

        logger.debug(
            "Context build summary: required={required} built={built} files={files}",
            required=total_required,
            built=total_built,
            files=len(files_with_context),
        )
        if languages:
            logger.debug(
                "Context languages distribution: {dist}",
                dist=languages,
            )
        if missing:
            # log a few missing samples to avoid huge logs
            sample = list(missing)[:10]
            logger.debug(
                "Missing contexts (sample up to 10): {sample} (total_missing={cnt})",
                sample=sample,
                cnt=len(missing),
            )

    def _analyze_required_contexts(self) -> None:
        """
        Analyze diff chunks to determine which file versions need context.
        """
        for chunk in self.diff_chunks:
            if chunk.is_standard_modification:
                # Standard modification: need both old and new versions of the same file
                file_path = chunk.canonical_path()
                self._required_contexts.setdefault((file_path, True), []).append(
                    self._get_line_range(chunk, True)
                )  # old version
                self._required_contexts.setdefault((file_path, False), []).append(
                    self._get_line_range(chunk, False)
                )  # new version

            elif chunk.is_file_addition:
                # File addition: only need new version
                file_path = chunk.new_file_path
                self._required_contexts.setdefault((file_path, False), []).append(
                    self._get_line_range(chunk, False)
                )  # new version only

            elif chunk.is_file_deletion:
                # File deletion: only need old version
                file_path = chunk.old_file_path
                self._required_contexts.setdefault((file_path, True), []).append(
                    self._get_line_range(chunk, True)
                )  # old version only

            elif chunk.is_file_rename:
                # File rename: need old version with old name, new version with new name
                old_path = chunk.old_file_path
                new_path = chunk.new_file_path
                self._required_contexts.setdefault((old_path, True), []).append(
                    self._get_line_range(chunk, True)
                )  # old version with old name
                self._required_contexts.setdefault((new_path, False), []).append(
                    self._get_line_range(chunk, False)
                )  # new version with new name

    @staticmethod
    def _get_line_range(chunk: DiffChunk, is_old_range: bool) -> tuple[int, int]:
        # Returns 0-indexed line range from chunk
        if is_old_range:
            return (chunk.old_start - 1, chunk.old_start + chunk.old_len() - 2)
        else:
            # For new file ranges, use abs_new_line (absolute position from original diff)
            # This is ONLY for semantic grouping purposes!
            start = chunk.get_abs_new_line_start()
            end = chunk.get_abs_new_line_end()
            if start is None or end is None:
                # No additions in this chunk, use old_start as fallback
                return (chunk.old_start - 1, chunk.old_start - 1)
            return (start - 1, end - 1)

    def _generate_parsed_files(self) -> None:
        from loguru import logger

        # Gather all required files
        old_files = []
        new_files = []
        context_keys = []

        for (
            file_path,
            is_old_version,
        ), line_ranges in self._required_contexts.items():
            if not line_ranges:
                logger.debug(
                    f"No line ranges for file: {file_path}, skipping semantic generation"
                )
                continue

            # Decode bytes file path for file_reader
            path_str = (
                file_path.decode("utf-8", errors="replace")
                if isinstance(file_path, bytes)
                else file_path
            )

            if is_old_version:
                old_files.append(path_str)
            else:
                new_files.append(path_str)

            context_keys.append((file_path, is_old_version, path_str))

        # Read all files at once
        old_contents, new_contents = self.file_reader.read_all(
            self.base_commit, self.patched_commit, old_files, new_files
        )

        # Map contents back to context keys
        content_map: dict[tuple[str, bool], str | None] = {}
        for i, path in enumerate(old_files):
            content_map[(path, True)] = old_contents[i]
        for i, path in enumerate(new_files):
            content_map[(path, False)] = new_contents[i]

        # Parse each file
        for file_path, is_old_version, path_str in context_keys:
            try:
                content = content_map.get((path_str, is_old_version))
                if content is None:
                    logger.debug(f"Content read for {path_str} is None")
                    continue

                line_ranges = self._required_contexts[(file_path, is_old_version)]
                # Parse the file (file_parser expects string path)
                parsed_file = FileParser.parse_file(
                    path_str, content, self._simplify_overlapping_ranges(line_ranges)
                )
                if parsed_file is None:
                    logger.debug(f"Parsed file for {path_str} is None")
                    continue

                self._parsed_files[(file_path, is_old_version)] = parsed_file
            finally:
                pbar = ProgressBarManager.get_pbar()
                if pbar is not None:
                    pbar.update(1)
                    pbar.set_postfix(
                        {
                            "phase": "parsing",
                            "files": f"{len(self._parsed_files)}/{len(self._required_contexts)}",
                        }
                    )

    def _simplify_overlapping_ranges(
        self, ranges: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        # simplify by filtering invalid ranges, and collapsing overlapping ranges
        new_ranges = []
        for line_range in sorted(ranges):
            start, cur_end = line_range
            if cur_end < start:
                # filter invalid range
                continue

            if new_ranges:
                prev_start, end = new_ranges[-1]
                start, cur_end = line_range

                if end >= start - 1:
                    # direct neighbors
                    new_ranges[-1] = (min(prev_start, start), max(cur_end, end))
                else:
                    new_ranges.append(line_range)
            else:
                new_ranges.append(line_range)

        return new_ranges

    def _build_shared_contexts(self) -> None:
        """
        Build shared analysis contexts for all required file versions.
        """
        from loguru import logger

        languages: dict[str, list[ParsedFile]] = {}

        for (_, is_old), parsed_file in self._parsed_files.items():
            languages.setdefault((parsed_file.detected_language, is_old), []).append(
                parsed_file
            )

        # If some files failed to parse, we should still advance the pbar for them in this phase
        # to keep the total consistent.
        files_processed_in_this_phase = 0
        total_files = len(self._required_contexts)

        for (language, is_old), parsed_files in languages.items():
            defined_symbols: set[str] = set()
            try:
                for parsed_file in parsed_files:
                    try:
                        defined_symbols.update(
                            self.symbol_extractor.extract_defined_symbols(
                                parsed_file.detected_language,
                                parsed_file.root_node,
                                parsed_file.line_ranges,
                            )
                        )
                    finally:
                        pbar = ProgressBarManager.get_pbar()
                        if pbar is not None:
                            pbar.update(1)
                            files_processed_in_this_phase += 1
                            pbar.set_postfix(
                                {
                                    "phase": "shared",
                                    "files": f"{files_processed_in_this_phase}/{total_files}",
                                }
                            )

                context = SharedContext(defined_symbols)
                self._shared_context_cache[(language, is_old)] = context
            except Exception as e:
                logger.debug(f"Failed to build shared context for {language}: {e}")

        # Advance pbar for any files that were required but not parsed (so not in self._parsed_files)
        pbar = ProgressBarManager.get_pbar()
        if pbar is not None:
            remaining = total_files - files_processed_in_this_phase
            if remaining > 0:
                pbar.update(remaining)

    def _build_all_contexts(self) -> None:
        """
        Build analysis contexts for all required file versions.
        """
        from loguru import logger

        total_files = len(self._required_contexts)
        files_processed_in_this_phase = 0

        for (
            file_path,
            is_old_version,
        ) in self._required_contexts:
            try:
                parsed_file = self._parsed_files.get((file_path, is_old_version))
                if parsed_file:
                    context = self._build_context(
                        file_path, is_old_version, parsed_file
                    )
                    if context is not None:
                        self._context_cache[(file_path, is_old_version)] = context
                    else:
                        logger.debug(
                            f"Failed to build context for {file_path} (old={is_old_version})"
                        )
            finally:
                pbar = ProgressBarManager.get_pbar()
                if pbar is not None:
                    pbar.update(1)
                    files_processed_in_this_phase += 1
                    pbar.set_postfix(
                        {
                            "phase": "final",
                            "contexts": f"{len(self._context_cache)}/{total_files}",
                        }
                    )

    def _build_context(
        self, file_path: bytes, is_old_version: bool, parsed_file: ParsedFile
    ) -> AnalysisContext | None:
        """
        Build analysis context for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version
            parsed_file: The parsed file

        Returns:
            AnalysisContext if successful, None if file cannot be processed
        """
        from loguru import logger

        # check if any of the new ast has syntax errors

        def traverse_errors(node) -> bool:
            if node.has_error:
                return True
            return any(traverse_errors(child) for child in node.children)

        if (not is_old_version) and traverse_errors(parsed_file.root_node):
            file_path_str = file_path.decode("utf-8", errors="replace")
            if not is_old_version and self.fail_on_syntax_errors:
                raise SyntaxErrorDetected(
                    f"Exiting commit early! Syntax errors detected in current version of {file_path_str}! (fail_on_syntax_errors is enabled)"
                )

            logger.warning(
                f"Syntax errors detected in current version of {file_path_str}!"
            )
            return None

        try:
            # Build scope map
            scope_map = self.scope_mapper.build_scope_map(
                parsed_file.detected_language,
                parsed_file.root_node,
                file_path,
                parsed_file.line_ranges,
            )

            # If we need to share symbols between files, use the shared context

            if self.query_manager.get_config(
                parsed_file.detected_language
            ).share_tokens_between_files:
                symbols = self._shared_context_cache.get(
                    (parsed_file.detected_language, is_old_version)
                ).defined_symbols
            else:
                symbols = self.symbol_extractor.extract_defined_symbols(
                    parsed_file.detected_language,
                    parsed_file.root_node,
                    parsed_file.line_ranges,
                )

            # Build symbol map
            symbol_map = self.symbol_mapper.build_symbol_map(
                parsed_file.detected_language,
                parsed_file.root_node,
                symbols,
                parsed_file.line_ranges,
            )

            comment_map = self.comment_mapper.build_comment_map(
                parsed_file.detected_language,
                parsed_file.root_node,
                parsed_file.content_bytes,
                parsed_file.line_ranges,
            )
        except Exception as e:
            logger.debug(f"Error building maps for {file_path}: {e}")
            return None

        context = AnalysisContext(
            file_path=file_path,
            detected_language=parsed_file.detected_language,
            content_bytes=parsed_file.content_bytes,
            line_ranges=parsed_file.line_ranges,
            scope_map=scope_map,
            symbol_map=symbol_map,
            comment_map=comment_map,
            symbols=symbols,
            is_old_version=is_old_version,
        )

        logger.debug(f"{context=}")

        return context
