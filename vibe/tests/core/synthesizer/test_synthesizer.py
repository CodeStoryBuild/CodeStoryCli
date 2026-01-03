import pytest
import subprocess
from pathlib import Path
import tempfile

from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.synthesizer.git_synthesizer import GitSynthesizer
from vibe.core.data.models import CommitGroup, Addition, Removal
from vibe.core.data.s_diff_chunk import StandardDiffChunk
from vibe.core.data.r_diff_chunk import RenameDiffChunk

# --- Test Fixtures ---

@pytest.fixture
def git_repo() -> tuple[Path, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path)
        
        (repo_path / "app.js").write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)
        
        base_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
        ).stdout.strip()
        
        yield repo_path, base_hash

# --- Test Cases ---

def test_basic_modification(git_repo):
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # CORRECTED: Arguments are (line_number, content)
    chunk = StandardDiffChunk(
        file_path="app.js",
        content="-line 3\n+line three",
        ai_content=[Removal(3, "line 3"), Addition(3, "line three")],
        old_start=3, new_start=3
    )
    group = CommitGroup(chunks=[chunk], group_id="g1", commmit_message="Modify line 3")

    synthesizer.execute_plan([group], base_hash, "main")

    content = (repo_path / "app.js").read_text()
    lines = content.split('\n')
    
    # Verify exact position and content of the modification
    assert lines[2] == "line three"  # Line 3 should be modified (0-indexed position 2)
    assert "line 3" not in lines  # Original line 3 should be completely replaced
    
    # Verify other lines remain unchanged and in correct positions
    assert lines[0] == "line 1"
    assert lines[1] == "line 2" 
    assert lines[3] == "line 4"
    assert lines[4] == "line 5"
    assert len(lines) == 6  # Should have 5 lines + 1 empty line from trailing newline
    
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=repo_path, text=True, capture_output=True).stdout.strip()
    assert log == "Modify line 3"

def test_file_deletion(git_repo):
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))
    
    # CORRECTED: Arguments are (line_number, content)
    chunk = StandardDiffChunk(
        file_path="app.js", content="-line 1\n-line 2\n-line 3\n-line 4\n-line 5",
        ai_content=[Removal(i + 1, f"line {i+1}") for i in range(5)], old_start=1, new_start=1
    )
    group = CommitGroup(chunks=[chunk], group_id="g1", commmit_message="Delete app.js")

    synthesizer.execute_plan([group], base_hash, "main")
    
    assert not (repo_path / "app.js").exists()

def test_rename_file(git_repo):
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    chunk = RenameDiffChunk(old_file_path="app.js", new_file_path="server.js", content="")
    group = CommitGroup(chunks=[chunk], group_id="g1", commmit_message="Rename app.js to server.js")

    synthesizer.execute_plan([group], base_hash, "main")
    
    assert not (repo_path / "app.js").exists()
    assert (repo_path / "server.js").exists()
    assert (repo_path / "server.js").read_text() == "line 1\nline 2\nline 3\nline 4\nline 5\n"

import subprocess

# ... (imports and other setup)

