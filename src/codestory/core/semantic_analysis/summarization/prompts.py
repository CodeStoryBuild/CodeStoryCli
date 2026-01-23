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
# Single Chunk Summary Prompts
# -----------------------------------------------------------------------------

INITIAL_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

{message}

Input Format
The user will provide an annotated code change in XML.
- <metadata>: Context about the languages and symbols of the change.
- <patch>: The diff for the change, using specific line tags:
  - [add]: Lines added (Focus on these for the intent).
  - [rem]: Lines removed.
  - [ctx]: Context lines (Use these for understanding, but do not describe them as changes).
  - [h]:   File headers or hunk markers.

Task
Write a single, concise commit message for the change.

Constraints
- Imperative mood (e.g., "Add", "Fix", "Update").
- Max 72 characters.
- Describe the change, not the goal
- Focus on the logic in <patch>, using <metadata> for context
- Output only the commit message

Example input:
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[ctx] class Authenticator:
[add]     def login(self, user, pwd):
[add]         return True
</patch>

Example output:
Add login method to Authenticator
"""

INITIAL_SUMMARY_USER = """Here is a code change:

{changes}

Commit message:"""


# -----------------------------------------------------------------------------
# Batched Chunk Summary Prompts
# -----------------------------------------------------------------------------

BATCHED_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple code changes in XML format (each wrapped in a <change_group> tag with an index), write one commit message per change.
{message}

Input Format
The user will provide code changes in XML.
- <metadata>: Context about the languages and symbols for the change.
- <patch>: The diff for the change, using specific line tags:
  - [add]: Lines added (Focus on these for the intent).
  - [rem]: Lines removed.
  - [ctx]: Context lines (Use these for understanding, but do not describe them as changes).
  - [h]:   File headers or hunk markers.

Rules:
- Output a numbered list with one message per change
- Each message: single line, max 72 characters, imperative mood
- Match the input order exactly

Example input:
### Change 1
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[add] def login(user, pwd):
[add]     return True
</patch>

---

### Change 2
<metadata>
languages: python
symbols: function parse_config
</metadata>
<patch>
[h] --- a/config.py
[h] +++ b/config.py
[rem] def parse_config(path):
[add] def parse_config(path, soft=True):
</patch>

Example output:
1. Add login method to Authenticator
2. Update config parser with soft mode
"""

BATCHED_SUMMARY_USER = """Here are {count} code changes:

{changes}

Provide {count} commit messages as a numbered list:"""


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
- Output only the commit message

Example input:
- Add login method
- Fix session validation
- Update logout logic

Example output:
Update authentication logic and add login method"""

CLUSTER_SUMMARY_USER = """Here are related commit messages:

{summaries}

Combined commit message:"""


BATCHED_CLUSTER_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple groups of related commit messages, combine each group into one cohesive commit message.
{message}
Rules:
- Output a numbered list with one message per group
- Each message: single line, max 72 characters, imperative mood
- Match the input order exactly

Example input:
### Group 1
- Add login method
- Fix session validation

### Group 2
- Update config parser
- Add tests for parser

Example output:
1. Add login and session validation
2. Update config parser and add tests"""

BATCHED_CLUSTER_SUMMARY_USER = """Here are {count} groups of related commit messages:

{groups}

Provide {count} combined commit messages as a numbered list:"""


# -----------------------------------------------------------------------------
# Descriptive Chunk Summary Prompts
# -----------------------------------------------------------------------------

INITIAL_DESCRIPTIVE_SUMMARY_SYSTEM = """You are an expert developer analyzing code changes.

{message}

Input Format
The user will provide an annotated code change in XML.
- <metadata>: Context about the languages and symbols.
- <patch>: The diff for the change.

Task
Write a descriptive summary of the change (3-5 sentences).
- Focus on WHAT changed and WHY (if inferable).
- precise technical details are encouraged.
- Do NOT format as a commit message. Use full sentences.

Example input:
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[ctx] class Authenticator:
[add]     def login(self, user, pwd):
[add]         return True
</patch>

Example output:
The `Authenticator.login` method was added to `auth.py`, implementing credential validation. This method takes a username and password and returns a boolean indicating success. This appears to be the initial implementation of the authentication flow.
"""

