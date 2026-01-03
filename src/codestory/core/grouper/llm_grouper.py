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

# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
# -----------------------------------------------------------------------------

import json
import re
from collections.abc import Callable
from typing import Any

from loguru import logger

from codestory.core.data.chunk import Chunk
from codestory.core.data.commit_group import CommitGroup
from codestory.core.data.immutable_chunk import ImmutableChunk
from codestory.core.exceptions import LLMResponseError, LogicalGroupingError
from codestory.core.grouper.interface import LogicalGrouper
from codestory.core.llm import CodeStoryAdapter
from codestory.core.synthesizer.utils import get_patches_chunk

# -----------------------------------------------------------------------------
# Prompts
# -----------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an experienced committer preparing commit messages for a set of code changes.
Your primary task is to analyze the provided code diffs and group them into logical commits, and produce commit messages written from the committer's perspective (first-person where appropriate).

You must output a VALID JSON object. Do not output markdown text, just the JSON.

JSON Schema:
{
    "groups": [
        {
            "group_id": "string (unique id)",
            "commit_message": "string (Conventional Commits format)",
            "extended_message": "string or null",
            "changes": [int, int, ...],
            "description": "string (rationale)"
        }
    ]
}

Commit Message Guidance (committer-perspective):
- Write the `commit_message` as a Conventional Commits style header (e.g., `feat:`, `fix:`, `refactor:`) but authored from the committer's voice. Use short declarative action plus a brief reason in the message body or `extended_message`.
- Prefer first-person rationale when it clarifies intent: e.g., "feat: add X to Y" and in `extended_message` or description explain "I added X because Y" or "I changed A to B to fix Y".
- Keep the header concise and use `extended_message` for additional context, motivation, and any tradeoffs or known limitations.

Guidelines:
1. Semantic Grouping: Group changes based on the committer's intention (feature, fix, refactor, docs, chore). Each group should represent a single logical change the committer would make.
2. Completeness: Every `chunk_id` from the input MUST be assigned to exactly one group.
3. Atomicity: Avoid catch-all groups; favor smaller, focused commits unless changes are genuinely related.
4. Tone: Use the committer's voice for `commit_message` and `extended_message` — explain what you did and why (e.g., "I removed redundant code because it caused X" or "I implemented caching to improve Y").
"""

ANALYSIS_PROMPT_TEMPLATE = """Analyze these code changes and group them:

{guidance}

