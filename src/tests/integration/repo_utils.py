# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import os
import shutil
import subprocess
import uuid
from pathlib import Path


class RepoState:
    def __init__(self, path: Path):
        self.path = path

    def setup_repo(self):
        """Initialize a git repository."""
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True)

        subprocess.run(["git", "init", "-b", "main"], cwd=self.path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=self.path, check=True
        )

        # Initial commit
        (self.path / ".gitignore").write_text("__pycache__/\n*.pyc\n")
        (self.path / "README.md").write_text("# Test Repo\n")

        # Create some structure for complex tests
        src_dir = self.path / "src"
        src_dir.mkdir()
        (src_dir / "old_module.py").write_text("def old(): pass\n")
        (src_dir / "unused.py").write_text("def unused(): pass\n")

        subprocess.run(["git", "add", "."], cwd=self.path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=self.path, check=True
        )

    def apply_changes(self, changes: dict[str, str | bytes | None]):
        """Apply changes to the repository.

        Args:
            changes: Dictionary where key is filename and value is:
                     - str: Text content to write (creates/modifies file)
                     - bytes: Binary content to write (creates/modifies file)
                     - None: Delete the file
                     - tuple (str, str): Rename file (old_path, new_path) - content preserved if not specified otherwise
        """
        for filename, content in changes.items():
            file_path = self.path / filename

            if content is None:
                # Delete file
                if file_path.exists():
                    try:
                        subprocess.run(
                            ["git", "rm", filename],
                            cwd=self.path,
                            check=True,
                            capture_output=True,
                        )
                    except subprocess.CalledProcessError:
                        # Fallback if not tracked
                        os.remove(file_path)
            elif isinstance(content, (str, bytes)):
                # Create or modify file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                mode = "w" if isinstance(content, str) else "wb"
                with open(file_path, mode) as f:
                    f.write(content)
            elif isinstance(content, tuple) and len(content) == 2:
                # Rename: (old, new)
                old_path = self.path / filename
                new_path = self.path / content[1]

                if old_path.exists():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        subprocess.run(
                            ["git", "mv", filename, content[1]],
                            cwd=self.path,
                            check=True,
                            capture_output=True,
                        )
                    except subprocess.CalledProcessError:
                        # Fallback if not tracked
                        shutil.move(str(old_path), str(new_path))

    def stage_all(self):
        """Stage all changes."""
        subprocess.run(["git", "add", "."], cwd=self.path, check=True)

    def commit(self, message: str):
        """Commit staged changes."""
        subprocess.run(["git", "commit", "-m", message], cwd=self.path, check=True)

    def get_current_tree(self) -> str:
        """Get the tree hash of the current working directory state.

        This does NOT modify the actual index or HEAD. It uses a
        temporary index to calculate the tree object.
        """
        # Create a temporary index file with a cryptographically unique name
        temp_index = self.path / ".git" / f"temp_index_{uuid.uuid4().hex}"
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(temp_index)

        # Read HEAD into temp index
        subprocess.run(["git", "read-tree", "HEAD"], cwd=self.path, env=env, check=True)

        # Add current working directory changes to temp index
        subprocess.run(["git", "add", "-A"], cwd=self.path, env=env, check=True)

        # Write tree from temp index
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=self.path,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        # Clean up
        if temp_index.exists():
            os.remove(temp_index)

        return result.stdout.strip()

    def get_head_tree(self) -> str:
        """Get the tree hash of HEAD."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def create_branch(self, name: str):
        """Create a new branch."""
        subprocess.run(["git", "branch", name], cwd=self.path, check=True)

    def checkout(self, name: str):
        """Checkout a branch or commit."""
        subprocess.run(["git", "checkout", name], cwd=self.path, check=True)

    def get_current_branch(self) -> str:
        """Get the name of the current branch."""
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_commit_hash(self, ref: str = "HEAD") -> str:
        """Get the commit hash of a reference."""
        result = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
