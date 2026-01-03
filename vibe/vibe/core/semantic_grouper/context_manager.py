from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from tree_sitter import Node

from vibe.core.file_reader.protocol import FileReader
from vibe.core.file_reader.file_parser import FileParser, ParsedFile
from vibe.core.data.diff_chunk import DiffChunk
from .query_manager import QueryManager
from .scope_mapper import ScopeMapper, ScopeMap
from .symbol_mapper import SymbolMapper, SymbolMap
from .comment_mapper import CommentMapper, CommentMap
from .symbol_extractor import SymbolExtractor
from loguru import logger


@dataclass(frozen=True)
class AnalysisContext:
    """Contains the analysis context for a specific file version."""

    file_path: str
    parsed_file: ParsedFile
    scope_map: ScopeMap
    symbol_map: SymbolMap
    comment_map: CommentMap
    symbols: set[str]
    is_old_version: bool


@dataclass(frozen=True)
class SharedContext:
    """Contains shared context between all files of the same type"""

    defined_symbols: set[str]


class ContextManager:
    """
    Manages analysis context for files mentioned in diff chunks.

    Creates scope and symbol maps for old and new versions of files that appear
    in diff chunks, enabling semantic analysis across file changes.
    """

    def __init__(
        self,
        file_parser: FileParser,
        file_reader: FileReader,
        query_manager: QueryManager,
        diff_chunks: List[DiffChunk],
    ):
        self.file_parser = file_parser
        self.file_reader = file_reader
        self.query_manager = query_manager
        self.diff_chunks = diff_chunks

        # Initialize mappers
        self.scope_mapper = ScopeMapper(query_manager)
        self.symbol_mapper = SymbolMapper(query_manager)
        self.symbol_extractor = SymbolExtractor(query_manager)
        self.comment_mapper = CommentMapper(query_manager)

        # Context storage: (file_type (language name)) -> SharedContext
        self._shared_context_cache: Dict[str, SharedContext] = {}
        # Context storage: (file_path, is_old_version) -> AnalysisContext
        self._context_cache: Dict[tuple[str, bool], AnalysisContext] = {}

        # Determine which file versions need to be analyzed
        self._required_contexts: dict[tuple[str, bool], list[tuple[int, int]]] = {}
        self._analyze_required_contexts()

        self._parsed_files: dict[tuple[str, bool], ParsedFile] = {}
        self._generate_parsed_files()

        # First, build shared context
        self._build_shared_contexts()

        # THen, Build all required contexts (dependant on shared context)
        self._build_all_contexts()

        # Log a summary of built contexts
        self._log_context_summary()

    def _log_context_summary(self) -> None:
        total_required = len(self._required_contexts.keys())
        total_built = len(self._context_cache)
        files_with_context = {fp for fp, _ in self._context_cache.keys()}
        languages: Dict[str, int] = {}
        for ctx in self._context_cache.values():
            lang = ctx.parsed_file.detected_language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1

        missing = set(self._required_contexts.keys()) - set(self._context_cache.keys())

        logger.info(
            "Context build summary: required={required} built={built} files={files}",
            required=total_required,
            built=total_built,
            files=len(files_with_context),
        )
        if languages:
            logger.info(
                "Context languages distribution: {dist}",
                dist=languages,
            )
        if missing:
            # log a few missing samples to avoid huge logs
            sample = list(missing)[:10]
            logger.warning(
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
                    ContextManager._get_line_range(chunk, True)
                )  # old version
                self._required_contexts.setdefault((file_path, False), []).append(
                    ContextManager._get_line_range(chunk, False)
                )  # new version

            elif chunk.is_file_addition:
                # File addition: only need new version
                file_path = chunk.new_file_path
                self._required_contexts.setdefault((file_path, False), []).append(
                    ContextManager._get_line_range(chunk, False)
                )  # new version only

            elif chunk.is_file_deletion:
                # File deletion: only need old version
                file_path = chunk.old_file_path
                self._required_contexts.setdefault((file_path, True), []).append(
                    ContextManager._get_line_range(chunk, True)
                )  # old version only

            elif chunk.is_file_rename:
                # File rename: need old version with old name, new version with new name
                old_path = chunk.old_file_path
                new_path = chunk.new_file_path
                self._required_contexts.setdefault((old_path, True), []).append(
                    ContextManager._get_line_range(chunk, True)
                )  # old version with old name
                self._required_contexts.setdefault((new_path, False), []).append(
                    ContextManager._get_line_range(chunk, False)
                )  # new version with new name

    @staticmethod
    def _get_line_range(chunk: DiffChunk, is_old_range: bool) -> tuple[int, int]:
        # Returns 0-indexed line range from chunk
        if is_old_range:
            return (chunk.old_start - 1, chunk.old_start + chunk.old_len() - 2)
        else:
            return (chunk.new_start - 1, chunk.new_start + chunk.new_len() - 2)

    def _generate_parsed_files(self) -> None:
        for (file_path, is_old_version), line_ranges in self._required_contexts.items():
            # Decode bytes file path for file_reader
            path_str = file_path.decode('utf-8', errors='replace') if isinstance(file_path, bytes) else file_path
            content = self.file_reader.read(path_str, old_content=is_old_version)
            if content is None:
                continue

            # Parse the file (file_parser expects string path)
            parsed_file = self.file_parser.parse_file(
                path_str, content, self.simplify_overlapping_ranges(line_ranges)
            )
            if parsed_file is None:
                continue

            self._parsed_files[(file_path, is_old_version)] = parsed_file

    def simplify_overlapping_ranges(
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

        # TODO, this functionality is not in use right now
        # It is designed for languages where things are shared without explicit imports
        # If there are only explicit imports we only need to check tokens per file
        # However for languages like go, there are certain conditions where tokens can be shared
        # We must add this info to the language config, and alternate between the two approaches

        languages: dict[str, list[ParsedFile]] = {}

        for _, parsed_file in self._parsed_files.items():
            languages.setdefault(parsed_file.detected_language, []).append(parsed_file)

        for language, parsed_files in languages.items():
            defined_symbols: set[str] = set()
            try:
                for parsed_file in parsed_files:
                    defined_symbols.update(
                        self.symbol_extractor.extract_defined_symbols(
                            parsed_file.detected_language,
                            parsed_file.root_node,
                            parsed_file.line_ranges,
                        )
                    )

                context = SharedContext(defined_symbols)
                self._shared_context_cache[language] = context
            # TODO change all these to custom subclassed exceptions
            except Exception as e:
                logger.warning(f"Failed to build shared context for {language}: {e}")

    def _build_all_contexts(self) -> None:
        """
        Build analysis contexts for all required file versions.
        """
        for (file_path, is_old_version), parsed_file in self._parsed_files.items():
            try:
                context = self._build_context(file_path, is_old_version, parsed_file)
                if context:
                    self._context_cache[(file_path, is_old_version)] = context
            except Exception as e:
                # Log error but continue with other files
                logger.warning(
                    f"Failed to build context for {file_path} (old={is_old_version}): {e}"
                )

    def _build_context(
        self, file_path: str, is_old_version: bool, parsed_file: ParsedFile
    ) -> Optional[AnalysisContext]:
        """
        Build analysis context for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version
            line_ranges: list of tuples (start_line, end_line), to filter the tree sitter queries for a file

        Returns:
            AnalysisContext if successful, None if file cannot be processed
        """
        # for now, reject errored files
        if parsed_file.root_node.has_error:
            version = "old version" if is_old_version else "new version"
            logger.warning(
                f"Syntax errors detected in {version} of {file_path}; skipping context build"
            )
            return None

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
                parsed_file.detected_language
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

        context = AnalysisContext(
            file_path=file_path,
            parsed_file=parsed_file,
            scope_map=scope_map,
            symbol_map=symbol_map,
            comment_map=comment_map,
            symbols=symbols,
            is_old_version=is_old_version,
        )

        logger.debug(f"{context=}")

        return context

    def get_context(
        self, file_path: str, is_old_version: bool
    ) -> Optional[AnalysisContext]:
        """
        Get analysis context for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version

        Returns:
            AnalysisContext if available, None if not found or not required
        """
        return self._context_cache.get((file_path, is_old_version))

    def get_available_contexts(self) -> List[AnalysisContext]:
        """
        Get all available analysis contexts.

        Returns:
            List of all successfully built AnalysisContext objects
        """
        return list(self._context_cache.values())

    def has_context(self, file_path: str, is_old_version: bool) -> bool:
        """
        Check if context is available for a specific file version.

        Args:
            file_path: Path to the file
            is_old_version: True for old version, False for new version

        Returns:
            True if context is available, False otherwise
        """
        return (file_path, is_old_version) in self._context_cache

    def get_required_contexts(self) -> Set[tuple[str, bool]]:
        """
        Get the set of required contexts based on diff chunks.

        Returns:
            Set of (file_path, is_old_version) tuples that were determined to be needed
        """
        return self._required_contexts.copy()

    def get_file_paths(self) -> Set[str]:
        """
        Get all unique file paths that have contexts.

        Returns:
            Set of file paths that have at least one context (old or new)
        """
        return {file_path for file_path, _ in self._context_cache.keys()}