{changes_json}
"""


class LLMGrouper(LogicalGrouper):
    def __init__(self, model: CodeStoryAdapter):
        self.model = model

    def _prepare_changes(
        self, chunks: list[Chunk], immut_chunks: list[ImmutableChunk]
    ) -> str:
        """Convert chunks to a simplified structure for LLM analysis."""
        changes = []
        diff_map = get_patches_chunk(chunks)

        # Process mutable chunks
        for i in range(len(chunks)):
            changes.append({"chunk_id": i, "change": diff_map.get(i, "(no diff)")})

        # Process immutable chunks
        idx = len(chunks)
        for immut_chunk in immut_chunks:
            patch_content = immut_chunk.file_patch.decode("utf-8", errors="replace")
            # Truncate large patches
            if len(patch_content) > 300:
                patch_content = patch_content[:300] + "... (truncated)"

            changes.append({"chunk_id": idx, "change": patch_content})
            idx += 1

        return json.dumps({"changes": changes}, indent=2)

    def _validate_response(self, data: Any) -> list[dict[str, Any]]:
        """
        Manually validates the JSON structure.
        Expected: { "groups": [ { "group_id":..., "changes":... } ] }
        Returns the list of group dicts if valid, raises LLMResponseError/LogicalGroupingError if not.
        """
        if not isinstance(data, dict):
            raise LLMResponseError("Root JSON must be an object.")

        groups = data.get("groups")
        if not isinstance(groups, list):
            raise LLMResponseError("JSON must contain a 'groups' list.")

        valid_groups = []
        for i, item in enumerate(groups):
            if not isinstance(item, dict):
                continue  # Skip malformed items or raise error

            # Check required fields
            if "changes" not in item:
                logger.warning(f"Group {i} missing 'changes' list. Skipping.")
                continue

            # Ensure changes is a list of ints
            changes = item["changes"]
            if not isinstance(changes, list):
                logger.warning(f"Group {i} 'changes' is not a list. Skipping.")
                continue

            # Normalize fields
            valid_groups.append(
                {
                    "group_id": str(item.get("group_id", f"group_{i}")),
                    "commit_message": str(item.get("commit_message", "update code")),
                    "extended_message": item.get("extended_message"),  # can be None
                    "changes": [
                        int(c)
                        for c in changes
                        if isinstance(c, (int, str)) and str(c).isdigit()
                    ],
                    "description": str(item.get("description", "")),
                }
            )

        return valid_groups

    def _clean_and_parse_json(self, raw_content: str) -> list[dict[str, Any]]:
        """
        Extracts JSON from text and returns the validated list of groups.
        """
        json_data = None

        # 1. Try finding JSON within markdown code blocks or plain brackets
        # Matches { ... } spanning multiple lines
        match = re.search(r"(\{[\s\S]*\})", raw_content)

        if match:
            try:
                json_str = match.group(1)
                json_data = json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 2. If regex failed, try parsing the whole string
        if json_data is None:
            try:
                json_data = json.loads(raw_content)
            except json.JSONDecodeError:
                logger.error("Could not parse JSON from response.")
                logger.debug(f"Raw response: {raw_content}")
                raise LLMResponseError("Model did not return valid JSON.")

        # 3. Validate structure
        return self._validate_response(json_data)

    def _create_commit_groups(
        self,
        groups_data: list[dict[str, Any]],
        all_chunks: list[Chunk | ImmutableChunk],
    ) -> list[CommitGroup]:
        """
        Convert valid dictionary data into domain CommitGroup objects.
        """
        chunk_map = {i: chunk for i, chunk in enumerate(all_chunks)}
        commit_groups: list[CommitGroup] = []
        assigned_chunk_ids: set[int] = set()

        for group_data in groups_data:
            group_chunks = []

            for chunk_id in group_data["changes"]:
                if chunk_id not in chunk_map:
                    continue

                if chunk_id in assigned_chunk_ids:
                    continue  # Skip duplicates

                group_chunks.append(chunk_map[chunk_id])
                assigned_chunk_ids.add(chunk_id)

            if group_chunks:
                commit_groups.append(
                    CommitGroup(
                        chunks=group_chunks,
                        group_id=group_data["group_id"],
                        commit_message=group_data["commit_message"],
                        extended_message=group_data.get("extended_message"),
                    )
                )

        # Fallback for unassigned
        unassigned = []
        for i, chunk in enumerate(all_chunks):
            if i not in assigned_chunk_ids:
                unassigned.append(chunk)

        if unassigned:
            commit_groups.append(
                CommitGroup(
                    chunks=unassigned,
                    group_id="fallback_unassigned",
                    commit_message="chore: update unassigned files",
                    extended_message="These changes were not grouped by the AI analysis.",
                )
            )

        return commit_groups

    def group_chunks(
        self,
        chunks: list[Chunk],
        immut_chunks: list[ImmutableChunk],
        message: str,
        on_progress: Callable[[int], None] | None = None,
    ) -> list[CommitGroup]:
        """
        Main entry point.
        """
        if not (chunks or immut_chunks):
            return []

        if on_progress:
            on_progress(10)

        changes_json = self._prepare_changes(chunks, immut_chunks)
        guidance = f"User Instructions: {message}" if message else ""

        formatted_user_prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            guidance=guidance, changes_json=changes_json
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": formatted_user_prompt},
        ]

        if on_progress:
            on_progress(30)

        try:
            # Call Model
            raw_response = self.model.invoke(messages)

            if on_progress:
                on_progress(80)

            # Parse & Validate
            valid_groups_data = self._clean_and_parse_json(raw_response)

            if on_progress:
                on_progress(90)

            # Create Domain Objects
            result = self._create_commit_groups(
                valid_groups_data, chunks + immut_chunks
            )

            if on_progress:
                on_progress(100)

            return result

        except Exception as e:
            logger.exception("Error during LLM grouping")
            raise LogicalGroupingError(f"Grouping failed: {str(e)}") from e
