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

import subprocess
import tempfile
from pathlib import Path

import pytest

from codestory.core.diff.creation.hunk_wrapper import HunkWrapper
from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_interface import (
    GitInterface,
)
from codestory.core.git.git_synthesizer import GitSynthesizer
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


def hunk_to_chunk(
    hunk: HunkWrapper, base_hash: str = "HEAD", new_hash: str = "head"
) -> StandardDiffChunk:
    parsed_content = []
    current_old_line = hunk.old_start
    current_new_line = hunk.new_start
    contains_newline_fallback = False
    for line in hunk.hunk_lines:
        content = line[1:]
        if line.startswith(b"+"):
            parsed_content.append(
                Addition(
                    old_line=current_old_line,
                    abs_new_line=current_new_line,
                    content=content,
                )
            )
            current_new_line += 1
        elif line.startswith(b"-"):
            parsed_content.append(
                Removal(
                    old_line=current_old_line,
                    abs_new_line=current_new_line,
                    content=content,
                )
            )
            current_old_line += 1
        elif line.strip() == b"\\ No newline at end of file":
            if parsed_content:
                parsed_content[-1].newline_marker = True
            else:
                contains_newline_fallback = True

    return StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=hunk.old_file_path,
        new_file_path=hunk.new_file_path,
        file_mode=hunk.file_mode,
        contains_newline_fallback=contains_newline_fallback,
        parsed_content=parsed_content,
        old_start=hunk.old_start,
    )


class MockFileManager:
    def __init__(self, containers=None, git_commands=None):
        self.git_commands = git_commands
        self.containers = containers

    def get_line_count(self, file_path: bytes, commit_hash: str) -> int | None:
        if self.containers:
            from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
            from codestory.core.diff.data.utils import flatten_containers

            all_chunks = flatten_containers(self.containers)
            relevant_chunks = [
                c
                for c in all_chunks
                if isinstance(c, StandardDiffChunk)
                and c.canonical_path() == file_path
                and c.base_hash == commit_hash
            ]
            if relevant_chunks and all(c.is_file_deletion for c in relevant_chunks):
                return sum(c.old_len() for c in relevant_chunks)

        if self.git_commands:
            try:
                path_str = file_path.decode("utf-8", errors="replace")
                content = self.git_commands.cat_file(f"{commit_hash}:{path_str}")
                if content is not None:
                    return len(content.splitlines())
            except Exception:
                pass
        return None


## Fixtures


@pytest.fixture
def git_repo() -> tuple[Path, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=repo_path
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path)

        (repo_path / "app.js").write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
        )

        base_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            text=True,
            capture_output=True,
        ).stdout.strip()

        yield repo_path, base_hash


## Test Cases


