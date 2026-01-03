#!/usr/bin/env python
"""
Build script to create executable folder for dslate CLI tool.
"""

import importlib.util
import platform
import subprocess
import sys
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
    if not importlib.util.find_spec("PyInstaller"):
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyInstaller"])

    # Get the system platform
    system = platform.system().lower()

    # Set up PyInstaller command
    cmd = [
        "pyinstaller",
        "--onedir",  # one dir instead of one file
        "--name",
        "dslate",
        "--clean",
        "--noconfirm",
        "--collect-all", "readchar",
        "--collect-all", "dslate",
        "--additional-hooks-dir=custom_hooks",
        "dslate/dslate/cli.py",
    ]

    print(f"Building executable folder for {system}...")
    subprocess.check_call(cmd)

    # Output location
    output_dir = dist_dir / "dslate"
    
    # Validation check
    if system == "windows":
        exe_path = output_dir / "dslate.exe"
    else:
        exe_path = output_dir / "dslate"

    if exe_path.exists():
        print(f"Build successful! Artifacts located in: {output_dir}")
    else:
        print("Build failed: Executable not found.")
        sys.exit(1)

if __name__ == "__main__":
    main()