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
tag: (high level description)

(specific things actually changed)
- Logic change 1
- Logic change 2

Constraints:
- "tag" should be a category like Feat, Fix, Refactor, Docs, Build, etc.
- Max 72 characters for the first line.
- Use a single empty line between the first line and the body.

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

Implemented the initial login flow in the Authenticator class.
- Added login method to auth.py
- Provided basic return value for credential validation
"""

BATCHED_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple code changes in XML format, write one professional, descriptive commit message per change.
{message}

Rules:
- Output a numbered list with one message per change.
- Each message must use plaintext only (no Markdown like **bold** or `code`).
- Use the format: tag: (subject) \n\n (body).
- Match input order exactly.

Example output:
1. Feat: add login method to Authenticator

   Implemented initial authentication logic.
   - Added login method to auth.py
   - Set up basic validation placeholder

2. Fix: update config parser error handling

   Improved robustness of configuration loading.
   - Added try-except block to parse_config
   - Now returns default config on failure
"""

CLUSTER_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple related commit messages or summaries, combine them into one professional, descriptive commit message.
{message}

Rules:
- Use only plaintext. Do NOT use Markdown formatting.
- Synthesis the high-level intent into the first line (tag: subject).
- Use a single empty line between the first line and the body.
- Use bullet points for specific details.

Example output:
Feat: enhance user authentication and session management

Implemented comprehensive login, logout, and session validation flows.
- Added login method for credential verification
- Updated session logic to handle token expiration
- Exposed new logout endpoint in the API
"""

BATCHED_CLUSTER_DESCRIPTIVE_COMMIT_SYSTEM = """You are an expert developer writing Git commit messages.

Given multiple groups of related commit messages, combine each group into one professional, descriptive commit message.
{message}

Rules:
- Output a numbered list with one message per group.
- Each message must use plaintext only (no Markdown like **bold** or `code`).
- Use the format: tag: (subject) \n\n (body).
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

   Added core login and session validation components.
   - Implemented Authenticator.login
   - Added session state tracking

2. Build: add project scaffolding and configuration

   Established the repository basic structure and documentation.
   - Added .gitignore with standard Python patterns
   - Added README.md with project overview
   - Updated config.py with default settings
"""