def test_basic_modification(git_repo):
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))

    hunk = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 3", b"+line three"],
        old_start=3,
        new_start=3,
        old_len=1,
        new_len=1,
        file_mode=None,
    )
    chunk = hunk_to_chunk(hunk)
    group = CommitGroup(container=chunk, commit_message="Modify line 3")

    git_cmds = GitCommands(GitInterface(repo_path))
    fm = FileManager([chunk], git_cmds)
    synthesizer = GitSynthesizer(git_cmds, fm)
    final_hash = synthesizer.execute_plan([chunk], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    content = (repo_path / "app.js").read_text()
    lines = content.split("\n")

    # Verify exact position and content of the modification
    assert lines[2] == "line three"  # Line 3 should be modified (0-indexed position 2)
    assert "line 3" not in lines  # Original line 3 should be completely replaced

    # Verify other lines remain unchanged and in correct positions
    assert lines[0] == "line 1"
    assert lines[1] == "line 2"
    assert lines[3] == "line 4"
    assert lines[4] == "line 5"
    assert len(lines) == 6  # Should have 5 lines + 1 empty line from trailing newline

    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert log == "Modify line 3"


def test_file_deletion(git_repo):
    repo_path, base_hash = git_repo
    hunk = HunkWrapper(
        new_file_path=None,
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1", b"-line 2", b"-line 3", b"-line 4", b"-line 5"],
        old_start=1,
        new_start=1,
        old_len=5,
        new_len=0,
        file_mode=None,
    )
    chunk = hunk_to_chunk(hunk)
    group = CommitGroup(container=chunk, commit_message="Delete app.js")

    git_cmds = GitCommands(GitInterface(repo_path))
    fm = MockFileManager([chunk], git_cmds)
    synthesizer = GitSynthesizer(git_cmds, fm)
    final_hash = synthesizer.execute_plan([chunk], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    assert not (repo_path / "app.js").exists()


def test_rename_file(git_repo):
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    hunk = HunkWrapper(
        new_file_path=b"server.js",
        old_file_path=b"app.js",
        hunk_lines=[],
        old_start=0,
        new_start=0,
        old_len=0,
        new_len=0,
        file_mode=None,
    )
    chunk = hunk_to_chunk(hunk)
    group = CommitGroup(
        container=chunk,
        commit_message="Rename app.js to server.js",
    )

    git_cmds = GitCommands(GitInterface(repo_path))
    fm = FileManager([chunk], git_cmds)
    synthesizer = GitSynthesizer(git_cmds, fm)
    final_hash = synthesizer.execute_plan([chunk], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    assert not (repo_path / "app.js").exists()
    assert (repo_path / "server.js").exists()
    assert (
        repo_path / "server.js"
    ).read_text() == "line 1\nline 2\nline 3\nline 4\nline 5\n"


# ... (imports and other setup)


def test_critical_line_shift_scenario(git_repo):
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Single line modification (capitalize 'line 1')
    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1", b"+Line 1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=1,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)
    group1 = CommitGroup(container=chunk1, commit_message="Capitalize line 1")

    # Single line deletion
    hunk2 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 5"],
        old_start=5,
        new_start=5,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)
    group2 = CommitGroup(container=chunk2, commit_message="Delete line 5")

    # Single line addition
    hunk3 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"+new line 6"],
        old_start=5,
        new_start=5,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk3 = hunk_to_chunk(hunk3)
    group3 = CommitGroup(container=chunk3, commit_message="Add line 6")

    git_cmds = GitCommands(GitInterface(repo_path))
    fm = FileManager([chunk1, chunk2, chunk3], git_cmds)
    synthesizer = GitSynthesizer(git_cmds, fm)
    final_hash = synthesizer.execute_plan(
        [chunk1, chunk2, chunk3], [group1, group2, group3], base_hash
    )
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify final file content
    final_content = (repo_path / "app.js").read_text()
    expected_content = "Line 1\nline 2\nline 3\nline 4\nnew line 6\n"
    assert final_content == expected_content

    # Verify commit history
    log_output = (
        subprocess.run(
            ["git", "log", "--oneline", f"{base_hash}..HEAD"],
            cwd=repo_path,
            text=True,
            capture_output=True,
        )
        .stdout.strip()
        .splitlines()
    )

    assert len(log_output) == 3
    assert "Add line 6" in log_output[0]  # Newest commit (HEAD)
    assert "Delete line 5" in log_output[1]  # Parent commit (HEAD~1)
    assert "Capitalize line 1" in log_output[2]  # Grandparent commit (HEAD~2)

    # Verify diff of HEAD commit (group3)
    head_diff_output = subprocess.run(
        ["git", "show", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    assert "+new line 6" in head_diff_output
    assert "-line 5" not in head_diff_output
    assert "+Line 1" not in head_diff_output

    # Verify diff of HEAD~1 commit (group2)
    parent_diff_output = subprocess.run(
        ["git", "show", "HEAD~1"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    assert "-line 5" in parent_diff_output
    assert "+new line 6" not in parent_diff_output
    assert "+Line 1" not in parent_diff_output

    # Verify diff of HEAD~2 commit (group1)
    grandparent_diff_output = subprocess.run(
        ["git", "show", "HEAD~2"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    assert "-line 1" in grandparent_diff_output
    assert "+Line 1" in grandparent_diff_output
    assert "+new line 6" not in grandparent_diff_output
    assert "-line 5" not in grandparent_diff_output


# --- Pure Addition Tests ---


def test_pure_addition_single_file(git_repo):
    """Test adding new content to an existing file without any deletions."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Add header line at the beginning

    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"+header line"],
        old_start=0,
        new_start=1,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)

    hunk2 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"+middle insertion"],
        old_start=2,
        new_start=3,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)

    hunk3 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"+footer line"],
        old_start=5,
        new_start=6,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk3 = hunk_to_chunk(hunk3)

    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2, chunk3]),
        commit_message="Add multiple lines",
    )

    final_hash = synthesizer.execute_plan([chunk1, chunk2, chunk3], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    content = (repo_path / "app.js").read_text()
    lines = content.strip().split("\n")

    # Each insertion is handled independently
    assert "header line" in lines
    assert "middle insertion" in lines
    assert "footer line" in lines

    # Verify original content is still there
    assert "line 1" in lines
    assert "line 2" in lines
    assert "line 3" in lines
    assert "line 4" in lines
    assert "line 5" in lines

    # Verify total line count is correct (5 original + 3 additions)
    assert len(lines) == 8


def test_pure_addition_new_files(git_repo):
    """Test creating entirely new files."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Add multiple new files

    hunk1 = HunkWrapper(
        new_file_path=b"config.json",
        old_file_path=None,
        hunk_lines=[
            b"+{",
            b'+  "name": "test",',
            b'+  "version": "1.0.0"',
            b"+}",
        ],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=4,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)

    hunk2 = HunkWrapper(
        new_file_path=b"nested/deep/file.txt",
        old_file_path=None,
        hunk_lines=[b"+content line 1", b"+content line 2"],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=2,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)

    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2]), commit_message="Add new files"
    )

    final_hash = synthesizer.execute_plan([chunk1, chunk2], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify new files exist with correct content
    assert (repo_path / "config.json").exists()
    config_content = (repo_path / "config.json").read_text()
    assert '"name": "test"' in config_content

    assert (repo_path / "nested" / "deep" / "file.txt").exists()
    nested_content = (repo_path / "nested" / "deep" / "file.txt").read_text()
    assert nested_content == "content line 1\ncontent line 2\n"


def test_pure_addition_multiple_groups(git_repo):
    """Test multiple groups that only add content."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Add to existing file

    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"+// Header comment"],
        old_start=0,
        new_start=1,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)
    group1 = CommitGroup(container=chunk1, commit_message="Add header comment")

    hunk2 = HunkWrapper(
        new_file_path=b"README.md",
        old_file_path=None,
        hunk_lines=[b"+# Project Title", b"+", b"+Description here"],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=3,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)
    group2 = CommitGroup(container=chunk2, commit_message="Add README")

    final_hash = synthesizer.execute_plan([chunk1, chunk2], [group1, group2], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify both changes
    app_content = (repo_path / "app.js").read_text()
    assert app_content.startswith("// Header comment\n")

    readme_content = (repo_path / "README.md").read_text()
    assert "# Project Title" in readme_content


# --- Pure Deletion Tests ---


def test_pure_deletion_partial_content(git_repo):
    """Test deleting only some lines from files without adding anything."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Remove lines 2 and 4

    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 2"],
        old_start=2,
        new_start=2,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)

    hunk2 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 4"],
        old_start=4,
        new_start=4,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)

    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2]),
        commit_message="Remove lines 2 and 4",
    )

    final_hash = synthesizer.execute_plan([chunk1, chunk2], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    content = (repo_path / "app.js").read_text()
    lines = content.strip().split("\n")

    # Verify line count and positions after deletions
    assert len(lines) == 3  # Should have 3 lines remaining (5 original - 2 deleted)

    # Verify content and positions of remaining lines
    assert lines[0] == "line 1"  # First remaining line
    assert lines[1] == "line 3"  # Second remaining line
    assert lines[2] == "line 5"  # Third remaining line

    # Deleted lines should be gone
    assert "line 2" not in lines
    assert "line 4" not in lines


def test_pure_deletion_entire_files(git_repo):
    """Test deleting entire files completely."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Create files to delete
    (repo_path / "temp.txt").write_text("temporary content\n")
    (repo_path / "config.json").write_text('{"test": true}\n')
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add files to delete"],
        cwd=repo_path,
        check=True,
    )

    # Get new base commit hash
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    # Remove all content

    # temp.txt
    temp_lines = (repo_path / "temp.txt").read_text().splitlines()
    hunk1 = HunkWrapper(
        new_file_path=None,
        old_file_path=b"temp.txt",
        hunk_lines=[f"-{line}".encode() for line in temp_lines],
        old_start=1,
        new_start=1,
        old_len=len(temp_lines),
        new_len=0,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)
    # config.json
    config_lines = (repo_path / "config.json").read_text().splitlines()
    hunk2 = HunkWrapper(
        new_file_path=None,
        old_file_path=b"config.json",
        hunk_lines=[f"-{line}".encode() for line in config_lines],
        old_start=1,
        new_start=1,
        old_len=len(config_lines),
        new_len=0,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)
    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2]),
        commit_message="Delete temp files",
    )

    final_hash = synthesizer.execute_plan([chunk1, chunk2], [group], new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Files should be deleted
    assert not (repo_path / "temp.txt").exists()
    assert not (repo_path / "config.json").exists()
    # Original file should exist
    assert (repo_path / "app.js").exists()


def test_pure_deletion_multiple_groups(git_repo):
    """Test multiple groups that only delete content."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Add more content first
    (repo_path / "app.js").write_text(
        "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\n"
    )
    (repo_path / "other.txt").write_text("other line 1\nother line 2\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add more content"], cwd=repo_path, check=True
    )

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    # Remove from app.js

    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)
    hunk1b = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 3"],
        old_start=3,
        new_start=3,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk1b = hunk_to_chunk(hunk1b)
    group1 = CommitGroup(
        container=CompositeContainer([chunk1, chunk1b]),
        commit_message="Remove lines from app.js",
    )

    # Delete other.txt (all lines as removals)
    other_lines = (repo_path / "other.txt").read_text().splitlines()
    hunk2 = HunkWrapper(
        new_file_path=None,
        old_file_path=b"other.txt",
        hunk_lines=[f"-{line}".encode() for line in other_lines],
        old_start=1,
        new_start=1,
        old_len=len(other_lines),
        new_len=0,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)
    group2 = CommitGroup(container=chunk2, commit_message="Delete other.txt")

    final_hash = synthesizer.execute_plan(
        [chunk1, chunk1b, chunk2], [group1, group2], new_base_hash
    )
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify deletions
    app_content = (repo_path / "app.js").read_text()
    lines = app_content.strip().split("\n")

    # Some content should be removed, some remains
    assert len(lines) < 7  # Should have fewer lines than we started with
    assert len(lines) > 0  # Should have some lines remaining

    # Targeted lines should be gone
    assert "line 1" not in lines
    assert "line 3" not in lines

    assert not (repo_path / "other.txt").exists()


