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
from codestory.core.diff.data.line_changes import Addition
from codestory.core.diff.data.standard_diff_chunk import StandardDiffChunk
from codestory.core.filters.secret_filter import ScannerConfig, SecretsFilter
from codestory.core.git.git_commands import GitCommands
from codestory.core.semantic_analysis.annotation.file_manager import FileManager


class TestScannerPatterns:
    """Tests specific Regex logic across different aggression levels."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file.return_value = b"some file content"
        # FileManager uses cat_file_batch, return content for each file requested
        mock.cat_file_batch.side_effect = lambda objs: [b"some file content"] * len(
            objs
        )
        return mock

    def test_safe_mode_detects_aws_keys(self, mock_git):
        """Safe mode should catch high-confidence secrets like AWS keys."""
        config = ScannerConfig(aggression="safe")

        # Valid AWS Key format
        aws_content = b"AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'"
        container = self._create_container(content=aws_content)

        accepted, rejected = SecretsFilter(
            config, FileManager([container], mock_git)
        ).filter([container])
        assert len(rejected) == 1
        assert len(accepted) == 0

    def test_safe_mode_ignores_generic_variables(self, mock_git):
        """Safe mode should NOT catch generic variable assignments."""
        config = ScannerConfig(aggression="safe")

        # This looks suspicious, but in SAFE mode it should pass
        content = b"api_key = 'some_generic_value'"
        container = self._create_container(content=content)

        accepted, rejected = SecretsFilter(
            config, FileManager([container], mock_git)
        ).filter([container])
        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_balanced_mode_detects_generic_keys(self, mock_git):
        """Balanced mode should catch 'api_key = ...' patterns."""
        config = ScannerConfig(aggression="balanced")

        content = b"const stripeSecret = 'sk_test_4eC39HqLyjWDarjtT1zdp7dc'"
        container = self._create_container(content=content)

        accepted, rejected = SecretsFilter(
            config, FileManager([container], mock_git)
        ).filter([container])
        assert len(rejected) == 1
        assert len(accepted) == 0

    # --- Helper ---
    def _create_container(self, content: bytes, filename: bytes = b"test.py"):
        """Helper to create a container with a single StandardDiffChunk."""
        addition = Addition(old_line=1, abs_new_line=1, content=content)
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=filename,
            new_file_path=filename,
            parsed_content=[addition],
            old_start=1,
        )
        return CompositeContainer(containers=[chunk])


class TestEntropyLogic:
    """Tests the Shannon Entropy logic for catching high-randomness strings."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file.return_value = b"some file content"
        mock.cat_file_batch.side_effect = lambda objs: [b"some file content"] * len(
            objs
        )
        return mock

    def test_high_entropy_string_is_rejected(self, mock_git):
        """Random base64 strings should trigger the entropy filter."""
        config = ScannerConfig(aggression="balanced", entropy_threshold=3)

        # A high entropy string (random characters)
        # "7Fz/8x+92/11+5qQ=="
        high_entropy_line = b"secret = '7Fz/8x+92/11+5qQ=='"
        container = self._create_container(high_entropy_line)

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_low_entropy_string_is_accepted(self, mock_git):
        """Standard sentences should pass entropy checks."""
        config = ScannerConfig(aggression="balanced", entropy_threshold=4.5)

        # Low entropy (standard English distribution)
        low_entropy_line = b"description = 'The quick brown fox jumps over the dog'"
        container = self._create_container(low_entropy_line)

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1

    def test_short_strings_ignored(self, mock_git):
        """Strings below minimum length should be ignored regardless of entropy."""
        config = ScannerConfig(aggression="balanced", entropy_min_len=20)

        # High entropy but short
        short_line = b"key = 'Xy9z!'"
        container = self._create_container(short_line)

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1

    def _create_container(self, content: bytes):
        addition = Addition(old_line=1, abs_new_line=1, content=content)
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"file.py",
            new_file_path=b"file.py",
            parsed_content=[addition],
            old_start=1,
        )
        return CompositeContainer(containers=[chunk])


