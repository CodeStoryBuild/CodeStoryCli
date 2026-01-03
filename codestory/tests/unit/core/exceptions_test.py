# -----------------------------------------------------------------------------
# codestory - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
#
# codestory is available under a dual-license:
#   1. AGPLv3 (Affero General Public License v3)
#      - See LICENSE.txt and LICENSE-AGPL.txt
#      - Online: https://www.gnu.org/licenses/agpl-3.0.html
#
#   2. Commercial License
#      - For proprietary or revenue-generating use,
#        including SaaS, embedding in closed-source software,
#        or avoiding AGPL obligations.
#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt
#      - Contact: ademfcan@gmail.com
#
# By using this file, you agree to the terms of one of the two licenses above.
# -----------------------------------------------------------------------------


import pytest
from codestory.core.exceptions import (
    codestoryError,
    GitError,
    DetachedHeadError,
    ValidationError,
    ConfigurationError,
    AIServiceError,
    FileSystemError,
    ChunkingError,
    SynthesizerError,
    FixCommitError,
    git_not_found,
    not_git_repository,
    invalid_commit_hash,
    path_not_found,
    api_key_missing,
    ai_service_timeout,
)


def test_exception_inheritance():
    assert issubclass(GitError, codestoryError)
    assert issubclass(DetachedHeadError, GitError)
    assert issubclass(ValidationError, codestoryError)
    assert issubclass(ConfigurationError, codestoryError)
    assert issubclass(AIServiceError, codestoryError)
    assert issubclass(FileSystemError, codestoryError)
    assert issubclass(ChunkingError, codestoryError)
    assert issubclass(SynthesizerError, codestoryError)
    assert issubclass(FixCommitError, codestoryError)


def test_git_not_found():
    exc = git_not_found()
    assert isinstance(exc, GitError)
    assert "Git is not installed" in exc.message
    assert "Please install git" in exc.details


def test_not_git_repository():
    exc = not_git_repository("/some/path")
    assert isinstance(exc, GitError)
    assert "Not a git repository: /some/path" in exc.message
    assert "Run 'git init'" in exc.details


def test_invalid_commit_hash():
    exc = invalid_commit_hash("badhash")
    assert isinstance(exc, ValidationError)
    assert "Invalid commit hash: badhash" in exc.message


def test_path_not_found():
    exc = path_not_found("/missing/path")
    assert isinstance(exc, ValidationError)
    assert "Path not found: /missing/path" in exc.message


def test_api_key_missing():
    exc = api_key_missing("openai")
    assert isinstance(exc, ConfigurationError)
    assert "Missing API key for openai" in exc.message


def test_ai_service_timeout():
    exc = ai_service_timeout("gpt-4", 30)
    assert isinstance(exc, AIServiceError)
    assert "AI service 'gpt-4' timed out after 30 seconds" in exc.message
