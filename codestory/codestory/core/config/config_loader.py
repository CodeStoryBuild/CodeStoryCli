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


import os
from pathlib import Path

import tomllib
from loguru import logger
from pydantic import BaseModel, TypeAdapter


class ConfigLoader:
    """Handles loading and merging configuration from multiple sources into a unified model."""

    @staticmethod
    def get_full_config(
        config_model: type[BaseModel],
        input_args: dict,
        local_config_path: Path,
        env_app_prefix: str,
        global_config_path: Path,
        custom_config_path: Path | None = None,
    ):
        """Merges configuration from multiple sources with priority: input args, custom config, local config, environment variables, global config."""

        # priority: input_arg,s optional custom config, local_config_path, env vars, global_config_path,
        source_names = [
            "Input Args",
            "Local Config",
            "Environment Variables",
            "Global Config",
        ]
        sources = [
            input_args,
            ConfigLoader.load_toml(local_config_path),
            ConfigLoader.load_env(env_app_prefix),
            ConfigLoader.load_toml(global_config_path),
        ]

        if custom_config_path is not None:
            custom_config = ConfigLoader.load_toml(custom_config_path)
            # custom config is priority #2
            sources.insert(1, custom_config)
            source_names.insert(1, "Custom Config")

        for name, source in zip(source_names, sources, strict=True):
            logger.debug(f"{name=} {source=}")

        type_adapter = TypeAdapter(config_model)
        built_model, used_indexes, used_defaults = ConfigLoader.build(
            config_model, type_adapter, sources
        )

        source_names = [source_names[i] for i in used_indexes]

        return built_model, source_names, used_defaults

    @staticmethod
    def load_toml(path: Path):
        """Loads configuration data from a TOML file, returning an empty dict if the file doesn't exist or is invalid."""

        if not path.exists():
            logger.debug(f"{path} does not exist")
            return {}

        data = {}
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            logger.warning(f"Failed to load {path}: {e}")

        return data

    @staticmethod
    def load_env(app_prefix: str):
        """Extracts configuration values from environment variables prefixed with the app prefix, converting keys to lowercase."""

        data = {}
        for k, v in os.environ.items():
            if k.lower().startswith(app_prefix.lower()):
                key_clean = k[len(app_prefix) :]
                data[key_clean] = v

        return data

    @staticmethod
    def build(
        config_model: type[BaseModel],
        type_adapter: TypeAdapter,
        sources: list[dict],
    ):
        """Builds the configuration model by merging data from sources in priority order, filling in defaults where needed."""

        remaining_keys = set(config_model.model_fields.keys())

        final_data = {}
        used_indices = set()

        # 2. Iterate in order of highest-lowest preference
        for i, d in enumerate(sources):
            # Optimization: Stop if we have everything
            if not remaining_keys:
                break

            # Find which useful keys this dict provides
            # We use set intersection, which is very fast
            contributions = d.keys() & remaining_keys

            if contributions:
                used_indices.add(i)

                # Add these keys to our final data
                for key in contributions:
                    final_data[key] = d[key]

                # Remove found keys so we don't look for them in earlier dicts
                remaining_keys -= contributions

        model = type_adapter.validate_python(final_data, extra="ignore")

        # built model, what sources we used, and if we used any defaults
        return model, used_indices, bool(remaining_keys)
