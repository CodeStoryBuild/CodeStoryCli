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

import importlib.metadata
import signal
from unittest.mock import Mock, patch

import pytest
import typer

from codestory.runtimeutil import (
    ensure_utf8_output,
    setup_signal_handlers,
    version_callback,
)

# -----------------------------------------------------------------------------
# ensure_utf8_output
# -----------------------------------------------------------------------------


def test_ensure_utf8_output():
    """Test that stdout and stderr are reconfigured to utf-8."""
    with patch("sys.stdout") as mock_stdout, patch("sys.stderr") as mock_stderr:
        # Setup mocks to have reconfigure method
        mock_stdout.reconfigure = Mock()
        mock_stderr.reconfigure = Mock()

        ensure_utf8_output()

        mock_stdout.reconfigure.assert_called_once_with(encoding="utf-8")
        mock_stderr.reconfigure.assert_called_once_with(encoding="utf-8")


def test_ensure_utf8_output_no_reconfigure():
    """Test that it handles streams without reconfigure method (e.g. during some tests)."""
    with patch("sys.stdout") as mock_stdout, patch("sys.stderr") as mock_stderr:
        # Ensure they don't have reconfigure
        del mock_stdout.reconfigure
        del mock_stderr.reconfigure

        # Should not raise
        ensure_utf8_output()


# -----------------------------------------------------------------------------
# setup_signal_handlers
# -----------------------------------------------------------------------------


def test_setup_signal_handlers():
    """Test that signal handlers are registered."""
    with patch("signal.signal") as mock_signal:
        setup_signal_handlers()

        # Check that handlers were registered for SIGINT and SIGTERM
        assert mock_signal.call_count == 2

        # Verify calls
        calls = mock_signal.call_args_list
        args_list = [call.args[0] for call in calls]
        assert signal.SIGINT in args_list
        assert signal.SIGTERM in args_list

        # Get the handler function passed to signal.signal
        handler = calls[0].args[1]

        # Verify the handler raises typer.Exit(130)
        with pytest.raises(typer.Exit) as excinfo:
            handler(None, None)
        assert excinfo.value.exit_code == 130


# -----------------------------------------------------------------------------
# version_callback
# -----------------------------------------------------------------------------


def test_version_callback_no_flag():
    """Test that nothing happens if flag is False."""
    # Should just return
    version_callback(False)


@patch("typer.echo")
@patch("importlib.metadata.version")
def test_version_callback_installed(mock_version, mock_echo):
    """Test version display when package is installed."""
    mock_version.return_value = "1.2.3"

    with pytest.raises(typer.Exit):
        version_callback(True)

    mock_version.assert_called_once_with("codestory")
    mock_echo.assert_called_once_with("codestory version 1.2.3")


@patch("typer.echo")
@patch("importlib.metadata.version")
def test_version_callback_development(mock_version, mock_echo):
    """Test version display when package is not found (dev mode)."""
    mock_version.side_effect = importlib.metadata.PackageNotFoundError

    with pytest.raises(typer.Exit):
        version_callback(True)

    mock_echo.assert_called_once_with("codestory version: development")
