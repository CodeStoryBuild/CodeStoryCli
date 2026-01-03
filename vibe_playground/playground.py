# semantic_grouping.py

import json
from dataclasses import dataclass, field
from typing import Protocol, Optional
from tree_sitter import Language, Parser, Node
from tree_sitter_language_pack import get_parser
from vibe.core.data.chunk import Chunk

# --- 0. Protocol Definition (from your project) ---


class Chunk(Protocol):
    """
    Protocol for a diff chunk.
    Assumes your git_commands parser provides objects that satisfy this.
    """

    @property
    def new_start(self) -> int: ...

    @property
    def new_end(self) -> int: ...

    # We will dynamically add these attributes during analysis
    structural_scope_id: str
    used_definition_scope_ids: set[str]


# --- 1. Core Data Structures ---


class UnionFind:
    """A simple Union-Find data structure for grouping."""

    # (Implementation is the same as before)
    def __init__(self, elements):
        self.parent = {el: el for el in elements}

    def find(self, i):
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_j] = root_i


@dataclass
class Scope:
    """Represents a structural scope like a function or class."""

    id: str
    type: str
    name: str | None
    start_line: int
    end_line: int
    parent: Optional["Scope"] = None
    children: list["Scope"] = field(default_factory=list)


@dataclass
class Symbol:
    """Represents a defined symbol."""

    name: str
    type: str
    definition_scope_id: str


@dataclass
class AnalysedHunk:
    """An internal representation of a single, continuous hunk range."""

    parent_chunk: Chunk  # Reference to the original Chunk
    new_start: int
    new_end: int

    # Fields to be populated by semantic analysis
    structural_scope_id: str = ""
    used_definition_scope_ids: set[str] = field(default_factory=set)


@dataclass
class AnalysisContext:
    """Holds all necessary analysis artifacts for a single file."""

    # 'Before' state artifacts
    before_ast: Node | None = None
    before_scope_tree: Scope | None = None
    before_symbol_table: dict[str, Symbol] = field(default_factory=dict)
    before_all_scopes: dict[str, Scope] = field(default_factory=dict)

    # 'After' state artifacts
    after_ast: Node | None = None
    after_scope_tree: Scope | None = None
    after_symbol_table: dict[str, Symbol] = field(default_factory=dict)
    after_all_scopes: dict[str, Scope] = field(default_factory=dict)


# In a new file, e.g., vibe/core/analysis/interfaces.py
from typing import Protocol


# --- 2. The Semantic Analysis Engine ---


