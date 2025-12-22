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

from codestory.context import GlobalContext
from codestory.core.exceptions import GitError


class GitSandbox(AbstractContextManager):
    """
    Context manager that sandboxes Git object creation to a temporary directory.

    This prevents polluting the main repository with loose objects during
    intermediate processing. Use .sync(commit_hash) to migrate the result.
    """

    def __init__(self, context: GlobalContext):
        self.context = context
        self.temp_dir = None
        self.original_env = {}
        self.sandbox_env = {}

    def __enter__(self):
        # Create temp directory for objects
        self.temp_dir = tempfile.mkdtemp(prefix="codestory_sandbox_")

        # Capture original environment
        self.original_env = os.environ.copy()

        # Determine real paths
        # We use the raw git interface to ensure we get the resolved paths
        git = self.context.git_interface

        # Note: We use run_git_text_out directly from interface, not commands, to reduce circular deps
        objects_dir = git.run_git_text_out(["rev-parse", "--git-path", "objects"])
        if objects_dir:
            objects_dir = objects_dir.strip()
        else:
            # Fallback if rev-parse fails (unlikely in valid repo)
            objects_dir = str(self.context.repo_path / ".git" / "objects")

        # Handle existing alternates (e.g. if the repo itself uses alternates)
        existing_alternates = os.environ.get("GIT_ALTERNATE_OBJECT_DIRECTORIES", "")
        sep = ";" if os.name == "nt" else ":"

        # Construct alternates list: real_objects + existing
        # This allows the sandbox to read all existing objects
        new_alternates = [objects_dir]
        if existing_alternates:
            new_alternates.extend(existing_alternates.split(sep))

        self.sandbox_env = self.original_env.copy()
        self.sandbox_env["GIT_OBJECT_DIRECTORY"] = self.temp_dir
        self.sandbox_env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = sep.join(new_alternates)

        # Apply to current process
        os.environ.update(self.sandbox_env)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore environment
        if "GIT_OBJECT_DIRECTORY" in self.original_env:
            os.environ["GIT_OBJECT_DIRECTORY"] = self.original_env[
                "GIT_OBJECT_DIRECTORY"
            ]
        else:
            if "GIT_OBJECT_DIRECTORY" in os.environ:
                del os.environ["GIT_OBJECT_DIRECTORY"]

        if "GIT_ALTERNATE_OBJECT_DIRECTORIES" in self.original_env:
            os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = self.original_env[
                "GIT_ALTERNATE_OBJECT_DIRECTORIES"
            ]
        else:
            if "GIT_ALTERNATE_OBJECT_DIRECTORIES" in os.environ:
                del os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"]

        # Cleanup temp dir
        if self.temp_dir and os.path.exists(self.temp_dir):
            with contextlib.suppress(OSError):
                shutil.rmtree(self.temp_dir)

    def sync(self, new_commit_hash: str):
        """
        Packs objects reachable from new_commit_hash (but not in the main repo)
        and indexes them into the main repository.
        """
        if not new_commit_hash:
            return

        from loguru import logger

        logger.debug(f"Syncing sandbox objects for {new_commit_hash[:7]}...")

        git = self.context.git_interface

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
        # We pass self.sandbox_env explicitely just to be safe, though os.environ is already set
        pack_data = git.run_git_binary_out(
            ["pack-objects", "--stdout"], input_bytes=input_bytes
        )

        if not pack_data:
            raise GitError("Failed to create pack of sandbox objects")

        # 3. Ingest Pack (Original Environment)
        # 'index-pack' reads the pack stream and writes .pack and .idx to the main repo
        # CRITICAL: We must use self.original_env here so that index-pack writes
        # to the REAL .git/objects directory, ignoring the current GIT_OBJECT_DIRECTORY env var.
        logger.debug("Indexing pack into real repository...")

        git.run_git_binary_out(
            ["index-pack", "--stdin", "--fix-thin"],
            input_bytes=pack_data,
            env=self.original_env,  # Must use original env to write to real object dir
        )

        logger.debug("Sandbox sync complete.")
