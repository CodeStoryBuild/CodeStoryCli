#!/usr/bin/env python
"""
Build script to create standalone executable for dslate CLI tool using PyOxidizer.
Usage:
    python build_exe_opt.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    # Define output directories
    dist_path = Path("dist") / "file"
    
    # Clean previous build if exists
    if dist_path.exists():
        print(f"Cleaning {dist_path}...")
        shutil.rmtree(dist_path)
    dist_path.mkdir(parents=True, exist_ok=True)

    # Check for PyOxidizer
    try:
        subprocess.check_call(["pyoxidizer", "--version"], stdout=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyOxidizer not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyoxidizer"])

    # Build wheel
    print("Building wheel...")
    try:
        subprocess.check_call([sys.executable, "-m", "build", "--wheel"])
    except subprocess.CalledProcessError as e:
        print(f"Wheel build failed: {e}")
        sys.exit(1)

    print("Building with PyOxidizer...")
    
    # Run PyOxidizer build
    # We use 'pyoxidizer run --release' to build and run, but here we just want to build.
    # 'pyoxidizer build' builds the targets.
    try:
        subprocess.check_call(["pyoxidizer", "build"])
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

    # Locate the generated executable
    # PyOxidizer builds into build/<target>/<release>/...
    # The default target is 'install' which produces a directory.
    # We want the executable from the 'exe' target or the 'install' target.
    # Based on our config, 'install' target puts the exe in the root of the output.
    
    # The path usually looks like: build/x86_64-pc-windows-msvc/release/install/dslate.exe
    # We need to find it dynamically or assume the path based on platform.
    
    build_dir = Path("build")
    # Find the debug directory (architecture dependent)
    # We look for any directory in build/ that contains 'debug'
    exe_source = None
    
    for root, dirs, files in os.walk(build_dir):
        if "debug" in root and "install" in root:
            possible_exe = Path(root) / "dslate.exe"
            if possible_exe.exists():
                exe_source = possible_exe
                break
    
    if not exe_source:
        # Try looking in 'exe' target dir if 'install' didn't have it (though install should)
        for root, dirs, files in os.walk(build_dir):
            if "debug" in root and "exe" in root: # optimization: check 'exe' dir
                 possible_exe = Path(root) / "dslate.exe"
                 if possible_exe.exists():
                    exe_source = possible_exe
                    break

    if exe_source and exe_source.exists():
        print(f"Found executable at: {exe_source}")
        target_exe = dist_path / "dslate.exe"
        shutil.copy2(exe_source, target_exe)
        print(f"Build successful! Artifact located at: {target_exe}")
    else:
        print("Build failed: Could not locate generated executable.")
        sys.exit(1)

if __name__ == "__main__":
    main()
