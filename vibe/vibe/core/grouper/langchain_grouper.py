import json
import logging
from typing import List, Optional, Set
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .interface import LogicalGrouper
from ..data.models import CommitGroup, ProgressCallback
from ..data.chunk import Chunk
from ..synthesizer.utils import get_patches_chunk
from loguru import logger


class ChangeGroup(BaseModel):
    """Represents a group of related changes as analyzed by the LLM."""

    group_id: str
    commit_message: str
    extended_message: Optional[str]
    changes: List[int]  # List of chunk IDs that belong to this group
    description: Optional[str]  # Brief description of why these changes are grouped


class GroupingResponse(BaseModel):
    """Container for the complete grouping response."""

    groups: List[ChangeGroup]


SYSTEM_PROMPT = """You are an expert code reviewer analyzing code changes.
Your primary task is to analyze the provided code diffs and group them into logical commits based on their intention and purpose.

Your response must be a single, valid JSON object that strictly adheres to the schema provided below.

Guidelines for creating the groups:
1.  **Semantic Grouping**: Group changes based on their underlying intention. A refactoring of a function should be separate from adding a new feature, even if they touch the same file.
2.  **Commit Messages**: Write concise and descriptive commit messages that follow the Conventional Commits specification (e.g., `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
3.  **Extended Messages**: Use the `extended_message` field only for complex changes that require a more detailed explanation.
4.  **Completeness**: Ensure every single `chunk_id` provided in the input is assigned to exactly one group in your output. Do not leave any chunks out.
5.  **Rationale**: Briefly explain your reasoning for the grouping in the `description` field.

{format_instructions}"""

ANALYSIS_PROMPT = """Analyze these code changes and group them by intention:

{optional_guidance_message}

{changes_json}

Return a JSON response that strictly follows the schema.
Ensure every chunk_id is assigned to exactly one group."""


class LangChainGrouper(LogicalGrouper):
    def __init__(self, chat_model: BaseChatModel):
        """Initialize the grouper with a LangChain chat model."""
        self.chat_model = chat_model
        self.output_parser = PydanticOutputParser(pydantic_object=GroupingResponse)

    def _prepare_changes(self, chunks: List[Chunk]) -> str:
        """Convert chunks to a structured format for LLM analysis."""
        changes = []
        diff_map = get_patches_chunk(chunks)
        for i, _ in enumerate(chunks):
            # Get the JSON representation of the chunk
            data = {}
            data["change"] = diff_map.get(i, "(no diff)")
            # Add a unique ID for reference
            data["chunk_id"] = i
            changes.append(data)
        return json.dumps({"changes": changes}, indent=2)

    def _create_commit_groups(
        self, response: GroupingResponse, original_chunks: List[Chunk]
    ) -> List[CommitGroup]:
        """
        Convert LLM's response into CommitGroup objects, with mitigations for
        duplicate and unassigned chunks.
        """
        # Create a lookup map for chunks from the original list
        chunk_map = {i: chunk for i, chunk in enumerate(original_chunks)}

        commit_groups: List[CommitGroup] = []
        assigned_chunk_ids: Set[int] = set()  # Track chunks that have been assigned

        for group_response in response.groups:
            group_chunks: List[Chunk] = []
            for chunk_id in group_response.changes:
                if chunk_id not in chunk_map:
                    logger.warning(
                        f"LLM proposed chunk_id {chunk_id} not found in original chunks. Skipping."
                    )
                    continue

                if chunk_id in assigned_chunk_ids:
                    logger.warning(
                        f"LLM assigned chunk_id {chunk_id} to multiple groups. "
                        f"It was already assigned. Assigning to the first encountered group."
                    )
                    continue  # Skip duplicate assignment

                # Assign the chunk to this group
                group_chunks.append(chunk_map[chunk_id])
                assigned_chunk_ids.add(chunk_id)

            if group_chunks:
                commit_groups.append(
                    CommitGroup(
                        chunks=group_chunks,
                        group_id=group_response.group_id,
                        commit_message=group_response.commit_message,
                        extended_message=group_response.extended_message,
                    )
                )

        # Mitigation 2: Handle chunks not assigned by the LLM
        unassigned_chunks: List[Chunk] = []
        unassigned_chunk_ids: List[int] = []
        for i, chunk in enumerate(original_chunks):
            if i not in assigned_chunk_ids:
                unassigned_chunks.append(chunk)
                unassigned_chunk_ids.append(i)

        if unassigned_chunks:
            logger.warning(
                f"LLM failed to assign {len(unassigned_chunks)} chunks to any group. "
                f"Chunk IDs: {unassigned_chunk_ids}. Creating a fallback group."
            )
            commit_groups.append(
                CommitGroup(
                    chunks=unassigned_chunks,
                    group_id="fallback-unassigned-changes",
                    commit_message="chore: Fallback for unassigned changes",
                    extended_message="These changes were not assigned to a specific group by the AI. "
                    "Review them manually.",
                )
            )

        return commit_groups

    def _estimate_progress(self, content: str) -> None:
        """Provide heuristic progress estimation based on number of output tokens."""
        if not content:
            return

        # Estimate tokens by splitting on whitespace and common separators
        # This is a rough approximation of token count
        n_tokens = (
            len(content.split())
            + content.count(",")
            + content.count("{")
            + content.count("}")
        )

        progress = min(95, n_tokens // 5)
        return progress

    def group_chunks(
        self,
        chunks: List[Chunk],
        message: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[CommitGroup]:
        """
        Group chunks using LangChain chat model to analyze intentions and relationships.

        Args:
            chunks: List of Chunk objects to analyze and group
            message: Optional user guidance message
            on_progress: Optional callback for progress updates

        Returns:
            List of CommitGroup objects with semantically related changes

        Raises:
            ValueError: If LLM's response cannot be parsed or is invalid
        """
        if not chunks:
            return []

        if on_progress:
            on_progress(5)

        # Prepare the changes for analysis
        changes_json = self._prepare_changes(chunks)

        optional_guidance_message = (
            f"Custom user instructions: {message}" if message else ""
        )

        # Create the prompt template
        prompt_template = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", ANALYSIS_PROMPT)]
        )

        # Format the prompt with our specific data
        formatted_prompt = prompt_template.format_messages(
            format_instructions=self.output_parser.get_format_instructions(),
            optional_guidance_message=optional_guidance_message,
            changes_json=changes_json,
        )

        # Stream the response
        accumulated_content = ""
        try:
            stream = self.chat_model.stream(formatted_prompt)

            for chunk in stream:
                if hasattr(chunk, "content") and chunk.content:
                    accumulated_content += chunk.content
                    if on_progress:
                        progress = self._estimate_progress(accumulated_content)
                        on_progress(progress)
        except Exception as e:
            raise ValueError(f"Error during LLM streaming: {str(e)}")

        if on_progress:
            on_progress(95)

        # Parse the complete response
        try:
            parsed_response = self.output_parser.parse(accumulated_content)
        except Exception as e:
            raise ValueError(f"Failed to parse LLM response: {str(e)}")

        if on_progress:
            on_progress(100)

        # Apply mitigations during the conversion to CommitGroup objects
        return self._create_commit_groups(parsed_response, chunks)
