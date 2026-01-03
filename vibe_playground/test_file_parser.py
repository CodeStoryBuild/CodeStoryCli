from vibe.semantic_grouping.file_reader.file_parser import FileParser

# Test with the existing fileA.py
FILE_PATH = "fileA.py"

with open(FILE_PATH, "r", encoding="utf8") as f:
    content = f.read()

# Parse the file using FileParser
parsed_file = FileParser.parse_file(FILE_PATH, content)

if parsed_file:
    print(f"Successfully parsed {FILE_PATH}")
    print(f"Detected language: {parsed_file.detected_language}")
    print(f"Root node type: {parsed_file.root_node.type}")
    print(f"Root node has {len(parsed_file.root_node.children)} children")
    print(f"First few lines of AST:")
    for i, child in enumerate(parsed_file.root_node.children[:5]):
        print(f"  Child {i}: {child.type} at line {child.start_point[0]}")
else:
    print(f"Failed to parse {FILE_PATH}")