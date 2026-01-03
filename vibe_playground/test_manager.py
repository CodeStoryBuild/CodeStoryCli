from dataclasses import dataclass

from query_manager import QueryManager


@dataclass(frozen=True)
class SymbolMap:
    """Maps line number to symbol classes, to the specific symbols
    EX:
    line_classes = {
        10: {"function_class": ["foo"], "variable_class": ["bar"]},
        11: {"variable_class": ["bar"]},
        ...
    }
    """

    line_classes: dict[int, dict[str, set[str]]]


@dataclass(frozen=True)
class ScopeMap:
    """Maps line numbers where scope changes
    EX:
    scope_lines = {
        1: "module",
        5: "class Foo",
        10: "function bar"
    }
    """

    scope_lines: dict[int, str]


from tree_sitter_language_pack import get_parser, get_language
from tree_sitter import Query, QueryCursor
import json


parser = get_parser("python")

with open("fileA.py") as fileA:
    content = fileA.read()

    root = parser.parse(bytes(content, "utf8")).root_node

q_manager = QueryManager("language_config.json")


captures = q_manager.run_query("python", root, is_scope_query=False)

content_bytes = bytes(content, "utf8")

print(f"Found {len(captures)} captures:\n")

print(captures)

symMap: SymbolMap = SymbolMap({})

for match_class, nodes in captures.items():
    for node in nodes:
        text = content_bytes[node.start_byte : node.end_byte].decode(
            "utf8", errors="replace"
        )
        start_line, start_col = node.start_point
        end_line, end_col = node.end_point
        for i in range(start_line, end_line + 1):
            symbols = symMap.line_classes.get(i, set())
            symbols.add(f"{match_class}:{text}")
            symMap.line_classes[i] = symbols

        print(match_class, f"{start_line}-{end_line}", repr(text))

print(symMap.line_classes)
