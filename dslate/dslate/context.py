# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of DSLATE.
#
# DSLATE is available under a dual-license:
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


from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from dslate.core.commands.git_commands import GitCommands
from dslate.core.git_interface.interface import GitInterface
from dslate.core.git_interface.SubprocessGitInterface import (
    SubprocessGitInterface,
)
from dslate.core.llm.config import try_create_model


class GlobalConfig(BaseModel):
    model: str | None = Field(
        default=None,
        description="LLM model (format: provider:model, e.g., openai:gpt-4)",
    )
    api_key: str | None = Field(
        default=None, description="API key for the LLM provider"
    )
    model_temperature: float = Field(
        default=0.7, description="Temperature for LLM responses (0.0-1.0)"
    )
    aggresiveness: Literal["Conservative", "Regular", "Extra"] = Field(
        default="Regular", description="How aggressively to split commits smaller"
    )
    verbose: bool = Field(default=False, description="Enable verbose logging output")
    auto_accept: bool = Field(
        default=False,
        description="Automatically accept all prompts without user confirmation",
    )


@dataclass(frozen=True)
class GlobalContext:
    repo_path: Path
    model: BaseChatModel
    git_interface: GitInterface
    git_commands: GitCommands
    verbose: bool
    model_temperature: float
    aggresiveness: Literal["Conservative", "Regular", "Extra"]
    auto_accept: bool

    @classmethod
    def from_global_config(cls, config: GlobalConfig, repo_path: Path):
        model = try_create_model(config.model, config.api_key)

        git_interface = SubprocessGitInterface(repo_path)
        git_commands = GitCommands(git_interface)

        return GlobalContext(
            repo_path,
            model,
            git_interface,
            git_commands,
            config.verbose,
            config.model_temperature,
            config.aggresiveness,
            config.auto_accept,
        )


@dataclass(frozen=True)
class CommitContext:
    target: Path = "."
    message: str | None = None


@dataclass(frozen=True)
class FixContext:
    commit_hash: str


@dataclass(frozen=True)
class CleanContext:
    ignore: Sequence[str] | None = None
    min_size: int | None = None
    start_from: str | None = None
    skip_merge: bool = False
