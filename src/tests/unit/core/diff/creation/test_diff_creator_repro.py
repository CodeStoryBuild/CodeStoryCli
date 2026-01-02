import unittest

from codestory.core.diff.creation.diff_creator import DiffCreator
from codestory.core.diff.creation.hunk_wrapper import HunkWrapper


class TestDiffCreatorRepro(unittest.TestCase):
    def test_regex_anchor(self):
        # Scenario: a diff line that would confuse the old regex
        # Previous regex: .*a/(.+?) b/(.+)
        # Confusing line: "diff --git a/src/codestory/core/data/hunk_wrapper.py b/src/codestory/core/diff/creation/hunk_wrapper.py"
        # The 'data/' part ends in 'a/', so greedy .* matches up to there.

        line = b"diff --git a/src/codestory/core/data/hunk_wrapper.py b/src/codestory/core/diff/creation/hunk_wrapper.py"

        # We test the regex on DiffCreator class directly
        regex = DiffCreator._A_B_PATHS_RE
        match = regex.match(line)

        self.assertIsNotNone(match)
        # Group 1 should be the FULL path
        self.assertEqual(match.group(1), b"src/codestory/core/data/hunk_wrapper.py")
        self.assertEqual(
            match.group(2), b"src/codestory/core/diff/creation/hunk_wrapper.py"
        )

    def test_create_empty_rename_exists(self):
        # Verify method exists and works
        hunk = HunkWrapper.create_empty_rename(
            new_file_path=b"new.py", old_file_path=b"old.py", file_mode=b"100644"
        )
        self.assertEqual(hunk.new_file_path, b"new.py")
        self.assertEqual(hunk.old_file_path, b"old.py")
        self.assertEqual(hunk.hunk_lines, [])
        self.assertEqual(hunk.old_start, 0)


if __name__ == "__main__":
    unittest.main()