BATCHED_DESCRIPTIVE_SUMMARY_SYSTEM = """You are an expert developer analyzing code changes.

Given multiple code changes in XML format (each wrapped in a <change_group> tag with an index), write a descriptive summary for each change.
{message}
Rules:
- Output a numbered list with one summary per change.
- Each summary should be a single paragraph (3-5 sentences).
- Descriptive, technical, full sentences.
- Match input order exactly.

Example input:
### Change 1
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[add] def login(user, pwd):
[add]     return True
</patch>

---

### Change 2
<metadata>
languages: python
symbols: function parse_config
</metadata>
<patch>
[h] --- a/config.py
[h] +++ b/config.py
[rem] def parse_config(path):
[add] def parse_config(path, soft=True):
</patch>

Example output:
1. The `Authenticator.login` method was added to `auth.py`. It validates user credentials by checking the provided username and password against the database, returning True on success.
2. The `parse_config` function in `config.py` was updated to accept a new `soft` parameter. This allows for soft parsing where errors are logged instead of raising an exception.
"""

# -----------------------------------------------------------------------------
# Cluster from Descriptive Summary Prompts
# -----------------------------------------------------------------------------

CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple descriptive summaries of code changes, synthesize them into a single cohesive commit message.
{message}
Rules:
- Single line, max 72 characters.
- Imperative mood (Add, Update, Remove, Refactor).
- Capture the high-level intent that groups these changes.

Example input:
- The `Authenticator.login` method was added to `auth.py`. It validates user credentials.
- The `Session` class was updated to track login times in `session.py`.
- Logout functionality was exposed in the API.

Example output:
Implement user authentication and session tracking
"""

BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple groups of descriptive summaries (describing code changes), generate one cohesive commit message for each group.
{message}
Rules:
- Output a numbered list with one message per group.
- Each message: single line, max 72 characters, imperative mood.
- Match input order exactly.

Example input:
### Group 1
- The `Authenticator` class was added.
- Login validation logic was implemented in `auth.utils`.

### Group 2
- The configuration parser now supports YAML.
- Added unit tests for YAML parsing.

Example output:
1. Implement Authenticator and login validation
2. Add YAML support to config parser
"""
BATCHED_CLUSTER_FROM_DESCRIPTIVE_SUMMARY_USER = """Here are {count} groups of change summaries:

{groups}

Provide {count} combined commit messages as a numbered list:"""


# -----------------------------------------------------------------------------
# Descriptive Commit Message Prompts
# -----------------------------------------------------------------------------

INITIAL_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Input Format
The user will provide an annotated code change in XML.
- <metadata>: Context about the languages and symbols.
- <patch>: The diff for the change.