# --- Large Mixed Change Tests ---


def test_large_mixed_changes_single_group(git_repo):
    """Test a single group with many files and mixed change types."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Create additional files
    (repo_path / "src").mkdir()
    (repo_path / "src" / "utils.py").write_text("def helper():\n    pass\n")
    (repo_path / "docs").mkdir()
    (repo_path / "docs" / "readme.txt").write_text("Old documentation\n")
    (repo_path / "config.ini").write_text("[section]\nold_value=1\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Setup for mixed changes"],
        cwd=repo_path,
        check=True,
    )

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    # Mixed operations

    chunks = []
    # Modify file
    hunk_app = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1", b"+modified line 1", b"+new line after 1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=2,
        file_mode=None,
    )
    chunks.append(hunk_to_chunk(hunk_app))
    # Add nested file
    hunk_user = HunkWrapper(
        new_file_path=b"src/models/user.py",
        old_file_path=None,
        hunk_lines=[
            b"+class User:",
            b"+    def __init__(self, name):",
            b"+        self.name = name",
        ],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=3,
        file_mode=None,
    )
    chunks.append(hunk_to_chunk(hunk_user))
    # Modify nested file
    hunk_utils = HunkWrapper(
        new_file_path=b"src/utils.py",
        old_file_path=b"src/utils.py",
        hunk_lines=[
            b"-def helper():",
            b"-    pass",
            b"+def helper(param):",
            b"+    return param * 2",
        ],
        old_start=1,
        new_start=1,
        old_len=2,
        new_len=2,
        file_mode=None,
    )
    chunks.append(hunk_to_chunk(hunk_utils))
    # Remove file

    # Remove docs/readme.txt (all lines as removals)
    readme_lines = (repo_path / "docs" / "readme.txt").read_text().splitlines()
    hunk_readme = HunkWrapper(
        new_file_path=None,
        old_file_path=b"docs/readme.txt",
        hunk_lines=[f"-{line}".encode() for line in readme_lines],
        old_start=1,
        new_start=1,
        old_len=len(readme_lines),
        new_len=0,
        file_mode=None,
    )
    chunks.append(hunk_to_chunk(hunk_readme))
    # Rename and modify
    hunk_rename = HunkWrapper(
        new_file_path=b"config/settings.ini",
        old_file_path=b"config.ini",
        hunk_lines=[
            b"+[database]",
            b"+host=localhost",
            b"+port=5432",
            b"-[section]",
            b"-old_value=1",
        ],
        old_start=1,
        new_start=1,
        old_len=2,
        new_len=3,
        file_mode=None,
    )
    chunks.append(hunk_to_chunk(hunk_rename))

    group = CommitGroup(
        container=CompositeContainer(chunks),
        commit_message="Large mixed changes",
    )
    final_hash = synthesizer.execute_plan(chunks, [group], new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify all changes
    # Verify modified file
    app_content = (repo_path / "app.js").read_text()
    app_lines = app_content.split("\n")
    assert app_lines[0] == "modified line 1"  # First line should be modified
    assert app_lines[1] == "new line after 1"  # Second line should be the addition
    # Original "line 1" should be completely replaced, not just modified
    assert "line 1" not in app_lines

    # Verify new nested file
    assert (repo_path / "src" / "models" / "user.py").exists()
    user_content = (repo_path / "src" / "models" / "user.py").read_text()
    user_lines = user_content.split("\n")
    assert user_lines[0] == "class User:"
    assert user_lines[1] == "    def __init__(self, name):"
    assert user_lines[2] == "        self.name = name"

    # Verify modified nested file
    utils_content = (repo_path / "src" / "utils.py").read_text()
    utils_lines = utils_content.split("\n")
    assert utils_lines[0] == "def helper(param):"
    assert utils_lines[1] == "    return param * 2"
    # Old content should be gone
    assert "def helper():" not in utils_lines
    assert "pass" not in utils_lines

    # File removed
    assert not (repo_path / "docs" / "readme.txt").exists()

    # Renamed and modified file
    assert not (repo_path / "config.ini").exists()
    assert (repo_path / "config" / "settings.ini").exists()
    config_content = (repo_path / "config" / "settings.ini").read_text()
    config_lines = config_content.split("\n")
    assert config_lines[0] == "[database]"
    assert config_lines[1] == "host=localhost"
    assert config_lines[2] == "port=5432"
    # Old content should be gone
    assert "[section]" not in config_lines
    assert "old_value=1" not in config_lines


def test_large_mixed_changes_multiple_groups(git_repo):
    """Test multiple groups each with several files and mixed operations."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Setup initial structure
    (repo_path / "frontend").mkdir()
    (repo_path / "backend").mkdir()
    (repo_path / "frontend" / "index.html").write_text(
        "<html><body>Old</body></html>\n"
    )
    (repo_path / "backend" / "server.py").write_text("print('old server')\n")
    (repo_path / "shared.txt").write_text("shared content\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial structure"], cwd=repo_path, check=True
    )

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    # Frontend changes
    group1_chunks = [
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"frontend/index.html",
                old_file_path=b"frontend/index.html",
                hunk_lines=[
                    b"-<html><body>Old</body></html>",
                    b"+<html><head><title>New</title></head><body>New</body></html>",
                ],
                old_start=1,
                new_start=1,
                old_len=1,
                new_len=1,
                file_mode=None,
            )
        ),
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"frontend/styles.css",
                old_file_path=None,
                hunk_lines=[
                    b"+body { margin: 0; }",
                    b"+.container { width: 100%; }",
                ],
                old_start=1,
                new_start=1,
                old_len=0,
                new_len=2,
                file_mode=None,
            )
        ),
    ]
    group1 = CommitGroup(
        container=CompositeContainer(group1_chunks),
        commit_message="Update frontend",
    )

    # Backend changes
    group2_chunks = [
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"backend/server.py",
                old_file_path=b"backend/server.py",
                hunk_lines=[
                    b"-print('old server')",
                    b"+from flask import Flask",
                    b"+app = Flask(__name__)",
                    b"+",
                    b"+@app.route('/')",
                    b"+def hello():",
                    b"+    return 'Hello World'",
                ],
                old_start=1,
                new_start=1,
                old_len=1,
                new_len=6,
                file_mode=None,
            )
        ),
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"backend/models.py",
                old_file_path=None,
                hunk_lines=[
                    b"+class User:",
                    b"+    pass",
                    b"+",
                    b"+class Post:",
                    b"+    pass",
                ],
                old_start=1,
                new_start=1,
                old_len=0,
                new_len=5,
                file_mode=None,
            )
        ),
    ]
    group2 = CommitGroup(
        container=CompositeContainer(group2_chunks),
        commit_message="Update backend",
    )

    # Cleanup and restructure
    # Remove shared.txt (all lines as removals)
    shared_lines = (repo_path / "shared.txt").read_text().splitlines()
    hunk_shared = HunkWrapper(
        new_file_path=None,
        old_file_path=b"shared.txt",
        hunk_lines=[f"-{line}".encode() for line in shared_lines],
        old_start=1,
        new_start=1,
        old_len=len(shared_lines),
        new_len=0,
        file_mode=None,
    )
    group3_chunks = [
        hunk_to_chunk(hunk_shared),
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"legacy/app.js",
                old_file_path=b"app.js",
                hunk_lines=[],
                old_start=0,
                new_start=0,
                old_len=0,
                new_len=0,
                file_mode=None,
            )
        ),
    ]
    group3 = CommitGroup(
        container=CompositeContainer(group3_chunks),
        commit_message="Cleanup and reorganize",
    )

    all_chunks = group1_chunks + group2_chunks + group3_chunks
    all_groups = [group1, group2, group3]

    final_hash = synthesizer.execute_plan(all_chunks, all_groups, new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify all changes
    # Group 1 changes
    html_content = (repo_path / "frontend" / "index.html").read_text()
    assert "<title>New</title>" in html_content
    assert (repo_path / "frontend" / "styles.css").exists()

    # Group 2 changes
    server_content = (repo_path / "backend" / "server.py").read_text()
    assert "from flask import Flask" in server_content
    assert (repo_path / "backend" / "models.py").exists()

    # Group 3 changes
    assert not (repo_path / "shared.txt").exists()
    assert not (repo_path / "app.js").exists()
    assert (repo_path / "legacy" / "app.js").exists()


def test_complex_interdependent_changes(git_repo):
    """Test changes that depend on each other across multiple files."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Create files that reference each other
    (repo_path / "main.py").write_text(
        "from utils import old_function\nold_function()\n"
    )
    (repo_path / "utils.py").write_text("def old_function():\n    return 'old'\n")
    (repo_path / "config.py").write_text("OLD_CONFIG = True\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Setup interdependent files"],
        cwd=repo_path,
        check=True,
    )

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    chunk_utils = hunk_to_chunk(
        HunkWrapper(
            new_file_path=b"utils.py",
            old_file_path=b"utils.py",
            hunk_lines=[
                b"-def old_function():",
                b"-    return 'old'",
                b"+def new_function():",
                b"+    return 'new'",
                b"+",
                b"+def helper():",
                b"+    return 'helper'",
            ],
            old_start=1,
            new_start=1,
            old_len=2,
            new_len=5,
            file_mode=None,
        )
    )
    chunk_main = hunk_to_chunk(
        HunkWrapper(
            new_file_path=b"main.py",
            old_file_path=b"main.py",
            hunk_lines=[
                b"-from utils import old_function",
                b"-old_function()",
                b"+from utils import new_function, helper",
                b"+from config import NEW_CONFIG",
                b"+",
                b"+if NEW_CONFIG:",
                b"+    result = new_function()",
                b"+    helper()",
            ],
            old_start=1,
            new_start=1,
            old_len=2,
            new_len=6,
            file_mode=None,
        )
    )
    chunk_config = hunk_to_chunk(
        HunkWrapper(
            new_file_path=b"config.py",
            old_file_path=b"config.py",
            hunk_lines=[
                b"-OLD_CONFIG = True",
                b"+NEW_CONFIG = True",
                b"+DEBUG = False",
            ],
            old_start=1,
            new_start=1,
            old_len=1,
            new_len=2,
            file_mode=None,
        )
    )
    chunks = [chunk_utils, chunk_main, chunk_config]

    group = CommitGroup(
        container=CompositeContainer(chunks),
        commit_message="Refactor interdependent code",
    )
    final_hash = synthesizer.execute_plan(chunks, [group], new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify coordinated changes
    main_content = (repo_path / "main.py").read_text()
    assert "from utils import new_function, helper" in main_content
    assert "from config import NEW_CONFIG" in main_content
    assert "old_function" not in main_content

    utils_content = (repo_path / "utils.py").read_text()
    assert "def new_function():" in utils_content
    assert "def helper():" in utils_content
    assert "old_function" not in utils_content

    config_content = (repo_path / "config.py").read_text()
    assert "NEW_CONFIG = True" in config_content
    assert "DEBUG = False" in config_content
    assert "OLD_CONFIG" not in config_content


# --- Edge Case Tests ---


def test_empty_group_handling(git_repo):
    """Test handling of empty groups and groups with no changes."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Empty group

    empty_group = CommitGroup(
        container=CompositeContainer([]), commit_message="Empty commit"
    )

    # No-op group (removes and adds the same line)
    hunk = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1", b"+line 1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=1,
        file_mode=None,
    )
    no_op_chunk = hunk_to_chunk(hunk)
    no_op_group = CommitGroup(container=no_op_chunk, commit_message="No-op change")

    # Handles edge cases
    final_hash = synthesizer.execute_plan(
        [no_op_chunk], [empty_group, no_op_group], base_hash
    )
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # File should be unchanged
    content = (repo_path / "app.js").read_text()
    assert content == "line 1\nline 2\nline 3\nline 4\nline 5\n"


