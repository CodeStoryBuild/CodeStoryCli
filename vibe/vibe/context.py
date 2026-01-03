from pathlib import Path
from typing import Literal, Optional, Sequence
from pydantic import BaseModel

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel

from vibe.core.commands.git_commands import GitCommands
from vibe.core.git_interface.SubprocessGitInterface import (
    SubprocessGitInterface,
)
from vibe.core.git_interface.interface import GitInterface
from vibe.core.llm.config import try_create_model


class GlobalConfig(BaseModel):
    # (format: provider:model-name, e.g., openai:gpt-4, gemini:gemini-2.5-flash)
    model: Optional[str] = None
    api_key: Optional[str] = None
    model_temperature: float = 0.7
    aggresiveness: Literal["Conservative", "Regular", "Extra"] = "Regular"
    verbose: bool = False
    auto_accept: bool = False


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
    message: Optional[str] = None


@dataclass(frozen=True)
class ExpandContext:
    commit_hash: str


@dataclass(frozen=True)
class CleanContext:
    ignore: Sequence[str] | None = None
    min_size: int | None = None
    start_from: str | None = None
    skip_merge: bool = False
