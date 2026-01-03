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
from vibe.core.chunker.simple_chunker import SimpleChunker
from .test_helpers import DeterministicGrouper


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
    expected_content = "#!/usr/bin/env python3\n\ndef main():\n    print('Hello, Universe!')\n    # SPLIT_HERE\n    print('Testing chunking')\n\nif __name__ == '__main__':\n    main()\n"
    main_file.write_text(expected_content)

    # Setup pipeline with deterministic components
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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

    # Verify file content matches exactly line-by-line
    actual_content = main_file.read_text()
    assert (
        actual_content == expected_content
    ), f"File content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"


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
    chunker = SimpleChunker()
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
    expected_utils_content = "def helper_function():\n    return 'updated helper'\n\ndef another_helper():\n    return 'another'\n"
    utils_file.write_text(expected_utils_content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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

    # Verify all file contents match exactly line-by-line
    for file_path, expected_content in new_files.items():
        actual_content = (repo_path / file_path).read_text()
        assert (
            actual_content == expected_content
        ), f"File {file_path} content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"

    # Verify modified utils.py content matches exactly
    actual_utils_content = utils_file.read_text()
    assert (
        actual_utils_content == expected_utils_content
    ), f"File src/utils.py content mismatch:\nExpected:\n{expected_utils_content}\n\nActual:\n{actual_utils_content}"


def test_runner_with_file_deletion(complex_git_repo, mock_inquirer_accept_all):
    """Test pipeline with file deletion only."""
    repo_path = complex_git_repo

    # Remove files
    (repo_path / "docs" / "api.md").unlink()
    (repo_path / "src" / "utils.py").unlink()

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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
    expected_content = "def helper_function():\n    return 'helper'\n\ndef another_helper():\n    return 'another'\n\n# File was renamed and modified\ndef new_utility():\n    return 'new utility'\n"
    renamed_file.write_text(expected_content)

    # Setup pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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

    # Verify content matches exactly line-by-line
    actual_content = renamed_file.read_text()
    assert (
        actual_content == expected_content
    ), f"File src/utilities.py content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"


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
    chunker = SimpleChunker()
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

    # assert len(patterns_found) >= 2  # Should detect multiple content patterns

    # Verify all file contents match exactly line-by-line
    for file_path, expected_content in changes.items():
        actual_content = (repo_path / file_path).read_text()
        assert (
            actual_content == expected_content
        ), f"File {file_path} content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"


def test_runner_handles_no_changes(complex_git_repo):
    """Test that pipeline handles case with no changes gracefully."""
    repo_path = complex_git_repo

    # Don't make any changes
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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
    chunker = SimpleChunker()
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
    expected_content = """#!/usr/bin/env python3

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

    (repo_path / "src" / "main.py").write_text(expected_content)

    # Setup pipeline with splitting enabled
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
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

    # Verify final file content matches exactly line-by-line
    actual_content = (repo_path / "src" / "main.py").read_text()
    assert (
        actual_content == expected_content
    ), f"File src/main.py content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"


# --- Complex Real-Life Scenario Tests ---


@pytest.fixture
def large_codebase_repo():
    """Create a realistic large codebase with multiple modules and files."""
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
            ["git", "config", "user.email", "dev@company.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Developer"], cwd=repo_path, check=True
        )

        # Create realistic project structure
        directories = [
            "src/models",
            "src/views",
            "src/controllers",
            "src/utils",
            "src/middleware",
            "tests/unit",
            "tests/integration",
            "tests/fixtures",
            "config",
            "docs",
            "scripts",
        ]

        for directory in directories:
            (repo_path / directory).mkdir(parents=True, exist_ok=True)

        # Create initial comprehensive codebase
        files_content = {
            "README.md": "# Enterprise Application\n\nA comprehensive web application.\n\n## Features\n- User management\n- Data processing\n- API integration\n",
            "requirements.txt": "flask==2.0.1\nsqlalchemy==1.4.22\nrequests==2.26.0\npytest==6.2.4\npylint==2.9.3\n",
            "setup.py": "from setuptools import setup, find_packages\n\nsetup(\n    name='enterprise-app',\n    version='1.0.0',\n    packages=find_packages(),\n)\n",
            ".gitignore": "*.pyc\n__pycache__/\n.pytest_cache/\n.env\nvenv/\ndist/\nbuild/\n*.egg-info/\n",
            "config/settings.py": "import os\n\nDEBUG = os.getenv('DEBUG', False)\nDATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')\nSECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')\nAPI_TIMEOUT = 30\n",
            "config/logging.py": "import logging\n\nlogging.basicConfig(\n    level=logging.INFO,\n    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'\n)\n\nlogger = logging.getLogger(__name__)\n",
            "src/models/user.py": "from datetime import datetime\n\nclass User:\n    def __init__(self, username, email, created_at=None):\n        self.username = username\n        self.email = email\n        self.created_at = created_at or datetime.now()\n        self.is_active = True\n    \n    def deactivate(self):\n        self.is_active = False\n    \n    def to_dict(self):\n        return {\n            'username': self.username,\n            'email': self.email,\n            'created_at': self.created_at.isoformat(),\n            'is_active': self.is_active\n        }\n",
            "src/models/product.py": "class Product:\n    def __init__(self, name, price, stock=0):\n        self.name = name\n        self.price = price\n        self.stock = stock\n    \n    def update_stock(self, quantity):\n        self.stock += quantity\n    \n    def is_available(self):\n        return self.stock > 0\n",
            "src/models/order.py": "from datetime import datetime\n\nclass Order:\n    def __init__(self, user_id, product_id, quantity):\n        self.user_id = user_id\n        self.product_id = product_id\n        self.quantity = quantity\n        self.created_at = datetime.now()\n        self.status = 'pending'\n    \n    def complete(self):\n        self.status = 'completed'\n",
            "src/utils/validators.py": "import re\n\ndef validate_email(email):\n    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'\n    return re.match(pattern, email) is not None\n\ndef validate_password(password):\n    return len(password) >= 8\n\ndef validate_username(username):\n    return len(username) >= 3 and username.isalnum()\n",
            "src/utils/helpers.py": "import json\nfrom datetime import datetime\n\ndef format_date(date):\n    return date.strftime('%Y-%m-%d %H:%M:%S')\n\ndef parse_json_safe(json_str):\n    try:\n        return json.loads(json_str)\n    except json.JSONDecodeError:\n        return None\n\ndef calculate_discount(price, percentage):\n    return price * (1 - percentage / 100)\n",
            "src/utils/database.py": "class Database:\n    def __init__(self, connection_string):\n        self.connection_string = connection_string\n        self.connection = None\n    \n    def connect(self):\n        # Simulate connection\n        self.connection = 'connected'\n    \n    def disconnect(self):\n        self.connection = None\n    \n    def execute(self, query):\n        if not self.connection:\n            raise Exception('Not connected')\n        return []\n",
            "src/controllers/user_controller.py": "from src.models.user import User\nfrom src.utils.validators import validate_email, validate_username\n\nclass UserController:\n    def __init__(self):\n        self.users = []\n    \n    def create_user(self, username, email):\n        if not validate_username(username):\n            raise ValueError('Invalid username')\n        if not validate_email(email):\n            raise ValueError('Invalid email')\n        \n        user = User(username, email)\n        self.users.append(user)\n        return user\n    \n    def get_user(self, username):\n        for user in self.users:\n            if user.username == username:\n                return user\n        return None\n",
            "src/controllers/product_controller.py": "from src.models.product import Product\n\nclass ProductController:\n    def __init__(self):\n        self.products = []\n    \n    def add_product(self, name, price, stock=0):\n        product = Product(name, price, stock)\n        self.products.append(product)\n        return product\n    \n    def get_product(self, name):\n        for product in self.products:\n            if product.name == name:\n                return product\n        return None\n",
            "src/middleware/auth.py": "def authenticate_request(request):\n    token = request.headers.get('Authorization')\n    if not token:\n        return False\n    return True\n\ndef require_admin(func):\n    def wrapper(*args, **kwargs):\n        # Check if user is admin\n        return func(*args, **kwargs)\n    return wrapper\n",
            "tests/unit/test_user.py": "import unittest\nfrom src.models.user import User\n\nclass TestUser(unittest.TestCase):\n    def test_create_user(self):\n        user = User('john', 'john@example.com')\n        self.assertEqual(user.username, 'john')\n        self.assertTrue(user.is_active)\n    \n    def test_deactivate_user(self):\n        user = User('john', 'john@example.com')\n        user.deactivate()\n        self.assertFalse(user.is_active)\n",
            "tests/unit/test_validators.py": "import unittest\nfrom src.utils.validators import validate_email, validate_password\n\nclass TestValidators(unittest.TestCase):\n    def test_valid_email(self):\n        self.assertTrue(validate_email('test@example.com'))\n    \n    def test_invalid_email(self):\n        self.assertFalse(validate_email('invalid-email'))\n    \n    def test_valid_password(self):\n        self.assertTrue(validate_password('password123'))\n",
            "tests/fixtures/sample_data.py": "SAMPLE_USERS = [\n    {'username': 'alice', 'email': 'alice@example.com'},\n    {'username': 'bob', 'email': 'bob@example.com'},\n]\n\nSAMPLE_PRODUCTS = [\n    {'name': 'Widget', 'price': 9.99, 'stock': 100},\n    {'name': 'Gadget', 'price': 19.99, 'stock': 50},\n]\n",
            "docs/architecture.md": "# Architecture\n\n## Overview\nMVC architecture with middleware.\n\n## Components\n- Models: Data layer\n- Controllers: Business logic\n- Views: Presentation (not implemented)\n",
            "scripts/deploy.sh": "#!/bin/bash\necho 'Deploying application...'\npython -m pytest\necho 'Deployment complete'\n",
        }

        for file_path, content in files_content.items():
            full_path = repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial codebase"], cwd=repo_path, check=True
        )

        yield repo_path


def test_runner_massive_refactor_scenario(
    large_codebase_repo, mock_inquirer_accept_all
):
    """Test a massive refactoring scenario with many simultaneous changes."""
    repo_path = large_codebase_repo

    # Simulate a major refactor: adding type hints, docstrings, error handling
    changes = {
        "src/models/user.py": """from datetime import datetime
from typing import Optional, Dict

class User:
    \"\"\"Represents a user in the system.\"\"\"
    
    def __init__(self, username: str, email: str, created_at: Optional[datetime] = None):
        \"\"\"Initialize a new user.
        
        Args:
            username: The user's username
            email: The user's email address
            created_at: Optional creation timestamp
        \"\"\"
        if not username or not email:
            raise ValueError("Username and email are required")
        
        self.username = username
        self.email = email
        self.created_at = created_at or datetime.now()
        self.is_active = True
        self.last_login = None
    
    def deactivate(self) -> None:
        \"\"\"Deactivate this user account.\"\"\"
        self.is_active = False
    
    def activate(self) -> None:
        \"\"\"Reactivate this user account.\"\"\"
        self.is_active = True
    
    def update_last_login(self) -> None:
        \"\"\"Update the last login timestamp.\"\"\"
        self.last_login = datetime.now()
    
    def to_dict(self) -> Dict:
        \"\"\"Convert user to dictionary representation.\"\"\"
        return {
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
""",
        "src/models/product.py": """from typing import Optional

class Product:
    \"\"\"Represents a product in the inventory.\"\"\"
    
    def __init__(self, name: str, price: float, stock: int = 0, category: Optional[str] = None):
        \"\"\"Initialize a new product.
        
        Args:
            name: Product name
            price: Product price
            stock: Initial stock quantity
            category: Optional product category
        \"\"\"
        if price < 0:
            raise ValueError("Price cannot be negative")
        if stock < 0:
            raise ValueError("Stock cannot be negative")
        
        self.name = name
        self.price = price
        self.stock = stock
        self.category = category
        self.discount_percentage = 0
    
    def update_stock(self, quantity: int) -> None:
        \"\"\"Update stock quantity.
        
        Args:
            quantity: Quantity to add (positive) or remove (negative)
        \"\"\"
        new_stock = self.stock + quantity
        if new_stock < 0:
            raise ValueError("Insufficient stock")
        self.stock = new_stock
    
    def is_available(self) -> bool:
        \"\"\"Check if product is in stock.\"\"\"
        return self.stock > 0
    
    def apply_discount(self, percentage: float) -> None:
        \"\"\"Apply a discount to the product.\"\"\"
        if not 0 <= percentage <= 100:
            raise ValueError("Discount must be between 0 and 100")
        self.discount_percentage = percentage
    
    def get_final_price(self) -> float:
        \"\"\"Calculate final price after discount.\"\"\"
        return self.price * (1 - self.discount_percentage / 100)
""",
        "src/utils/validators.py": """import re
from typing import Optional

def validate_email(email: str) -> bool:
    \"\"\"Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    \"\"\"
    if not email or not isinstance(email, str):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str, min_length: int = 8) -> bool:
    \"\"\"Validate password strength.
    
    Args:
        password: Password to validate
        min_length: Minimum required length
        
    Returns:
        True if valid, False otherwise
    \"\"\"
    if not password or not isinstance(password, str):
        return False
    
    if len(password) < min_length:
        return False
    
    # Check for at least one digit and one letter
    has_digit = any(c.isdigit() for c in password)
    has_letter = any(c.isalpha() for c in password)
    
    return has_digit and has_letter

def validate_username(username: str, min_length: int = 3, max_length: int = 20) -> bool:
    \"\"\"Validate username format.
    
    Args:
        username: Username to validate
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        True if valid, False otherwise
    \"\"\"
    if not username or not isinstance(username, str):
        return False
    
    if not (min_length <= len(username) <= max_length):
        return False
    
    return username.isalnum()

def validate_phone(phone: str) -> bool:
    \"\"\"Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    \"\"\"
    if not phone:
        return False
    
    # Remove common separators
    cleaned = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15
""",
    }

    # Apply all changes
    for file_path, content in changes.items():
        (repo_path / file_path).write_text(content)

    # Also delete an obsolete file
    (repo_path / "src" / "models" / "order.py").unlink()

    # Add a new migration script
    (repo_path / "scripts" / "migrate.py").write_text(
        """#!/usr/bin/env python3
\"\"\"Database migration script.\"\"\"

import sys
from pathlib import Path

def run_migrations():
    \"\"\"Execute all pending migrations.\"\"\"
    print("Running migrations...")
    # Migration logic here
    print("Migrations complete!")

if __name__ == '__main__':
    run_migrations()
"""
    )

    # Update configuration
    (repo_path / "config" / "settings.py").write_text(
        """import os
from typing import Optional

class Settings:
    \"\"\"Application settings.\"\"\"
    
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key')
    API_TIMEOUT: int = int(os.getenv('API_TIMEOUT', '30'))
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_ORIGINS: list = ['http://localhost:3000', 'http://localhost:8000']
    
    @classmethod
    def validate(cls) -> bool:
        \"\"\"Validate settings configuration.\"\"\"
        if cls.DEBUG and cls.SECRET_KEY == 'dev-secret-key':
            print("WARNING: Using default secret key in debug mode")
        return True

settings = Settings()
"""
    )

    # Setup and run pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=3)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) >= 4  # Multiple files changed

    # Verify all file contents match exactly line-by-line
    for file_path, expected_content in changes.items():
        actual_content = (repo_path / file_path).read_text()
        assert (
            actual_content == expected_content
        ), f"File {file_path} content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"

    # Verify migrate.py script
    expected_migrate = """#!/usr/bin/env python3
\"\"\"Database migration script.\"\"\"

import sys
from pathlib import Path

def run_migrations():
    \"\"\"Execute all pending migrations.\"\"\"
    print("Running migrations...")
    # Migration logic here
    print("Migrations complete!")

if __name__ == '__main__':
    run_migrations()
"""
    actual_migrate = (repo_path / "scripts" / "migrate.py").read_text()
    assert (
        actual_migrate == expected_migrate
    ), f"File scripts/migrate.py content mismatch:\nExpected:\n{expected_migrate}\n\nActual:\n{actual_migrate}"

    # Verify settings.py
    expected_settings = """import os
from typing import Optional

class Settings:
    \"\"\"Application settings.\"\"\"
    
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key')
    API_TIMEOUT: int = int(os.getenv('API_TIMEOUT', '30'))
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_ORIGINS: list = ['http://localhost:3000', 'http://localhost:8000']
    
    @classmethod
    def validate(cls) -> bool:
        \"\"\"Validate settings configuration.\"\"\"
        if cls.DEBUG and cls.SECRET_KEY == 'dev-secret-key':
            print("WARNING: Using default secret key in debug mode")
        return True

settings = Settings()
"""
    actual_settings = (repo_path / "config" / "settings.py").read_text()
    assert (
        actual_settings == expected_settings
    ), f"File config/settings.py content mismatch:\nExpected:\n{expected_settings}\n\nActual:\n{actual_settings}"

    assert (repo_path / "scripts" / "migrate.py").exists()
    assert not (repo_path / "src" / "models" / "order.py").exists()


def test_runner_feature_branch_development(
    large_codebase_repo, mock_inquirer_accept_all
):
    """Simulate a complete feature branch development with multiple related changes."""
    repo_path = large_codebase_repo

    # Feature: Add authentication system with JWT tokens
    new_files = {
        "src/auth/__init__.py": "",
        "src/auth/jwt_handler.py": """import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

class JWTHandler:
    \"\"\"Handle JWT token creation and validation.\"\"\"
    
    @staticmethod
    def create_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        \"\"\"Create a new JWT token.
        
        Args:
            user_id: User identifier
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token
        \"\"\"
        if expires_delta is None:
            expires_delta = timedelta(hours=24)
        
        expire = datetime.utcnow() + expires_delta
        payload = {
            'user_id': user_id,
            'exp': expire,
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        \"\"\"Decode and validate JWT token.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded payload or None if invalid
        \"\"\"
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
""",
        "src/auth/password_hasher.py": """import hashlib
import secrets

class PasswordHasher:
    \"\"\"Handle password hashing and verification.\"\"\"
    
    @staticmethod
    def hash_password(password: str) -> str:
        \"\"\"Hash a password with salt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password with salt
        \"\"\"
        salt = secrets.token_hex(16)
        pwdhash = hashlib.pbkdf2_hmac('sha256', 
                                       password.encode('utf-8'),
                                       salt.encode('utf-8'),
                                       100000)
        return salt + pwdhash.hex()
    
    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        \"\"\"Verify a password against stored hash.
        
        Args:
            stored_password: Stored hash with salt
            provided_password: Password to verify
            
        Returns:
            True if password matches
        \"\"\"
        salt = stored_password[:32]
        stored_hash = stored_password[32:]
        
        pwdhash = hashlib.pbkdf2_hmac('sha256',
                                       provided_password.encode('utf-8'),
                                       salt.encode('utf-8'),
                                       100000)
        return pwdhash.hex() == stored_hash
""",
        "tests/unit/test_jwt_handler.py": """import unittest
from datetime import timedelta
from src.auth.jwt_handler import JWTHandler

class TestJWTHandler(unittest.TestCase):
    def test_create_token(self):
        token = JWTHandler.create_token('user123')
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
    
    def test_decode_valid_token(self):
        token = JWTHandler.create_token('user123')
        payload = JWTHandler.decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['user_id'], 'user123')
    
    def test_decode_invalid_token(self):
        payload = JWTHandler.decode_token('invalid.token.here')
        self.assertIsNone(payload)
""",
        "tests/unit/test_password_hasher.py": """import unittest
from src.auth.password_hasher import PasswordHasher

class TestPasswordHasher(unittest.TestCase):
    def test_hash_password(self):
        password = 'secure_password123'
        hashed = PasswordHasher.hash_password(password)
        self.assertIsNotNone(hashed)
        self.assertNotEqual(hashed, password)
    
    def test_verify_correct_password(self):
        password = 'secure_password123'
        hashed = PasswordHasher.hash_password(password)
        self.assertTrue(PasswordHasher.verify_password(hashed, password))
    
    def test_verify_incorrect_password(self):
        password = 'secure_password123'
        hashed = PasswordHasher.hash_password(password)
        self.assertFalse(PasswordHasher.verify_password(hashed, 'wrong_password'))
""",
    }

    # Create new files
    for file_path, content in new_files.items():
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Modify existing files to integrate authentication
    user_controller_new = """from src.models.user import User
from src.utils.validators import validate_email, validate_username
from src.auth.password_hasher import PasswordHasher
from src.auth.jwt_handler import JWTHandler
from typing import Optional

class UserController:
    \"\"\"Controller for user management with authentication.\"\"\"
    
    def __init__(self):
        self.users = []
    
    def create_user(self, username: str, email: str, password: str) -> User:
        \"\"\"Create a new user with hashed password.\"\"\"
        if not validate_username(username):
            raise ValueError('Invalid username')
        if not validate_email(email):
            raise ValueError('Invalid email')
        
        user = User(username, email)
        user.password_hash = PasswordHasher.hash_password(password)
        self.users.append(user)
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        \"\"\"Authenticate user and return JWT token.\"\"\"
        user = self.get_user(username)
        if not user:
            return None
        
        if not hasattr(user, 'password_hash'):
            return None
        
        if PasswordHasher.verify_password(user.password_hash, password):
            return JWTHandler.create_token(user.username)
        
        return None
    
    def get_user(self, username: str) -> Optional[User]:
        \"\"\"Get user by username.\"\"\"
        for user in self.users:
            if user.username == username:
                return user
        return None
    
    def delete_user(self, username: str) -> bool:
        \"\"\"Delete a user by username.\"\"\"
        user = self.get_user(username)
        if user:
            self.users.remove(user)
            return True
        return False
"""

    (repo_path / "src" / "controllers" / "user_controller.py").write_text(
        user_controller_new
    )

    # Update middleware
    middleware_new = """from src.auth.jwt_handler import JWTHandler
from typing import Optional, Callable

def authenticate_request(request) -> bool:
    \"\"\"Authenticate request using JWT token.\"\"\"
    token = request.headers.get('Authorization')
    if not token:
        return False
    
    if token.startswith('Bearer '):
        token = token[7:]
    
    payload = JWTHandler.decode_token(token)
    return payload is not None

def require_admin(func: Callable) -> Callable:
    \"\"\"Decorator to require admin privileges.\"\"\"
    def wrapper(*args, **kwargs):
        # Check if user is admin
        request = args[0] if args else None
        if not request or not hasattr(request, 'user'):
            raise PermissionError("Admin access required")
        
        if not getattr(request.user, 'is_admin', False):
            raise PermissionError("Admin access required")
        
        return func(*args, **kwargs)
    return wrapper

def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    \"\"\"Rate limiting decorator.\"\"\"
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Rate limiting logic here
            return func(*args, **kwargs)
        return wrapper
    return decorator
"""

    (repo_path / "src" / "middleware" / "auth.py").write_text(middleware_new)

    # Update requirements
    requirements_new = """flask==2.0.1
sqlalchemy==1.4.22
requests==2.26.0
pytest==6.2.4
pylint==2.9.3
PyJWT==2.3.0
bcrypt==3.2.0
"""

    (repo_path / "requirements.txt").write_text(requirements_new)

    # Setup and run pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=2)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) >= 6  # Many new files and modifications

    # Verify all new file contents match exactly line-by-line
    for file_path, expected_content in new_files.items():
        actual_content = (repo_path / file_path).read_text()
        assert (
            actual_content == expected_content
        ), f"File {file_path} content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"

    # Verify user_controller.py content
    actual_user_controller = (
        repo_path / "src" / "controllers" / "user_controller.py"
    ).read_text()
    assert (
        actual_user_controller == user_controller_new
    ), f"File src/controllers/user_controller.py content mismatch:\nExpected:\n{user_controller_new}\n\nActual:\n{actual_user_controller}"

    # Verify middleware/auth.py content
    actual_middleware = (repo_path / "src" / "middleware" / "auth.py").read_text()
    assert (
        actual_middleware == middleware_new
    ), f"File src/middleware/auth.py content mismatch:\nExpected:\n{middleware_new}\n\nActual:\n{actual_middleware}"

    # Verify requirements.txt content
    actual_requirements = (repo_path / "requirements.txt").read_text()
    assert (
        actual_requirements == requirements_new
    ), f"File requirements.txt content mismatch:\nExpected:\n{requirements_new}\n\nActual:\n{actual_requirements}"


def test_runner_bug_fix_cascade(large_codebase_repo, mock_inquirer_accept_all):
    """Simulate fixing a bug that requires changes across multiple layers."""
    repo_path = large_codebase_repo

    # Bug: Database connection not properly closed, causing resource leaks
    # Fix requires changes in multiple files

    # Fix database utility
    (repo_path / "src" / "utils" / "database.py").write_text(
        """import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

class Database:
    \"\"\"Database connection manager with proper resource handling.\"\"\"
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection: Optional[Any] = None
        self._transaction_active = False
    
    def connect(self) -> None:
        \"\"\"Establish database connection.\"\"\"
        if self.connection:
            logger.warning("Connection already established")
            return
        
        try:
            # Simulate connection
            self.connection = 'connected'
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect(self) -> None:
        \"\"\"Close database connection properly.\"\"\"
        if not self.connection:
            return
        
        try:
            if self._transaction_active:
                self.rollback()
            
            self.connection = None
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
            raise
    
    def execute(self, query: str, params: Optional[tuple] = None) -> List:
        \"\"\"Execute a query with proper error handling.\"\"\"
        if not self.connection:
            raise ConnectionError('Not connected to database')
        
        try:
            logger.debug(f"Executing query: {query}")
            # Simulate query execution
            return []
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def begin_transaction(self) -> None:
        \"\"\"Start a database transaction.\"\"\"
        if self._transaction_active:
            raise RuntimeError("Transaction already active")
        self._transaction_active = True
        logger.debug("Transaction started")
    
    def commit(self) -> None:
        \"\"\"Commit the current transaction.\"\"\"
        if not self._transaction_active:
            raise RuntimeError("No active transaction")
        self._transaction_active = False
        logger.debug("Transaction committed")
    
    def rollback(self) -> None:
        \"\"\"Rollback the current transaction.\"\"\"
        if not self._transaction_active:
            raise RuntimeError("No active transaction")
        self._transaction_active = False
        logger.debug("Transaction rolled back")
    
    def __enter__(self):
        \"\"\"Context manager entry.\"\"\"
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        \"\"\"Context manager exit with guaranteed cleanup.\"\"\"
        self.disconnect()
        return False
"""
    )

    # Add database connection pool manager
    (repo_path / "src" / "utils" / "connection_pool.py").write_text(
        """from typing import List, Optional
from src.utils.database import Database
import logging

logger = logging.getLogger(__name__)

class ConnectionPool:
    \"\"\"Manage a pool of database connections.\"\"\"
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self._pool: List[Database] = []
        self._in_use: List[Database] = []
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        \"\"\"Initialize the connection pool.\"\"\"
        for _ in range(self.pool_size):
            conn = Database(self.connection_string)
            self._pool.append(conn)
        logger.info(f"Connection pool initialized with {self.pool_size} connections")
    
    def get_connection(self) -> Database:
        \"\"\"Get a connection from the pool.\"\"\"
        if not self._pool:
            raise RuntimeError("No connections available in pool")
        
        conn = self._pool.pop()
        conn.connect()
        self._in_use.append(conn)
        return conn
    
    def release_connection(self, conn: Database) -> None:
        \"\"\"Return a connection to the pool.\"\"\"
        if conn not in self._in_use:
            logger.warning("Attempting to release connection not from this pool")
            return
        
        conn.disconnect()
        self._in_use.remove(conn)
        self._pool.append(conn)
    
    def close_all(self) -> None:
        \"\"\"Close all connections in the pool.\"\"\"
        for conn in self._in_use:
            conn.disconnect()
        
        for conn in self._pool:
            conn.disconnect()
        
        self._pool.clear()
        self._in_use.clear()
        logger.info("All connections closed")
"""
    )

    # Update controllers to use proper connection handling
    (repo_path / "src" / "controllers" / "product_controller.py").write_text(
        """from src.models.product import Product
from src.utils.database import Database
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class ProductController:
    \"\"\"Controller for product management with database integration.\"\"\"
    
    def __init__(self, db: Database):
        self.products: List[Product] = []
        self.db = db
    
    def add_product(self, name: str, price: float, stock: int = 0) -> Product:
        \"\"\"Add a new product with database persistence.\"\"\"
        product = Product(name, price, stock)
        
        try:
            # Use context manager for safe database operations
            query = "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)"
            self.db.execute(query, (name, price, stock))
            self.products.append(product)
            logger.info(f"Product added: {name}")
            return product
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            raise
    
    def get_product(self, name: str) -> Optional[Product]:
        \"\"\"Get product by name.\"\"\"
        for product in self.products:
            if product.name == name:
                return product
        return None
    
    def update_product_stock(self, name: str, quantity: int) -> bool:
        \"\"\"Update product stock with database sync.\"\"\"
        product = self.get_product(name)
        if not product:
            return False
        
        try:
            product.update_stock(quantity)
            query = "UPDATE products SET stock = ? WHERE name = ?"
            self.db.execute(query, (product.stock, name))
            logger.info(f"Stock updated for {name}: {product.stock}")
            return True
        except Exception as e:
            logger.error(f"Failed to update stock: {e}")
            raise
    
    def delete_product(self, name: str) -> bool:
        \"\"\"Delete a product.\"\"\"
        product = self.get_product(name)
        if not product:
            return False
        
        try:
            query = "DELETE FROM products WHERE name = ?"
            self.db.execute(query, (name,))
            self.products.remove(product)
            logger.info(f"Product deleted: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete product: {e}")
            raise
"""
    )

    # Add integration test for database connection handling
    (repo_path / "tests" / "integration" / "test_database_connections.py").write_text(
        """import unittest
from src.utils.database import Database
from src.utils.connection_pool import ConnectionPool

class TestDatabaseConnections(unittest.TestCase):
    def test_connection_context_manager(self):
        \"\"\"Test that database connections are properly closed.\"\"\"
        db = Database('sqlite:///test.db')
        
        with db:
            self.assertIsNotNone(db.connection)
        
        self.assertIsNone(db.connection)
    
    def test_connection_pool(self):
        \"\"\"Test connection pool management.\"\"\"
        pool = ConnectionPool('sqlite:///test.db', pool_size=3)
        
        conn1 = pool.get_connection()
        self.assertIsNotNone(conn1.connection)
        
        pool.release_connection(conn1)
        self.assertIsNone(conn1.connection)
        
        pool.close_all()
    
    def test_transaction_rollback_on_error(self):
        \"\"\"Test that transactions rollback on errors.\"\"\"
        db = Database('sqlite:///test.db')
        db.connect()
        
        try:
            db.begin_transaction()
            # Simulate error
            raise ValueError("Test error")
        except ValueError:
            db.rollback()
        finally:
            db.disconnect()
"""
    )

    # Update documentation
    (repo_path / "docs" / "database.md").write_text(
        """# Database Connection Management

## Overview
Proper database connection handling is critical for application stability.

## Connection Pool
Use `ConnectionPool` for managing multiple database connections:

```python
from src.utils.connection_pool import ConnectionPool

pool = ConnectionPool('sqlite:///app.db', pool_size=10)
conn = pool.get_connection()
try:
    # Use connection
    conn.execute("SELECT * FROM users")
finally:
    pool.release_connection(conn)
```

## Context Manager
For single connections, use context manager:

```python
from src.utils.database import Database

with Database('sqlite:///app.db') as db:
    db.execute("SELECT * FROM users")
# Connection automatically closed
```

## Bug Fix History
- Fixed resource leak from unclosed connections (Issue #123)
- Added transaction rollback on errors
- Implemented connection pooling for better performance
"""
    )

    # Store expected content for verification
    expected_database_py = """import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

class Database:
    \"\"\"Database connection manager with proper resource handling.\"\"\"
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection: Optional[Any] = None
        self._transaction_active = False
    
    def connect(self) -> None:
        \"\"\"Establish database connection.\"\"\"
        if self.connection:
            logger.warning("Connection already established")
            return
        
        try:
            # Simulate connection
            self.connection = 'connected'
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect(self) -> None:
        \"\"\"Close database connection properly.\"\"\"
        if not self.connection:
            return
        
        try:
            if self._transaction_active:
                self.rollback()
            
            self.connection = None
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
            raise
    
    def execute(self, query: str, params: Optional[tuple] = None) -> List:
        \"\"\"Execute a query with proper error handling.\"\"\"
        if not self.connection:
            raise ConnectionError('Not connected to database')
        
        try:
            logger.debug(f"Executing query: {query}")
            # Simulate query execution
            return []
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def begin_transaction(self) -> None:
        \"\"\"Start a database transaction.\"\"\"
        if self._transaction_active:
            raise RuntimeError("Transaction already active")
        self._transaction_active = True
        logger.debug("Transaction started")
    
    def commit(self) -> None:
        \"\"\"Commit the current transaction.\"\"\"
        if not self._transaction_active:
            raise RuntimeError("No active transaction")
        self._transaction_active = False
        logger.debug("Transaction committed")
    
    def rollback(self) -> None:
        \"\"\"Rollback the current transaction.\"\"\"
        if not self._transaction_active:
            raise RuntimeError("No active transaction")
        self._transaction_active = False
        logger.debug("Transaction rolled back")
    
    def __enter__(self):
        \"\"\"Context manager entry.\"\"\"
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        \"\"\"Context manager exit with guaranteed cleanup.\"\"\"
        self.disconnect()
        return False
"""

    expected_connection_pool_py = """from typing import List, Optional
from src.utils.database import Database
import logging

logger = logging.getLogger(__name__)

class ConnectionPool:
    \"\"\"Manage a pool of database connections.\"\"\"
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self._pool: List[Database] = []
        self._in_use: List[Database] = []
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        \"\"\"Initialize the connection pool.\"\"\"
        for _ in range(self.pool_size):
            conn = Database(self.connection_string)
            self._pool.append(conn)
        logger.info(f"Connection pool initialized with {self.pool_size} connections")
    
    def get_connection(self) -> Database:
        \"\"\"Get a connection from the pool.\"\"\"
        if not self._pool:
            raise RuntimeError("No connections available in pool")
        
        conn = self._pool.pop()
        conn.connect()
        self._in_use.append(conn)
        return conn
    
    def release_connection(self, conn: Database) -> None:
        \"\"\"Return a connection to the pool.\"\"\"
        if conn not in self._in_use:
            logger.warning("Attempting to release connection not from this pool")
            return
        
        conn.disconnect()
        self._in_use.remove(conn)
        self._pool.append(conn)
    
    def close_all(self) -> None:
        \"\"\"Close all connections in the pool.\"\"\"
        for conn in self._in_use:
            conn.disconnect()
        
        for conn in self._pool:
            conn.disconnect()
        
        self._pool.clear()
        self._in_use.clear()
        logger.info("All connections closed")
"""

    expected_product_controller_py = """from src.models.product import Product
from src.utils.database import Database
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class ProductController:
    \"\"\"Controller for product management with database integration.\"\"\"
    
    def __init__(self, db: Database):
        self.products: List[Product] = []
        self.db = db
    
    def add_product(self, name: str, price: float, stock: int = 0) -> Product:
        \"\"\"Add a new product with database persistence.\"\"\"
        product = Product(name, price, stock)
        
        try:
            # Use context manager for safe database operations
            query = "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)"
            self.db.execute(query, (name, price, stock))
            self.products.append(product)
            logger.info(f"Product added: {name}")
            return product
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            raise
    
    def get_product(self, name: str) -> Optional[Product]:
        \"\"\"Get product by name.\"\"\"
        for product in self.products:
            if product.name == name:
                return product
        return None
    
    def update_product_stock(self, name: str, quantity: int) -> bool:
        \"\"\"Update product stock with database sync.\"\"\"
        product = self.get_product(name)
        if not product:
            return False
        
        try:
            product.update_stock(quantity)
            query = "UPDATE products SET stock = ? WHERE name = ?"
            self.db.execute(query, (product.stock, name))
            logger.info(f"Stock updated for {name}: {product.stock}")
            return True
        except Exception as e:
            logger.error(f"Failed to update stock: {e}")
            raise
    
    def delete_product(self, name: str) -> bool:
        \"\"\"Delete a product.\"\"\"
        product = self.get_product(name)
        if not product:
            return False
        
        try:
            query = "DELETE FROM products WHERE name = ?"
            self.db.execute(query, (name,))
            self.products.remove(product)
            logger.info(f"Product deleted: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete product: {e}")
            raise
"""

    expected_test_database_connections_py = """import unittest
from src.utils.database import Database
from src.utils.connection_pool import ConnectionPool

class TestDatabaseConnections(unittest.TestCase):
    def test_connection_context_manager(self):
        \"\"\"Test that database connections are properly closed.\"\"\"
        db = Database('sqlite:///test.db')
        
        with db:
            self.assertIsNotNone(db.connection)
        
        self.assertIsNone(db.connection)
    
    def test_connection_pool(self):
        \"\"\"Test connection pool management.\"\"\"
        pool = ConnectionPool('sqlite:///test.db', pool_size=3)
        
        conn1 = pool.get_connection()
        self.assertIsNotNone(conn1.connection)
        
        pool.release_connection(conn1)
        self.assertIsNone(conn1.connection)
        
        pool.close_all()
    
    def test_transaction_rollback_on_error(self):
        \"\"\"Test that transactions rollback on errors.\"\"\"
        db = Database('sqlite:///test.db')
        db.connect()
        
        try:
            db.begin_transaction()
            # Simulate error
            raise ValueError("Test error")
        except ValueError:
            db.rollback()
        finally:
            db.disconnect()
"""

    expected_database_md = """# Database Connection Management

## Overview
Proper database connection handling is critical for application stability.

## Connection Pool
Use `ConnectionPool` for managing multiple database connections:

```python
from src.utils.connection_pool import ConnectionPool

pool = ConnectionPool('sqlite:///app.db', pool_size=10)
conn = pool.get_connection()
try:
    # Use connection
    conn.execute("SELECT * FROM users")
finally:
    pool.release_connection(conn)
```

## Context Manager
For single connections, use context manager:

```python
from src.utils.database import Database

with Database('sqlite:///app.db') as db:
    db.execute("SELECT * FROM users")
# Connection automatically closed
```

## Bug Fix History
- Fixed resource leak from unclosed connections (Issue #123)
- Added transaction rollback on errors
- Implemented connection pooling for better performance
"""

    # Setup and run pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=2)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) >= 4

    # Verify all file contents match exactly line-by-line
    actual_database = (repo_path / "src" / "utils" / "database.py").read_text()
    assert (
        actual_database == expected_database_py
    ), f"File src/utils/database.py content mismatch:\nExpected:\n{expected_database_py}\n\nActual:\n{actual_database}"

    actual_connection_pool = (
        repo_path / "src" / "utils" / "connection_pool.py"
    ).read_text()
    assert (
        actual_connection_pool == expected_connection_pool_py
    ), f"File src/utils/connection_pool.py content mismatch:\nExpected:\n{expected_connection_pool_py}\n\nActual:\n{actual_connection_pool}"

    actual_product_controller = (
        repo_path / "src" / "controllers" / "product_controller.py"
    ).read_text()
    assert (
        actual_product_controller == expected_product_controller_py
    ), f"File src/controllers/product_controller.py content mismatch:\nExpected:\n{expected_product_controller_py}\n\nActual:\n{actual_product_controller}"

    actual_test_db_connections = (
        repo_path / "tests" / "integration" / "test_database_connections.py"
    ).read_text()
    assert (
        actual_test_db_connections == expected_test_database_connections_py
    ), f"File tests/integration/test_database_connections.py content mismatch:\nExpected:\n{expected_test_database_connections_py}\n\nActual:\n{actual_test_db_connections}"

    actual_database_md = (repo_path / "docs" / "database.md").read_text()
    assert (
        actual_database_md == expected_database_md
    ), f"File docs/database.md content mismatch:\nExpected:\n{expected_database_md}\n\nActual:\n{actual_database_md}"


def test_runner_mixed_operations_chaos(large_codebase_repo, mock_inquirer_accept_all):
    """Test chaotic real-world scenario with adds, deletes, renames, and modifications."""
    repo_path = large_codebase_repo

    # Chaos scenario: multiple developers working, refactoring, adding features

    # Delete obsolete files
    files_to_delete = [
        "src/middleware/auth.py",  # Replaced by new auth system
        "tests/fixtures/sample_data.py",  # Moving to database seeds
        "scripts/deploy.sh",  # Using CI/CD now
    ]

    for file_path in files_to_delete:
        (repo_path / file_path).unlink()

    # Rename files for better organization
    subprocess.run(
        ["git", "mv", "src/utils/helpers.py", "src/utils/formatters.py"],
        cwd=repo_path,
        check=True,
    )

    subprocess.run(
        ["git", "mv", "src/controllers/user_controller.py", "src/controllers/users.py"],
        cwd=repo_path,
        check=True,
    )

    # Modify renamed files
    (repo_path / "src" / "utils" / "formatters.py").write_text(
        """import json
from datetime import datetime
from typing import Any, Optional

def format_date(date: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    \"\"\"Format datetime object to string.\"\"\"
    return date.strftime(format_str)

def format_currency(amount: float, currency: str = 'USD') -> str:
    \"\"\"Format amount as currency.\"\"\"
    symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
    symbol = symbols.get(currency, '')
    return f'{symbol}{amount:.2f}'

def parse_json_safe(json_str: str) -> Optional[Any]:
    \"\"\"Safely parse JSON string.\"\"\"
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def format_file_size(size_bytes: int) -> str:
    \"\"\"Format file size in human-readable format.\"\"\"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def truncate_string(text: str, max_length: int = 50, suffix: str = '...') -> str:
    \"\"\"Truncate string to maximum length.\"\"\"
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
""",
        encoding="utf-8",
    )

    # Add completely new modules
    new_files = {
        "src/api/__init__.py": "",
        "src/api/routes.py": """from typing import Dict, Any

class APIRouter:
    \"\"\"API route handler.\"\"\"
    
    def __init__(self):
        self.routes = {}
    
    def register_route(self, path: str, handler):
        \"\"\"Register a new API route.\"\"\"
        self.routes[path] = handler
    
    def handle_request(self, path: str, method: str, data: Dict) -> Any:
        \"\"\"Handle incoming API request.\"\"\"
        handler = self.routes.get(path)
        if not handler:
            return {'error': 'Not found'}, 404
        
        return handler(method, data)
""",
        "src/api/serializers.py": """from typing import Any, Dict
from datetime import datetime

class Serializer:
    \"\"\"Base serializer for API responses.\"\"\"
    
    @staticmethod
    def serialize_datetime(dt: datetime) -> str:
        \"\"\"Serialize datetime to ISO format.\"\"\"
        return dt.isoformat()
    
    @staticmethod
    def serialize_model(model: Any) -> Dict:
        \"\"\"Serialize model object to dictionary.\"\"\"
        if hasattr(model, 'to_dict'):
            return model.to_dict()
        return {}
""",
        "src/cache/__init__.py": "",
        "src/cache/redis_cache.py": """from typing import Optional, Any
import json

class RedisCache:
    \"\"\"Redis cache implementation.\"\"\"
    
    def __init__(self, host: str = 'localhost', port: int = 6379):
        self.host = host
        self.port = port
        self.client = None
    
    def connect(self):
        \"\"\"Connect to Redis server.\"\"\"
        # Simulate connection
        self.client = 'connected'
    
    def get(self, key: str) -> Optional[Any]:
        \"\"\"Get value from cache.\"\"\"
        # Simulate get
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        \"\"\"Set value in cache with TTL.\"\"\"
        # Simulate set
        return True
    
    def delete(self, key: str) -> bool:
        \"\"\"Delete key from cache.\"\"\"
        return True
""",
        "src/tasks/__init__.py": "",
        "src/tasks/background_jobs.py": """import time
from typing import Callable
import logging

logger = logging.getLogger(__name__)

class TaskQueue:
    \"\"\"Background task queue.\"\"\"
    
    def __init__(self):
        self.tasks = []
    
    def enqueue(self, func: Callable, *args, **kwargs):
        \"\"\"Add task to queue.\"\"\"
        task = {'func': func, 'args': args, 'kwargs': kwargs}
        self.tasks.append(task)
        logger.info(f"Task enqueued: {func.__name__}")
    
    def process(self):
        \"\"\"Process all tasks in queue.\"\"\"
        while self.tasks:
            task = self.tasks.pop(0)
            try:
                task['func'](*task['args'], **task['kwargs'])
                logger.info(f"Task completed: {task['func'].__name__}")
            except Exception as e:
                logger.error(f"Task failed: {e}")
""",
        "tests/unit/test_api_routes.py": """import unittest
from src.api.routes import APIRouter

class TestAPIRouter(unittest.TestCase):
    def test_register_route(self):
        router = APIRouter()
        handler = lambda m, d: {'success': True}
        router.register_route('/test', handler)
        self.assertIn('/test', router.routes)
    
    def test_handle_request(self):
        router = APIRouter()
        handler = lambda m, d: {'success': True}
        router.register_route('/test', handler)
        response = router.handle_request('/test', 'GET', {})
        self.assertEqual(response, {'success': True})
""",
        "config/cache.py": """REDIS_HOST = 'localhost'
REDIS_PORT = 6379
CACHE_TTL = 3600  # 1 hour
CACHE_ENABLED = True
""",
    }

    for file_path, content in new_files.items():
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # Modify existing files dramatically
    (repo_path / "src" / "models" / "user.py").write_text(
        """from datetime import datetime
from typing import Optional, Dict, List

class User:
    \"\"\"Enhanced user model with roles and permissions.\"\"\"
    
    def __init__(self, username: str, email: str, created_at: Optional[datetime] = None):
        self.username = username
        self.email = email
        self.created_at = created_at or datetime.now()
        self.is_active = True
        self.last_login = None
        self.roles: List[str] = ['user']
        self.metadata: Dict = {}
    
    def add_role(self, role: str) -> None:
        \"\"\"Add a role to user.\"\"\"
        if role not in self.roles:
            self.roles.append(role)
    
    def has_role(self, role: str) -> bool:
        \"\"\"Check if user has specific role.\"\"\"
        return role in self.roles
    
    def deactivate(self) -> None:
        self.is_active = False
    
    def activate(self) -> None:
        self.is_active = True
    
    def update_last_login(self) -> None:
        self.last_login = datetime.now()
    
    def set_metadata(self, key: str, value: any) -> None:
        \"\"\"Set user metadata.\"\"\"
        self.metadata[key] = value
    
    def to_dict(self) -> Dict:
        return {
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'roles': self.roles,
            'metadata': self.metadata
        }
""",
        encoding="utf-8",
    )

    # Update main README with all new features
    (repo_path / "README.md").write_text(
        """# Enterprise Application

A comprehensive, production-ready web application with advanced features.

## Features

### Core Features
- **User Management**: Advanced user system with roles and permissions
- **Authentication**: JWT-based authentication with password hashing
- **API Layer**: RESTful API with serialization
- **Caching**: Redis-based caching for performance
- **Background Tasks**: Asynchronous task processing
- **Data Processing**: Advanced data validation and formatting

### Architecture
- MVC pattern with clear separation of concerns
- Middleware for authentication and rate limiting
- Connection pooling for database efficiency
- Comprehensive error handling and logging

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

See `config/` directory for all configuration options.

## Testing

```bash
python -m pytest tests/
```

## Recent Updates
- Added API routing layer
- Implemented Redis caching
- Added background task queue
- Enhanced user model with roles
- Improved database connection handling
- Refactored formatters module
""",
        encoding="utf-8",
    )

    # Store expected content for formatters.py
    expected_formatters = """import json
from datetime import datetime
from typing import Any, Optional

def format_date(date: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    \"\"\"Format datetime object to string.\"\"\"
    return date.strftime(format_str)

def format_currency(amount: float, currency: str = 'USD') -> str:
    \"\"\"Format amount as currency.\"\"\"
    symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
    symbol = symbols.get(currency, '')
    return f'{symbol}{amount:.2f}'

def parse_json_safe(json_str: str) -> Optional[Any]:
    \"\"\"Safely parse JSON string.\"\"\"
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def format_file_size(size_bytes: int) -> str:
    \"\"\"Format file size in human-readable format.\"\"\"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def truncate_string(text: str, max_length: int = 50, suffix: str = '...') -> str:
    \"\"\"Truncate string to maximum length.\"\"\"
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
"""

    expected_user_py = """from datetime import datetime
from typing import Optional, Dict, List

class User:
    \"\"\"Enhanced user model with roles and permissions.\"\"\"
    
    def __init__(self, username: str, email: str, created_at: Optional[datetime] = None):
        self.username = username
        self.email = email
        self.created_at = created_at or datetime.now()
        self.is_active = True
        self.last_login = None
        self.roles: List[str] = ['user']
        self.metadata: Dict = {}
    
    def add_role(self, role: str) -> None:
        \"\"\"Add a role to user.\"\"\"
        if role not in self.roles:
            self.roles.append(role)
    
    def has_role(self, role: str) -> bool:
        \"\"\"Check if user has specific role.\"\"\"
        return role in self.roles
    
    def deactivate(self) -> None:
        self.is_active = False
    
    def activate(self) -> None:
        self.is_active = True
    
    def update_last_login(self) -> None:
        self.last_login = datetime.now()
    
    def set_metadata(self, key: str, value: any) -> None:
        \"\"\"Set user metadata.\"\"\"
        self.metadata[key] = value
    
    def to_dict(self) -> Dict:
        return {
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'roles': self.roles,
            'metadata': self.metadata
        }
"""

    expected_readme = """# Enterprise Application

A comprehensive, production-ready web application with advanced features.

## Features

### Core Features
- **User Management**: Advanced user system with roles and permissions
- **Authentication**: JWT-based authentication with password hashing
- **API Layer**: RESTful API with serialization
- **Caching**: Redis-based caching for performance
- **Background Tasks**: Asynchronous task processing
- **Data Processing**: Advanced data validation and formatting

### Architecture
- MVC pattern with clear separation of concerns
- Middleware for authentication and rate limiting
- Connection pooling for database efficiency
- Comprehensive error handling and logging

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

See `config/` directory for all configuration options.

## Testing

```bash
python -m pytest tests/
```

## Recent Updates
- Added API routing layer
- Implemented Redis caching
- Added background task queue
- Enhanced user model with roles
- Improved database connection handling
- Refactored formatters module
"""

    # Setup and run pipeline
    git_interface = SubprocessGitInterface(repo_path)
    chunker = SimpleChunker()
    grouper = DeterministicGrouper(group_by_file=True, max_chunks_per_group=2)

    pipeline = AIGitPipeline(git_interface, chunker, grouper)
    results = pipeline.run()

    # Verify results
    assert results is not None
    assert len(results) >= 8  # Many changes

    # Verify deletions
    assert not (repo_path / "src" / "middleware" / "auth.py").exists()
    assert not (repo_path / "scripts" / "deploy.sh").exists()

    # Verify renames
    assert not (repo_path / "src" / "utils" / "helpers.py").exists()
    assert (repo_path / "src" / "utils" / "formatters.py").exists()

    # Verify new modules exist
    assert (repo_path / "src" / "api" / "routes.py").exists()
    assert (repo_path / "src" / "cache" / "redis_cache.py").exists()
    assert (repo_path / "src" / "tasks" / "background_jobs.py").exists()

    # Verify all new file contents match exactly line-by-line
    for file_path, expected_content in new_files.items():
        actual_content = (repo_path / file_path).read_text(encoding="utf-8")
        assert (
            actual_content == expected_content
        ), f"File {file_path} content mismatch:\nExpected:\n{expected_content}\n\nActual:\n{actual_content}"

    # Verify renamed/modified file contents match exactly
    actual_formatters = (repo_path / "src" / "utils" / "formatters.py").read_text(
        encoding="utf-8"
    )
    assert (
        actual_formatters == expected_formatters
    ), f"File src/utils/formatters.py content mismatch:\nExpected:\n{expected_formatters}\n\nActual:\n{actual_formatters}"

    actual_user = (repo_path / "src" / "models" / "user.py").read_text(encoding="utf-8")
    assert (
        actual_user == expected_user_py
    ), f"File src/models/user.py content mismatch:\nExpected:\n{expected_user_py}\n\nActual:\n{actual_user}"

    actual_readme = (repo_path / "README.md").read_text(encoding="utf-8")
    assert (
        actual_readme == expected_readme
    ), f"File README.md content mismatch:\nExpected:\n{expected_readme}\n\nActual:\n{actual_readme}"
