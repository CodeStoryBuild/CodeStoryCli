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

from unittest.mock import Mock

import pytest

from codestory.core.diff.data.composite_container import CompositeContainer
from codestory.core.diff.data.immutable_diff_chunk import ImmutableDiffChunk
from codestory.core.diff.data.line_changes import Addition, Removal
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.filters.secret_filter import ScannerConfig, SecretsFilter
from codestory.core.git.git_commands import GitCommands
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class TestFileLifecycle:
    """
    Tests specific git operations: Additions, Deletions, Renames.
    """

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file_batch.side_effect = lambda objs: [b"content"] * len(objs)
        return mock

    def test_new_file_addition_blocked_by_name(self, mock_git):
        """Verify that adding a new file with a blocked name (e.g. .env) is rejected
        regardless of content."""
        config = ScannerConfig()

        # New file addition: old_path is None
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=None,
            new_file_path=b".env",
            parsed_content=[Addition(0, 1, b"some_config=1")],
            old_start=0,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1
        assert rejected[0] == container

    def test_new_file_addition_scans_content(self, mock_git):
        """Verify that adding a 'safe' named file still scans its content."""
        config = ScannerConfig(aggression="balanced")

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=None,
            new_file_path=b"script.py",
            parsed_content=[Addition(0, 1, b"api_key = '12345'")],
            old_start=0,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_file_deletion_ignores_removed_secrets(self, mock_git):
        """
        CRITICAL: Deleting code usually involves 'Removal' objects.
        The scanner must NOT flag secrets inside removed lines.
        """
        config = ScannerConfig(aggression="strict")

        # A chunk that removes a hardcoded password
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"auth.py",
            new_file_path=b"auth.py",
            parsed_content=[
                Removal(1, 1, b"password = 'super_secret'"),  # Removing the bad line
                Addition(1, 1, b"password = os.getenv('PASS')"),  # Adding the good line
            ],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        # Since the Addition is safe, the chunk should be accepted.
        # The Removal contains the secret, but we shouldn't scan Removals.
        accepted, rejected = SecretsFilter(
            config, FileManager([container], mock_git)
        ).filter([container])

        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_file_rename_to_blocked_extension(self, mock_git):
        """Verify renaming a safe file (text.txt) to a blocked file (key.pem) is
        rejected."""
        config = ScannerConfig()

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"dummy.txt",
            new_file_path=b"private.pem",  # .pem is blocked by default
            parsed_content=[],  # Even with no content changes (just a rename)
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_file_rename_preserves_content_scanning(self, mock_git):
        """Verify that if a file is renamed AND content is added, we check both."""
        config = ScannerConfig(aggression="balanced")

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"old_name.py",
            new_file_path=b"new_name.py",
            parsed_content=[Addition(1, 1, b"aws_secret = 'AKIA...'")],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1


class TestPathIntegration:
    """Tests nuances of path resolution, bytes vs strings, and nested directories."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file_batch.side_effect = lambda objs: [b"content"] * len(objs)
        return mock

    def test_nested_blocked_file(self, mock_git):
        """Ensure we catch blocked files deep in directories."""
        config = ScannerConfig()

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=None,
            new_file_path=b"src/backend/config/.env.production",
            parsed_content=[],
            old_start=0,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_canonical_path_logic_on_deletion(self, mock_git):
        """
        Edge Case: When deleting a file, new_file_path is None.
        We must check old_file_path.
        """
        config = ScannerConfig()

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"secrets.json",
            new_file_path=None,  # Deletion
            parsed_content=[Removal(1, 1, b"{...}")],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_partial_path_matches_are_safe(self, mock_git):
        """Ensure that 'env.py' is not blocked just because it contains '.env'.

        The regex must be anchored or specific enough.
        """
        config = ScannerConfig()

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=None,
            new_file_path=b"my_env_variables.py",  # Should be safe
            parsed_content=[Addition(0, 1, b"x = 1")],
            old_start=0,
        )
        container = CompositeContainer(containers=[chunk])

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1


class TestImmutableDiffChunkLifecycle:
    """Tests specifically for ImmutableDiffChunks (raw patches), which handle paths and
    diff parsing differently."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file_batch.side_effect = lambda objs: [b"content"] * len(objs)
        return mock

    def test_immutable_rename_detection(self, mock_git):
        """Immutable chunks store path in canonical_path."""
        config = ScannerConfig()

        chunk = ImmutableDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"id_rsa",
            new_file_path=b"id_rsa",
            file_patch=b"...",
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_immutable_patch_parsing_additions_only(self, mock_git):
        """
        Verify we strictly parse lines starting with +
        and ignore lines starting with - in the raw bytes.
        """
        config = ScannerConfig(aggression="strict")

        # A patch that removes a secret and adds a safe line
        patch = (
            b"@@ -10,1 +10,1 @@\n"
            b"- password = 'secret'\n"  # Should be ignored
            b"+ password = env_var"  # Should be scanned (and passed)
        )

        chunk = ImmutableDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"settings.py",
            new_file_path=b"settings.py",
            file_patch=patch,
        )
        container = CompositeContainer(containers=[chunk])

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1

    def test_immutable_patch_header_confusion(self, mock_git):
        """Ensure the '+++' header in diffs isn't confused for an added line."""
        config = ScannerConfig(aggression="strict")

        patch = (
            b"--- a/file.py\n"
            b"+++ b/file.py\n"  # This line starts with +, but is header
            b"@@ ... @@\n"
            b"+ safe_code = 1"
        )

        chunk = ImmutableDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"file.py",
            new_file_path=b"file.py",
            file_patch=patch,
        )
        container = CompositeContainer(containers=[chunk])

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1