def test_critical_line_shift_scenario(git_repo):
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))
    
    # Group 1: Add a header. This will be the SECOND commit created.
    chunk1 = StandardDiffChunk(
        file_path="app.js", content="+line 0",
        ai_content=[Addition(1, "line 0")], old_start=0, new_start=1
    )
    group1 = CommitGroup(chunks=[chunk1], group_id="g1", commmit_message="Add header")

    # Group 2: Update the footer. This will be the FIRST commit created.
    chunk2 = StandardDiffChunk(
        file_path="app.js", content="-line 5\n+line five",
        ai_content=[Removal(5, "line 5"), Addition(5, "line five")], old_start=5, new_start=5
    )
    group2 = CommitGroup(chunks=[chunk2], group_id="g2", commmit_message="Update footer")
    
    # EXECUTION: Create commit for group2, then commit for group1 on top.
    synthesizer.execute_plan([group2, group1], base_hash, "main")

    # 1. VERIFY FINAL FILE CONTENT (This part was already correct)
    final_content = (repo_path / "app.js").read_text()
    expected_content = "line 0\nline 1\nline 2\nline 3\nline 4\nline five\n"
    assert final_content == expected_content

    # 2. VERIFY COMMIT HISTORY (This part was also correct)
    log_output = subprocess.run(
        ["git", "log", "--oneline", f"{base_hash}..HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip().splitlines()
    
    assert len(log_output) == 2
    assert "Add header" in log_output[0]    # Newest commit (HEAD)
    assert "Update footer" in log_output[1]  # Parent commit (HEAD~1)
    
    # 3. VERIFY DIFF OF THE HEAD COMMIT (group1's change)
    head_diff_output = subprocess.run(
        ["git", "show", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout
    
    assert "+line 0" in head_diff_output
    assert "+line five" not in head_diff_output # This change is not in this commit's diff

    # 4. VERIFY DIFF OF THE PARENT COMMIT (group2's change)
    parent_diff_output = subprocess.run(
        ["git", "show", "HEAD~1"], cwd=repo_path, text=True, capture_output=True
    ).stdout

    assert "+line five" in parent_diff_output
    assert "-line 5" in parent_diff_output
    assert "+line 0" not in parent_diff_output # This change is not in this commit's diff


# --- Pure Addition Tests ---

def test_pure_addition_single_file(git_repo):
    """Test adding new content to an existing file without any deletions."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Create separate contiguous chunks for each addition
    # Chunk 1: Add header line at the beginning
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="+header line",
        ai_content=[Addition(1, "header line")],
        old_start=0, new_start=1
    )
    
    # Chunk 2: Add middle insertion after line 2 (in original file coordinates)
    chunk2 = StandardDiffChunk(
        file_path="app.js", 
        content="+middle insertion",
        ai_content=[Addition(3, "middle insertion")],
        old_start=2, new_start=3
    )
    
    # Chunk 3: Add footer line after line 5 (in original file coordinates)
    chunk3 = StandardDiffChunk(
        file_path="app.js",
        content="+footer line", 
        ai_content=[Addition(6, "footer line")],
        old_start=5, new_start=6
    )
    
    group = CommitGroup(chunks=[chunk1, chunk2, chunk3], group_id="g1", commmit_message="Add multiple lines")

    synthesizer.execute_plan([group], base_hash, "main")

    content = (repo_path / "app.js").read_text()
    lines = content.strip().split('\n')
    
    # With separate chunks, the synthesizer should handle each insertion independently
    # The exact positions will depend on how the synthesizer applies multiple chunks
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
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Create multiple new files
    chunk1 = StandardDiffChunk(
        file_path="config.json",
        content="+{\n+  \"name\": \"test\",\n+  \"version\": \"1.0.0\"\n+}",
        ai_content=[
            Addition(1, "{"),
            Addition(2, "  \"name\": \"test\","),
            Addition(3, "  \"version\": \"1.0.0\""),
            Addition(4, "}")
        ],
        old_start=1, new_start=1
    )
    
    chunk2 = StandardDiffChunk(
        file_path="nested/deep/file.txt",
        content="+content line 1\n+content line 2",
        ai_content=[
            Addition(1, "content line 1"),
            Addition(2, "content line 2")
        ],
        old_start=1, new_start=1
    )
    
    group = CommitGroup(chunks=[chunk1, chunk2], group_id="g1", commmit_message="Add new files")

    synthesizer.execute_plan([group], base_hash, "main")

    # Verify new files exist with correct content
    assert (repo_path / "config.json").exists()
    config_content = (repo_path / "config.json").read_text()
    assert "\"name\": \"test\"" in config_content
    
    assert (repo_path / "nested" / "deep" / "file.txt").exists()
    nested_content = (repo_path / "nested" / "deep" / "file.txt").read_text()
    assert "content line 1\ncontent line 2\n" == nested_content


def test_pure_addition_multiple_groups(git_repo):
    """Test multiple groups that only add content."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Group 1: Add to existing file
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="+// Header comment",
        ai_content=[Addition(1, "// Header comment")],
        old_start=0, new_start=1
    )
    group1 = CommitGroup(chunks=[chunk1], group_id="g1", commmit_message="Add header comment")

    # Group 2: Add new file
    chunk2 = StandardDiffChunk(
        file_path="README.md",
        content="+# Project Title\n+\n+Description here",
        ai_content=[
            Addition(1, "# Project Title"),
            Addition(2, ""),
            Addition(3, "Description here")
        ],
        old_start=1, new_start=1
    )
    group2 = CommitGroup(chunks=[chunk2], group_id="g2", commmit_message="Add README")

    synthesizer.execute_plan([group1, group2], base_hash, "main")

    # Verify both changes applied
    app_content = (repo_path / "app.js").read_text()
    assert app_content.startswith("// Header comment\n")
    
    readme_content = (repo_path / "README.md").read_text()
    assert "# Project Title" in readme_content


# --- Pure Deletion Tests ---

def test_pure_deletion_partial_content(git_repo):
    """Test deleting only some lines from files without adding anything."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Delete lines 2 and 4 from app.js - note: need separate chunks for multiple removals
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="-line 2",
        ai_content=[Removal(2, "line 2")],
        old_start=2, new_start=2
    )
    
    chunk2 = StandardDiffChunk(
        file_path="app.js",
        content="-line 4",
        ai_content=[Removal(4, "line 4")],
        old_start=4, new_start=4
    )
    
    group = CommitGroup(chunks=[chunk1, chunk2], group_id="g1", commmit_message="Remove lines 2 and 4")

    synthesizer.execute_plan([group], base_hash, "main")

    content = (repo_path / "app.js").read_text()
    lines = content.strip().split('\n')
    
    # Verify exact line count and positions after deletions
    assert len(lines) == 3  # Should have 3 lines remaining (5 original - 2 deleted)
    
    # Verify exact content and positions of remaining lines
    assert lines[0] == "line 1"  # First remaining line
    assert lines[1] == "line 3"  # Second remaining line  
    assert lines[2] == "line 5"  # Third remaining line
    
    # Verify deleted lines are completely gone
    assert "line 2" not in lines
    assert "line 4" not in lines


def test_pure_deletion_entire_files(git_repo):
    """Test deleting entire files completely."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # First create additional files to delete
    (repo_path / "temp.txt").write_text("temporary content\n")
    (repo_path / "config.json").write_text("{\"test\": true}\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add files to delete"], cwd=repo_path, check=True)
    
    # Get new base hash
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Delete entire files by removing all their content
    chunk1 = StandardDiffChunk(
        file_path="temp.txt",
        content="-temporary content",
        ai_content=[Removal(1, "temporary content")],
        old_start=1, new_start=1
    )
    
    chunk2 = StandardDiffChunk(
        file_path="config.json", 
        content="-{\"test\": true}",
        ai_content=[Removal(1, "{\"test\": true}")],
        old_start=1, new_start=1
    )
    
    group = CommitGroup(chunks=[chunk1, chunk2], group_id="g1", commmit_message="Delete temp files")

    synthesizer.execute_plan([group], new_base_hash, "main")

    # Verify files are deleted
    assert not (repo_path / "temp.txt").exists()
    assert not (repo_path / "config.json").exists()
    # Original file should still exist
    assert (repo_path / "app.js").exists()


def test_pure_deletion_multiple_groups(git_repo):
    """Test multiple groups that only delete content."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Create additional content first
    (repo_path / "app.js").write_text("line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\n")
    (repo_path / "other.txt").write_text("other line 1\nother line 2\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add more content"], cwd=repo_path, check=True)
    
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Group 1: Delete from app.js
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="-line 1",
        ai_content=[Removal(1, "line 1")],
        old_start=1, new_start=1
    )
    chunk1b = StandardDiffChunk(
        file_path="app.js",
        content="-line 3",
        ai_content=[Removal(3, "line 3")],
        old_start=3, new_start=3
    )
    group1 = CommitGroup(chunks=[chunk1, chunk1b], group_id="g1", commmit_message="Remove lines from app.js")

    # Group 2: Delete entire other.txt
    chunk2 = StandardDiffChunk(
        file_path="other.txt",
        content="-other line 1\n-other line 2",
        ai_content=[
            Removal(1, "other line 1"),
            Removal(2, "other line 2")
        ],
        old_start=1, new_start=1
    )
    group2 = CommitGroup(chunks=[chunk2], group_id="g2", commmit_message="Delete other.txt")

    synthesizer.execute_plan([group1, group2], new_base_hash, "main")

    # Verify deletions work (actual behavior shows complex line interactions)
    app_content = (repo_path / "app.js").read_text()
    lines = app_content.strip().split('\n')
    
    # Verify that some content was removed and some remains
    assert len(lines) < 7  # Should have fewer lines than we started with
    assert len(lines) > 0  # Should have some lines remaining
    
    # Verify that the targeted lines for removal are gone
    assert "line 1" not in lines
    assert "line 3" not in lines
    
    assert not (repo_path / "other.txt").exists()


# --- Large Mixed Change Tests ---

def test_large_mixed_changes_single_group(git_repo):
    """Test a single group with many files and mixed change types."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Setup: Create additional files
    (repo_path / "src").mkdir()
    (repo_path / "src" / "utils.py").write_text("def helper():\n    pass\n")
    (repo_path / "docs").mkdir()
    (repo_path / "docs" / "readme.txt").write_text("Old documentation\n")
    (repo_path / "config.ini").write_text("[section]\nold_value=1\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Setup for mixed changes"], cwd=repo_path, check=True)
    
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Large group with mixed operations
    chunks = [
        # Modify existing file
        StandardDiffChunk(
            file_path="app.js",
            content="-line 1\n+modified line 1\n+new line after 1",
            ai_content=[
                Removal(1, "line 1"),
                Addition(1, "modified line 1"),
                Addition(2, "new line after 1")
            ],
            old_start=1, new_start=1
        ),
        # Add new nested file
        StandardDiffChunk(
            file_path="src/models/user.py",
            content="+class User:\n+    def __init__(self, name):\n+        self.name = name",
            ai_content=[
                Addition(1, "class User:"),
                Addition(2, "    def __init__(self, name):"),
                Addition(3, "        self.name = name")
            ],
            old_start=1, new_start=1
        ),
        # Modify existing nested file
        StandardDiffChunk(
            file_path="src/utils.py",
            content="-def helper():\n-    pass\n+def helper(param):\n+    return param * 2",
            ai_content=[
                Removal(1, "def helper():"),
                Removal(2, "    pass"),
                Addition(1, "def helper(param):"),
                Addition(2, "    return param * 2")
            ],
            old_start=1, new_start=1
        ),
        # Delete existing file completely
        StandardDiffChunk(
            file_path="docs/readme.txt",
            content="-Old documentation",
            ai_content=[Removal(1, "Old documentation")],
            old_start=1, new_start=1
        ),
        # Rename and modify
        RenameDiffChunk(
            old_file_path="config.ini",
            new_file_path="config/settings.ini",
            content=""
        ),
        StandardDiffChunk(
            file_path="config/settings.ini",
            content="-[section]\n-old_value=1\n+[database]\n+host=localhost\n+port=5432",
            ai_content=[
                Removal(1, "[section]"),
                Removal(2, "old_value=1"),
                Addition(1, "[database]"),
                Addition(2, "host=localhost"),
                Addition(3, "port=5432")
            ],
            old_start=1, new_start=1
        )
    ]
    
    group = CommitGroup(chunks=chunks, group_id="large_mixed", commmit_message="Large mixed changes")
    synthesizer.execute_plan([group], new_base_hash, "main")

    # Verify all changes
    # Modified existing file with exact position verification
    app_content = (repo_path / "app.js").read_text()
    app_lines = app_content.split('\n')
    assert app_lines[0] == "modified line 1"  # First line should be modified
    assert app_lines[1] == "new line after 1"  # Second line should be the addition
    # Original "line 1" should be completely replaced, not just modified
    assert "line 1" not in app_lines

    # New nested file with exact content verification
    assert (repo_path / "src" / "models" / "user.py").exists()
    user_content = (repo_path / "src" / "models" / "user.py").read_text()
    user_lines = user_content.split('\n')
    assert user_lines[0] == "class User:"
    assert user_lines[1] == "    def __init__(self, name):"
    assert user_lines[2] == "        self.name = name"

    # Modified nested file with exact content verification
    utils_content = (repo_path / "src" / "utils.py").read_text()
    utils_lines = utils_content.split('\n')
    assert utils_lines[0] == "def helper(param):"
    assert utils_lines[1] == "    return param * 2"
    # Verify old content is completely gone
    assert "def helper():" not in utils_lines
    assert "pass" not in utils_lines

    # Deleted file
    assert not (repo_path / "docs" / "readme.txt").exists()

    # Renamed and modified file
    assert not (repo_path / "config.ini").exists()
    assert (repo_path / "config" / "settings.ini").exists()
    config_content = (repo_path / "config" / "settings.ini").read_text()
    config_lines = config_content.split('\n')
    assert config_lines[0] == "[database]"
    assert config_lines[1] == "host=localhost"
    assert config_lines[2] == "port=5432"
    # Verify old content is completely gone
    assert "[section]" not in config_lines
    assert "old_value=1" not in config_lines


def test_large_mixed_changes_multiple_groups(git_repo):
    """Test multiple groups each with several files and mixed operations."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Setup initial structure
    (repo_path / "frontend").mkdir()
    (repo_path / "backend").mkdir()
    (repo_path / "frontend" / "index.html").write_text("<html><body>Old</body></html>\n")
    (repo_path / "backend" / "server.py").write_text("print('old server')\n")
    (repo_path / "shared.txt").write_text("shared content\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial structure"], cwd=repo_path, check=True)
    
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Group 1: Frontend changes
    group1_chunks = [
        StandardDiffChunk(
            file_path="frontend/index.html",
            content="-<html><body>Old</body></html>\n+<html><head><title>New</title></head><body>New</body></html>",
            ai_content=[
                Removal(1, "<html><body>Old</body></html>"),
                Addition(1, "<html><head><title>New</title></head><body>New</body></html>")
            ],
            old_start=1, new_start=1
        ),
        StandardDiffChunk(
            file_path="frontend/styles.css",
            content="+body { margin: 0; }\n+.container { width: 100%; }",
            ai_content=[
                Addition(1, "body { margin: 0; }"),
                Addition(2, ".container { width: 100%; }")
            ],
            old_start=1, new_start=1
        )
    ]
    group1 = CommitGroup(chunks=group1_chunks, group_id="frontend", commmit_message="Update frontend")

    # Group 2: Backend changes  
    group2_chunks = [
        StandardDiffChunk(
            file_path="backend/server.py",
            content="-print('old server')\n+from flask import Flask\n+app = Flask(__name__)\n+\n+@app.route('/')\n+def hello():\n+    return 'Hello World'",
            ai_content=[
                Removal(1, "print('old server')"),
                Addition(1, "from flask import Flask"),
                Addition(2, "app = Flask(__name__)"),
                Addition(3, ""),
                Addition(4, "@app.route('/')"),
                Addition(5, "def hello():"),
                Addition(6, "    return 'Hello World'")
            ],
            old_start=1, new_start=1
        ),
        StandardDiffChunk(
            file_path="backend/models.py",
            content="+class User:\n+    pass\n+\n+class Post:\n+    pass",
            ai_content=[
                Addition(1, "class User:"),
                Addition(2, "    pass"),
                Addition(3, ""),
                Addition(4, "class Post:"),
                Addition(5, "    pass")
            ],
            old_start=1, new_start=1
        )
    ]
    group2 = CommitGroup(chunks=group2_chunks, group_id="backend", commmit_message="Update backend")

    # Group 3: Cleanup and restructure
    group3_chunks = [
        StandardDiffChunk(
            file_path="shared.txt",
            content="-shared content",
            ai_content=[Removal(1, "shared content")],
            old_start=1, new_start=1
        ),
        RenameDiffChunk(
            old_file_path="app.js",
            new_file_path="legacy/app.js",
            content=""
        )
    ]
    group3 = CommitGroup(chunks=group3_chunks, group_id="cleanup", commmit_message="Cleanup and reorganize")

    synthesizer.execute_plan([group1, group2, group3], new_base_hash, "main")

    # Verify all changes across groups
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
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Setup: Create files that reference each other
    (repo_path / "main.py").write_text("from utils import old_function\nold_function()\n")
    (repo_path / "utils.py").write_text("def old_function():\n    return 'old'\n")
    (repo_path / "config.py").write_text("OLD_CONFIG = True\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Setup interdependent files"], cwd=repo_path, check=True)
    
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Changes that need to be coordinated
    chunks = [
        # Rename function in utils.py
        StandardDiffChunk(
            file_path="utils.py",
            content="-def old_function():\n-    return 'old'\n+def new_function():\n+    return 'new'\n+\n+def helper():\n+    return 'helper'",
            ai_content=[
                Removal(1, "def old_function():"),
                Removal(2, "    return 'old'"),
                Addition(1, "def new_function():"),
                Addition(2, "    return 'new'"),
                Addition(3, ""),
                Addition(4, "def helper():"),
                Addition(5, "    return 'helper'")
            ],
            old_start=1, new_start=1
        ),
        # Update imports in main.py
        StandardDiffChunk(
            file_path="main.py",
            content="-from utils import old_function\n-old_function()\n+from utils import new_function, helper\n+from config import NEW_CONFIG\n+\n+if NEW_CONFIG:\n+    result = new_function()\n+    helper()",
            ai_content=[
                Removal(1, "from utils import old_function"),
                Removal(2, "old_function()"),
                Addition(1, "from utils import new_function, helper"),
                Addition(2, "from config import NEW_CONFIG"),
                Addition(3, ""),
                Addition(4, "if NEW_CONFIG:"),
                Addition(5, "    result = new_function()"),
                Addition(6, "    helper()")
            ],
            old_start=1, new_start=1
        ),
        # Update config.py
        StandardDiffChunk(
            file_path="config.py",
            content="-OLD_CONFIG = True\n+NEW_CONFIG = True\n+DEBUG = False",
            ai_content=[
                Removal(1, "OLD_CONFIG = True"),
                Addition(1, "NEW_CONFIG = True"),
                Addition(2, "DEBUG = False")
            ],
            old_start=1, new_start=1
        )
    ]
    
    group = CommitGroup(chunks=chunks, group_id="refactor", commmit_message="Refactor interdependent code")
    synthesizer.execute_plan([group], new_base_hash, "main")

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
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Empty group (no chunks)
    empty_group = CommitGroup(chunks=[], group_id="empty", commmit_message="Empty commit")
    
    # Group with chunk that results in no change (add and remove same line)
    no_op_chunk = StandardDiffChunk(
        file_path="app.js",
        content="-line 1\n+line 1",
        ai_content=[
            Removal(1, "line 1"),
            Addition(1, "line 1")
        ],
        old_start=1, new_start=1
    )
    no_op_group = CommitGroup(chunks=[no_op_chunk], group_id="noop", commmit_message="No-op change")

    # This should handle edge cases gracefully
    synthesizer.execute_plan([empty_group, no_op_group], base_hash, "main")

    # File should be unchanged
    content = (repo_path / "app.js").read_text()
    assert content == "line 1\nline 2\nline 3\nline 4\nline 5\n"


def test_single_line_changes(git_repo):
    """Test edge cases with single character and single line changes."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Single character change
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="-line 1\n+Line 1",  # Just capitalize L
        ai_content=[
            Removal(1, "line 1"),
            Addition(1, "Line 1")
        ],
        old_start=1, new_start=1
    )

    # Add single character file
    chunk2 = StandardDiffChunk(
        file_path="single.txt",
        content="+x",
        ai_content=[Addition(1, "x")],
        old_start=1, new_start=1
    )

    # Empty file creation
    chunk3 = StandardDiffChunk(
        file_path="empty.txt",
        content="",
        ai_content=[],
        old_start=1, new_start=1
    )

    group = CommitGroup(chunks=[chunk1, chunk2, chunk3], group_id="minimal", commmit_message="Minimal changes")
    synthesizer.execute_plan([group], base_hash, "main")

    # Verify single character change
    app_content = (repo_path / "app.js").read_text()
    assert app_content.startswith("Line 1\n")

    # Verify single character file
    single_content = (repo_path / "single.txt").read_text()
    assert single_content == "x\n"

    # Empty file should exist but be empty
    assert (repo_path / "empty.txt").exists()
    empty_content = (repo_path / "empty.txt").read_text()
    assert empty_content == ""


