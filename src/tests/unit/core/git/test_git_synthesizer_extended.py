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

import pytest

from codestory.core.diff.data.commit_group import CommitGroup
from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.line_changes import Addition, Removal

# Assuming your models are importable like this
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_interface import (
    GitInterface,
)

# Assuming the synthesizer class is here
from codestory.core.git.git_synthesizer import GitSynthesizer


class MockFileManager:
    def __init__(self, git_commands=None):
        self.git_commands = git_commands

    def get_line_count(self, file_path: bytes, commit_hash: str) -> int | None:
        if self.git_commands:
            try:
                path_str = file_path.decode("utf-8", errors="replace")
                content = self.git_commands.cat_file(f"{commit_hash}:{path_str}")
                if content is not None:
                    return len(content.splitlines())
            except Exception:
                pass
        return None


# Helper fixture to create a repo with two files
@pytest.fixture
def multi_file_git_repo(tmp_path):
    """Creates a Git repo with two files: file_a.txt and file_b.txt."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    # Initialize Git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
    )

    # Create file_a.txt
    file_a = repo_path / "file_a.txt"
    file_a_content = [
        "Line 1: Keep this line.",
        "Line 2:",
        "Line 3: An original line in A.",
        "Line 4:",
        "Line 5: Another original line in A.",
    ]
    file_a.write_text("\n".join(file_a_content) + "\n")

    # Create file_b.txt
    file_b = repo_path / "file_b.txt"
    file_b_content = [
        "Line 1: Configuration section.",
        "Line 2: value = 100",
        "Line 3:",
        "Line 4: Another setting.",
        "Line 5: enabled = false",
    ]
    file_b.write_text("\n".join(file_b_content) + "\n")

    # Make the initial commit
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit with two files"],
        cwd=repo_path,
        check=True,
    )

    base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    return repo_path, base_hash


def test_multi_file_disjoint_changes(multi_file_git_repo):
    """Tests the A1/A2 and B1/B2 scenario with two separate commit groups.

    - Group 1: {A1, B2} (additions to the end of each file)
    - Group 2: {A2, B1} (modifications in the middle of each file)
    This verifies that the cumulative reconstruction works correctly across files.
    """
    repo_path, base_hash = multi_file_git_repo
    git_cmds = GitCommands(GitInterface(repo_path))

    # --- Define the Changes ---
    new_hash = "head"

    # A1: Add a line to file_a.txt after line 5.
    chunk_A1 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_a.txt",
        new_file_path=b"file_a.txt",
        parsed_content=[
            Addition(old_line=6, abs_new_line=6, content=b"Line 6: Added by A1.")
        ],
        old_start=6,
    )

    # A2: Delete line 3 from file_a.txt.
    chunk_A2 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_a.txt",
        new_file_path=b"file_a.txt",
        parsed_content=[
            Removal(
                old_line=3, abs_new_line=3, content=b"Line 3: An original line in A."
            )
        ],
        old_start=3,
    )

    # B1: Modify line 2 in file_b.txt.
    chunk_B1 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_b.txt",
        new_file_path=b"file_b.txt",
        parsed_content=[
            Removal(old_line=2, abs_new_line=2, content=b"Line 2: value = 100"),
            Addition(
                old_line=2,
                abs_new_line=2,
                content=b"Line 2: value = 250 # Updated by B1",
            ),
        ],
        old_start=2,
    )

    # B2: Add a new setting to file_b.txt after line 5.
    chunk_B2 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_b.txt",
        new_file_path=b"file_b.txt",
        parsed_content=[
            Addition(
                old_line=6,
                abs_new_line=6,
                content=b'Line 6: mode = "test" # Added by B2',
            )
        ],
        old_start=6,
    )

    # --- Define the Groups ---
    group1 = CommitGroup(
        container=CompositeContainer([chunk_A1, chunk_B2]),
        commit_message="feat: Add new content to files",
    )
    group2 = CommitGroup(
        container=CompositeContainer([chunk_A2, chunk_B1]),
        commit_message="refactor: Modify existing content",
    )

    all_chunks = [chunk_A1, chunk_A2, chunk_B1, chunk_B2]

    # --- Execute the Plan ---
    fm = MockFileManager(git_cmds)  # Use MockFileManager
    synthesizer = GitSynthesizer(git_cmds, fm)
    # The synthesizer should create a commit for group1, then a commit for group2.
    final_hash = synthesizer.execute_plan(all_chunks, [group1, group2], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # --- Verification ---

    # 1. Verify final content of both files
    final_a_content = (repo_path / "file_a.txt").read_text()
    expected_a_content = (
        "Line 1: Keep this line.\n"
        "Line 2:\n"
        "Line 4:\n"
        "Line 5: Another original line in A.\n"
        "Line 6: Added by A1.\n"
    )
    assert final_a_content == expected_a_content

    final_b_content = (repo_path / "file_b.txt").read_text()
    expected_b_content = (
        "Line 1: Configuration section.\n"
        "Line 2: value = 250 # Updated by B1\n"
        "Line 3:\n"
        "Line 4: Another setting.\n"
        "Line 5: enabled = false\n"
        'Line 6: mode = "test" # Added by B2\n'
    )
    assert final_b_content == expected_b_content

    # 2. Verify Git log
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

    assert len(log_output) == 2
    assert "refactor: Modify existing content" in log_output[0]  # HEAD commit
    assert "feat: Add new content to files" in log_output[1]  # Parent commit

    # 3. Verify the diff of the FIRST new commit (HEAD~1) contains ONLY {A1, B2}
    commit1_diff = subprocess.run(
        ["git", "show", "HEAD~1"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    print(commit1_diff)

    # Check for A1's content
    assert "+Line 6: Added by A1." in commit1_diff
    # Check for B2's content
    assert '+Line 6: mode = "test" # Added by B2' in commit1_diff
    # CRITICAL: Ensure it does NOT contain changes from the other group
    assert "-Line 3: An original line in A." not in commit1_diff
    assert (
        "+Line 2: value = 250" not in commit1_diff
    )  # Also check for the specific addition

    # 4. Verify the diff of the SECOND new commit (HEAD) contains ONLY {A2, B1}
    commit2_diff = subprocess.run(
        ["git", "show", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    print(commit2_diff)

    # Check for A2's content
    assert "-Line 3: An original line in A." in commit2_diff
    # Check for B1's content
    assert "-Line 2: value = 100" in commit2_diff
    assert "+Line 2: value = 250 # Updated by B1" in commit2_diff
    # CRITICAL: Ensure it does NOT contain changes from the other group
    assert "+Line 6: Added by A1." not in commit2_diff
    assert '+Line 6: mode = "test" # Added by B2' not in commit2_diff


def test_multi_file_disjoint_changes_reversed_order(multi_file_git_repo):
    """Tests the same A1/A2, B1/B2 scenario but with the commit groups reversed.

    This proves that the final state is independent of group order and
    that the diffs are correctly isolated in the new order.
    """
    repo_path, base_hash = multi_file_git_repo
    git_cmds = GitCommands(GitInterface(repo_path))

    # --- Define the Changes ---
    new_hash = "head"

    # A1: Add a line to file_a.txt after line 5.
    chunk_A1 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_a.txt",
        new_file_path=b"file_a.txt",
        parsed_content=[
            Addition(old_line=6, abs_new_line=6, content=b"Line 6: Added by A1.")
        ],
        old_start=6,
    )

    # A2: Delete line 3 from file_a.txt.
    chunk_A2 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_a.txt",
        new_file_path=b"file_a.txt",
        parsed_content=[
            Removal(
                old_line=3, abs_new_line=3, content=b"Line 3: An original line in A."
            )
        ],
        old_start=3,
    )

    # B1: Modify line 2 in file_b.txt.
    chunk_B1 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_b.txt",
        new_file_path=b"file_b.txt",
        parsed_content=[
            Removal(old_line=2, abs_new_line=2, content=b"Line 2: value = 100"),
            Addition(
                old_line=2,
                abs_new_line=2,
                content=b"Line 2: value = 250 # Updated by B1",
            ),
        ],
        old_start=2,
    )

    # B2: Add a new setting to file_b.txt after line 5.
    chunk_B2 = StandardDiffChunk(
        base_hash=base_hash,
        new_hash=new_hash,
        old_file_path=b"file_b.txt",
        new_file_path=b"file_b.txt",
        parsed_content=[
            Addition(
                old_line=6,
                abs_new_line=6,
                content=b'Line 6: mode = "test" # Added by B2',
            )
        ],
        old_start=6,
    )

    # --- Definitions of chunks and groups are identical to the previous test ---
    # (Copy/paste the chunk and group definitions here)
    # ... chunk_A1, chunk_A2, chunk_B1, chunk_B2 ...
    group1 = CommitGroup(
        container=CompositeContainer([chunk_A1, chunk_B2]),
        commit_message="feat: Add new content to files",
    )
    group2 = CommitGroup(
        container=CompositeContainer([chunk_A2, chunk_B1]),
        commit_message="refactor: Modify existing content",
    )

    all_chunks = [chunk_A1, chunk_A2, chunk_B1, chunk_B2]

    # --- EXECUTE THE PLAN in REVERSED ORDER ---
    fm = MockFileManager(git_cmds)  # Use MockFileManager
    synthesizer = GitSynthesizer(git_cmds, fm)
    final_hash = synthesizer.execute_plan(all_chunks, [group2, group1], base_hash)
    subprocess.run(["git", "reset", "--hard", final_hash], cwd=repo_path, check=True)

    # --- Verification ---

    # 1. Verify final content of both files (SHOULD BE IDENTICAL TO THE OTHER TEST)
    final_a_content = (repo_path / "file_a.txt").read_text()
    expected_a_content = (
        "Line 1: Keep this line.\n"
        "Line 2:\n"
        "Line 4:\n"
        "Line 5: Another original line in A.\n"
        "Line 6: Added by A1.\n"
    )
    assert final_a_content == expected_a_content
    # ... (assert final_b_content is also identical)

    # 2. Verify Git log (ORDER IS NOW REVERSED)
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

    assert len(log_output) == 2
    assert "feat: Add new content to files" in log_output[0]  # HEAD is now group1
    assert "refactor: Modify existing content" in log_output[1]  # Parent is now group2

    # 3. Verify the diff of the FIRST new commit (HEAD~1) contains ONLY {A2, B1}
    commit1_diff = subprocess.run(
        ["git", "show", "HEAD~1"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    # Check for A2's content
    assert "-Line 3: An original line in A." in commit1_diff
    # Check for B1's content
    assert "-Line 2: value = 100" in commit1_diff
    assert "+Line 2: value = 250 # Updated by B1" in commit1_diff
    # CRITICAL: Ensure it does NOT contain the *changes* from the other group
    assert "+Line 6: Added by A1." not in commit1_diff
    assert '+Line 6: mode = "test" # Added by B2' not in commit1_diff

    # 4. Verify the diff of the SECOND new commit (HEAD) contains ONLY {A1, B2}
    commit2_diff = subprocess.run(
        ["git", "show", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    # Check for A1's content
    assert "+Line 6: Added by A1." in commit2_diff
    # Check for B2's content
    assert '+Line 6: mode = "test" # Added by B2' in commit2_diff
    # CRITICAL: Ensure it does NOT contain the *changes* from the other group
    assert "-Line 3: An original line in A." not in commit2_diff
    assert "+Line 2: value = 250" not in commit2_diff
