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
"""
Prompts for chunk summarization.
"""

# -----------------------------------------------------------------------------
# Single Chunk Summary Prompts
# -----------------------------------------------------------------------------

INITIAL_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages. 

Given code changes with git patches and metadata (added/removed/modified symbols), write a concise commit message that describes what changed.
{message}
Rules:
- Single line, max 72 characters
- Imperative mood (Add, Update, Remove, Refactor)
- Describe the change, not the goal
- Output only the commit message"""

INITIAL_SUMMARY_USER = """Here is a code change:

{changes}

Commit message:"""


# -----------------------------------------------------------------------------
# Batched Chunk Summary Prompts
# -----------------------------------------------------------------------------

BATCHED_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given a JSON array of code changes, write a commit message for each one. Each change includes git patches and metadata about added/removed/modified symbols.
{message}
Rules:
- Output a JSON array of strings with one message per input change
- Each message: single line, max 72 characters, imperative mood
- Output ONLY the JSON array, no other text
- Match the input order exactly

Example:
Input: [{{"git_patch": "..."}}, {{"git_patch": "..."}}]
Output: ["Add user authentication", "Update config parser"]"""

BATCHED_SUMMARY_USER = """Here are {count} code changes:

{changes}

Provide {count} commit messages as a JSON array:"""


# -----------------------------------------------------------------------------
# Cluster Summary Prompts
# -----------------------------------------------------------------------------

CLUSTER_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple related commit messages, combine them into one cohesive commit message.
{message}
Rules:
- Single line, max 72 characters
- Imperative mood (Add, Update, Remove, Refactor)
- Capture all key changes
- Output only the commit message"""

CLUSTER_SUMMARY_USER = """Here are related commit messages:

{summaries}

Combined commit message:"""


BATCHED_CLUSTER_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given a JSON array where each element contains multiple related commit messages, combine each group into one cohesive commit message.
{message}
Rules:
- Output a JSON array of strings with one message per input group
- Each message: single line, max 72 characters, imperative mood
- Output ONLY the JSON array, no other text
- Match the input order exactly

Example:
Input: [["Add login", "Add logout"], ["Fix parser", "Update tests"]]
Output: ["Add authentication system", "Fix parser and update tests"]"""

BATCHED_CLUSTER_SUMMARY_USER = """Here are {count} groups of related commit messages:

{groups}

Provide {count} combined commit messages as a JSON array:"""
