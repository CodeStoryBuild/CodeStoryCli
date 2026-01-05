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

import math
import re
from dataclasses import dataclass, field
from re import Pattern
from typing import Literal

# Assumed imports from your codebase
from codestory.core.diff.data.atomic_chunk import AtomicDiffChunk
from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.diff.patch.git_patch_generator import GitPatchGenerator
from codestory.core.diff.pipeline.filter import Filter
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.annotation.file_manager import FileManager

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------


@dataclass
class ScannerConfig:
    aggression: Literal["safe", "standard", "strict"] = "safe"

    # Entropy threshold (0-8). Standard random base64 keys usually sit > 4.5
    entropy_threshold: float = 4

    # Minimum string length to trigger entropy check (avoid checking short words)
    entropy_min_len: int = 16  # Lowered slightly to catch shorter test secrets

    # Custom regex strings to block
    custom_blocklist: list[str] = field(default_factory=list)

    # File glob patterns to reject (e.g. "*.key", ".env*")
    blocked_file_patterns: list[str] = field(
        default_factory=lambda: [
            r".*\.env.*",  # .env, .env.local, prod.env
            r".*\.pem$",  # Private keys
            r".*\.key$",  # Generic key files
            r"^id_rsa$",  # SSH keys
            r".*secrets.*\.json$",
            r".*credentials.*\.xml$",
        ]
    )

    # File extensions to ignore content scanning for (images, locks)
    ignored_extensions: list[str] = field(
        default_factory=lambda: [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".lock",
            ".pdf",
        ]
    )


# -----------------------------------------------------------------------------
# Regex Patterns
# -----------------------------------------------------------------------------

PATTERNS_SAFE = [
    r"-----BEGIN [A-Z]+ PRIVATE KEY-----",
    r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA)[A-Z0-9]{16}",
    r"ghp_[0-9a-zA-Z]{36}",
    r"xox[baprs]-([0-9a-zA-Z]{10,48})?",
    r"sk_live_[0-9a-zA-Z]{24}",
    r"AIza[0-9A-Za-z\\-_]{35}",
]

PATTERNS_BALANCED = [
    # Looks for specific sensitive variable names assigned to string literals
    r"(?i)(api_?key|auth_?token|client_?secret|db_?pass|private_?key|aws_?secret)\s*[:=]\s*['\"][^'\"]+['\"]",
    r"(postgres|mysql|mongodb|redis|amqp)://[a-zA-Z0-9_]+:[a-zA-Z0-9_]+@",
]

PATTERNS_STRICT = [r"(?i)secret"]

# -----------------------------------------------------------------------------
# Entropy Calculation
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Scanner Logic
# -----------------------------------------------------------------------------


class SecretsFilter(Filter):
    def __init__(
        self,
        config: ScannerConfig,
        file_manager: FileManager,
    ):
        self.__config = config
        self.__file_manager = file_manager
        self.__patterns = self.__compile_content_patterns()
        self.__file_blocklist_regex = self.__compile_file_patterns()

    def __shannon_entropy(self, data: str) -> float:
        if not data:
            return 0
        entropy = 0.0
        length = len(data)
        counts = {}
        for char in data:
            counts[char] = counts.get(char, 0) + 1
        for count in counts.values():
            p_x = count / length
            entropy -= p_x * math.log2(p_x)
        return entropy

    def __compile_content_patterns(self) -> list[Pattern]:
        regex_list = list(PATTERNS_SAFE)

        if self.__config.aggression in {"balanced", "strict"}:
            regex_list.extend(PATTERNS_BALANCED)

        if self.__config.aggression == "strict":
            regex_list.extend(PATTERNS_STRICT)

        for block_str in self.__config.custom_blocklist:
            regex_list.append(re.escape(block_str))

        return [re.compile(p) for p in regex_list]

    def __compile_file_patterns(self) -> Pattern:
        if not self.__config.blocked_file_patterns:
            return re.compile(r"(?!x)x")
        combined = "|".join(f"(?:{p})" for p in self.__config.blocked_file_patterns)
        return re.compile(combined, re.IGNORECASE)

    def __decode_bytes(self, data: bytes) -> str:
        return data.decode("utf-8", errors="ignore")

    def __is_filename_blocked(self, file_path: bytes | None) -> bool:
        if file_path is None:
            return False
        name_str = self.__decode_bytes(file_path)
        return bool(self.__file_blocklist_regex.match(name_str))

    def __is_extension_ignored(self, file_path: bytes | None) -> bool:
        if file_path is None:
            return False
        name_str = self.__decode_bytes(file_path)
        return any(name_str.endswith(ext) for ext in self.__config.ignored_extensions)

    def __contains_high_entropy(self, text: str) -> bool:
        # Split by typical code delimiters: space, quote, equals, colon, comma, parens
        tokens = re.split(r"[\s\"'=:;,\(\)\[\]\{\}]+", text)

        for token in tokens:
            if len(token) < self.__config.entropy_min_len:
                continue

            score = self.__shannon_entropy(token)
            if score > self.__config.entropy_threshold:
                return True
        return False

    def __scan_text_content(self, text: str) -> bool:
        # Scan lines iteratively to avoid huge memory allocations and exit early
        for line in text.splitlines():
            # Only scan lines that were added (+), excluding the +++ file header
            if not line.startswith("+") or line.startswith("+++"):
                continue

            actual_content = line[1:]
            if not actual_content:
                continue

            # 1. Regex check
            for pattern in self.__patterns:
                if pattern.search(actual_content):
                    return True

            # 2. Entropy check (only if NOT safe mode)
            if self.__config.aggression != "safe" and self.__contains_high_entropy(
                actual_content
            ):
                return True

        return False

    def __check_atomic_chunk(
        self, chunk: AtomicDiffChunk, patch_generator: GitPatchGenerator
    ) -> bool:
        canonical = chunk.canonical_path()
        if self.__is_filename_blocked(canonical):
            return True

        if self.__is_extension_ignored(canonical):
            return False

        patch = patch_generator.get_patch(chunk, is_bytes=False)
        return self.__scan_text_content(patch)

    def filter(
        self,
        containers: list[AtomicContainer],
    ) -> tuple[list[AtomicContainer], list[AtomicContainer]]:
        """Filters chunks and immutable chunks for hardcoded secrets.

        The primary filtering rule is:
        If a Chunk (wrapper) contains ANY sensitive StandardDiffChunk, the entire Chunk is rejected.

        Args:
            containers: List of AtomicContainers to scan.

        Returns:
            (accepted_chunks, rejected_chunks)
        """

        accepted_chunks: list[AtomicContainer] = []
        rejected_chunks: list[AtomicContainer] = []

        git_generator = GitPatchGenerator(containers, file_manager=self.__file_manager)

        pbar = ProgressBarManager.get_pbar()
        if pbar is not None:
            pbar.set_postfix({"phase": f"scanning secrets 0/{len(containers)}"})

        for i, container in enumerate(containers):
            if pbar is not None:
                pbar.set_postfix(
                    {"phase": f"scanning secrets {i + 1}/{len(containers)}"}
                )
            invalid = any(
                self.__check_atomic_chunk(chunk, git_generator)
                for chunk in container.get_atomic_chunks()
            )

            if invalid:
                rejected_chunks.append(container)
            else:
                accepted_chunks.append(container)

        return accepted_chunks, rejected_chunks
