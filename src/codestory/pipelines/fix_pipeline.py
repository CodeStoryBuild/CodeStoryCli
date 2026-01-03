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

        # Get list of downstream commits (oldest to newest)
        downstream_out = self.git.run_git_text_out(
            ["rev-list", "--reverse", f"{old_end_hash}..HEAD"]
        )

        if not downstream_out or not downstream_out.strip():
            # No downstream commits, we're done
            return new_commit_hash

        downstream_commits = downstream_out.strip().splitlines()

        # Use merge-tree to rebase each commit (bare-repo friendly)
        import os

        new_parent = new_commit_hash

        for commit in downstream_commits:
            # Get commit metadata
            log_format = "%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B"
            meta_out = self.git.run_git_text_out(
                ["log", "-1", f"--format={log_format}", commit]
            )

            if not meta_out:
                raise FixCommitError(f"Failed to get metadata for commit {commit[:7]}")

            lines = meta_out.splitlines()
            if len(lines) < 7:
                raise FixCommitError(f"Invalid metadata for commit {commit[:7]}")

            author_name = lines[0]
            author_email = lines[1]
            author_date = lines[2]
            committer_name = lines[3]
            committer_email = lines[4]
            committer_date = lines[5]
            message = "\n".join(lines[6:])

            # Get the parent of the original commit
            original_parent_out = self.git.run_git_text_out(["rev-parse", f"{commit}^"])
            if not original_parent_out:
                raise FixCommitError(f"Failed to get parent of commit {commit[:7]}")

            original_parent = original_parent_out.strip()

            # Use merge-tree to compute the new tree
            tree_out = self.git.run_git_text_out(
                [
                    "merge-tree",
                    "--write-tree",
                    "--merge-base",
                    original_parent,
                    new_parent,
                    commit,
                ]
            )

            if not tree_out:
                raise FixCommitError(
                    f"Failed to merge-tree for commit {commit[:7]}. May have conflicts."
                )

            new_tree = tree_out.strip()

            # Create commit with the new tree
            cmd_env = os.environ.copy()
            cmd_env["GIT_AUTHOR_NAME"] = author_name
            cmd_env["GIT_AUTHOR_EMAIL"] = author_email
            cmd_env["GIT_AUTHOR_DATE"] = author_date
            cmd_env["GIT_COMMITTER_NAME"] = committer_name
            cmd_env["GIT_COMMITTER_EMAIL"] = committer_email
            cmd_env["GIT_COMMITTER_DATE"] = committer_date

            new_commit = self.git.run_git_text_out(
                ["commit-tree", new_tree, "-p", new_parent, "-m", message],
                env=cmd_env,
            )

            if not new_commit:
                raise FixCommitError(f"Failed to create commit for {commit[:7]}")

            new_parent = new_commit.strip()

        return new_parent
