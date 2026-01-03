#!/usr/bin/env python
"""
Build script to create executable for vibe CLI tool.
"""
import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


def main():
    # Create build directory if it doesn't exist
    build_dir = Path("build")
    dist_dir = Path("dist")

    for directory in [build_dir, dist_dir]:
        if not directory.exists():
            directory.mkdir()

    # Install PyInstaller if not already installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])

    # Get the system platform
    system = platform.system().lower()

    # Define output executable name based on platform
    if system == "windows":
        exe_name = "vibe.exe"
        separator = ";"
    else:
        exe_name = "vibe"
        separator = ":"

    # Set up PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",  # Create a single executable file
        "--name",
        "vibe",
        "--clean",  # Clean PyInstaller cache and remove temporary files
        "--copy-metadata",
        "readchar",  # Include package metadata for readchar
        "--add-data",
        f"vibe/vibe{separator}vibe/vibe",  # Include package data
        "vibe/vibe/cli.py",  # Main script to execute
    ]

    print(f"Building executable for {system}...")
    subprocess.check_call(cmd)

    # Move executable to dist directory and clean up
    output_path = dist_dir / exe_name

    print(f"Executable created at: {output_path}")
    print("Build completed successfully!")


if __name__ == "__main__":
    main()
