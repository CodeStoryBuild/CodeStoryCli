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
