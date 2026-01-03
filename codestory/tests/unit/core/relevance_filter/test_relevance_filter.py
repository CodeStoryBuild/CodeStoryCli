import json
import pytest
from unittest.mock import Mock, MagicMock

from codestory.core.relevance_filter.relevance_filter import RelevanceFilter, RelevanceFilterConfig
from codestory.core.data.composite_diff_chunk import CompositeDiffChunk
from codestory.core.data.diff_chunk import DiffChunk
from codestory.core.data.line_changes import Addition
from codestory.core.llm import CodeStoryAdapter

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
            parsed_slice=[Addition(1, 1, content.encode())]
        )
        # Wrap in Chunk (which is what the filter expects mostly)
        chunk = CompositeDiffChunk(chunks=[diff_chunk])
        return chunk

    def test_standard_mode_rejects_print_without_intent(self, mock_adapter):
        """
        Scenario: User adds a print statement. Intent is 'fix bug'.
        Expected: Filter REJECTS it because aggression is 'standard' and intent didn't specify debugging.
        """
        config = RelevanceFilterConfig(aggression="standard")
        filter_ = RelevanceFilter(mock_adapter, config)

        # Mock LLM Response
        mock_adapter.invoke.return_value = json.dumps({
            "rejected_chunk_ids": [0],
            "reasoning": "Print statement found but intent was just 'fix bug'"
        })

        chunk = self._create_mock_chunk("print('wtf')", "api.py")
        
        accepted, _, rejected = filter_.filter([chunk], [], intent="fix the login bug")

        assert len(rejected) == 1
        assert len(accepted) == 0
        
        # Verify prompt contained the intent
        call_args = mock_adapter.invoke.call_args[0][0] # messages list
        user_prompt = call_args[1]["content"]
        assert 'User Intent: "fix the login bug"' in user_prompt

    def test_standard_mode_accepts_print_with_intent(self, mock_adapter):
        """
        Scenario: User adds a print statement. Intent is 'add logging'.
        Expected: Filter ACCEPTS it because intent overrides the heuristic.
        """
        config = RelevanceFilterConfig(aggression="standard")
        filter_ = RelevanceFilter(mock_adapter, config)

        # Mock LLM Response (Simulating a smart model that sees the intent)
        mock_adapter.invoke.return_value = json.dumps({
            "rejected_chunk_ids": [],
            "reasoning": "Print matches intent"
        })

        chunk = self._create_mock_chunk("print('logging user action')", "api.py")
        
        accepted, _, rejected = filter_.filter([chunk], [], intent="add logging for user actions")

        assert len(accepted) == 1
        assert len(rejected) == 0

    def test_safe_mode_ignores_prints(self, mock_adapter):
        """
        Scenario: Aggression is SAFE.
        Expected: Even 'garbage' prints are kept unless they are strict errors.
        """
        config = RelevanceFilterConfig(aggression="safe")
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