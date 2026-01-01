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
import subprocess
from pathlib import Path

import pytest

from codestory.core.diff.creation.diff_creator import DiffCreator
from codestory.core.diff.creation.hunk_wrapper import HunkWrapper
from codestory.core.diff.creation.immutable_hunk_wrapper import ImmutableHunkWrapper
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_interface import GitInterface


@pytest.fixture
def git_repo(tmp_path: Path):
    """A pytest fixture that creates a temporary directory, initializes a Git repository
    in it, and configures user identity.

    It changes the current working directory to the new repo for the
    duration of the test.
    """
    original_cwd = Path.cwd()
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    os.chdir(repo_path)

    subprocess.check_call(["git", "init", "-b", "main"])
    subprocess.check_call(["git", "config", "user.name", "Test User"])
    subprocess.check_call(["git", "config", "user.email", "test@example.com"])

    # Create an initial commit so HEAD exists
    (repo_path / "initial.txt").write_text("initial commit")
    subprocess.check_call(["git", "add", "initial.txt"])
    subprocess.check_call(["git", "commit", "-m", "Initial commit"])

    yield repo_path

    os.chdir(original_cwd)


class TestDiffCreatorIntegration:
    """Integration tests for DiffCreator using a real Git repository."""

    def setup_method(self, method):
        """Setup GitCommands and DiffCreator instances for each test method."""
        git = GitInterface(".")
        self.git_commands = GitCommands(git=git)
        self.diff_creator = DiffCreator(git=git)

    def test_parse_simple_modification(self, git_repo: Path):
        """Test parsing a diff for a simple text file modification."""
        file_path = git_repo / "test.txt"
        file_path.write_text("line 1\nline 2\n")
        subprocess.check_call(["git", "add", "test.txt"])
        subprocess.check_call(["git", "commit", "-m", "add test.txt"])
        base_hash = self.git_commands.get_commit_hash("HEAD")

        file_path.write_text("line 1\nline 2 modified\n")
        subprocess.check_call(["git", "add", "test.txt"])
        subprocess.check_call(["git", "commit", "-m", "modification"])
        new_hash = self.git_commands.get_commit_hash("HEAD")
        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, HunkWrapper)
        assert hunk.old_file_path == b"test.txt"
        assert hunk.new_file_path == b"test.txt"
        assert hunk.hunk_lines == [b"-line 2", b"+line 2 modified"]

    def test_parse_file_addition(self, git_repo: Path):
        """Test parsing a diff for a newly added file."""
        base_hash = self.git_commands.get_commit_hash("HEAD")
        (git_repo / "new_file.txt").write_text("hello world")
        subprocess.check_call(["git", "add", "new_file.txt"])
        subprocess.check_call(["git", "commit", "-m", "add new file"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, HunkWrapper)
        assert hunk.old_file_path is None
        assert hunk.new_file_path == b"new_file.txt"
        assert hunk.hunk_lines == [
            b"+hello world",
            b"\\ No newline at end of file",
        ]

    def test_parse_file_addition_empty(self, git_repo: Path):
        """Test parsing a diff for a newly added file."""
        base_hash = self.git_commands.get_commit_hash("HEAD")
        (git_repo / "new_file.txt").write_text("")
        subprocess.check_call(["git", "add", "new_file.txt"])
        subprocess.check_call(["git", "commit", "-m", "add new file"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, HunkWrapper)
        assert hunk.old_file_path is None
        assert hunk.new_file_path == b"new_file.txt"
        assert hunk.hunk_lines == []

    def test_parse_file_deletion(self, git_repo: Path):
        """Test parsing a diff for a deleted file."""
        file_path = git_repo / "to_delete.txt"
        file_path.write_text("delete me")
        subprocess.check_call(["git", "add", str(file_path)])
        subprocess.check_call(["git", "commit", "-m", "add to_delete"])
        base_hash = self.git_commands.get_commit_hash("HEAD")

        file_path.unlink()
        subprocess.check_call(["git", "rm", str(file_path)])
        subprocess.check_call(["git", "commit", "-m", "delete file"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, HunkWrapper)
        assert hunk.old_file_path == b"to_delete.txt"
        assert hunk.new_file_path is None
        assert hunk.hunk_lines == [
            b"-delete me",
            b"\\ No newline at end of file",
        ]

    def test_parse_rename_with_modification(self, git_repo: Path):
        """Test a file that is renamed and modified in the same commit."""
        (git_repo / "original.txt").write_text("content\n")
        subprocess.check_call(["git", "add", "original.txt"])
        subprocess.check_call(["git", "commit", "-m", "add original"])
        base_hash = self.git_commands.get_commit_hash("HEAD")

        subprocess.check_call(["git", "mv", "original.txt", "renamed.txt"])
        (git_repo / "renamed.txt").write_text("content\ncontent2")
        subprocess.check_call(["git", "commit", "-am", "rename file"])
        new_hash = self.git_commands.get_commit_hash("HEAD")
        hunks = self.diff_creator.get_full_working_diff(
            base_hash, new_hash, similarity=50
        )

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, HunkWrapper)
        assert hunk.old_file_path == b"original.txt"
        assert hunk.new_file_path == b"renamed.txt"
        assert hunk.hunk_lines == [
            b"+content2",
            b"\\ No newline at end of file",
        ]

    def test_add_binary_file(self, git_repo: Path):
        """Test that binary file changes are captured as ImmutableHunkWrapper."""
        base_hash = self.git_commands.get_commit_hash("HEAD")
        binary_file = git_repo / "logo.png"
        binary_file.write_bytes(b"\x00")
        subprocess.check_call(["git", "add", str(binary_file)])
        subprocess.check_call(["git", "commit", "-m", "add logo"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, ImmutableHunkWrapper)
        assert (
            b"GIT binary patch\nliteral 1\nIcmZPo000310RR91\n\nliteral 0\nHcmV?d00001\n"
            in hunk.file_patch
        )

    def test_parse_binary_file_diff(self, git_repo: Path):
        """Test that binary file changes are captured as ImmutableHunkWrapper."""
        binary_file = git_repo / "logo.png"
        binary_file.write_bytes(b"\x00")
        subprocess.check_call(["git", "add", str(binary_file)])
        subprocess.check_call(["git", "commit", "-m", "add logo"])
        base_hash = self.git_commands.get_commit_hash("HEAD")

        # Modify the binary file
        binary_file.write_bytes(b"\x00\x12")
        subprocess.check_call(["git", "add", str(binary_file)])
        subprocess.check_call(["git", "commit", "-m", "modify logo"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 1
        hunk = hunks[0]
        assert isinstance(hunk, ImmutableHunkWrapper)
        assert (
            b"GIT binary patch\nliteral 2\nJcmZP&0ssIM022TJ\n\nliteral 1\nIcmZPo000310RR91\n"
            in hunk.file_patch
        )

    def test_add_multiple_binary_file_diff(self, git_repo: Path):
        """Test that binary file changes are captured as ImmutableHunkWrapper."""
        base_hash = self.git_commands.get_commit_hash("HEAD")
        binary_file = git_repo / "logo.png"
        binary_file2 = git_repo / "logo2.png"
        binary_file.write_bytes(b"\x00")
        binary_file2.write_bytes(b"\x00")
        subprocess.check_call(["git", "add", "."])
        subprocess.check_call(["git", "commit", "-m", "add logos"])
        new_hash = self.git_commands.get_commit_hash("HEAD")

        hunks = self.diff_creator.get_full_working_diff(base_hash, new_hash)

        assert len(hunks) == 2
        for hunk in hunks[
            0:
        ]:  # first one might be initial.txt if we didn't use base_hash correctly, but here we did.
            assert isinstance(hunk, ImmutableHunkWrapper)
            assert hunk.file_patch.startswith(b"diff --git")
