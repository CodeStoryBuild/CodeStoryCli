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

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from codestory.core.config.type_constraints import (
    BoolConstraint,
    LiteralTypeConstraint,
    RangeTypeConstraint,
    StringConstraint,
)
from codestory.core.git_commands.git_commands import GitCommands
from codestory.core.git_interface.interface import GitInterface
from codestory.core.git_interface.SubprocessGitInterface import (
    SubprocessGitInterface,
)
from codestory.core.llm import CodeStoryAdapter, ModelConfig


@dataclass
class GlobalConfig:
    model: str | None = None
    api_key: str | None = None
    logical_grouping_type: Literal["embeddings", "brute_force_llm"] = "embeddings"
    temperature: float = 0.7
    relevance_filter_level: Literal["safe", "standard", "strict", "none"] = "none"
    secret_scanner_aggression: Literal["safe", "standard", "strict", "none"] = "safe"
    fallback_grouping_strategy: Literal[
        "all_together", "by_file_path", "by_file_name", "by_file_extension", "all_alone"
    ] = "all_together"
    split_hunks: bool = True
    verbose: bool = False
    auto_accept: bool = False
    silent: bool = False
    ask_for_commit_message: bool = False

    constraints = {
        "model": StringConstraint(),
        "api_key": StringConstraint(),
        "logical_grouping_type": LiteralTypeConstraint(
            allowed=["embeddings", "brute_force_llm"]
        ),
        "temperature": RangeTypeConstraint(min_value=0.0, max_value=1.0),
        "relevance_filter_level": LiteralTypeConstraint(
            allowed=["safe", "standard", "strict", "none"]
        ),
        "secret_scanner_aggression": LiteralTypeConstraint(
            allowed=["safe", "standard", "strict", "none"]
        ),
        "fallback_grouping_strategy": LiteralTypeConstraint(
            allowed=(
                "all_together",
                "by_file_path",
                "by_file_name",
                "by_file_extension",
                "all_alone",
            )
        ),
        "split_hunks": BoolConstraint(),
        "verbose": BoolConstraint(),
        "auto_accept": BoolConstraint(),
        "silent": BoolConstraint(),
        "ask_for_commit_message": BoolConstraint(),
    }

    descriptions = {
        "model": "LLM model (format: provider:model, e.g., openai:gpt-4)",
        "api_key": "API key for the LLM provider",
        "logical_grouping_type": "Strategy for logically grouping chunks. Note embeddings will make many batched api calls, only really recommended for local models",
        "temperature": "Temperature for LLM responses (0.0-1.0)",
        "relevance_filter_level": "How much to filter irrelevant changes",
        "secret_scanner_aggression": "How aggresively to scan for secrets",
        "fallback_grouping_strategy": "Strategy for grouping chunks that fail annotation",
        "split_hunks": "Whether to split git hunks into smaller atomic chunks",
        "verbose": "Enable verbose logging output",
        "auto_accept": "Automatically accept all prompts without user confirmation",
        "silent": "Do not output any text to the console, except for prompting acceptance",
        "ask_for_commit_message": "Allow asking you to provide commit messages to optionally override the auto generated ones",
    }


@dataclass(frozen=True)
class GlobalContext:
    repo_path: Path
    model: CodeStoryAdapter | None
    git_interface: GitInterface
    git_commands: GitCommands
    config: GlobalConfig

    @classmethod
    def from_global_config(cls, config: GlobalConfig, repo_path: Path):
        if config.model == "no-model" or config.model is None:
            model = None
        else:
            model = CodeStoryAdapter(
                ModelConfig(config.model, config.api_key, config.temperature, None)
            )

        git_interface = SubprocessGitInterface(repo_path)
        git_commands = GitCommands(git_interface)

        return GlobalContext(repo_path, model, git_interface, git_commands, config)


@dataclass(frozen=True)
class CommitContext:
    target: Path
    message: str | None = None
    relevance_filter_level: Literal["safe", "standard", "strict", "none"] = "none"
    secret_scanner_aggression: Literal["safe", "standard", "strict", "none"] = "none"
    relevance_filter_intent: str | None = None
    fail_on_syntax_errors: bool = False


@dataclass(frozen=True)
class FixContext:
    end_commit_hash: str
    start_commit_hash: str | None = None


@dataclass(frozen=True)
class CleanContext:
    ignore: Sequence[str] | None = None
    min_size: int | None = None
    start_from: str | None = None
