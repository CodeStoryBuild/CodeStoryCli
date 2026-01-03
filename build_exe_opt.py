#!/usr/bin/env python
"""
Build script to create executable for dslate CLI tool using Nuitka.
Usage:
    python build_exe_opt.py
"""

import argparse
import platform
import subprocess
import sys
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build dslate executable with Nuitka")
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
    exe_name = "dslate.exe" if is_windows else "dslate"
    
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
    entry_point = Path("dslate/dslate/cli.py")
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
        
        # --- CORE INCLUDES ---
        "--include-package=dslate",
        "--include-package-data=dslate",
        
        # --- LANGCHAIN (Dynamic Imports) ---
        # LangChain relies heavily on dynamic loading. We must include these explicitely.
        "--include-package=langchain",
        "--include-package=langchain_core",
        # Providers (Add others if you add more to pyproject.toml)
        "--include-package=langchain_openai",
        "--include-package=langchain_anthropic",
        "--include-package=langchain_google_genai",
        "--include-package=langchain_ollama",

        # --- SYNTAX HIGHLIGHTING ---
        # Pygments loads lexers dynamically by string name
        "--include-package=pygments",

        # --- CLI UTILS ---
        "--include-package=inquirer",
        "--include-package=readchar",

        # --- PARSING ---
        "--include-package=tree_sitter",
        "--include-package-data=tree_sitter_language_pack",

        # --- OUTPUT CONFIG ---
        f"--output-dir={dist_path}",
        f"--output-filename={exe_name}",
        "--remove-output", # Removes the build/ temporary directory, keeps dist/
        "--no-deployment-flag=self-execution",
    ]

    # Add platform specific options
    if is_windows:
        # Crucial for CLI tools on Windows. 
        # Without this, it might open a new window or hide stdout/stderr.
        cmd.append("--windows-console-mode=force")
        
    elif system == "linux":
        pass
    elif system == "darwin":
        pass

    # Add the entry point
    cmd.append(str(entry_point))

    print(f"Building {exe_name} for {system} using Nuitka...")
    print("Command:", " ".join(cmd))

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        sys.exit(e.returncode)

    # Validation check
    target_output = dist_path / exe_name

    if target_output.exists():
         print(f"Build successful! Artifact located at: {target_output}")
    else:
        print(f"Build finished but expected artifact {target_output} not found.")
        print(f"Contents of {dist_path}:")
        if dist_path.exists():
            for item in dist_path.iterdir():
                print(f" - {item.name}")
        sys.exit(1)


if __name__ == "__main__":
    main()