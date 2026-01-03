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

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from codestory.core.config.type_constraints import (
    BoolConstraint,
    LiteralTypeConstraint,
    RangeTypeConstraint,
    StringConstraint,
    TypeConstraint,
)
from codestory.core.git.git_commands import GitCommands
from codestory.core.git.git_interface import GitInterface
from codestory.core.llm import CodeStoryAdapter, ModelConfig


class CodeStoryConfig(Protocol):
    """Protocol for CodeStory configuration objects."""

    # fields
    # ...
    # indexed per field name
    constraints: dict[str, TypeConstraint]
    descriptions: dict[str, str]
    arg_options: dict[str, list[str]]


@dataclass
class GlobalConfig:
    model: str = "no-model"
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0
    max_tokens: int | None = 32000
    relevance_filtering: bool = False
    relevance_filter_similarity_threshold: float = 0.75
    secret_scanner_aggression: Literal["safe", "standard", "strict", "none"] = "safe"
    fallback_grouping_strategy: Literal[
        "all_together", "by_file_path", "by_file_name", "by_file_extension", "all_alone"
    ] = "all_together"
    chunking_level: Literal["none", "full_files", "all_files"] = "all_files"
    verbose: bool = False
    auto_accept: bool = False
    silent: bool = False
    ask_for_commit_message: bool = False
    display_diff_type: Literal["semantic", "git"] = "semantic"
    custom_language_config: str | None = None
    batching_strategy: Literal["auto", "requests", "prompt"] = "auto"
    custom_embedding_model: str | None = None
    cluster_strictness: float = 0.5
    num_retries: int = 3
    no_log_files: bool = False

    constraints = {
        "model": StringConstraint(),
        "api_key": StringConstraint(),
        "api_base": StringConstraint(),
        "temperature": RangeTypeConstraint(min_value=0.0, max_value=1.0),
        "max_tokens": RangeTypeConstraint(min_value=1, is_int=True),
        "relevance_filtering": BoolConstraint(),
        "relevance_filter_similarity_threshold": RangeTypeConstraint(
            0, 1, is_int=False
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
        "chunking_level": LiteralTypeConstraint(
            allowed=["none", "full_files", "all_files"]
        ),
        "verbose": BoolConstraint(),
        "auto_accept": BoolConstraint(),
        "silent": BoolConstraint(),
        "ask_for_commit_message": BoolConstraint(),
        "display_diff_type": LiteralTypeConstraint(allowed=["semantic", "git"]),
        "custom_language_config": StringConstraint(),
        "batching_strategy": LiteralTypeConstraint(
            allowed=["auto", "requests", "prompt"]
        ),
        "custom_embedding_model": StringConstraint(),
        "cluster_strictness": RangeTypeConstraint(min_value=0.0, max_value=1.0),
        "num_retries": RangeTypeConstraint(min_value=0, max_value=10, is_int=True),
        "no_log_files": BoolConstraint(),
    }

    descriptions = {
        "model": "LLM model (format: provider:model, e.g., openai:gpt-4)",
        "api_key": "API key for the LLM provider",
        "api_base": "Custom API base URL for the LLM provider (optional)",
        "temperature": "Temperature for LLM responses (0.0-1.0)",
        "max_tokens": "Maximum tokens to send per llm request",
        "relevance_filtering": "Whether to filter changes by relevance to your intent ('cst commit' only)",
        "relevance_filter_similarity_threshold": "How similar do changes have to be to your intent to be included. Higher means more strict",
        "secret_scanner_aggression": "How aggresively to scan for secrets ('cst commit' only)",
        "fallback_grouping_strategy": "Strategy for grouping changes that were not able to be analyzed",
        "chunking_level": "Which type of changes should be chunked further into smaller pieces",
        "verbose": "Enable verbose logging output",
        "auto_accept": "Automatically accept all prompts without user confirmation",
        "silent": "Do not output any text to the console, except for prompting acceptance",
        "ask_for_commit_message": "Allow asking you to provide commit messages to optionally override the auto generated ones",
        "display_diff_type": "Type of diff to display when showing diffs (semantic or git)",
        "custom_language_config": "Path to custom language configuration JSON file to override built-in language configs",
        "batching_strategy": "Strategy for batching LLM requests (auto, requests, prompt)",
        "custom_embedding_model": "FastEmbed supported text embedding model (will download on first run if not cached)",
        "cluster_strictness": "Strictness of clustering logical groups together. (0-1) Higher value = higher threshold of similarity required to group together.",
        "num_retries": "How many times to retry calling a model if it fails to return an output (0-10)",
        "no_log_files": "Disable logging to files, only output to console",
    }

    arg_options = {
        "model": ["--model"],
        "api_key": ["--api-key"],
        "api_base": ["--api-base"],
        "temperature": ["--temperature"],
        "max_tokens": ["--max-tokens"],
        "relevance_filtering": ["--relevance-filtering"],
        "relevance_filter_similarity_threshold": [
            "--relevance-filter-similarity-threshold"
        ],
        "secret_scanner_aggression": ["--secret-scanner-aggression"],
        "fallback_grouping_strategy": ["--fallback-grouping-strategy"],
        "chunking_level": ["--chunking-level"],
        "verbose": ["--verbose", "-v"],
        "auto_accept": ["--yes", "-y"],
        "silent": ["--silent", "-s"],
        "ask_for_commit_message": ["--ask-for-commit-message"],
        "display_diff_type": ["--display-diff-type"],
        "custom_language_config": ["--custom-language-config"],
        "batching_strategy": ["--batching-strategy"],
        "custom_embedding_model": ["--custom-embedding-model"],
        "cluster_strictness": ["--cluster-strictness"],
        "num_retries": ["--num-retries"],
        "no_log_files": ["--no-log-files"],
    }

    @classmethod
    def get_cli_params(cls):
        """Generate typer parameter specifications from GlobalConfig metadata.

        Returns a dict mapping field names to their typer.Option
        configuration.
        """
        from dataclasses import fields

        import typer

        params = {}
        for field in fields(cls):
            field_name = field.name

            # Get metadata for this field
            arg_names = cls.arg_options.get(
                field_name, [f"--{field_name.replace('_', '-')}"]
            )
            description = cls.descriptions.get(field_name, "")
            field_type = field.type

            # Build typer.Option kwargs - default is the first positional arg
            option_kwargs = {"help": description}

            # Handle typing to make fields optional (since they can be overridden)
            # All CLI args should be optional to allow config file/env var precedence
            if field_type is bool:
                # For bool fields, keep as bool | None for CLI
                params[field_name] = (
                    bool | None,
                    typer.Option(None, *arg_names, **option_kwargs),
                )
            elif field_type is float:
                params[field_name] = (
                    float | None,
                    typer.Option(None, *arg_names, **option_kwargs),
                )
            elif field_type is int:
                params[field_name] = (
                    int | None,
                    typer.Option(None, *arg_names, **option_kwargs),
                )
            elif hasattr(field_type, "__origin__") and field_type.__origin__ is Literal:
                # Literal types - make optional
                params[field_name] = (
                    field_type | None,
                    typer.Option(None, *arg_names, **option_kwargs),
                )
            else:
                # String or other types - make optional
                params[field_name] = (
                    str | None,
                    typer.Option(None, *arg_names, **option_kwargs),
                )

        return params


@dataclass
class GlobalContext:
    repo_path: Path
    git_interface: GitInterface
    git_commands: GitCommands
    config: GlobalConfig
    current_branch: str
    _model: CodeStoryAdapter | None = None
    _embedder = None

    def get_model(self) -> CodeStoryAdapter | None:
        """Lazy-loaded getter for the model instance."""
        if self.config.model == "no-model":
            return None

        if self._model is not None:
            return self._model
        else:
            self._model = CodeStoryAdapter(
                ModelConfig(
                    self.config.model,
                    self.config.api_key,
                    self.config.api_base,
                    self.config.temperature,
                    self.config.max_tokens,
                )
            )
        return self._model

    def get_embedder(self):
        """Lazy-loaded getter for the embedder instance."""
        from codestory.core.embeddings.embedder import Embedder

        if self._embedder is not None:
            return self._embedder

        self._embedder = Embedder(self.config.custom_embedding_model)
        return self._embedder

    def model_enabled(self) -> bool:
        return self.config.model != "no-model"

    def filter_secrets(self) -> bool:
        return self.config.secret_scanner_aggression != "none"

    def filter_relevance(self) -> bool:
        return self.config.relevance_filtering

    @classmethod
    def from_global_config(
        cls, config: GlobalConfig, repo_path: Path, current_branch: str = ""
    ):
        git_interface = GitInterface(repo_path)
        git_commands = GitCommands(git_interface)
        return GlobalContext(
            repo_path, git_interface, git_commands, config, current_branch
        )
