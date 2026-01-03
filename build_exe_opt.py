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
import importlib.util
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
        
        # --- ESSENTIAL DEPENDENCIES ---
        "--include-package=platformdirs",
        "--include-package=typer",
        "--include-package=rich",
        "--include-package=loguru",
        "--include-package=dotenv",
        "--include-package=git",
        
        # --- LANGCHAIN ---
        "--include-package=langchain",
        "--include-package=langchain_core",
        "--include-package=langchain_openai",
        "--include-package=langchain_anthropic",
        "--include-package=langchain_google_genai",
        "--include-package=langchain_ollama",

        # --- UTILS ---
        "--include-package=pygments",
        "--include-package=inquirer",
        "--include-package=readchar",
        
        # --- TREE SITTER FIX ---
        "--include-package=tree_sitter",
        # Note: --include-package-data IGNORES .pyd/.so files by default!
        # We must manually force the bindings folder to be included as data directory.
    ]

    # --- DYNAMICALLY FIND TREE_SITTER BINDINGS ---
    # This replicates PyInstaller's 'collect_all' for the bindings folder
    try:
        ts_spec = importlib.util.find_spec("tree_sitter_language_pack")
        if ts_spec and ts_spec.submodule_search_locations:
            ts_path = Path(ts_spec.submodule_search_locations[0])
            bindings_path = ts_path / "bindings"
            if bindings_path.exists():
                print(f"Found tree-sitter bindings at: {bindings_path}")
                # Force include the bindings folder. 
                # Syntax: --include-data-dir=/source/path=package/internal/path
                cmd.append(f"--include-data-dir={bindings_path}=tree_sitter_language_pack/bindings")
            else:
                print("Warning: tree_sitter_language_pack found but 'bindings' folder is missing.")
    except ImportError:
        print("Warning: tree_sitter_language_pack not found in environment.")

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