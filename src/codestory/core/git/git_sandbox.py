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

import contextlib
import os
import shutil
import tempfile
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

from codestory.core.exceptions import GitError

if TYPE_CHECKING:
    from codestory.context import GlobalContext
    from codestory.core.git_interface import GitInterface


class GitSandbox(AbstractContextManager):
    """Context manager that sandboxes Git object creation to a temporary directory.

    This prevents polluting the main repository with loose objects
    during intermediate processing. Use .sync(commit_hash) to migrate
    the result.

    Can be instantiated with GitInterface + repo_path directly, or via
    the from_context() class method for backward compatibility with
    GlobalContext.
    """

    # Keys that the sandbox overrides in the git interface environment
    _SANDBOX_ENV_KEYS = frozenset(
        ["GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"]
    )

    def __init__(self, git_interface: "GitInterface", repo_path: Path):
        """Initialize GitSandbox with explicit git interface and repo path.

        Args:
            git_interface: The GitInterface instance to use for git operations.
            repo_path: Path to the repository (used for fallback objects dir).
        """
        self.git_interface = git_interface
        self.repo_path = repo_path
        self.temp_dir = None
        self.original_override: dict | None = None
        self.sandbox_override: dict = {}

    @classmethod
    def from_context(cls, context: "GlobalContext") -> "GitSandbox":
        """Create a GitSandbox from a GlobalContext (backward compatibility).

        Args:
            context: GlobalContext containing git_interface and repo_path.

        Returns:
            A new GitSandbox instance.
        """
        return cls(context.git_interface, context.repo_path)

    def __enter__(self):
        # Create temp directory for objects
        self.temp_dir = tempfile.mkdtemp(prefix="codestory_sandbox_")

        git = self.git_interface

        # Capture original override state (might be None or a dict)
        self.original_override = git.global_env_override

        # Determine real paths
        # We use the raw git interface to ensure we get the resolved paths
        # Note: We use run_git_text_out directly from interface, not commands, to reduce circular deps
        objects_dir = git.run_git_text_out(["rev-parse", "--git-path", "objects"])
        if objects_dir:
            objects_dir = objects_dir.strip()
        else:
            # Fallback if rev-parse fails (unlikely in valid repo)
            objects_dir = str(self.repo_path / ".git" / "objects")

        # Handle existing alternates (e.g. if the repo itself uses alternates)
        existing_alternates = os.environ.get("GIT_ALTERNATE_OBJECT_DIRECTORIES", "")
        sep = ";" if os.name == "nt" else ":"

        # Construct alternates list: real_objects + existing
        # This allows the sandbox to read all existing objects
        new_alternates = [objects_dir]
        if existing_alternates:
            new_alternates.extend(existing_alternates.split(sep))

        # Build sandbox override - only the specific keys we need
        self.sandbox_override = {
            "GIT_OBJECT_DIRECTORY": self.temp_dir,
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": sep.join(new_alternates),
        }

        # Apply override to git interface (NOT os.environ)
        # If there was an existing override, merge our keys on top
        if self.original_override:
            git.global_env_override = {
                **self.original_override,
                **self.sandbox_override,
            }
        else:
            git.global_env_override = self.sandbox_override

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore original git interface override state
        git = self.git_interface
        git.global_env_override = self.original_override

        # Cleanup temp dir
        if self.temp_dir and os.path.exists(self.temp_dir):
            with contextlib.suppress(OSError):
                shutil.rmtree(self.temp_dir)

    def sync(self, new_commit_hash: str, thin_pack: bool = False):
        """Packs objects reachable from new_commit_hash (but not in the main repo) and
        indexes them into the main repository."""
        if not new_commit_hash:
            return

        from loguru import logger

        logger.debug(f"Syncing sandbox objects for {new_commit_hash[:7]}...")

        git = self.git_interface

        # 1. Identify new objects
        # We calculate: Reachable(NewHash) - Reachable(All Refs in Main Repo)
        # Because we are in the SANDBOX env, 'rev-list' sees our new objects.
        # We use --not --all to exclude everything already reachable by current branches/tags
        cmd_rev_list = ["rev-list", "--objects", new_commit_hash, "--not", "--all"]
        objects_out = git.run_git_text_out(cmd_rev_list)

        if not objects_out:
            logger.debug("No new objects to sync.")
            return

        # Prepare list of SHAs (strip paths from output of --objects)
        object_shas = [line.split()[0] for line in objects_out.splitlines()]
        if not object_shas:
            return

        logger.debug(f"Packing {len(object_shas)} objects...")

        input_bytes = "\n".join(object_shas).encode("utf-8")

        # 2. Generate Pack (Sandbox Environment)
        # 'pack-objects' reads the list of objects from stdin and outputs a pack stream
        if thin_pack:
            cmd_pack = ["pack-objects", "--stdout", "--thin", "--delta-base-offset"]
        else:
            cmd_pack = ["pack-objects", "--stdout"]

        pack_data = git.run_git_binary_out(cmd_pack, input_bytes=input_bytes)

        if not pack_data:
            raise GitError("Failed to create pack of sandbox objects")

        logger.debug("Indexing pack into real repository...")

        # Pass original override to bypass the sandbox overrides and write to the real object dir
        original = git.global_env_override
        git.global_env_override = (
            self.original_override
        )  # Temporarily restore to pre-sandbox state
        try:
            git.run_git_binary_out(
                ["index-pack", "--stdin", "--fix-thin"],
                input_bytes=pack_data,
            )
        finally:
            git.global_env_override = original  # Restore sandbox override

        logger.debug("Sandbox sync complete.")
