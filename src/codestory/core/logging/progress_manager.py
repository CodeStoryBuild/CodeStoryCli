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

"""Global progress bar manager for the codestory CLI.

Provides centralized control over tqdm progress bars, allowing:
- Global access to the active progress bar
- Automatic routing of logger output through tqdm.write() when active
- Silent mode support (when enabled, no progress bars are displayed)
- Nested progress bar support via context manager pattern
"""

import contextlib
from collections.abc import Generator

from tqdm import tqdm


class ProgressBarManager:
    """Static class for managing global progress bar state.

    Similar to loguru's centralized approach, this class provides:
    - set_pbar() context manager for push/pop of progress bars
    - get_pbar() to access the current progress bar
    - is_active() to check if a progress bar is active
    - set_silent() to disable all progress bars

    Usage:
        with ProgressBarManager.set_pbar(my_pbar):
            # pbar is now active, logger output will use tqdm.write()
            pbar = ProgressBarManager.get_pbar()
            if pbar:
                pbar.set_postfix(...)
    """

    _pbar_stack: list[tqdm] = []
    _silent: bool = False

    @classmethod
    @contextlib.contextmanager
    def set_pbar(
        cls,
        pbar: tqdm | None = None,
        description: str | None = None,
        total: int | None = None,
        silent: bool = False,
    ) -> Generator[tqdm | None]:
        """Context manager to set or create the active progress bar.

        On enter: pushes the pbar onto the stack. If pbar is None but description is
        provided, creates a new transient tqdm object.
        On exit: pops from the stack and closes the pbar if it was created internally.

        Args:
            pbar: An existing tqdm progress bar to make active.
            description: Description for a new transient bar (if pbar is None).
            total: Total steps for a new transient bar.
            silent: Local override to disable progress bar.

        Yields:
            The active progress bar, or None if silent.
        """
        if cls._silent or silent:
            yield None
            return

        should_close = False
        if pbar is None:
            if description is None:
                yield None
                return

            pbar = tqdm(
                total=total,
                desc=description,
                unit="step",
                leave=False,
                bar_format="{desc}{postfix}",
            )
            should_close = True

        cls._pbar_stack.append(pbar)
        try:
            yield pbar
        finally:
            if cls._pbar_stack and cls._pbar_stack[-1] is pbar:
                cls._pbar_stack.pop()
            if should_close:
                pbar.close()

    @classmethod
    def get_pbar(cls) -> tqdm | None:
        """Get the currently active progress bar.

        Returns:
            The top of the progress bar stack, or None if empty/silent
        """
        if cls._silent or not cls._pbar_stack:
            return None
        return cls._pbar_stack[-1]

    @classmethod
    def is_active(cls) -> bool:
        """Check if a progress bar is currently active.

        Returns:
            True if there's an active pbar and not in silent mode
        """
        return not cls._silent and bool(cls._pbar_stack)

    @classmethod
    def set_silent(cls, silent: bool) -> None:
        """Enable or disable silent mode.

        When silent, set_pbar() does nothing and get_pbar() returns None.

        Args:
            silent: True to suppress all progress bars
        """
        cls._silent = silent

    @classmethod
    def is_silent(cls) -> bool:
        """Check if silent mode is enabled."""
        return cls._silent

    @classmethod
    def clear(cls) -> None:
        """Clear all state (for testing purposes)."""
        cls._pbar_stack.clear()
        cls._silent = False