def test_single_line_changes(git_repo):
    """Test edge cases with single character and single line changes."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Single character change

    hunk1 = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 1", b"+Line 1"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=1,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)

    hunk2 = HunkWrapper(
        new_file_path=b"single.txt",
        old_file_path=None,
        hunk_lines=[b"+x"],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=1,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)

    hunk3 = HunkWrapper.create_empty_addition(b"empty.txt", file_mode=b"100644")
    chunk3 = hunk_to_chunk(hunk3)

    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2, chunk3]),
        commit_message="Minimal changes",
    )
    final_hash = synthesizer.execute_plan([chunk1, chunk2, chunk3], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify single character change
    app_content = (repo_path / "app.js").read_text()
    assert app_content.startswith("Line 1\n")

    # Verify single character file
    single_content = (repo_path / "single.txt").read_text()
    assert single_content == "x\n"

    # Empty file should exist and be empty
    assert (repo_path / "empty.txt").exists()
    empty_content = (repo_path / "empty.txt").read_text()
    assert empty_content == ""


def test_boundary_line_numbers(git_repo):
    """Test edge cases with line number boundaries."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Create initial files for the test
    (repo_path / "app.js").write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")
    (repo_path / "src").mkdir()
    (repo_path / "src/utils.py").write_text("def old_util():\n    pass\n")
    (repo_path / "config.ini").write_text("timeout=100\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial files for boundary test"],
        cwd=repo_path,
        check=True,
    )

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    chunks = []

    hunk_app = HunkWrapper(
        new_file_path=b"app.js",
        old_file_path=b"app.js",
        hunk_lines=[b"-line 2", b"+modified line two", b"+added line after two"],
        old_start=2,
        new_start=2,
        old_len=1,
        new_len=2,
        file_mode=None,
    )
    chunk_app = hunk_to_chunk(hunk_app)
    chunks.append(chunk_app)

    hunk_utils = HunkWrapper(
        new_file_path=b"src/utils.py",
        old_file_path=b"src/utils.py",
        hunk_lines=[b"+# Utils header", b"+def new_helper():", b"+    pass"],
        old_start=0,
        new_start=1,
        old_len=0,
        new_len=3,
        file_mode=None,
    )
    chunk_utils = hunk_to_chunk(hunk_utils)
    chunks.append(chunk_utils)

    hunk_config = HunkWrapper(
        new_file_path=None,
        old_file_path=b"config.ini",
        hunk_lines=[b"-timeout=100"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=0,
        file_mode=None,
    )
    chunk_config = hunk_to_chunk(hunk_config)
    chunks.append(chunk_config)

    group = CommitGroup(
        container=CompositeContainer(chunks),
        commit_message="Mixed architectural changes",
    )

    final_hash = synthesizer.execute_plan(chunks, [group], new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    content = (repo_path / "app.js").read_text()
    lines = content.split("\n")
    assert lines[0] == "line 1"  # Original line 1
    assert lines[1] == "modified line two"
    assert lines[2] == "added line after two"
    assert "line 2" not in content  # Original line 2 removed

    utils_content = (repo_path / "src/utils.py").read_text()
    utils_lines = utils_content.split("\n")
    assert utils_lines[0] == "# Utils header"
    assert utils_lines[1] == "def new_helper():"
    assert utils_lines[2] == "    pass"
    assert (
        "def old_util():" in utils_content
    )  # Should still be there after insertion at top

    assert not (repo_path / "config.ini").exists()  # File should be deleted


def test_unicode_and_special_characters(git_repo):
    """Test handling of unicode and special characters in file content."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Unicode content

    hunk1 = HunkWrapper(
        new_file_path=b"unicode.txt",
        old_file_path=None,
        hunk_lines=[
            b"+Hello \xe4\xb8\x96\xe7\x95\x8c \xf0\x9f\x8c\x8d",
            b"+Caf\xc3\xa9 na\xc3\xafve r\xc3\xa9sum\xc3\xa9",
            b"+\xce\x95\xce\xbb\xce\xbb\xce\xb7\xce\xbd\xce\xb9\xce\xba\xce\xac \xd0\xa0\xd1\x83\xd1\x81\xd1\x81\xce\xba\xd0\xb8\xd0\xb9 \xd8\xa7\xd9\x84\xd8\xb9\xd8\xb1\xd8\xa8\xd9\x8a\xd8\xa9",
        ],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=3,
        file_mode=None,
    )
    chunk1 = hunk_to_chunk(hunk1)

    hunk2 = HunkWrapper(
        new_file_path=b"special.txt",
        old_file_path=None,
        hunk_lines=[
            b"+#!/bin/bash",
            b'+echo "$HOME"',
            b"+regex: [a-zA-Z0-9]+@[a-zA-Z0-9]+\\.[a-zA-Z]{2,}",
            b"+math: \xe2\x88\x91(x\xc2\xb2) = \xcf\x80/2",
        ],
        old_start=1,
        new_start=1,
        old_len=0,
        new_len=4,
        file_mode=None,
    )
    chunk2 = hunk_to_chunk(hunk2)

    group = CommitGroup(
        container=CompositeContainer([chunk1, chunk2]),
        commit_message="Unicode and special chars",
    )
    final_hash = synthesizer.execute_plan([chunk1, chunk2], [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify unicode content
    unicode_content = (repo_path / "unicode.txt").read_text(encoding="utf-8")
    assert "Hello 世界 🌍" in unicode_content
    assert "Café naïve résumé" in unicode_content
    assert "Ελληνικά Руссκий العربية" in unicode_content

    # Verify special characters
    special_content = (repo_path / "special.txt").read_text(encoding="utf-8")
    assert "#!/bin/bash" in special_content
    assert 'echo "$HOME"' in special_content
    assert "∑(x²) = π/2" in special_content


def test_conflicting_simultaneous_changes(git_repo):
    """Test handling of potentially conflicting changes to the same file regions."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Overlapping changes
    chunks = [
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"app.js",
                old_file_path=b"app.js",
                hunk_lines=[b"-line 2"],
                old_start=2,
                new_start=2,
                old_len=1,
                new_len=0,
                file_mode=None,
            )
        ),
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"app.js",
                old_file_path=b"app.js",
                hunk_lines=[b"+inserted line"],
                old_start=2,
                new_start=2,
                old_len=0,
                new_len=1,
                file_mode=None,
            )
        ),
        hunk_to_chunk(
            HunkWrapper(
                new_file_path=b"app.js",
                old_file_path=b"app.js",
                hunk_lines=[b"-line 3", b"+modified line 3"],
                old_start=3,
                new_start=3,
                old_len=1,
                new_len=1,
                file_mode=None,
            )
        ),
    ]

    group = CommitGroup(
        container=CompositeContainer(chunks),
        commit_message="Overlapping changes",
    )
    final_hash = synthesizer.execute_plan(chunks, [group], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Should handle overlapping changes gracefully
    content = (repo_path / "app.js").read_text()
    assert "line 2" not in content
    assert "inserted line" in content  # Inserted
    assert "modified line 3" in content  # Modified


def test_very_large_file_changes(git_repo):
    """Test performance with larger files and many changes."""
    repo_path, base_hash = git_repo
    git_cmds = GitCommands(GitInterface(repo_path))
    synthesizer = GitSynthesizer(
        git_cmds, MockFileManager([], git_cmds)
    )  # No chunks yet

    # Create a large file
    large_content = "\n".join([f"line {i}" for i in range(1, 101)])  # 100 lines
    (repo_path / "large.txt").write_text(large_content + "\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add large file"], cwd=repo_path, check=True)

    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    # Many separate contiguous chunks for modifications
    chunks = []

    # Chunks for each 10th line modification

    for i in range(10, 101, 10):
        hunk = HunkWrapper(
            new_file_path=b"large.txt",
            old_file_path=b"large.txt",
            hunk_lines=[f"-line {i}".encode(), f"+MODIFIED line {i}".encode()],
            old_start=i,
            new_start=i,
            old_len=1,
            new_len=1,
            file_mode=None,
        )
        chunk = hunk_to_chunk(hunk)
        chunks.append(chunk)

    # Chunks for insertions at various positions
    for i in [25, 50, 75]:
        hunk = HunkWrapper(
            new_file_path=b"large.txt",
            old_file_path=b"large.txt",
            hunk_lines=[f"+INSERTED at {i}".encode()],
            old_start=i - 1,
            new_start=i,
            old_len=0,
            new_len=1,
            file_mode=None,
        )
        chunk = hunk_to_chunk(hunk)
        chunks.append(chunk)

    group = CommitGroup(
        container=CompositeContainer(chunks),
        commit_message="Many changes to large file",
    )
    final_hash = synthesizer.execute_plan(chunks, [group], new_base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # Verify changes
    content = (repo_path / "large.txt").read_text()
    lines = content.split("\n")

    # Check that modifications exist (exact positions may vary due to insertions)
    modified_lines = [line for line in lines if "MODIFIED line" in line]
    assert len(modified_lines) == 10  # Should have 10 modified lines

    # Check that specific modifications exist
    assert "MODIFIED line 10" in modified_lines
    assert "MODIFIED line 50" in modified_lines
    assert "MODIFIED line 90" in modified_lines

    # Check insertions exist
    inserted_lines = [line for line in lines if "INSERTED at" in line]
    assert len(inserted_lines) == 3  # Should have 3 insertions
    assert "INSERTED at 25" in inserted_lines
    assert "INSERTED at 50" in inserted_lines
    assert "INSERTED at 75" in inserted_lines

    # Verify original unmodified lines still exist
    assert "line 5" in lines  # Should be unchanged (not every 10th)
    assert "line 15" in lines  # Should be unchanged (not every 10th)
    assert "line 35" in lines  # Should be unchanged (not every 10th)

    # Original modified lines should not exist anymore (every 10th line was modified)
    assert "line 10" not in lines  # Was modified to "MODIFIED line 10"
    assert "line 20" not in lines  # Was modified to "MODIFIED line 20"
    assert "line 90" not in lines  # Was modified to "MODIFIED line 90"
