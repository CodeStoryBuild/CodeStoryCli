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

import json
from unittest.mock import Mock

import pytest

from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.data.line_changes import Addition
from codestory.core.llm import CodeStoryAdapter
from codestory.core.relevance_filter.relevance_filter import (
    RelevanceFilter,
    RelevanceFilterConfig,
)


class TestRelevanceFilter:
    @pytest.fixture
    def mock_adapter(self):
        return Mock(spec=CodeStoryAdapter)

    def _create_mock_chunk(self, content: str, filename: str = "main.py"):
        """Helper to create a Chunk with specific content."""
        # Create inner DiffChunk
        diff_chunk = DiffChunk.from_parsed_content_slice(
            old_file_path=filename.encode(),
            new_file_path=filename.encode(),
            file_mode=b"100644",
            contains_newline_fallback=False,
            contains_newline_marker=False,
            parsed_slice=[Addition(1, 1, content.encode())],
        )
        # Wrap in Chunk (which is what the filter expects mostly)
        chunk = CompositeDiffChunk(chunks=[diff_chunk])
        return chunk

    def _create_mock_immut_chunk(self, patch_content: str, filename: str = "main.py"):
        """Helper to create an ImmutableChunk with specific patch content."""
        immut_chunk = ImmutableChunk(
            canonical_path=filename.encode(), file_patch=patch_content.encode()
        )
        return immut_chunk

    def test_standard_mode_rejects_print_without_intent(self, mock_adapter):
        """
        Scenario: User adds a print statement. Intent is 'fix bug'.
        Expected: Filter REJECTS it because aggression is 'standard' and intent didn't specify debugging.
        """
        config = RelevanceFilterConfig(level="standard")
        filter_ = RelevanceFilter(mock_adapter, config)

        # Mock LLM Response
        mock_adapter.invoke.return_value = json.dumps(
            {
                "rejected_chunk_ids": [0],
                "reasoning": "Print statement found but intent was just 'fix bug'",
            }
        )

        chunk = self._create_mock_chunk("print('wtf')", "api.py")

        accepted, _, rejected = filter_.filter([chunk], [], intent="fix the login bug")

        assert len(rejected) == 1
        assert len(accepted) == 0

        # Verify prompt contained the intent
        call_args = mock_adapter.invoke.call_args[0][0]  # messages list
        user_prompt = call_args[1]["content"]
        assert 'User Intent: "fix the login bug"' in user_prompt

    def test_standard_mode_accepts_print_with_intent(self, mock_adapter):
        """
        Scenario: User adds a print statement. Intent is 'add logging'.
        Expected: Filter ACCEPTS it because intent overrides the heuristic.
        """
        config = RelevanceFilterConfig(level="standard")
        filter_ = RelevanceFilter(mock_adapter, config)

        # Mock LLM Response (Simulating a smart model that sees the intent)
        mock_adapter.invoke.return_value = json.dumps(
            {"rejected_chunk_ids": [], "reasoning": "Print matches intent"}
        )

        chunk = self._create_mock_chunk("print('logging user action')", "api.py")

        accepted, _, rejected = filter_.filter(
            [chunk], [], intent="add logging for user actions"
        )

        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_safe_mode_ignores_prints(self, mock_adapter):
        """
        Scenario: Aggression is SAFE.
        Expected: Even 'garbage' prints are kept unless they are strict errors.
        """
        config = RelevanceFilterConfig(level="safe")
        filter_ = RelevanceFilter(mock_adapter, config)

        # We need to ensure the system prompt sent to the LLM reflects SAFE mode
        mock_adapter.invoke.return_value = json.dumps({"rejected_chunk_ids": []})

        chunk = self._create_mock_chunk("print('debug')", "test.py")
        filter_.filter([chunk], [], intent="update")

        # Check system prompt in call args
        messages = mock_adapter.invoke.call_args[0][0]
        system_content = messages[0]["content"]
        assert "MODE: SAFE" in system_content

    def test_json_recovery(self, mock_adapter):
        """
        Scenario: LLM returns markdown fences around JSON.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        raw_response = """
        Here is the analysis:
        ```json
        {
            "rejected_chunk_ids": [1],
            "reasoning": "Chunk 1 is junk"
        }
        ```
        """
        mock_adapter.invoke.return_value = raw_response

        c1 = self._create_mock_chunk("valid code")
        c2 = self._create_mock_chunk("junk")

        accepted, _, rejected = filter_.filter([c1, c2], [], intent="feat")

        assert len(accepted) == 1
        assert len(rejected) == 1
        assert rejected[0] == c2

    def test_fail_open_on_exception(self, mock_adapter):
        """
        Scenario: LLM crashes or returns nonsense.
        Expected: Return all chunks as Accepted (Fail Open) to prevent data loss.
        """
        filter_ = RelevanceFilter(mock_adapter, RelevanceFilterConfig())
        mock_adapter.invoke.side_effect = Exception("API Down")

        chunk = self._create_mock_chunk("code")
        accepted, _, rejected = filter_.filter([chunk], [], intent="feat")

        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_filter_only_immutable_chunks_accept_all(self, mock_adapter):
        """
        Scenario: Only immutable chunks provided, all accepted.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        mock_adapter.invoke.return_value = json.dumps(
            {"rejected_chunk_ids": [], "reasoning": "All relevant"}
        )

        immut_chunk1 = self._create_mock_immut_chunk("patch1", "file1.py")
        immut_chunk2 = self._create_mock_immut_chunk("patch2", "file2.py")

        accepted_chunks, accepted_immut, rejected = filter_.filter(
            [], [immut_chunk1, immut_chunk2], intent="update"
        )

        assert len(accepted_chunks) == 0
        assert len(accepted_immut) == 2
        assert len(rejected) == 0
        assert accepted_immut == [immut_chunk1, immut_chunk2]

    def test_filter_only_immutable_chunks_reject_some(self, mock_adapter):
        """
        Scenario: Only immutable chunks, some rejected.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        mock_adapter.invoke.return_value = json.dumps(
            {"rejected_chunk_ids": [0], "reasoning": "First chunk irrelevant"}
        )

        immut_chunk1 = self._create_mock_immut_chunk("irrelevant patch", "file1.py")
        immut_chunk2 = self._create_mock_immut_chunk("relevant patch", "file2.py")

        accepted_chunks, accepted_immut, rejected = filter_.filter(
            [], [immut_chunk1, immut_chunk2], intent="fix bug"
        )

        assert len(accepted_chunks) == 0
        assert len(accepted_immut) == 1
        assert len(rejected) == 1
        assert accepted_immut == [immut_chunk2]
        assert rejected == [immut_chunk1]

    def test_filter_mixed_chunks_and_immutable(self, mock_adapter):
        """
        Scenario: Mix of mutable chunks and immutable chunks.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        mock_adapter.invoke.return_value = json.dumps(
            {
                "rejected_chunk_ids": [
                    1,
                    2,
                ],  # Reject second mutable and first immutable
                "reasoning": "Mixed rejection",
            }
        )

        chunk1 = self._create_mock_chunk("good code", "main.py")
        chunk2 = self._create_mock_chunk("bad code", "main.py")
        immut_chunk1 = self._create_mock_immut_chunk("bad patch", "lib.py")
        immut_chunk2 = self._create_mock_immut_chunk("good patch", "lib.py")

        accepted_chunks, accepted_immut, rejected = filter_.filter(
            [chunk1, chunk2], [immut_chunk1, immut_chunk2], intent="refactor"
        )

        assert len(accepted_chunks) == 1
        assert accepted_chunks == [chunk1]
        assert len(accepted_immut) == 1
        assert accepted_immut == [immut_chunk2]
        assert len(rejected) == 2
        assert rejected == [chunk2, immut_chunk1]

    def test_immutable_chunk_immutability(self, mock_adapter):
        """
        Scenario: Ensure ImmutableChunk instances are not modified during filtering.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        mock_adapter.invoke.return_value = json.dumps(
            {"rejected_chunk_ids": [], "reasoning": "All good"}
        )

        immut_chunk = self._create_mock_immut_chunk("some patch", "test.py")
        original_path = immut_chunk.canonical_path
        original_patch = immut_chunk.file_patch

        accepted_chunks, accepted_immut, rejected = filter_.filter(
            [], [immut_chunk], intent="update"
        )

        # Check that the returned instance is the same and unchanged
        assert accepted_immut[0] is immut_chunk
        assert accepted_immut[0].canonical_path == original_path
        assert accepted_immut[0].file_patch == original_patch

    def test_empty_immutable_chunks(self, mock_adapter):
        """
        Scenario: No immutable chunks provided.
        """
        config = RelevanceFilterConfig()
        filter_ = RelevanceFilter(mock_adapter, config)

        mock_adapter.invoke.return_value = json.dumps(
            {"rejected_chunk_ids": [], "reasoning": "Accepted"}
        )

        chunk = self._create_mock_chunk("code", "main.py")
        accepted_chunks, accepted_immut, rejected = filter_.filter(
            [chunk], [], intent="feat"
        )

        assert len(accepted_chunks) == 1
        assert len(accepted_immut) == 0
        assert len(rejected) == 0
