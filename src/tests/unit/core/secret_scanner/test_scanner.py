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

from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.data.line_changes import Addition
from codestory.core.secret_scanner.secret_scanner import ScannerConfig, filter_hunks

# For the sake of this test file execution, we assume the classes
# behave as defined in your previous prompt.


class TestScannerPatterns:
    """
    Tests specific Regex logic across different aggression levels.
    """

    def test_safe_mode_detects_aws_keys(self):
        """Safe mode should catch high-confidence secrets like AWS keys."""
        config = ScannerConfig(aggression="safe")

        # Valid AWS Key format
        aws_content = b"AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'"
        chunk = self._create_diff_chunk(content=aws_content)

        accepted, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1
        assert len(accepted) == 0

    def test_safe_mode_ignores_generic_variables(self):
        """Safe mode should NOT catch generic variable assignments."""
        config = ScannerConfig(aggression="safe")

        # This looks suspicious, but in SAFE mode it should pass
        content = b"api_key = 'some_generic_value'"
        chunk = self._create_diff_chunk(content=content)

        accepted, _, rejected = filter_hunks([chunk], [], config)
        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_balanced_mode_detects_generic_keys(self):
        """Balanced mode should catch 'api_key = ...' patterns."""
        config = ScannerConfig(aggression="balanced")

        content = b"const stripeSecret = 'sk_test_4eC39HqLyjWDarjtT1zdp7dc'"
        chunk = self._create_diff_chunk(content=content)

        accepted, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1

    # --- Helper ---
    def _create_diff_chunk(self, content: bytes, filename: bytes = b"test.py"):
        """Helper to create a DiffChunk with a single Addition."""
        # Using the assumed class structure
        addition = Addition(old_line=1, abs_new_line=1, content=content)
        return DiffChunk(
            old_file_path=filename, new_file_path=filename, parsed_content=[addition]
        )


class TestEntropyLogic:
    """
    Tests the Shannon Entropy logic for catching high-randomness strings.
    """

    def test_high_entropy_string_is_rejected(self):
        """Random base64 strings should trigger the entropy filter."""
        config = ScannerConfig(aggression="balanced", entropy_threshold=3)

        # A high entropy string (random characters)
        # "7Fz/8x+92/11+5qQ=="
        high_entropy_line = b"secret = '7Fz/8x+92/11+5qQ=='"
        chunk = self._create_diff_chunk(high_entropy_line)

        _, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1

    def test_low_entropy_string_is_accepted(self):
        """Standard sentences should pass entropy checks."""
        config = ScannerConfig(aggression="balanced", entropy_threshold=4.5)

        # Low entropy (standard English distribution)
        low_entropy_line = b"description = 'The quick brown fox jumps over the dog'"
        chunk = self._create_diff_chunk(low_entropy_line)

        accepted, _, _ = filter_hunks([chunk], [], config)
        assert len(accepted) == 1

    def test_short_strings_ignored(self):
        """Strings below minimum length should be ignored regardless of entropy."""
        config = ScannerConfig(aggression="balanced", entropy_min_len=20)

        # High entropy but short
        short_line = b"key = 'Xy9z!'"
        chunk = self._create_diff_chunk(short_line)

        accepted, _, _ = filter_hunks([chunk], [], config)
        assert len(accepted) == 1

    def _create_diff_chunk(self, content: bytes):
        addition = Addition(old_line=1, abs_new_line=1, content=content)
        return DiffChunk(
            old_file_path=b"file.py",
            new_file_path=b"file.py",
            parsed_content=[addition],
        )


class TestFileFiltering:
    """
    Tests file name blocking, extension ignoring, and glob patterns.
    """

    def test_exact_filename_block(self):
        config = ScannerConfig()
        # .env is in the default blocklist
        chunk = DiffChunk(
            old_file_path=b".env", new_file_path=b".env", parsed_content=[]
        )

        _, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1

    def test_glob_pattern_block(self):
        config = ScannerConfig()
        # default blocks *.key
        chunk = DiffChunk(
            old_file_path=b"certs/production.key",
            new_file_path=b"certs/production.key",
            parsed_content=[],
        )

        _, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1

    def test_ignored_extension_skips_scanning(self):
        """
        Files with ignored extensions (e.g. .png) should be accepted
        even if they contain 'secret' in the binary data.
        """
        config = ScannerConfig(aggression="strict")

        # Valid "bad" content
        bad_content = b"password = 'password'"

        # But in a PNG file
        chunk = DiffChunk(
            old_file_path=b"image.png",
            new_file_path=b"image.png",
            parsed_content=[Addition(1, 1, bad_content)],
        )

        accepted, _, rejected = filter_hunks([chunk], [], config)

        # Should be ACCEPTED because we skip scanning .png files
        assert len(accepted) == 1
        assert len(rejected) == 0


class TestIntegration:
    """
    Tests mixed lists and ImmutableChunk handling.
    """

    def test_mixed_batch_processing(self):
        config = ScannerConfig(aggression="safe")

        good_chunk = DiffChunk(
            old_file_path=b"safe.py",
            new_file_path=b"safe.py",
            parsed_content=[Addition(1, 1, b"print('hello')")],
        )

        bad_chunk = DiffChunk(
            old_file_path=b"keys.py",
            new_file_path=b"keys.py",
            parsed_content=[Addition(1, 1, b"-----BEGIN RSA PRIVATE KEY-----")],
        )

        accepted, _, rejected = filter_hunks([good_chunk, bad_chunk], [], config)

        assert len(accepted) == 1
        assert accepted[0] == good_chunk
        assert len(rejected) == 1
        assert rejected[0] == bad_chunk

    def test_immutable_chunk_parsing(self):
        """
        Verifies that ImmutableChunk checks the raw patch bytes correctly.
        """
        config = ScannerConfig(aggression="balanced")

        # Simulate a Unified Diff
        # +++ header should be ignored
        # - removed lines should be ignored
        # + added lines should be scanned
        patch_bytes = (
            b"--- old.py\n"
            b"+++ new.py\n"
            b"@@ -1,1 +1,1 @@\n"
            b"- harmless_line = 1\n"
            b"+ api_key = '12345_secret'"  # This should trigger detection
        )

        chunk = ImmutableChunk(canonical_path=b"new.py", file_patch=patch_bytes)

        _, _, rejected = filter_hunks([], [chunk], config)
        assert len(rejected) == 1

    def test_immutable_chunk_context_ignored(self):
        """
        Context lines (starting with space) or removed lines (starting with -)
        should NOT trigger a rejection.
        """
        config = ScannerConfig(aggression="balanced")

        # The secret is in the removed line (safe to commit a removal usually)
        patch_bytes = (
            b"@@ -1,1 +1,1 @@\n- api_key = 'bad_value'\n+ api_key = os.getenv('KEY')"
        )

        chunk = ImmutableChunk(canonical_path=b"fix.py", file_patch=patch_bytes)

        _, accepted, _ = filter_hunks([], [chunk], config)
        assert len(accepted) == 1

    def test_custom_blocklist(self):
        config = ScannerConfig(custom_blocklist=["my_internal_server_ip"])

        chunk = DiffChunk(
            old_file_path=b"config.yaml",
            new_file_path=b"config.yaml",
            parsed_content=[Addition(1, 1, b"host: my_internal_server_ip")],
        )

        _, _, rejected = filter_hunks([chunk], [], config)
        assert len(rejected) == 1
