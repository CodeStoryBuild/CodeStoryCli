from tree_sitter_language_pack import get_parser

parser = get_parser("dart")

code = """
typedef IntList = List<int>;
extension NumberParsing on String {
  int parseInt() {
    return int.parse(this);
  }
}
"""

tree = parser.parse(bytes(code, "utf8"))


def traverse(node, code_lines, indent=0):
    indent_str = "  " * indent
    if node.start_point[0] < len(code_lines):
        line_len = len(code_lines[node.start_point[0]])
        end_col = min(node.end_point[1], line_len) if node.start_point[0] == node.end_point[0] else line_len
        node_text = code_lines[node.start_point[0]][
            node.start_point[1] : end_col
        ]
    else:
        node_text = ""
    print(f"{indent_str}{node.type}: '{node_text}'")
    for child in node.children:
        traverse(child, code_lines, indent + 1)


traverse(tree.root_node, code.splitlines())
