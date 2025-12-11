#!/usr/bin/env python
"""
Build script to create executable for codestory CLI tool using PyInstaller.
Usage:
    python build_lite.py
"""

import platform
import subprocess
import sys
from pathlib import Path


def main():
    # Get the system platform
    system = platform.system().lower()
    is_windows = system == "windows"

    # Define output directory and filenames
    dist_path = Path("dist")
    exe_name = "cst.exe" if is_windows else "cst"

    # Entry point
    entry_point = Path("src/codestory/cli.py")
    if not entry_point.exists():
        print(f"Error: Entry point {entry_point} not found.")
        sys.exit(1)

    # Ensure PyInstaller is installed
    try:
        subprocess.check_call(
            [sys.executable, "-m", "PyInstaller", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Set up PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onedir",
        "--name",
        exe_name.replace(".exe", ""),
        "--clean",
        # Include dynamically imported modules
        "--hidden-import=tree_sitter_language_pack.bindings",
        "--collect-all=tree_sitter_language_pack",
        "--collect-all=codestory",
        # Include package data
        "--copy-metadata=tree_sitter_language_pack",
        "--copy-metadata=codestory",
        str(entry_point),
    ]

    if is_windows:
        cmd.append("--console")

    print(f"Building {exe_name} for {system} using PyInstaller...")
    print("Command:", " ".join(cmd))

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error code {e.returncode}")
        sys.exit(e.returncode)

    # Validation
    target_output = dist_path / exe_name.replace(".exe", "") / exe_name
    if target_output.exists():
        print(f"Build successful! Artifact located at: {target_output}")
    else:
        print(f"Build finished but expected artifact {target_output} not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
