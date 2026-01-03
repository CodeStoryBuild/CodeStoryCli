import pytest
from unittest.mock import MagicMock, patch
from vibe.core.commands.git_commands import GitCommands
from vibe.core.data.hunk_wrapper import HunkWrapper
from vibe.core.data.diff_chunk import DiffChunk
from vibe.core.data.composite_diff_chunk import CompositeDiffChunk
from vibe.core.git_interface.interface import GitInterface


class DummyGit(GitInterface):
    def __init__(self, repo_path="/repo"):
        self.repo_path = repo_path
        self.calls = []
        self.binary_output = b""
        self.text_output = ""

    def run_git_binary(self, args):
        self.calls.append(("binary", args))
        return self.binary_output

    def run_git_text(self, args):
        self.calls.append(("text", args))
        return self.text_output


def make_git_commands():
    git = DummyGit()
    return GitCommands(git), git


def test_get_working_diff_with_renames_empty():
    gc, git = make_git_commands()
    git.binary_output = b""
    result = gc.get_working_diff_with_renames()
    assert result == []


def test_get_working_diff_with_renames_decodes():
    gc, git = make_git_commands()
    # Minimal diff with one hunk
    git.binary_output = b"diff --git a/foo.txt b/foo.txt\n--- a/foo.txt\n+++ b/foo.txt\n@@ -1,0 +1,1 @@\n+hello\n"
    result = gc.get_working_diff_with_renames()
    assert isinstance(result, list)
    assert len(result) == 1
    h = result[0]
    assert isinstance(h, HunkWrapper)
    assert h.new_file_path == "foo.txt"
    assert h.old_file_path == "foo.txt"
    assert h.hunk_lines == ["+hello"]


def test_parse_hunks_with_renames_none():
    gc, _ = make_git_commands()
    assert gc._parse_hunks_with_renames(None) == []
    assert gc._parse_hunks_with_renames("") == []


def test_parse_file_metadata_regular():
    gc, _ = make_git_commands()
    lines = ["--- a/foo.txt", "+++ b/foo.txt"]
    old_path, new_path, file_mode = gc._parse_file_metadata(lines)
    assert old_path == "foo.txt"
    assert new_path == "foo.txt"
    assert file_mode is None


def test_parse_file_metadata_new_file():
    gc, _ = make_git_commands()
    lines = ["new file mode 100644", "--- /dev/null", "+++ b/bar.txt"]
    old_path, new_path, file_mode = gc._parse_file_metadata(lines)
    assert old_path is None
    assert new_path == "bar.txt"
    assert file_mode == "100644"


def test_parse_file_metadata_deleted_file():
    gc, _ = make_git_commands()
    lines = ["deleted file mode 100644", "--- a/bar.txt", "+++ /dev/null"]
    old_path, new_path, file_mode = gc._parse_file_metadata(lines)
    assert old_path == "bar.txt"
    assert new_path is None
    assert file_mode == "100644"


def test_parse_file_metadata_rename():
    gc, _ = make_git_commands()
    lines = [
        "diff --git a/old.txt b/new.txt",
        "rename from old.txt",
        "rename to new.txt",
    ]
    # fallback logic
    old_path, new_path, file_mode = gc._parse_file_metadata(lines)
    assert old_path == "old.txt"
    assert new_path == "new.txt"


def test_parse_hunk_start():
    gc, _ = make_git_commands()
    header = "@@ -10,2 +20,3 @@"
    old_start, old_len, new_start, new_len = gc._parse_hunk_start(header)
    assert (old_start, old_len, new_start, new_len) == (10, 2, 20, 3)
    # No length
    header = "@@ -5 +7 @@"
    old_start, old_len, new_start, new_len = gc._parse_hunk_start(header)
    assert (old_start, old_len, new_start, new_len) == (5, 1, 7, 1)
    # Malformed
    header = "@@ nonsense @@"
    assert gc._parse_hunk_start(header) == (0, 0, 0, 0)


def test_reset_calls_git():
    gc, git = make_git_commands()
    gc.reset()
    assert ("text", ["reset"]) in git.calls


def test_track_untracked_with_target():
    gc, git = make_git_commands()
    gc.track_untracked("foo.txt")
    assert ("text", ["add", "-N", "foo.txt"]) in git.calls


def test_track_untracked_all():
    gc, git = make_git_commands()
    git.text_output = "a.txt\nb.txt"
    gc.track_untracked()
    assert ("text", ["add", "-N", "a.txt", "b.txt"]) in git.calls


def test_track_untracked_none():
    gc, git = make_git_commands()
    git.text_output = ""
    gc.track_untracked()
    # Should not call add -N if nothing to add
    assert ("text", ["add", "-N"]) not in git.calls


def test_need_reset_true_false(monkeypatch):
    gc, git = make_git_commands()
    # True case
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: type("R", (), {"returncode": 1})()
    )
    assert gc.need_reset() is True
    # False case
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: type("R", (), {"returncode": 0})()
    )
    assert gc.need_reset() is False


def test_need_track_untracked_true_false():
    gc, git = make_git_commands()
    git.text_output = "foo.txt"
    assert gc.need_track_untracked() is True
    git.text_output = ""
    assert gc.need_track_untracked() is False


def test_get_processed_diff_merges(monkeypatch):
    gc, git = make_git_commands()
    # Patch get_working_diff_with_renames to return two hunks in same file, overlapping
    h1 = HunkWrapper(
        new_file_path="foo.txt",
        old_file_path="foo.txt",
        file_mode=None,
        hunk_lines=["+a"],
        old_start=1,
        new_start=1,
        old_len=1,
        new_len=1,
    )
    h2 = HunkWrapper(
        new_file_path="foo.txt",
        old_file_path="foo.txt",
        file_mode=None,
        hunk_lines=["+b"],
        old_start=1,
        new_start=2,
        old_len=1,
        new_len=1,
    )
    monkeypatch.setattr(
        gc, "get_working_diff_with_renames", lambda target=None: [h1, h2]
    )
    result = gc.get_processed_diff()
    assert len(result) == 1
    assert isinstance(result[0], CompositeDiffChunk)


def test_merge_overlapping_chunks_disjoint():
    gc, _ = make_git_commands()
    d1 = DiffChunk.from_hunk(HunkWrapper("foo.txt", "foo.txt", ["+ a"], 1, 1, 0, 1))
    d2 = DiffChunk.from_hunk(HunkWrapper("foo.txt", "foo.txt", ["+ b"], 10, 10, 0, 1))
    merged = gc.merge_overlapping_chunks([d1, d2])
    assert len(merged) == 2
    assert all(isinstance(x, DiffChunk) for x in merged)


def test_merge_overlapping_chunks_overlap():
    gc, _ = make_git_commands()
    d1 = DiffChunk.from_hunk(HunkWrapper("foo.txt", "foo.txt", ["+ a"], 1, 1, 0, 1))
    d2 = DiffChunk.from_hunk(HunkWrapper("foo.txt", "foo.txt", ["+ a"], 1, 2, 0, 1))
    merged = gc.merge_overlapping_chunks([d1, d2])
    assert len(merged) == 1
    assert isinstance(merged[0], CompositeDiffChunk)


def test_get_current_branch():
    gc, git = make_git_commands()
    git.text_output = "main\n"
    assert gc.get_current_branch() == "main"


def test_get_current_base_commit_hash():
    gc, git = make_git_commands()
    git.text_output = "abc123\n"
    assert gc.get_current_base_commit_hash() == "abc123"
