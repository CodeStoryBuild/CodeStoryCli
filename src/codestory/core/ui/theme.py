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

from colorama import Fore, Style


@dataclass(frozen=True)
class Theme:
    name: str
    styles: dict[str, str]
    reset: str

    def apply(self, key: str, text: str) -> str:
        prefix = self.styles.get(key, "")
        if not prefix:
            return text
        return f"{prefix}{text}{self.reset}"


def _build_themes() -> dict[str, Theme]:
    reset = Style.RESET_ALL
    return {
        "classic": Theme(
            name="classic",
            reset=reset,
            styles={
                "primary": Fore.CYAN + Style.BRIGHT,
                "info": Fore.YELLOW,
                "warn": Fore.YELLOW + Style.BRIGHT,
                "error": Fore.RED + Style.BRIGHT,
                "success": Fore.GREEN + Style.BRIGHT,
                "muted": Fore.WHITE + Style.DIM,
                "label": Fore.CYAN,
                "value": Fore.GREEN,
                "source": Fore.YELLOW,
                "diff_header": Fore.BLUE,
                "diff_between": Fore.WHITE + Style.BRIGHT,
                "diff_header_removed": Fore.RED + Style.BRIGHT,
                "diff_header_added": Fore.GREEN + Style.BRIGHT,
                "diff_hunk": Fore.BLUE,
                "diff_removed": Fore.RED,
                "diff_added": Fore.GREEN,
                "diff_context": Fore.WHITE + Style.DIM,
                "semantic_header": Fore.BLUE,
                "semantic_removed": Fore.RED,
                "semantic_added": Fore.GREEN,
                "semantic_context": Fore.WHITE + Style.DIM,
            },
        ),
        "ocean": Theme(
            name="ocean",
            reset=reset,
            styles={
                "primary": Fore.CYAN + Style.BRIGHT,
                "info": Fore.CYAN,
                "warn": Fore.MAGENTA + Style.BRIGHT,
                "error": Fore.RED + Style.BRIGHT,
                "success": Fore.GREEN + Style.BRIGHT,
                "muted": Fore.BLUE + Style.DIM,
                "label": Fore.CYAN,
                "value": Fore.WHITE + Style.BRIGHT,
                "source": Fore.BLUE,
                "diff_header": Fore.CYAN,
                "diff_between": Fore.BLUE + Style.BRIGHT,
                "diff_header_removed": Fore.RED + Style.BRIGHT,
                "diff_header_added": Fore.GREEN + Style.BRIGHT,
                "diff_hunk": Fore.CYAN + Style.DIM,
                "diff_removed": Fore.RED,
                "diff_added": Fore.GREEN,
                "diff_context": Fore.BLUE + Style.DIM,
                "semantic_header": Fore.CYAN,
                "semantic_removed": Fore.RED,
                "semantic_added": Fore.GREEN,
                "semantic_context": Fore.BLUE + Style.DIM,
            },
        ),
        "mono": Theme(
            name="mono",
            reset="",
            styles={},
        ),
    }


_THEMES = _build_themes()
_current_theme: Theme = _THEMES["classic"]


def set_theme(name: str) -> None:
    global _current_theme
    _current_theme = _THEMES.get(name, _THEMES["classic"])


def get_theme() -> Theme:
    return _current_theme


def available_themes() -> list[str]:
    return sorted(_THEMES.keys())


def themed(key: str, text: str) -> str:
    return _current_theme.apply(key, text)
