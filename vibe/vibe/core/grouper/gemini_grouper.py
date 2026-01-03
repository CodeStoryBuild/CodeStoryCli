"""
GeminiGrouper

A semantic-based implementation of GrouperInterface that uses Google's Gemini API
to analyze diff chunks and group them by intention, using strictly typed responses.
"""

import json
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from vibe.core.data.diff_chunk import DiffChunk
from .interface import GrouperInterface
from ..data.models import CommitGroup


class ChangeGroup(BaseModel):
    """Represents a group of related changes as analyzed by Gemini."""

    group_id: str
    commit_message: str
    branch_name: str
    extended_message: Optional[str]
    changes: List[str]  # List of chunk IDs that belong to this group
    description: Optional[str]  # Brief description of why these changes are grouped


SYSTEM_PROMPT = """You are an expert code reviewer analyzing code changes.
Analyze the provided changes and group them by intention and purpose.
Your response must be valid JSON matching this structure:

{
    "groups": [
        {
            "group_id": "1",
            "commit_message": "feat: Short description following conventional commits",
            "extended_message": "Optional detailed explanation if needed",
            "changes": ["0", "1"],  // IDs of chunks that belong together
            "description": "Why these changes are grouped together"
        }
    ]
}

Guidelines:
1. Use semantic grouping based on change intention
2. Keep commit messages concise and descriptive
3. Follow conventional commits format (feat, fix, refactor, etc)
4. Include extended_message only for complex changes
5. Each change must be assigned to exactly one group
6. Provide brief description of grouping rationale
"""

ANALYSIS_PROMPT = """Analyze these code changes and group them by intention:

{changes_json}

Return a JSON response that strictly follows the schema.
Ensure every chunk_id is assigned to exactly one group.
"""


class GeminiGrouper(GrouperInterface):
    def __init__(self, api_key: str):
        """Initialize the grouper with Gemini API credentials."""
        self.client = genai.Client(api_key=api_key)

    def _prepare_changes(self, chunks: List[DiffChunk]) -> str:
        """Convert chunks to a structured format for Gemini analysis."""
        changes = []
        for i, chunk in enumerate(chunks):
            # Get the JSON representation of the chunk
            change = json.loads(chunk.format_json())
            # Add a unique ID for reference
            change["chunk_id"] = str(i)
            changes.append(change)
        return json.dumps({"changes": changes}, indent=2)

    def _create_commit_groups(
        self, response: List[ChangeGroup], chunks: List[DiffChunk]
    ) -> List[CommitGroup]:
        """Convert Gemini's response into CommitGroup objects."""
        # Create a lookup map for chunks
        chunk_map = {str(i): chunk for i, chunk in enumerate(chunks)}

        commit_groups = []
        for group in response:
            # Collect all chunks for this group
            group_chunks = [
                chunk_map[chunk_id]
                for chunk_id in group.changes
                if chunk_id in chunk_map
            ]

            if not group_chunks:
                continue

            # Create a CommitGroup for these changes
            commit_groups.append(
                CommitGroup(
                    chunks=group_chunks,
                    group_id=group.group_id,
                    branch_name=group.branch_name,
                    commmit_message=group.commit_message,
                    extended_message=group.extended_message,
                )
            )

        return commit_groups

    def group_chunks(self, chunks: List[DiffChunk]) -> List[CommitGroup]:
        """
        Group chunks using Gemini API to analyze intentions and relationships.

        Args:
            chunks: List of ExtendedDiffChunks to analyze and group

        Returns:
            List of CommitGroup objects with semantically related changes

        Raises:
            ValueError: If Gemini's response cannot be parsed or is invalid
        """
        if not chunks:
            return []

        # Prepare the changes for analysis
        changes_json = self._prepare_changes(chunks)

        # Get Gemini's analysis
        prompt = ANALYSIS_PROMPT.format(changes_json=changes_json)

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": list[ChangeGroup],
            },
        )

        # Use the response as a JSON string.
        # print(response.text)

        # Use instantiated objects.
        grouping_response: List[ChangeGroup] = response.parsed

        return self._create_commit_groups(grouping_response, chunks)
