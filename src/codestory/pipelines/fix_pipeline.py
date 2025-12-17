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

from codestory.context import FixContext, GlobalContext
from codestory.core.exceptions import FixCommitError
from codestory.pipelines.rewrite_pipeline import RewritePipeline


def _short(hash_: str) -> str:
    return (hash_ or "")[:7]


class FixPipeline:
    """
    Core orchestration for fixing a commit.

    This implementation manipulates the Git Object Database directly to re-parent
    downstream commits onto the fixed history without using worktrees or
    intermediate filesystem operations.
    """

    def __init__(
        self,
        global_context: GlobalContext,
        fix_context: FixContext,
        rewrite_pipeline: RewritePipeline,
    ):
        self.global_context = global_context
        self.fix_context = fix_context
        self.rewrite_pipeline = rewrite_pipeline
        # Use the abstract interface as requested
        self.git = self.global_context.git_interface

    def run(self) -> str:
        from loguru import logger
        
        base_hash = self.rewrite_pipeline.base_commit_hash
        old_end_hash = self.rewrite_pipeline.new_commit_hash

        logger.debug(
            "Starting expansion for base {base} to end {end}",
            base=_short(base_hash),
            end=_short(old_end_hash),
        )

        # Run the expansion pipeline
        # This generates the new commit(s) in the object database.
        # Returns the hash of the *last* commit in the new sequence.
        new_commit_hash = self.rewrite_pipeline.run()

        if not new_commit_hash:
            raise FixCommitError("Commit pipeline returned no hash. Aborting.")

        if new_commit_hash == old_end_hash:
            logger.debug(
                "No changes detected between original end {end} and new commit {new}",
                end=_short(old_end_hash),
                new=_short(new_commit_hash),
            )
            return old_end_hash  # No changes, nothing to reparent

        logger.debug(
            "Rebasing downstream history onto new fix ({new})...",
            new=_short(new_commit_hash),
        )

        try:
            self.git.run_git_text_out(
                ["rebase", "--onto", new_commit_hash, old_end_hash, "HEAD"]
            )
        except Exception as e:
            # If rebase fails, we must abort to return repo to safe state
            logger.debug("Rebase failed. Aborting operation.")
            try:
                self.git.run_git_text_out(["rebase", "--abort"])
            except Exception:
                pass

            raise FixCommitError("Failed to rebase downstream commits") from e

        final_head = self.git.run_git_text_out(["rev-parse", "HEAD"]).strip()
        return final_head
