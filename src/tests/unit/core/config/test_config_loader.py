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
from unittest.mock import mock_open, patch

import pytest

from codestory.core.config.config_loader import ConfigLoader
from codestory.core.config.type_constraints import IntConstraint
from codestory.core.exceptions import ConfigurationError

# -----------------------------------------------------------------------------
# Test Models
# -----------------------------------------------------------------------------


@dataclass
class SampleConfig:
    val: str | None = None
    number: int = 0
    flag: bool = False

    constraints = {
        "number": IntConstraint(),
    }

    descriptions = {}

    arg_options = {}


# -----------------------------------------------------------------------------
# ConfigLoader Tests
# -----------------------------------------------------------------------------


def test_load_toml_exists():
    """Test loading a valid TOML file."""
    toml_content = b'val = "test"\nnumber = 42'
    with (
        patch("builtins.open", mock_open(read_data=toml_content)),
        patch("pathlib.Path.exists", return_value=True),
    ):
        data = ConfigLoader.load_toml(Path("config.toml"))
        assert data == {"val": "test", "number": 42}


def test_load_toml_not_exists():
    """Test loading a non-existent file returns empty dict."""
    with patch("pathlib.Path.exists", return_value=False):
        data = ConfigLoader.load_toml(Path("missing.toml"))
        assert data == {}


def test_load_toml_invalid():
    """Test loading an invalid TOML file handles exception."""
    with (
        patch("builtins.open", mock_open(read_data=b"invalid toml content")),
        patch("pathlib.Path.exists", return_value=True),
    ):
        data = ConfigLoader.load_toml(Path("bad.toml"))
        assert data == {}


def test_load_env():
    """Test loading environment variables with prefix."""
    with patch.dict(
        "os.environ", {"APP_VAL": "env_val", "APP_NUMBER": "10", "OTHER": "ignore"}
    ):
        data = ConfigLoader.load_env("APP_")
        assert data == {"val": "env_val", "number": "10"}


def test_precedence_order():
    """Test the precedence order: Args > Custom > Local > Env > Global."""

    # Setup sources
    custom = {"val": "custom"}
    local = {"val": "local"}
    env = {"val": "env"}
    global_ = {"val": "global"}

    # Helper to run get_full_config with mocked loaders
    def run_config(args_in, custom_path=None):
        with (
            patch.object(ConfigLoader, "load_toml") as mock_load_toml,
            patch.object(ConfigLoader, "load_env") as mock_load_env,
        ):
            # Setup mocks
            mock_load_env.return_value = env

            def side_effect(path):
                if str(path) == "local.toml":
                    return local
                if str(path) == "global.toml":
                    return global_
                if str(path) == "custom.toml":
                    return custom
                return {}

            mock_load_toml.side_effect = side_effect

            config, sources, used_defaults = ConfigLoader.get_full_config(
                SampleConfig,
                args_in,
                Path("local.toml"),
                "APP_",
                Path("global.toml"),
                Path("custom.toml") if custom_path else None,
            )
            return config, sources

    # 1. Args should win
    config, _ = run_config({"val": "args"}, "custom.toml")
    assert config.val == "args"

    # 2. Custom should win over others
    config, _ = run_config({}, "custom.toml")
    assert config.val == "custom"

    # order is: Args, Custom, Local, Env, Global.

    # Test Local wins over Env/Global (no custom provided)
    with (
        patch.object(ConfigLoader, "load_toml") as mock_load_toml,
        patch.object(ConfigLoader, "load_env") as mock_load_env,
    ):
        mock_load_env.return_value = env
        mock_load_toml.side_effect = (
            lambda p: local if str(p) == "local.toml" else global_
        )

        config, _, _ = ConfigLoader.get_full_config(
            SampleConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
        )
        assert config.val == "local"

    # 4. Env should win over Global
    with (
        patch.object(ConfigLoader, "load_toml") as mock_load_toml,
        patch.object(ConfigLoader, "load_env") as mock_load_env,
    ):
        mock_load_env.return_value = env
        mock_load_toml.side_effect = lambda p: {} if str(p) == "local.toml" else global_

        config, _, _ = ConfigLoader.get_full_config(
            SampleConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
        )
        assert config.val == "env"

    # 5. Global should be last resort
    with (
        patch.object(ConfigLoader, "load_toml") as mock_load_toml,
        patch.object(ConfigLoader, "load_env") as mock_load_env,
    ):
        mock_load_env.return_value = {}
        mock_load_toml.side_effect = lambda p: {} if str(p) == "local.toml" else global_

        config, _, _ = ConfigLoader.get_full_config(
            SampleConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
        )
        assert config.val == "global"


def test_validation_error():
    """Test that invalid types raise ValidationError."""
    # 'number' expects int, give it a string that isn't an int
    args = {"number": "not-a-number"}

    with (
        patch.object(ConfigLoader, "load_toml", return_value={}),
        patch.object(ConfigLoader, "load_env", return_value={}),
        pytest.raises(ConfigurationError),
    ):
        config = ConfigLoader.get_full_config(
            SampleConfig, args, Path("local.toml"), "APP_", Path("global.toml")
        )
        assert config is None
