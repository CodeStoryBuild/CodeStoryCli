#!/usr/bin/env python
"""
Build script to create executable for dslate CLI tool.
"""

import importlib.util
import platform
import subprocess
import sys
from pathlib import Path


def main():
    # Create build directory if it doesn't exist
    build_dir = Path("build")
    dist_dir = Path("dist")

    for directory in [build_dir, dist_dir]:
        if not directory.exists():
            directory.mkdir()

    # Install PyInstaller if not already installed
    if not importlib.util.find_spec("PyInstaller"):    
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])

    # Get the system platform
    system = platform.system().lower()

    # Define output executable name based on platform
    exe_name = "dslate.exe" if system == "windows" else "dslate"

    # Set up PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",  # Create a single executable file
        "--name",
        "dslate",
        "--clean",  # Clean PyInstaller cache and remove temporary files
        "--collect-all",
        "readchar",  # Include package metadata for readchar
        "--collect-all",
        "dslate",  # Include package data
        "--additional-hooks-dir=custom_hooks",
        "dslate/dslate/cli.py",  # Main script to execute
    ]

    print(f"Building executable for {system}...")
    subprocess.check_call(cmd)

    # Move executable to dist directory and clean up
    output_path = dist_dir / exe_name

    print(f"Executable created at: {output_path}")
    print("Build completed successfully!")


if __name__ == "__main__":
    main()
