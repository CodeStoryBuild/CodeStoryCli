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

from codestory.core.exceptions import (
    AIServiceError,
    ChunkingError,
    CodestoryError,
    ConfigurationError,
    DetachedHeadError,
    FileSystemError,
    FixCommitError,
    GitError,
    SynthesizerError,
    ValidationError,
    ai_service_timeout,
    api_key_missing,
    git_not_found,
    invalid_commit_hash,
    not_git_repository,
    path_not_found,
)


def test_exception_inheritance():
    assert issubclass(GitError, CodestoryError)
    assert issubclass(DetachedHeadError, GitError)
    assert issubclass(ValidationError, CodestoryError)
    assert issubclass(ConfigurationError, CodestoryError)
    assert issubclass(AIServiceError, CodestoryError)
    assert issubclass(FileSystemError, CodestoryError)
    assert issubclass(ChunkingError, CodestoryError)
    assert issubclass(SynthesizerError, CodestoryError)
    assert issubclass(FixCommitError, CodestoryError)


def test_git_not_found():
    exc = git_not_found()
    assert isinstance(exc, GitError)
    assert "Git is not installed" in str(exc)
    assert "Please install git" in str(exc)


def test_not_git_repository():
    exc = not_git_repository("/some/path")
    assert isinstance(exc, GitError)
    assert "Not a git repository: /some/path" in str(exc)
    assert "Run 'git init'" in str(exc)


def test_invalid_commit_hash():
    exc = invalid_commit_hash("badhash")
    assert isinstance(exc, ValidationError)
    assert "Invalid commit hash: badhash" in str(exc)


def test_path_not_found():
    exc = path_not_found("/missing/path")
    assert isinstance(exc, ValidationError)
    assert "Path not found: /missing/path" in str(exc)


def test_api_key_missing():
    exc = api_key_missing("openai")
    assert isinstance(exc, ConfigurationError)
    assert "Missing API key for openai" in str(exc)


def test_ai_service_timeout():
    exc = ai_service_timeout("gpt-4", 30)
    assert isinstance(exc, AIServiceError)
    assert "AI service 'gpt-4' timed out after 30 seconds" in str(exc)
