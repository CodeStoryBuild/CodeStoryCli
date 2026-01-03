# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# codestory is available under a dual-license:
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


from codestory.core.file_reader.file_parser import FileParser


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
