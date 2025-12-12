#!/usr/bin/env python
"""
Build script to create executable for codestory CLI tool using Nuitka.
Usage:
    python build.py
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Build codestory executable with Nuitka"
    )
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
        subprocess.check_call(
            [sys.executable, "-m", "nuitka", "--version"], stdout=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka not found. Installing...")
        raise RuntimeError(
            "Nuitka and zstandard must be installed to build the executable."
        )

    # Entry point
    entry_point = Path("src/codestory/cli.py")
    if not entry_point.exists():
        print(f"Error: Entry point {entry_point} not found.")
        sys.exit(1)

    # Set up Nuitka command
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--debug",
        "--standalone",
        "--assume-yes-for-downloads",
        "--show-modules",
        "--include-package=tree_sitter_language_pack",
        "--include-module=tree_sitter_language_pack.bindings",
        "--include-package=codestory",
        "--include-package-data=codestory",
        "--include-package=tree_sitter",
        "--include-package=aisuite",
        # Lazy imports from embedder.py and clusterer.py
        "--include-package=fastembed",
        "--include-package=sklearn",
        "--include-package=networkx",
        "--nofollow-import-to=sympy",
        "--nofollow-import-to=onnxruntime.quantization",
        "--nofollow-import-to=onnxruntime.transformers",
        "--nofollow-import-to=onnxruntime.datasets",
    ]

    cmd.extend(
        [
            f"--output-dir={dist_path}",
            f"--output-filename={exe_name}",
            "--remove-output",
            "--no-deployment-flag=self-execution",
        ]
    )

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

    # Validation - Nuitka creates a .dist directory for standalone builds
    # The directory is named after the entry point (cli.py -> cli.dist)
    standalone_dir = dist_path / "cli.dist"
    target_output = standalone_dir / exe_name
    if target_output.exists():
        print(f"Build successful! Artifact located at: {target_output}")
    else:
        print(f"Build finished but expected artifact {target_output} not found.")
        print(f"Checking if standalone directory exists: {standalone_dir.exists()}")
        if standalone_dir.exists():
            print(f"Contents of {standalone_dir}:")
            for item in standalone_dir.iterdir():
                print(f"  - {item.name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
