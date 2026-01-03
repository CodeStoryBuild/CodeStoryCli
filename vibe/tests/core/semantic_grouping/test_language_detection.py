from vibe.semantic_grouping.file_reader.file_parser import FileParser


def test_language_detection():


    print("\n--- Testing language detection for various extensions ---")
    # Test language detection with different file extensions
    test_cases = [
        ("test.py", "print('hello')"),
        ("app.js", "console.log('hello');"),
        ("main.cpp", "#include <iostream>\nint main() { return 0; }"),
        ("script.sh", "#!/bin/bash\necho 'hello'"),
        ("style.css", "body { color: red; }"),
        ("data.json", '{"key": "value"}'),
    ]

    for filename, content in test_cases:
        parsed = FileParser.parse_file(filename, content)
        if parsed:
            print(f"  {filename:<12} -> {parsed.detected_language}")
        else:
            print(f"  {filename:<12} -> Not supported/Failed")