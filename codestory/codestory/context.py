"""
-----------------------------------------------------------------------------
/*
 * Copyright (C) 2025 CodeStory
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; Version 2.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, you can contact us at support@codestory.build
 */
-----------------------------------------------------------------------------
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from codestory.core.commands.git_commands import GitCommands
from codestory.core.config.type_constraints import (
    BoolConstraint,
    LiteralTypeConstraint,
    RangeTypeConstraint,
    StringConstraint,
)
from codestory.core.git_interface.interface import GitInterface
from codestory.core.git_interface.SubprocessGitInterface import (
    SubprocessGitInterface,
)
from codestory.core.llm import CodeStoryAdapter, ModelConfig


@dataclass
class GlobalConfig:
    model: str | None = None
    api_key: str | None = None
    temperature: float = 0.7
    aggresiveness: Literal["Conservative", "Regular", "Extra"] = "Regular"
    verbose: bool = False
    auto_accept: bool = False
    silent: bool = False

    constraints = {
        "model": StringConstraint(),
        "api_key": StringConstraint(),
        "temperature": RangeTypeConstraint(min_value=0.0, max_value=1.0),
        "aggresiveness": LiteralTypeConstraint(
            allowed=("Conservative", "Regular", "Extra")
        ),
        "verbose": BoolConstraint(),
        "auto_accept": BoolConstraint(),
        "silent": BoolConstraint(),
    }


@dataclass(frozen=True)
class GlobalContext:
    repo_path: Path
    model: CodeStoryAdapter | None
    git_interface: GitInterface
    git_commands: GitCommands
    verbose: bool
    temperature: float
    aggresiveness: Literal["Conservative", "Regular", "Extra"]
    auto_accept: bool
    silent: bool

    @classmethod
    def from_global_config(cls, config: GlobalConfig, repo_path: Path):
        # TODO add extra args/max tokens
        if config.model == "no-model" or config.model is None:
            model = None
        else:
            model = CodeStoryAdapter(
                ModelConfig(config.model, config.api_key, config.temperature, None)
            )

        git_interface = SubprocessGitInterface(repo_path)
        git_commands = GitCommands(git_interface)

        return GlobalContext(
            repo_path,
            model,
            git_interface,
            git_commands,
            config.verbose,
            config.temperature,
            config.aggresiveness,
            config.auto_accept,
            config.silent,
        )


@dataclass(frozen=True)
class CommitContext:
    target: Path
    message: str | None = None
    relevance_filter_level: Literal["safe", "standard", "strict", "none"] = "none"
    relevance_filter_intent: str | None = None
    secret_scanner_aggression: Literal["safe", "balanced", "paranoid", "none"] = "none"


@dataclass(frozen=True)
class FixContext:
    commit_hash: str


@dataclass(frozen=True)
class CleanContext:
    ignore: Sequence[str] | None = None
    min_size: int | None = None
    start_from: str | None = None
    skip_merge: bool = False