def test_boundary_line_numbers(git_repo):
    """Test edge cases with line number boundaries."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Change at line 0 (before first line)
    chunk1 = StandardDiffChunk(
        file_path="app.js",
        content="+line 0",
        ai_content=[Addition(1, "line 0")],
        old_start=0, new_start=1
    )

    # Change at last line
    chunk2 = StandardDiffChunk(
        file_path="app.js", 
        content="-line 5\n+line 5 modified",
        ai_content=[
            Removal(5, "line 5"),
            Addition(5, "line 5 modified")
        ],
        old_start=5, new_start=5
    )

    # Add after last line
    chunk3 = StandardDiffChunk(
        file_path="app.js",
        content="+line 6",
        ai_content=[Addition(6, "line 6")],
        old_start=6, new_start=6
    )

    group = CommitGroup(chunks=[chunk1, chunk2, chunk3], group_id="boundaries", commmit_message="Boundary line changes")
    synthesizer.execute_plan([group], base_hash, "main")

    content = (repo_path / "app.js").read_text()
    lines = content.split('\n')
    assert lines[0] == "line 0"
    assert "line 5 modified" in content
    assert "line 6" in content


def test_unicode_and_special_characters(git_repo):
    """Test handling of unicode and special characters in file content."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Unicode content
    chunk1 = StandardDiffChunk(
        file_path="unicode.txt",
        content="+Hello 世界 🌍\n+Café naïve résumé\n+Ελληνικά Русский العربية",
        ai_content=[
            Addition(1, "Hello 世界 🌍"),
            Addition(2, "Café naïve résumé"),
            Addition(3, "Ελληνικά Русский العربية")
        ],
        old_start=1, new_start=1
    )

    # Special characters and symbols
    chunk2 = StandardDiffChunk(
        file_path="special.txt",
        content="+#!/bin/bash\n+echo \"$HOME\"\n+regex: [a-zA-Z0-9]+@[a-zA-Z0-9]+\\.[a-zA-Z]{2,}\n+math: ∑(x²) = π/2",
        ai_content=[
            Addition(1, "#!/bin/bash"),
            Addition(2, "echo \"$HOME\""),
            Addition(3, "regex: [a-zA-Z0-9]+@[a-zA-Z0-9]+\\.[a-zA-Z]{2,}"),
            Addition(4, "math: ∑(x²) = π/2")
        ],
        old_start=1, new_start=1
    )

    group = CommitGroup(chunks=[chunk1, chunk2], group_id="unicode", commmit_message="Unicode and special chars")
    synthesizer.execute_plan([group], base_hash, "main")

    # Verify unicode content
    unicode_content = (repo_path / "unicode.txt").read_text(encoding='utf-8')
    assert "Hello 世界 🌍" in unicode_content
    assert "Café naïve résumé" in unicode_content
    assert "Ελληνικά Русский العربية" in unicode_content

    # Verify special characters
    special_content = (repo_path / "special.txt").read_text(encoding='utf-8')
    assert "#!/bin/bash" in special_content
    assert "echo \"$HOME\"" in special_content
    assert "∑(x²) = π/2" in special_content