class SemanticAnalyser:
    def __init__(self, language_config: dict, file_reader: FileReader):
        self.language_config = language_config
        self.file_reader = file_reader
        self.parsers = {}
        self.context_cache: dict[str, AnalysisContext] = {}

    def get_parser(self, language: str) -> Parser | None:
        """Lazily loads and caches parsers."""
        if language not in self.parsers:
            try:
                self.parsers[language] = get_parser(language)
            except Exception:
                # Language not supported by tree-sitter-language-pack
                return None
        return self.parsers[language]

    def _get_or_create_context(self, file_path: str, language: str) -> AnalysisContext:
        """
        Lazily loads and analyzes file content to build an AnalysisContext.
        This is the core of the multi-file and dual-state logic.
        """
        if file_path in self.context_cache:
            return self.context_cache[file_path]

        context = AnalysisContext()
        parser = self.get_parser(language)

        if parser and language in self.language_config:
            lang_conf = self.language_config[language]

            # Build 'before' context
            old_content = self.file_reader.read(file_path, old_content=True)
            if old_content:
                ast = parser.parse(bytes(old_content, "utf8")).root_node
                context.before_ast = ast
                (
                    context.before_scope_tree,
                    context.before_symbol_table,
                    context.before_all_scopes,
                ) = self._build_context(ast, lang_conf)

            # Build 'after' context
            new_content = self.file_reader.read(file_path, old_content=False)
            if new_content:
                ast = parser.parse(bytes(new_content, "utf8")).root_node
                context.after_ast = ast
                (
                    context.after_scope_tree,
                    context.after_symbol_table,
                    context.after_all_scopes,
                ) = self._build_context(ast, lang_conf)

        self.context_cache[file_path] = context
        return context

    def group_chunks_for_file(
        self, chunks: list[Chunk], file_content: str, language: str
    ) -> list[list[Chunk]]:
        """
        The main entry point for analyzing and grouping chunks for a single file.
        Handles complex chunks with multiple, non-continuous hunks.
        """
        parser = self.get_parser(language)
        if not parser or language not in self.language_config:
            return [[chunk] for chunk in chunks]

        lang_conf = self.language_config[language]
        ast_root = parser.parse(bytes(file_content, "utf8")).root_node

        # Step 1: Build full-file context (no change here)
        scope_root, symbol_table, all_scopes = self._build_context(ast_root, lang_conf)

        # Step 2: FLATTEN Chunks into individual, analyzable hunks
        analysed_hunks = []
        for chunk in chunks:
            for _, _, new_start, new_len in chunk.hunk_ranges().get(file_path, []):
                if new_len > 0:
                    analysed_hunks.append(
                        AnalysedHunk(
                            parent_chunk=chunk,
                            new_start=new_start,
                            new_end=new_start + new_len - 1,
                        )
                    )

        # Step 3: Annotate each individual hunk
        self._annotate_analysed_hunks(
            analysed_hunks, ast_root, scope_root, symbol_table, lang_conf
        )

        # Step 4: Group the individual hunks semantically
        hunk_groups = self._group_analysed_hunks(
            analysed_hunks, list(all_scopes.keys())
        )

        # Step 5: CONSOLIDATE parent Chunks based on the hunk groups
        final_chunk_groups = []
        processed_chunks = set()
        for group_of_hunks in hunk_groups:
            # Find all unique parent chunks represented in this hunk group
            parent_chunks_in_group = {h.parent_chunk for h in group_of_hunks}

            # Avoid creating duplicate groups
            unprocessed_parents = parent_chunks_in_group - processed_chunks
            if unprocessed_parents:
                final_chunk_groups.append(list(unprocessed_parents))
                processed_chunks.update(unprocessed_parents)

        return final_chunk_groups

    def _build_context(self, root_node: Node, config: dict):
        """Builds the Scope Tree and Symbol Table."""
        scope_tree_root = Scope(
            id="module",
            type="module",
            name=None,
            start_line=1,
            end_line=root_node.end_point[0] + 1,
        )
        symbol_table = {}
        all_scopes = {"module": scope_tree_root}

        def traverse(node, current_scope):
            node_type = node.type
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            new_scope = None

            if node_type in config.get("scopes", []):
                scope_id = f"{node_type}@{start_line}"
                scope_name = None

                if node_type in config.get("definitions", {}):
                    id_node_name = config["definitions"][node_type]
                    id_node = node.child_by_field_name(id_node_name)
                    if id_node:
                        scope_name = id_node.text.decode("utf8")

                new_scope = Scope(
                    id=scope_id,
                    type=node_type,
                    name=scope_name,
                    start_line=start_line,
                    end_line=end_line,
                    parent=current_scope,
                )
                current_scope.children.append(new_scope)
                all_scopes[scope_id] = new_scope

                if scope_name:
                    symbol = Symbol(
                        name=scope_name, type=node_type, definition_scope_id=scope_id
                    )
                    symbol_table[scope_name] = symbol

            for child in node.children:
                traverse(child, new_scope or current_scope)

        traverse(root_node, scope_tree_root)
        return scope_tree_root, symbol_table, all_scopes

    def _annotate_chunks(
        self,
        chunks: list[Chunk],
        root_node: Node,
        scope_root: Scope,
        symbol_table: dict,
        config: dict,
    ):
        """Adds semantic attributes to each Chunk object in-place."""
        for chunk in chunks:
            # Dynamically add the attributes required by the protocol
            chunk.structural_scope_id = ""
            chunk.used_definition_scope_ids = set()

            # 1. Find Structural Scope (LCA)
            lca_scope = self._find_lca_scope(chunk, scope_root)
            chunk.structural_scope_id = lca_scope.id

            # 2. Find Symbol Usages within the chunk's new line range
            self._analyze_chunk_for_usages(chunk, root_node, symbol_table, config)

    def _find_lca_scope(self, chunk: Chunk, scope_root: Scope) -> Scope:
        """Finds the Lowest Common Ancestor scope containing the chunk."""

        def find_innermost(scope: Scope):
            for child in scope.children:
                if (
                    child.start_line <= chunk.new_start
                    and child.end_line >= chunk.new_end
                ):
                    return find_innermost(child)
            return scope

        return find_innermost(scope_root)

    def _analyze_chunk_for_usages(
        self, chunk: Chunk, node: Node, symbol_table: dict, config: dict
    ):
        """Recursively traverses the AST, analyzing nodes that overlap with the chunk."""
        node_start = node.start_point[0] + 1
        node_end = node.end_point[0] + 1

        # Fast exit if the node is completely outside the chunk's range
        if node_end < chunk.new_start or node_start > chunk.new_end:
            return

        # Check for overlap
        if max(chunk.new_start, node_start) <= min(chunk.new_end, node_end):
            if node.type in config.get("usages", {}):
                id_node_name = config["usages"][node.type]
                id_node = node.child_by_field_name(id_node_name)
                if id_node:
                    symbol_name = id_node.text.decode("utf8")
                    if symbol_name in symbol_table:
                        definition_id = symbol_table[symbol_name].definition_scope_id
                        chunk.used_definition_scope_ids.add(definition_id)

            for child in node.children:
                self._analyze_chunk_for_usages(child, symbol_table, config)

    def _group_chunks(
        self, chunks: list[Chunk], all_scope_ids: list[str]
    ) -> list[list[Chunk]]:
        """Groups chunks based on their annotations using Union-Find."""
        if not chunks:
            return []

        uf = UnionFind(all_scope_ids)
        for chunk in chunks:
            for used_scope_id in chunk.used_definition_scope_ids:
                uf.union(chunk.structural_scope_id, used_scope_id)

        final_groups = {}
        for chunk in chunks:
            root = uf.find(chunk.structural_scope_id)
            if root not in final_groups:
                final_groups[root] = []
            final_groups[root].append(chunk)

        return list(final_groups.values())


