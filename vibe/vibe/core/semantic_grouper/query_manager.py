from dataclasses import dataclass
from importlib.abc import Traversable
import json
from typing import Dict, List, Tuple, Literal
from loguru import logger

from tree_sitter import Query, QueryCursor, Node
from tree_sitter_language_pack import get_language


@dataclass(frozen=True)
class SharedTokenQueries:
    general_queries: list[str]
    definition_queries: list[str]


@dataclass(frozen=True)
class LanguageConfig:
    language_name: str
    shared_token_queries: dict[str, SharedTokenQueries]
    scope_queries: list[str]
    comment_queries: list[str]
    share_tokens_between_files: bool

    @classmethod
    def from_json_dict(cls, name: str, json_dict: dict) -> "LanguageConfig":
        shared_token_queries: Dict[str, SharedTokenQueries] = {}
        for token_class, items in json_dict.get("shared_token_queries", {}).items():
            if isinstance(items, dict):
                general_queries = items.get("general_queries", [])
                definition_queries = items.get("definition_queries", [])
                query = SharedTokenQueries(general_queries, definition_queries)
            else:
                raise ValueError(
                    f"Invalid shared_token_queries entry for {token_class}"
                )
            shared_token_queries[token_class] = query

        scope_queries = json_dict.get("scope_queries", [])
        comment_queries = json_dict.get("comment_queries", [])
        share_tokens_between_files = json_dict.get("share_tokens_between_files", False)
        return cls(
            name,
            shared_token_queries,
            scope_queries,
            comment_queries,
            share_tokens_between_files,
        )

    def __get_source(self, queries: list[str], capture_class) -> str:
        lines = []
        for query in queries:
            if not "@placeholder" in query:
                logger.error(f"{query} in the language {self.language_name} {capture_class=} config, is missing a capture class @placeholder!")
            else:
                # TODO consider if multiple @placeholders should be supported or warned against
                # .replace will replace all instances of it
                query_filled = query.replace("@placeholder", f"@{capture_class}")
                lines.append(query_filled)

        return lines

    def __get_shared_token_source(self, is_general_query: bool) -> str:
        """
        Build query source for all shared tokens, injecting #not-eq? predicates
        for each configured filter. Each predicate line uses the capture name so
        the predicate has access to the node text.
        """
        lines: List[str] = []
        for capture_class, capture_queries in self.shared_token_queries.items():
            queries = (
                capture_queries.general_queries
                if is_general_query
                else capture_queries.definition_queries
            )
            lines.extend(self.__get_source(queries, capture_class))

        return "\n".join(lines)

    def get_source(
        self,
        query_type: Literal["scope", "comment", "token_general", "token_definition"],
    ):
        if query_type == "scope":
            return "\n".join(
                self.__get_source(self.scope_queries, "STRUCTURALSCOPEQUERY")
            )
        if query_type == "comment":
            return "\n".join(
                self.__get_source(self.comment_queries, "STRUCTURALCOMMENTQUERY")
            )
        if query_type == "token_definition":
            return self.__get_shared_token_source(is_general_query=False)
        if query_type == "token_general":
            return self.__get_shared_token_source(is_general_query=True)


class QueryManager:
    """
    Manages language configs and runs queries using the newer QueryCursor(query)
    constructor and cursor.captures(node, predicates=...).
    """

    def __init__(self, language_config_path: Traversable):
        self._language_configs: Dict[str, LanguageConfig] = self._init_configs(
            language_config_path
        )
        # cache per-language/per-query-type: key -> (Query, QueryCursor)
        self._cursor_cache: Dict[str, Tuple[Query, QueryCursor]] = {}

        # Log language configuration summary
        lang_summaries = {}
        for name, cfg in self._language_configs.items():
            shared_classes = len(cfg.shared_token_queries)
            scope_count = len(cfg.scope_queries)
            comment_count = len(cfg.comment_queries)
            lang_summaries[name] = {
                "shared_classes": shared_classes,
                "scope_queries": scope_count,
                "comment_queries": comment_count,
                "share_tokens_between_files": cfg.share_tokens_between_files,
            }
        logger.info(
            "Language config loaded: languages={n} details={details}",
            n=len(self._language_configs),
            details=lang_summaries,
        )

    def _init_configs(
        self, language_config_path: Traversable
    ) -> Dict[str, LanguageConfig]:
        try:
            with language_config_path.open("r", encoding="utf-8") as fh:
                config = json.load(fh)

            configs: Dict[str, LanguageConfig] = {}
            # iterate .items() to get (name, config)
            for language_name, language_config in config.items():
                configs[language_name] = LanguageConfig.from_json_dict(
                    language_name, language_config
                )
            return configs

        except OSError as e:
            raise ValueError(f"Failed to read from {language_config_path}") from e
        except Exception as e:
            raise RuntimeError("Failed to parse language configs!") from e

    def run_query(
        self,
        language_name: str,
        tree_root: Node,
        query_type: Literal["scope", "comment", "token_general", "token_definition"],
        line_ranges: list[tuple[int, int]] | None = None,
    ):
        """
        Run either the scope or shared token query for the language on `tree_root`.
        If `line_ranges` is provided, only matches within those 0-indexed (start, end) line ranges are returned.
        Returns a dict: {capture_name: [Node, ...]}
        """
        key = f"{language_name}:{query_type}"

        language = get_language(language_name)
        if language is None:
            raise ValueError(f"Invalid language '{language_name}'")

        lang_config = self._language_configs.get(language_name)
        if lang_config is None:
            raise ValueError(f"Missing config for language '{language_name}'")

        # Build and cache Query + QueryCursor if not present
        if key not in self._cursor_cache:
            query_src = lang_config.get_source(query_type)

            if not query_src.strip():
                # Empty query -> no matches
                logger.warning(f"Empty query for {language_name} {query_type=}!")
                return {}

            query = Query(language, query_src)
            cursor = QueryCursor(query)
            self._cursor_cache[key] = (query, cursor)
        else:
            query, cursor = self._cursor_cache[key]

        # If no line_ranges provided, just run over the whole tree
        if line_ranges is None:
            # make sure the capture range is the whole file
            cursor.set_point_range(tree_root.start_point, tree_root.end_point)
            return cursor.captures(tree_root)

        # Otherwise, loop over line ranges
        # Prepare result dictionary
        results: dict[str, list[Node]] = {}
        for start_line, end_line in line_ranges:
            if end_line < start_line:
                # cases like empty hunks will head to invalid range
                continue
            start_point = (start_line, 0)
            end_point = (end_line + 1, 0)  # end is exclusive

            # Reset cursor and restrict to this range
            cursor.set_point_range(start_point, end_point)

            for capture_name, nodes in cursor.captures(tree_root).items():
                results.setdefault(capture_name, []).extend(nodes)

        return results

    def get_config(self, language_name: str) -> LanguageConfig:
        lang_config = self._language_configs.get(language_name)
        if lang_config is None:
            raise ValueError(f"Missing config for language '{language_name}'")
        return lang_config

    @staticmethod
    def create_qualified_symbol(capture_class: str, token_name: str) -> str:
        return f"{capture_class}:{token_name}"