class TestFileFiltering:
    """Tests file name blocking, extension ignoring, and glob patterns."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file.return_value = None  # Assume fine
        mock.cat_file_batch.side_effect = lambda objs: [None] * len(objs)
        return mock

    def test_exact_filename_block(self, mock_git):
        config = ScannerConfig()
        # .env is in the default blocklist
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b".env",
            new_file_path=b".env",
            parsed_content=[],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_glob_pattern_block(self, mock_git):
        config = ScannerConfig()
        # default blocks *.key
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"certs/production.key",
            new_file_path=b"certs/production.key",
            parsed_content=[],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_ignored_extension_skips_scanning(self, mock_git):
        """Files with ignored extensions (e.g. .png) should be accepted even if they
        contain 'secret' in the binary data."""
        config = ScannerConfig(aggression="strict")

        # Valid "bad" content
        bad_content = b"password = 'password'"

        # But in a PNG file
        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"image.png",
            new_file_path=b"image.png",
            parsed_content=[Addition(1, 1, bad_content)],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        accepted, rejected = SecretsFilter(
            config, FileManager([container], mock_git)
        ).filter([container])

        # Should be ACCEPTED because we skip scanning .png files
        assert len(accepted) == 1
        assert len(rejected) == 0


class TestIntegration:
    """Tests mixed lists and ImmutableDiffChunk handling."""

    @pytest.fixture
    def mock_git(self):
        mock = Mock(spec=GitCommands)
        mock.cat_file.return_value = b"some context"
        mock.cat_file_batch.side_effect = lambda objs: [b"some context"] * len(objs)
        return mock

    def test_mixed_batch_processing(self, mock_git):
        config = ScannerConfig(aggression="safe")

        good_chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"safe.py",
            new_file_path=b"safe.py",
            parsed_content=[Addition(1, 1, b"print('hello')")],
            old_start=1,
        )
        good_container = CompositeContainer(containers=[good_chunk])

        bad_chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"keys.py",
            new_file_path=b"keys.py",
            parsed_content=[Addition(1, 1, b"-----BEGIN RSA PRIVATE KEY-----")],
            old_start=1,
        )
        bad_container = CompositeContainer(containers=[bad_chunk])

        accepted, rejected = SecretsFilter(
            config, FileManager([good_container, bad_container], mock_git)
        ).filter([good_container, bad_container])

        assert len(accepted) == 1
        assert accepted[0] == good_container
        assert len(rejected) == 1
        assert rejected[0] == bad_container

    def test_immutable_chunk_parsing(self, mock_git):
        """Verifies that ImmutableDiffChunk checks the raw patch bytes correctly."""
        config = ScannerConfig(aggression="balanced")

        # Simulate a Unified Diff
        patch_bytes = (
            b"--- old.py\n"
            b"+++ new.py\n"
            b"@@ -1,1 +1,1 @@\n"
            b"- harmless_line = 1\n"
            b"+ api_key = '12345_secret'"  # This should trigger detection
        )

        chunk = ImmutableDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"old.py",
            new_file_path=b"new.py",
            file_patch=patch_bytes,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1

    def test_immutable_chunk_context_ignored(self, mock_git):
        """Context lines (starting with space) or removed lines (starting with -) should
        NOT trigger a rejection."""
        config = ScannerConfig(aggression="balanced")

        # The secret is in the removed line (safe to commit a removal usually)
        patch_bytes = (
            b"@@ -1,1 +1,1 @@\n- api_key = 'bad_value'\n+ api_key = os.getenv('KEY')"
        )

        chunk = ImmutableDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"fix.py",
            new_file_path=b"fix.py",
            file_patch=patch_bytes,
        )
        container = CompositeContainer(containers=[chunk])

        accepted, _ = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(accepted) == 1

    def test_custom_blocklist(self, mock_git):
        config = ScannerConfig(custom_blocklist=["my_internal_server_ip"])

        chunk = StandardDiffChunk(
            base_hash="base",
            new_hash="new",
            old_file_path=b"config.yaml",
            new_file_path=b"config.yaml",
            parsed_content=[Addition(1, 1, b"host: my_internal_server_ip")],
            old_start=1,
        )
        container = CompositeContainer(containers=[chunk])

        _, rejected = SecretsFilter(config, FileManager([container], mock_git)).filter(
            [container]
        )
        assert len(rejected) == 1