Task
Write a professional, descriptive commit message for the change.
- Use only plaintext. Do NOT use Markdown formatting (like **bold**, `code`, [links], or # headers).
- Capture the technical details and impact.
{message}

Format:
<optional tag>: (high level description)

(specific things actually changed)
- High level Logic change 1
- High level Logic change 2

Constraints:
- "tag" should be a category like Feat, Fix, Refactor, Docs, Build, etc.
- Max 72 characters for the first line.
- Use a single empty line between the first line and the body.
- Imperative mood (Add, Update, Remove, Refactor) for both the subject and the body.
- Capture the high-level intent that groups these changes.
- Combine similar changes into the same high level change.
- Keep descriptions concise and technical.

Example input:
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[ctx] class Authenticator:
[add]     def login(self, user, pwd):
[add]         return True
</patch>

Example output:
Feat: add login capability to Authenticator

Implement initial authentication flow in Authenticator.
- Add login method with placeholder validation
"""

BATCHED_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple code changes in XML format, write one professional, descriptive commit message per change.
{message}

Format:

<group #>. <optional tag>: (high level description)

(specific things actually changed)
- High level Logic change 1
- High level Logic change 2

Rules:
- Output a numbered list with one message per change.
- Each message must use plaintext only (no Markdown like **bold** or `code`).
- Imperative mood (Add, Update, Remove, Refactor) for both the subject and the body.
- Capture the high-level intent that groups these changes.
- Combine similar changes descriptions into the same high level change
- Be concise and technical.
- Match input order exactly.

Example input:
### Group 1
<metadata>
languages: python
symbols: class Authenticator
</metadata>
<patch>
[h] --- a/auth.py
[h] +++ b/auth.py
[ctx] class Authenticator:
[add]     def login(self, user, pwd):
[add]         return True
</patch>
### Group 2
<metadata>
languages: javascript
symbols: function parseConfig
</metadata>
<patch>
[h] --- a/config.js
[h] +++ b/config.js
[ctx] function parseConfig(){{
[add]  try{{
[add]     doParse();
[add]  }} catch (error) {{
[add]     return defaultConfig;
[add]  }}
</patch>


Example output:
1. Feat: add login method to Authenticator

   Implement initial authentication logic.
   - Add login method to Authenticator
   - Set up basic validation placeholder

2. Fix: update config parser error handling

   Improve robustness of configuration loading.
   - Add try-catch block to parseConfig
   - Return default config on failure
"""

CLUSTER_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple related commit messages or summaries, combine them into one professional, descriptive commit message.
{message}

Rules:
- Use only plaintext. Do NOT use Markdown formatting.
- Synthesis the high-level intent into the first line (tag: subject).
- Use a single empty line between the first line and the body.
- Imperative mood (Add, Update, Remove, Refactor) for both the subject and the body.
- Use bullet points for specific details.
- Be concise and technical.

Example input:
- Add login method
- Fix session validation
- Update logout logic

Example output:
Feat: enhance user authentication and session management

Improve authentication and session validation flows.
- Add login method for credential verification
- Update session logic to handle token expiration
- Expose new logout endpoint in the API
"""

BATCHED_CLUSTER_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple groups of related commit messages, combine each group into one professional, descriptive commit message.
{message}

Rules:
- Output a numbered list with one message per group.
- Each message must use plaintext only (no Markdown like **bold** or `code`).
- Use the format: tag: (subject) \n\n (body).
- Imperative mood (Add, Update, Remove, Refactor) for both the subject and the body.
- Be concise and technical.
- Match input order exactly.

Example input:
### Group 1
- Add login method
- Fix session validation
- Update logout logic

### Group 2
- Add YAML support to config parser
- Add unit tests for YAML parsing

Example output:
1. Feat: implement authentication logic

   Add core login and session validation components.
   - Implement Authenticator.login
   - Add session state tracking

2. Build: add project scaffolding and configuration

   Establish repository basic structure and documentation.
   - Add .gitignore with standard Python patterns
   - Add README.md with project overview
   - Update config.py with default settings
"""

# -----------------------------------------------------------------------------
# Extra Context Header
# -----------------------------------------------------------------------------

EXTRA_CONTEXT_INSTRUCTIONS = """The following information provides extra context for the changes you are summarizing.
This context should influence the summaries and decisions you make."""

GIT_HISTORY_SECTION = """To help maintain consistency with recent work, here are the historical commit messages:
BEGIN GIT HISTORY
{history}
END GIT HISTORY"""

USER_INTENT_SECTION = """The user has provided additional information about the global intent of all their changes.
You should attempt to use this information to adjust your summaries.
BEGIN INTENT
{intent}
END INTENT"""

EXAMPLES_SECTION = """
### Examples of Context-Aware Summarization

Example 1: Using User Intent
- User Intent: "Refactoring the authentication module to use JWT instead of sessions"
- Standard Summary: "Add token validator and update auth"
- Context-Aware Summary: "Refactor auth: implement JWT token validation"

Example 2: Maintaining History Consistency
- Recent History:
  - "Fix: resolve null pointer in user service"
  - "Temp: add hardcoded validation for email format"
- Standard Summary: "remove hardcoded validation for email format"
- Context-Aware Summary: "Fix the hardcoded validation for email format"
"""


def _create_extra_context_header(
    recent_commits: list[str], intent_message: str | None
) -> str:
    """Format the intent message and git history for inclusion in prompts."""
    if not recent_commits and not intent_message:
        return ""

    context_parts = [EXTRA_CONTEXT_INSTRUCTIONS]

    if recent_commits:
        history = "\n".join(f"- {msg}" for msg in recent_commits)
        context_parts.append(GIT_HISTORY_SECTION.format(history=history))

    if intent_message:
        context_parts.append(USER_INTENT_SECTION.format(intent=intent_message))

    context_parts.append(EXAMPLES_SECTION)

    return "\n" + "\n\n".join(context_parts) + "\n"
