#!/usr/bin/env python
"""
Build script to create executable for codestory CLI tool using Nuitka.
Usage:
    python build_exe_opt.py
"""

import argparse
import platform
import subprocess
import sys
import shutil
import importlib.util
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build codestory executable with Nuitka")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean dist directory before building",
    )
    args = parser.parse_args()

    # Get the system platform
    system = platform.system().lower()
    is_windows = system == "windows"
    
    # Define output directory and filenames
    dist_path = Path("dist")
    exe_name = "cst.exe" if is_windows else "cst"
    
    if args.clean and dist_path.exists():
        print(f"Cleaning {dist_path}...")
        shutil.rmtree(dist_path)

    # Ensure Nuitka is installed
    try:
        subprocess.check_call([sys.executable, "-m", "nuitka", "--version"], stdout=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka", "zstandard"])

    # Entry point
    entry_point = Path("codestory/codestory/cli.py")
    if not entry_point.exists():
        print(f"Error: Entry point {entry_point} not found.")
        sys.exit(1)

    # Set up Nuitka command
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        "--show-modules",
        # --- FORCE INCLUSION ---
        # 1. Include the root package
        "--include-package=tree_sitter_language_pack",
        
        # 2. CRITICAL: Explicitly force the bindings subpackage
        #    Nuitka usually only includes modules it sees imported in your code.
        #    Since you dynamically load these languages, Nuitka won't "see" them.
        #    This flag forces it to scan and include everything in that folder.
        "--include-module=tree_sitter_language_pack.bindings",

        
        # --- CORE INCLUDES ---
        "--include-package=codestory",
        "--include-package-data=codestory",
        
        # --- LANGCHAIN ---
        "--include-package=langchain",
        # LANGSMITH HAS A PYTEST IMPORT WE DONT WANT (idk why all caps lol)
        "--nofollow-import-to=pytest",
        "--include-package=langchain_core",
        "--include-package=langchain_openai",
        "--include-package=langchain_anthropic",
        "--include-package=langchain_google_genai",
        "--include-package=langchain_ollama",

        # --- UTILS ---
        "--include-package=pygments",
        "--include-package=inquirer",
        "--include-package=readchar",
        
        "--include-package=tree_sitter",
    ]

    # --- FINAL CONFIG ---
    cmd.extend([
        f"--output-dir={dist_path}",
        f"--output-filename={exe_name}",
        "--remove-output",
        "--no-deployment-flag=self-execution",
    ])

    if is_windows:
        cmd.append("--windows-console-mode=force")
        
    cmd.append(str(entry_point))

    print(f"Building {exe_name} for {system} using Nuitka...")
    print("Command:", " ".join(cmd))

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        sys.exit(e.returncode)

    # Validation
    target_output = dist_path / exe_name
    if target_output.exists():
         print(f"Build successful! Artifact located at: {target_output}")
    else:
        print(f"Build finished but expected artifact {target_output} not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()