# --- Example Main Execution ---

if __name__ == "__main__":
    # This block now demonstrates how to USE the SemanticAnalyser class
    # In your actual project, you would import and instantiate this class.

    # 1. Load the universal language configuration
    language_config = {
        "python": {
            "definitions": {"function_definition": "name", "class_definition": "name"},
            "scopes": ["function_definition", "class_definition"],
            "usages": {"call": "function"},
        }
        # ... add other languages here
    }

    # 2. Instantiate the analyser
    analyser = SemanticAnalyser(language_config)

    # 3. Get your raw chunks from your git parser
    # Simulating your git_commands for this example
    from vibe.core.commands.git_commands import GitCommands
    from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface

    git_interface = SubprocessGitInterface(repo_path=".")
    git_commands = GitCommands(git_interface)

    # This gives you mechanically robust chunks for a specific file diff
    # NOTE: Your real code will loop through diffs for each file.
    file_diff = git_commands.get_file_diff_with_renames(
        fileA="fileA.py", fileB="fileB.py"
    )
    raw_chunks = git_commands.parse_and_merge_hunks([file_diff])

    # 4. Get the final file content
    with open("fileB.py", "r", encoding="utf8") as f:
        file_content = f.read()

    # 5. Run the semantic grouping process for this file
    print(f"--- Running semantic analysis for python file ---")
    semantic_groups = analyser.group_chunks_for_file(raw_chunks, file_content, "python")

    # 6. Display the results
    print(f"\nFound {len(semantic_groups)} semantic groups.")
    for i, group in enumerate(semantic_groups):
        print(f"\n--- Group {i+1} ---")
        # In your real code, you would use the Chunk's own methods
        for chunk in group:
            # Example of using the protocol's expected properties
            print(f"  - Chunk at new lines {chunk.new_start}-{chunk.new_end}")
