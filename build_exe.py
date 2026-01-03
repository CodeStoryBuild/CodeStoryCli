#!/usr/bin/env python
"""
Build script to create executable for codestory CLI tool.
Usage:
    python build_exe.py --mode folder
    python build_exe.py --mode file
"""

import argparse
import importlib.util
import platform
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build codestory executable")
    parser.add_argument(
        "--mode",
        choices=["file", "folder"],
        required=True,
        help="Build single file or directory",
    )
    args = parser.parse_args()

    # Install PyInstaller if not already installed
    if not importlib.util.find_spec("PyInstaller"):
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])

    # Get the system platform
    system = platform.system().lower()

    # Define output directories
    # dist/file  -> contains the single executable
    # dist/folder -> contains the folder structure
    dist_path = Path("dist") / args.mode

    # Set up PyInstaller command
    cmd = [
        "pyinstaller",
        "--name",
        "codestory",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(dist_path),  # Explicitly set output path
        "--collect-all",
        "readchar",
        "--collect-all",
        "codestory",
        "--additional-hooks-dir=custom_hooks",
        "codestory/codestory/cli.py",
    ]

    if args.mode == "folder":
        cmd.insert(1, "--onedir")
        print(f"Building Directory mode for {system}...")
    else:
        cmd.insert(1, "--onefile")
        print(f"Building OneFile mode for {system}...")

    subprocess.check_call(cmd)

    # Validation check
    if args.mode == "folder":
        # Folder mode: dist/folder/codestory/[exe]
        check_path = (
            dist_path / "codestory" / ("codestory.exe" if system == "windows" else "codestory")
        )
    else:
        # File mode: dist/file/[exe]
        check_path = dist_path / ("codestory.exe" if system == "windows" else "codestory")

    if check_path.exists():
        print(f"Build successful! Artifact located at: {check_path}")
    else:
        print(f"Build failed: Executable not found at {check_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
