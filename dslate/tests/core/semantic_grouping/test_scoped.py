# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


from dslate.core.file_reader.file_parser import FileParser
from dslate.core.semantic_grouper.query_manager import QueryManager
from dslate.core.semantic_grouper.scope_mapper import ScopeMapper
from dslate.core.semantic_grouper.symbol_mapper import SymbolMapper

# --- MAIN EXECUTION ---

FILE_PATH = "fileA.py"

with open(FILE_PATH, encoding="utf8") as f:
    content = f.read()

# Parse the file using FileParser
parsed_file = FileParser.parse_file(FILE_PATH, content)

if not parsed_file:
    print(f"Failed to parse {FILE_PATH}")
    exit(1)

print(f"Detected language: {parsed_file.detected_language}")
root = parsed_file.root_node

# Initialize QueryManager
query_manager = QueryManager("language_config.json")

# Initialize ScopeMapper
scope_mapper = ScopeMapper(query_manager)

# Initialize SymbolMapper
symbol_mapper = SymbolMapper(query_manager)

# --- PASS 1: Build Scope Map ---
scope_map = scope_mapper.build_scope_map(parsed_file.detected_language, root, FILE_PATH)

print("--- Generated Scope Map ---")
for line, scope in scope_map.scope_lines.items():
    print(f"Line {line}: {scope}")
print("-" * 25)

# --- PASS 2: Build Symbol Map ---
sym_map = symbol_mapper.build_symbol_map(parsed_file.detected_language, root, scope_map)

print("\n--- Found Symbols (with Scope Tagging) ---")
for line, symbols in sorted(sym_map.line_symbols.items()):
    for symbol in symbols:
        # Extract parts for display
        parts = symbol.split(":", 2)
        if len(parts) == 3:
            scope_name, match_class, text = parts
            print(
                f"  Symbol: {repr(text):<10} | Line: {line:<5} | Qualified Name: {symbol}"
            )

print("\n--- Final Scoped Symbol Map ---")
for line, symbols in sorted(sym_map.line_symbols.items()):
    print(f"Line {line}: {symbols}")
print("-" * 25)


def get_signature(start_line: int, end_line: int):
    signature = set()
    for line in range(start_line, end_line + 1):
        signature.update(sym_map.line_symbols.get(line, []))

    return signature


hunk1 = (6, 8)
hunk2 = (9, 11)

hunk1_sig = get_signature(hunk1[0], hunk1[1])
hunk2_sig = get_signature(hunk2[0], hunk2[1])

print(f"{hunk1_sig=}")
print(f"{hunk2_sig=}")

print(hunk1_sig.isdisjoint(hunk2_sig))
