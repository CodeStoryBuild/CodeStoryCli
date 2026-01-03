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


import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from pydantic import BaseModel, ValidationError
from dslate.core.config.config_loader import ConfigLoader

# -----------------------------------------------------------------------------
# Test Models
# -----------------------------------------------------------------------------


class TestConfig(BaseModel):
    val: str | None = None
    number: int = 0
    flag: bool = False


# -----------------------------------------------------------------------------
# ConfigLoader Tests
# -----------------------------------------------------------------------------


def test_load_toml_exists():
    """Test loading a valid TOML file."""
    toml_content = b'val = "test"\nnumber = 42'
    with patch("builtins.open", mock_open(read_data=toml_content)):
        with patch("pathlib.Path.exists", return_value=True):
            data = ConfigLoader.load_toml(Path("config.toml"))
            assert data == {"val": "test", "number": 42}


def test_load_toml_not_exists():
    """Test loading a non-existent file returns empty dict."""
    with patch("pathlib.Path.exists", return_value=False):
        data = ConfigLoader.load_toml(Path("missing.toml"))
        assert data == {}


def test_load_toml_invalid():
    """Test loading an invalid TOML file handles exception."""
    with patch("builtins.open", mock_open(read_data=b"invalid toml content")):
        with patch("pathlib.Path.exists", return_value=True):
            data = ConfigLoader.load_toml(Path("bad.toml"))
            assert data == {}


def test_load_env():
    """Test loading environment variables with prefix."""
    with patch.dict(
        "os.environ", {"APP_VAL": "env_val", "APP_NUMBER": "10", "OTHER": "ignore"}
    ):
        data = ConfigLoader.load_env("APP_")
        assert data == {"VAL": "env_val", "NUMBER": "10"}
        # Note: keys are uppercased in the implementation?
        # Code: key_clean = k[len(app_prefix) :] -> preserves case of the rest?
        # Code: if k.lower().startswith(app_prefix.lower()):
        # Example: APP_VAL -> starts with APP_. key_clean = VAL.
        # So it preserves case of the suffix.


def test_precedence_order():
    """Test the precedence order: Args > Custom > Local > Env > Global."""

    # Setup sources
    args = {"val": "args"}
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
                TestConfig,
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

    # 3. Local should win if no custom/args
    # Note: In get_full_config, sources list is: [args, local, env, global]
    # If custom is present: [args, custom, local, env, global]
    # Wait, let's check the code in Step 123.
    # Line 52: sources = [input_args, load_toml(local), load_env, load_toml(global)]
    # Line 62: sources.insert(1, custom)
    # So order is: Args, Custom, Local, Env, Global.

    # Test Local wins over Env/Global (no custom provided)
    # We need to modify our helper or just run it without custom
    with (
        patch.object(ConfigLoader, "load_toml") as mock_load_toml,
        patch.object(ConfigLoader, "load_env") as mock_load_env,
    ):
        mock_load_env.return_value = env
        mock_load_toml.side_effect = (
            lambda p: local if str(p) == "local.toml" else global_
        )

        config, _, _ = ConfigLoader.get_full_config(
            TestConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
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
            TestConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
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
            TestConfig, {}, Path("local.toml"), "APP_", Path("global.toml"), None
        )
        assert config.val == "global"


def test_validation_error():
    """Test that invalid types raise ValidationError."""
    # 'number' expects int, give it a string that isn't an int
    args = {"number": "not-a-number"}

    with (
        patch.object(ConfigLoader, "load_toml", return_value={}),
        patch.object(ConfigLoader, "load_env", return_value={}),
    ):
        with pytest.raises(ValidationError):
            ConfigLoader.get_full_config(
                TestConfig, args, Path("local.toml"), "APP_", Path("global.toml")
            )
