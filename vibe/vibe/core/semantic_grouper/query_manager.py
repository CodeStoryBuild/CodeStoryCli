from dataclasses import dataclass
from importlib.resources.abc import Traversable
import json
from typing import Dict, List, Tuple

from tree_sitter import Query, QueryCursor, Node
from tree_sitter_language_pack import get_language


@dataclass(frozen=True)
class SharedTokenQueries:
    queries: List[str]
    token_filters: set[str]


@dataclass(frozen=True)
class ScopeQueries:
    queries: List[str]


@dataclass(frozen=True)
class LanguageConfig:
    language_name: str
    shared_token_queries: Dict[str, SharedTokenQueries]
    scope_queries: ScopeQueries

    @classmethod
    def from_json_dict(cls, name: str, json_dict: dict) -> "LanguageConfig":
        shared_token_queries: Dict[str, SharedTokenQueries] = {}
        for token_class, items in json_dict.get("shared_token_queries", {}).items():
            if isinstance(items, list):
                query = SharedTokenQueries(items, set())
            elif isinstance(items, dict):
                queries = items.get("queries", [])
                filters = set(items.get("filters", []))
                query = SharedTokenQueries(queries, filters)
            else:
                raise ValueError(
                    f"Invalid shared_token_queries entry for {token_class}"
                )
            shared_token_queries[token_class] = query

        scope_queries = ScopeQueries(json_dict.get("scope_queries", []))
        return cls(name, shared_token_queries, scope_queries)

    def get_scope_source(self) -> str:
        return "\n".join(f"({q} @scope_query)" for q in self.scope_queries.queries)

    def get_shared_token_source(self) -> str:
        """
        Build query source for all shared tokens, injecting #not-eq? predicates
        for each configured filter. Each predicate line uses the capture name so
        the predicate has access to the node text.
        """
        lines: List[str] = []
        for capture_class, capture_queries in self.shared_token_queries.items():
            for query in capture_queries.queries:
                if capture_queries.token_filters:
                    lines.append(f"(")

                lines.append(f"({query} @{capture_class})")

                for flt in capture_queries.token_filters:
                    # Add a predicate that the QueryCursor will call. Predicate names
                    # do not include the leading '#', binding is done by name.
                    # We escape double-quotes in the filter string to keep the query valid.
                    escaped = flt.replace('"', r"\"")
                    lines.append(f'(#not-eq? @{capture_class} "{escaped}")')

                if capture_queries.token_filters:
                    lines.append(")")
        return "\n".join(lines)


class QueryManager:
    """
    Manages language configs and runs queries using the newer QueryCursor(query)
    constructor and cursor.captures(node, predicates=...).
    """

    def __init__(self, language_config_path: Traversable):
        self.language_configs: Dict[str, LanguageConfig] = self._init_configs(
            language_config_path
        )
        # cache per-language/per-query-type: key -> (Query, QueryCursor)
        self._cursor_cache: Dict[str, Tuple[Query, QueryCursor]] = {}

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

    @staticmethod
    def not_eq_predicate(name: str, args, pattern_index: int, captures: dict) -> bool:
        # Only handle our predicate of interest
        if name != "not-eq?":
            return True

        # Expect args to be: (capture_name, "capture"), (pattern_string, "string")
        try:
            cap_name, cap_type = args[0]
            filter_text, filter_type = args[1]
        except Exception:
            # malformed predicate usage -> do not reject at the predicate layer
            return True

        if cap_type != "capture" or filter_type != "string":
            return True

        for node in captures.get(cap_name, []):
            text = node.text.decode("utf8")
            if text == filter_text:
                # found a node whose text equals the filter -> reject the whole pattern
                return False
        return True

    def run_query(self, language_name: str, tree_root: Node, is_scope_query: bool):
        """
        Run either the scope or shared token query for the language on `tree_root`.
        Uses QueryCursor(query) + cursor.captures(node, predicates=...).
        Returns a list of (Node, capture_name) tuples.
        """
        key = f"{language_name}:{'scope' if is_scope_query else 'token'}"

        language = get_language(language_name)
        if language is None:
            raise ValueError(f"Invalid language '{language_name}'")

        lang_config = self.language_configs.get(language_name)
        if lang_config is None:
            raise ValueError(f"Missing config for language '{language_name}'")

        # Build and cache Query + QueryCursor if not present
        if key not in self._cursor_cache:
            if is_scope_query:
                query_src = lang_config.get_scope_source()
            else:
                query_src = lang_config.get_shared_token_source()

            # If there are no queries (empty string), create an empty Query to avoid errors
            if not query_src.strip():
                # Empty query -> no matches
                return []

            query = Query(language, query_src)
            cursor = QueryCursor(query)
            self._cursor_cache[key] = (query, cursor)
        else:
            query, cursor = self._cursor_cache[key]

        return cursor.captures(tree_root, QueryManager.not_eq_predicate)