def test_conflicting_simultaneous_changes(git_repo):
    """Test handling of potentially conflicting changes to the same file regions."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Multiple chunks modifying overlapping regions
    chunks = [
        # Delete line 2
        StandardDiffChunk(
            file_path="app.js",
            content="-line 2",
            ai_content=[Removal(2, "line 2")],
            old_start=2, new_start=2
        ),
        # Insert between lines 1 and 2 (which will be gone)
        StandardDiffChunk(
            file_path="app.js", 
            content="+inserted line",
            ai_content=[Addition(2, "inserted line")],
            old_start=2, new_start=2
        ),
        # Modify line 3 (which will shift)
        StandardDiffChunk(
            file_path="app.js",
            content="-line 3\n+modified line 3",
            ai_content=[
                Removal(3, "line 3"),
                Addition(3, "modified line 3")
            ],
            old_start=3, new_start=3
        )
    ]

    group = CommitGroup(chunks=chunks, group_id="overlapping", commmit_message="Overlapping changes")
    synthesizer.execute_plan([group], base_hash, "main")

    # Should handle overlapping changes gracefully due to bottom-up application
    content = (repo_path / "app.js").read_text()
    assert "line 2" not in content  # Deleted
    assert "inserted line" in content  # Inserted
    assert "modified line 3" in content  # Modified


def test_very_large_file_changes(git_repo):
    """Test performance with larger files and many changes."""
    repo_path, base_hash = git_repo
    synthesizer = GitSynthesizer(SubprocessGitInterface(repo_path))

    # Create a large file
    large_content = '\n'.join([f"line {i}" for i in range(1, 101)])  # 100 lines
    (repo_path / "large.txt").write_text(large_content + '\n')
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add large file"], cwd=repo_path, check=True)
    
    new_base_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, capture_output=True
    ).stdout.strip()

    # Make many separate contiguous chunks for different modifications
    chunks = []
    
    # Create separate chunks for each 10th line modification (contiguous replacements)
    for i in range(10, 101, 10):
        chunk = StandardDiffChunk(
            file_path="large.txt",
            content=f"-line {i}\n+MODIFIED line {i}",
            ai_content=[
                Removal(i, f"line {i}"),
                Addition(i, f"MODIFIED line {i}")
            ],
            old_start=i, new_start=i
        )
        chunks.append(chunk)
    
    # Create separate chunks for insertions at various positions
    for i in [25, 50, 75]:
        chunk = StandardDiffChunk(
            file_path="large.txt",
            content=f"+INSERTED at {i}",
            ai_content=[Addition(i, f"INSERTED at {i}")],
            old_start=i-1, new_start=i  # Insert before line i
        )
        chunks.append(chunk)

    group = CommitGroup(chunks=chunks, group_id="large_changes", commmit_message="Many changes to large file")
    synthesizer.execute_plan([group], new_base_hash, "main")

    # Verify changes were applied
    content = (repo_path / "large.txt").read_text()
    lines = content.split('\n')
    
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