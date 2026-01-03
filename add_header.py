#!/usr/bin/env python3

import os
import re
import argparse

# --- Configuration ---

LICENSE_HEADER = '''
"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build
 */
-----------------------------------------------------------------------------
"""
'''.strip()  # .strip() removes leading/trailing whitespace/newlines from the triple quotes


def add_license_header(root_dir):
    """
    Prepends the dual-license header to all .py files in a directory recursively.
    """
    print(f"Starting license check in directory: {root_dir}")
    
    # 1. Traverse the directory and find all .py files
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                py_files.append(os.path.join(dirpath, filename))

    if not py_files:
        print(f"No .py files found in {root_dir}.")
        return

    # 2. Process each file
    for filepath in py_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except UnicodeDecodeError:
            print(f"Skipping {filepath}: Could not read file with UTF-8 encoding.")
            continue
        except IOError as e:
            print(f"Skipping {filepath}: Error reading file: {e}")
            continue

        # Check if the header is already present
        header_present = False
        if re.search(r"Copyright\s*\(C\)", original_content) or re.search(r"GNU General Public License", original_content):
            header_present = True

        if header_present:
            print(f"License header already present in {filepath}")
            continue

        # 3. Handle Shebang and Prepend Header
        new_content = ""
        shebang_match = re.match(r"^\s*#!\s*.*", original_content)

        if shebang_match:
            # Shebang found: Insert header after the shebang line
            shebang_line = shebang_match.group(0).strip()
            # Everything after the shebang (trimming leading whitespace/newlines)
            rest_of_content = original_content[len(shebang_match.group(0)):].lstrip()
            
            # shebang \n header \n content (ensures a newline between header and content)
            new_content = f"{shebang_line}\n{LICENSE_HEADER}\n\n{rest_of_content}"
        else:
            # No shebang: Prepend header to the file content (trimming leading whitespace/newlines)
            rest_of_content = original_content.lstrip()
            
            # header \n content (ensures a newline between header and content)
            new_content = f"{LICENSE_HEADER}\n\n{rest_of_content}"

        # 4. Write back to file
        try:
            # Python's default behavior when writing to file with 'w' mode is to use 
            # the system's default line endings (e.g., \n on Linux, \r\n on Windows), 
            # and it will not write a BOM for 'utf-8'.
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Prepended license header to {filepath}")
        except IOError as e:
            print(f"Error writing to {filepath}: {e}")
            
    print(f"\nLicense headers added to all .py files in {root_dir}.")


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(
        description="Prepends a dual-license header to all .py files recursively."
    )
    parser.add_argument(
        "root_dir",
        nargs='?',
        default="./codestory",
        help="Path to the directory to start the search (defaults to ./codestory)"
    )
    
    args = parser.parse_args()
    
    add_license_header(args.root_dir)