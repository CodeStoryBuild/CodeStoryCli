"""
End-to-end tests for AIGitPipeline.run() method.

These tests create temporary git repositories and test the complete pipeline
from git diff extraction through chunking, grouping, and commit synthesis.
"""

import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.pipeline.runner import AIGitPipeline
from .test_helpers import DeterministicChunker, DeterministicGrouper


# --- Test Fixtures ---


@pytest.fixture
def complex_git_repo():
    """Create a complex git repository with multiple files for comprehensive testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
        )

        # Create initial project structure
        (repo_path / "src").mkdir()
        (repo_path / "tests").mkdir()
        (repo_path / "docs").mkdir()

        # Create initial files
        files_content = {
            "README.md": "# Test Project\n\nEnd-to-end testing project.\n",
            "src/main.py": "#!/usr/bin/env python3\n\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()\n",
            "src/utils.py": "def helper_function():\n    return 'helper'\n\ndef another_helper():\n    return 'another'\n",
            "tests/test_main.py": "import unittest\nfrom src.main import main\n\nclass TestMain(unittest.TestCase):\n    def test_main(self):\n        pass\n",
            "docs/api.md": "# API Documentation\n\n## Functions\n\n- main(): Entry point\n",
            ".gitignore": "*.pyc\n__pycache__/\n.pytest_cache/\n",
        }

        for file_path, content in files_content.items():
            full_path = repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
        )

        yield repo_path


@pytest.fixture
def mock_inquirer_accept_all():
    """Mock inquirer to accept all prompts automatically."""
    with patch("inquirer.confirm") as mock_confirm:
        mock_confirm.return_value = True
        yield mock_confirm


# --- Test Cases ---


def test_runner_basic_file_modification(complex_git_repo, mock_inquirer_accept_all):
    """Test basic file modification through the complete pipeline."""
    repo_path = complex_git_repo

    # Make changes to a file
    main_file = repo_path / "src" / "main.py"
    new_content = main_file.read_text().replace(
        "print('Hello, World!')",
        "print('Hello, Universe!')\n    # SPLIT_HERE\n    print('Testing chunking')",
    )
    main_file.write_text(new_content)

    # Setup pipeline with deterministic components
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker(split_keywords=["SPLIT_HERE"])
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=2)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 0

    # Check that commits were made
    log_output = subprocess.run(
        ["git", "log", "--oneline", "--since", "1 minute ago"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert log_output  # Should have new commits
    assert (
        "src/main.py" in log_output or "Modify" in log_output or "Update" in log_output
    )

    # Verify file was actually changed
    final_content = main_file.read_text()
    assert "Hello, Universe!" in final_content
    assert "Testing chunking" in final_content


def test_runner_multiple_files_complex_changes(
    complex_git_repo, mock_inquirer_accept_all
):
    """Test complex changes across multiple files."""
    repo_path = complex_git_repo

    # Make changes to multiple files
    changes = {
        "src/main.py": "#!/usr/bin/env python3\n\n# New feature addition\ndef new_feature():\n    return 'new feature'\n\ndef main():\n    print('Hello, Modified World!')\n    new_feature()\n\nif __name__ == '__main__':\n    main()\n",
        "src/utils.py": "# Refactored utilities\ndef helper_function():\n    return 'updated helper'\n\ndef another_helper():\n    return 'another updated'\n\n# SPLIT_HERE\ndef third_helper():\n    return 'third'\n",
        "tests/test_main.py": "import unittest\nfrom src.main import main, new_feature\n\nclass TestMain(unittest.TestCase):\n    def test_main(self):\n        self.assertIsNotNone(main())\n    \n    def test_new_feature(self):\n        self.assertEqual(new_feature(), 'new feature')\n",
        "docs/api.md": "# API Documentation\n\n## Functions\n\n- main(): Entry point (updated)\n- new_feature(): New functionality\n- helper_function(): Updated helper\n",
    }

    for file_path, content in changes.items():
        (repo_path / file_path).write_text(content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker(split_keywords=["SPLIT_HERE"])
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=2)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) >= 4  # Should have multiple commits for different files

    # Check commit history
    log_output = (
        subprocess.run(
            ["git", "log", "--oneline", "--since", "1 minute ago"],
            cwd=repo_path,
            text=True,
            capture_output=True,
        )
        .stdout.strip()
        .splitlines()
    )

    assert len(log_output) >= 4

    # Verify all files were changed
    for file_path, expected_content in changes.items():
        actual_content = (repo_path / file_path).read_text()
        assert actual_content == expected_content


def test_runner_with_file_deletion_and_addition(
    complex_git_repo, mock_inquirer_accept_all
):
    """Test pipeline with file deletions and new file additions."""
    repo_path = complex_git_repo

    # Remove an existing file
    (repo_path / "docs" / "api.md").unlink()

    # Add new files
    new_files = {
        "src/config.py": "# Configuration module\nCONFIG = {\n    'debug': True,\n    'version': '1.0.0'\n}\n",
        "tests/test_utils.py": "import unittest\nfrom src.utils import helper_function\n\nclass TestUtils(unittest.TestCase):\n    def test_helper(self):\n        self.assertEqual(helper_function(), 'helper')\n",
        "requirements.txt": "pytest>=6.0.0\nrequests>=2.25.0\n",
    }

    for file_path, content in new_files.items():
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Modify existing file too
    utils_file = repo_path / "src" / "utils.py"
    utils_content = utils_file.read_text().replace("'helper'", "'updated helper'")
    utils_file.write_text(utils_content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=3)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 0

    # Check that deleted file is gone and new files exist
    assert not (repo_path / "docs" / "api.md").exists()
    for file_path in new_files.keys():
        assert (repo_path / file_path).exists()

    # Verify commits were made
    log_output = subprocess.run(
        ["git", "log", "--oneline", "--since", "1 minute ago"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert log_output


def test_runner_with_file_deletion(complex_git_repo, mock_inquirer_accept_all):
    """Test pipeline with file deletion only."""
    repo_path = complex_git_repo

    # Remove files
    (repo_path / "docs" / "api.md").unlink()
    (repo_path / "src" / "utils.py").unlink()

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper(group_by_file=True)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 0

    # Check that files were deleted
    assert not (repo_path / "docs" / "api.md").exists()
    assert not (repo_path / "src" / "utils.py").exists()

    # Verify commits were made for deletions
    log_output = subprocess.run(
        ["git", "log", "--oneline", "--since", "1 minute ago"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    ).stdout.strip()

    assert log_output

    # Verify the deleted files are tracked in git history
    status_output = subprocess.run(
        ["git", "status", "--short"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # After pipeline runs and commits, there should be no pending changes
    assert status_output == ""


def test_runner_with_file_rename(complex_git_repo):
    """Test pipeline with file renames (more complex scenario)."""
    repo_path = complex_git_repo

    # Rename a file using git mv (this creates a rename diff)
    subprocess.run(
        ["git", "mv", "src/utils.py", "src/utilities.py"], cwd=repo_path, check=True
    )

    # Also modify the renamed file
    renamed_file = repo_path / "src" / "utilities.py"
    content = renamed_file.read_text()
    modified_content = (
        content
        + "\n# File was renamed and modified\ndef new_utility():\n    return 'new utility'\n"
    )
    renamed_file.write_text(modified_content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper(group_by_file=True)

    # Mock inquirer to accept the changes
    with patch("inquirer.confirm") as mock_confirm:
        mock_confirm.return_value = True

        pipeline = AIGitPipeline(git_interface, chunker, grouper)
        results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 0

    # Check that rename was successful
    assert not (repo_path / "src" / "utils.py").exists()
    assert (repo_path / "src" / "utilities.py").exists()

    # Verify content includes both old and new content
    final_content = (repo_path / "src" / "utilities.py").read_text()
    assert "def helper_function():" in final_content
    assert "new_utility" in final_content


def test_runner_content_based_grouping(complex_git_repo, mock_inquirer_accept_all):
    """Test pipeline with content-based grouping strategy."""
    repo_path = complex_git_repo

    # Make changes that should be grouped by content patterns
    changes = {
        "src/main.py": "#!/usr/bin/env python3\n\n# New feature: add logging\ndef main():\n    print('Hello, World!')\n    print('Feature: Logging added')\n\nif __name__ == '__main__':\n    main()\n",
        "src/utils.py": "# Bug fix: fix helper function\ndef helper_function():\n    return 'fixed helper'\n\ndef another_helper():\n    return 'another'\n",
        "tests/test_main.py": "import unittest\nfrom src.main import main\n\n# Refactor: improved test structure\nclass TestMain(unittest.TestCase):\n    def setUp(self):\n        self.main = main\n    \n    def test_main(self):\n        self.assertIsNotNone(self.main())\n",
    }

    for file_path, content in changes.items():
        (repo_path / file_path).write_text(content)

    # Setup pipeline with content-based grouping
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper(
        group_by_file=False, max_chunks_per_group=2
    )  # Content-based grouping

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 0

    # Check that commits were grouped by content type
    commit_messages = []
    for result in results:
        commit_messages.append(result.group.commmit_message)

    # Should have different types of commits based on content
    message_text = " ".join(commit_messages).lower()
    patterns_found = []
    if "feature" in message_text:
        patterns_found.append("feature")
    if "fix" in message_text or "bug" in message_text:
        patterns_found.append("fix")
    if "refactor" in message_text:
        patterns_found.append("refactor")

    assert len(patterns_found) >= 2  # Should detect multiple content patterns


def test_runner_handles_no_changes(complex_git_repo):
    """Test that pipeline handles case with no changes gracefully."""
    repo_path = complex_git_repo

    # Don't make any changes
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper()

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Mock inquirer in case it gets called
    with patch("inquirer.confirm") as mock_confirm:
        mock_confirm.return_value = True
        results = pipeline.run()

    # Should handle no changes gracefully (might return empty list or None)
    # The exact behavior depends on implementation
    if results is not None:
        assert isinstance(results, list)


def test_runner_with_staged_changes_reset(complex_git_repo):
    """Test pipeline behavior when there are pre-staged changes."""
    repo_path = complex_git_repo

    # Make some changes and stage them
    main_file = repo_path / "src" / "main.py"
    new_content = main_file.read_text().replace("Hello, World!", "Hello, Staged!")
    main_file.write_text(new_content)
    subprocess.run(["git", "add", "src/main.py"], cwd=repo_path, check=True)

    # Make additional unstaged changes
    utils_file = repo_path / "src" / "utils.py"
    utils_content = utils_file.read_text() + "\n# Unstaged change\n"
    utils_file.write_text(utils_content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker()
    grouper = DeterministicGrouper()

    # Mock inquirer to accept reset and continue
    with patch("inquirer.confirm") as mock_confirm:
        mock_confirm.return_value = True

        pipeline = AIGitPipeline(git_interface, chunker, grouper)
        results = pipeline.run()

    # Verify that pipeline handled the situation
    # Should either reset and process, or handle appropriately
    assert mock_confirm.called  # Should have prompted about staged changes


def test_runner_chunking_and_grouping_integration(
    complex_git_repo, mock_inquirer_accept_all
):
    """Test integration between chunking and grouping with complex scenarios."""
    repo_path = complex_git_repo

    # Create changes that will test chunking behavior
    complex_file_content = """#!/usr/bin/env python3

