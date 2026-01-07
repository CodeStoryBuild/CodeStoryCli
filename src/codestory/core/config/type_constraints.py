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

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from codestory.core.exceptions import ConfigurationError


class TypeConstraint(ABC):
    """Abstract base for type constraints.

    Subclasses should implement `coerce` which attempts to coerce/validate
    a provided value. If coercion/validation fails, raise ConfigurationError.
    """

    @abstractmethod
    def coerce(self, value: Any) -> Any:
        """Try to coerce and validate `value`.

        Return coerced value or raise.
        """


@dataclass
class RangeTypeConstraint(TypeConstraint):
    min_value: float | int | None = None
    max_value: float | int | None = None
    is_int: bool = False

    def coerce(self, value: Any) -> Any:
        try:
            v = int(value) if self.is_int else float(value)
        except (ValueError, TypeError, OverflowError):
            raise ConfigurationError(
                f"Value {value!r} is not a valid {'int' if self.is_int else 'float'}"
            )

        if self.min_value is not None and v < self.min_value:
            raise ConfigurationError(f"{v} < min {self.min_value}")
        if self.max_value is not None and v > self.max_value:
            raise ConfigurationError(f"{v} > max {self.max_value}")

        return v

    def __str__(self) -> str:
        parts = []
        if self.min_value is not None:
            parts.append(f"min={self.min_value}")
        if self.max_value is not None:
            parts.append(f"max={self.max_value}")
        return f"range({', '.join(parts)})"


@dataclass(init=False)
class LiteralTypeConstraint(TypeConstraint):
    allowed: set[Any]
    allowed_pretty: list[str]
    strs: dict[str, str]

    def __init__(self, allowed: Iterable[Any] = []):
        self.strs = {}
        for val in allowed:
            if not isinstance(val, str):
                continue
            self.strs[str(val).lower()] = val

        self.allowed_pretty = list(allowed)
        self.allowed: set[Any] = set(allowed)

    def coerce(self, value: Any) -> Any:
        if value in self.allowed:
            return value

        if isinstance(value, str) and value.lower() in self.strs:
            return self.strs[value.lower()]

        raise ConfigurationError(
            f"{value!r} not one of allowed values: {self.allowed_pretty}"
        )

    def __str__(self) -> str:
        return f"literal({self.allowed_pretty})"


class BoolConstraint(TypeConstraint):
    def coerce(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value in ("yes", "true", "t", "1"):
            return True
        elif value in ("no", "false", "f", "0"):
            return False
        raise ConfigurationError(f"Cannot coerce {value!r} to bool")

    def __str__(self) -> str:
        return "bool"


class IntConstraint(TypeConstraint):
    def coerce(self, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError, OverflowError):
            raise ConfigurationError(f"Cannot coerce {value!r} to int")

    def __str__(self) -> str:
        return "int"


class FloatConstraint(TypeConstraint):
    def coerce(self, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError, OverflowError):
            raise ConfigurationError(f"Cannot coerce {value!r} to float")

    def __str__(self) -> str:
        return "float"


class StringConstraint(TypeConstraint):
    def coerce(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return str(value)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(f"Cannot coerce {value!r} to str: {e}")

    def __str__(self) -> str:
        return "str"