# First feature: authentication
def authenticate(user):
    if user.is_valid():
        return True
    return False

# SPLIT_HERE - this should trigger chunking

# Second feature: authorization  
def authorize(user, resource):
    if user.has_permission(resource):
        return True
    return False

def main():
    print('Hello, Complex World!')
    # SPLIT_HERE
    print('Multiple features added')

if __name__ == '__main__':
    main()
"""

    (repo_path / "src" / "main.py").write_text(complex_file_content)

    # Setup pipeline with splitting enabled
    git_interface = SubprocessGitInterface(repo_path)
    chunker = DeterministicChunker(
        split_keywords=["SPLIT_HERE"]
    )  # Will split at SPLIT_HERE
    grouper = DeterministicGrouper(
        group_by_file=True, max_chunks_per_group=1
    )  # One chunk per group

    pipeline = AIGitPipeline(git_interface, chunker, grouper)

    # Run the pipeline
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) > 1  # Should have multiple commits due to chunking and grouping

    # Each commit should be small due to chunking and grouping limits
    for result in results:
        assert len(result.group.chunks) <= 1  # Max chunks per group is 1

    # Verify final file state
    final_content = (repo_path / "src" / "main.py").read_text()
    assert "authenticate" in final_content
    assert "authorize" in final_content
    assert "Complex World" in final_content
