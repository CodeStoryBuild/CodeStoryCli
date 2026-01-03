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

import os
import tempfile
from collections.abc import Sequence

from codestory.context import CleanContext, CommitContext, GlobalContext
from codestory.core.exceptions import CleanCommandError
from codestory.pipelines.rewrite_init import create_rewrite_pipeline


class CleanPipeline:
    """
    Rewrites a linear segment of git history atomically and safely for bare repositories.

    Mechanics:
    - Uses Git plumbing commands (read-tree, commit-tree, update-ref) exclusively.
    - Uses explicit temporary GIT_INDEX_FILE env vars for internal merge operations.
    - Does NOT touch the working directory.
    - Maintains a detached chain of commit hashes.
    - Atomically updates the target branch reference only upon success.
    """

    def __init__(
        self,
        global_context: GlobalContext,
        clean_context: CleanContext,
    ):
        self.global_context = global_context
        self.clean_context = clean_context

    def run(self) -> str | None:
        from loguru import logger

        # ------------------------------------------------------------------
        # 1. Determine linear history window candidates
        # ------------------------------------------------------------------
        raw_commits = self._get_linear_history(self.clean_context.start_from)

        if not raw_commits:
            logger.warning(
                "No commits eligible for cleaning (root or merge-only history)."
            )
            return None

        # Process from Oldest -> Newest
        commits_to_rewrite = list(reversed(raw_commits))

        original_branch = self.global_context.current_branch

        start_commit = commits_to_rewrite[0]
        end_commit = commits_to_rewrite[-1]

        logger.debug(
            "Starting index-only clean on {n} commits ({start}...{end})",
            n=len(commits_to_rewrite),
            start=start_commit[:7],
            end=end_commit[:7],
        )

        # ------------------------------------------------------------------
        # 2. Establish initial base (parent of first window start)
        # ------------------------------------------------------------------
        current_base_hash = self.global_context.git_commands.try_get_parent_hash(
            start_commit
        )

        if not current_base_hash:
            raise CleanCommandError(
                f"Cannot clean history starting at root commit {start_commit}"
            )

        rewritten_count = 0
        skipped_count = 0
        current_idx = 0

        try:
            # ------------------------------------------------------------------
            # 3. Iterate through the history
            # ------------------------------------------------------------------
            while current_idx < len(commits_to_rewrite):
                window_end_idx = current_idx

                # Future: Grow window logic here
                # while should_grow(window_end_idx): window_end_idx++

                commit_hash = commits_to_rewrite[window_end_idx]
                short = commit_hash[:7]

                # Check filters
                should_skip_clean = False

                changes = self._count_line_changes(commit_hash)
                if self._is_ignored(commit_hash, self.clean_context.ignore):
                    should_skip_clean = True
                elif self.clean_context.min_size is not None:
                    if changes is not None and changes < self.clean_context.min_size:
                        should_skip_clean = True
                        logger.debug(
                            "Commit {commit} size {changes} < min {min_size}, skipping clean.",
                            commit=short,
                            changes=changes,
                            min_size=self.clean_context.min_size,
                        )
                elif changes < 1:
                    # no changes, treat as empty commit and skip
                    should_skip_clean = True

                if should_skip_clean:
                    logger.debug(
                        "Copying (plumbing merge) ignored commit {commit}", commit=short
                    )

                    # Perform an in-memory 3-way merge/copy using a temporary index
                    new_commit = self._copy_commit_index_only(
                        commit_hash, current_base_hash
                    )

                    if not new_commit:
                        raise CleanCommandError(
                            f"Failed to copy commit {short} (likely merge conflict). Atomic clean aborted."
                        )

                    current_base_hash = new_commit
                    skipped_count += 1
                else:
                    logger.debug(
                        "Rewriting commit {commit} ({i}/{t})",
                        commit=short,
                        i=current_idx + 1,
                        t=len(commits_to_rewrite),
                    )

                    commit_ctx = CommitContext(
                        target=None,
                        message=None,
                        fail_on_syntax_errors=False,
                        relevance_filter_level="none",
                        secret_scanner_aggression="none",
                    )

                    pipeline = create_rewrite_pipeline(
                        self.global_context,
                        commit_ctx,
                        base_commit_hash=current_base_hash,
                        new_commit_hash=commit_hash,
                        source="fix",
                    )

                    new_tip_hash = pipeline.run()

                    if new_tip_hash:
                        current_base_hash = new_tip_hash
                        rewritten_count += 1
                    else:
                        logger.warning(
                            f"Commit {short} resulted in empty change or was dropped."
                        )
                        # If dropped, current_base_hash stays same.

                # Advance window
                current_idx = window_end_idx + 1

            # ------------------------------------------------------------------
            # 4. Finalize: Atomic Update
            # ------------------------------------------------------------------
            logger.success("History rewrite complete. Updating references.")

            # Check if there are downstream commits that need to be rebased
            # This happens when start_from is not HEAD
            original_head = self.global_context.git_commands.get_commit_hash(
                self.global_context.current_branch
            )

            # Check if there are commits after the cleaned range
            downstream_commits = None
            if end_commit != original_head:
                # There are commits between end_commit and the branch tip that need rebasing
                downstream_commits = self.global_context.git_commands.get_rev_list(
                    f"{end_commit}..{self.global_context.current_branch}", reverse=True
                )

            if downstream_commits:
                logger.info(
                    f"Rebasing {len(downstream_commits)} downstream commit(s) onto new history..."
                )

                # Use merge-tree to rebase downstream commits (bare-repo friendly)
                # Process commits from oldest to newest
                new_parent = current_base_hash

                for commit in downstream_commits:
                    # Get commit metadata
                    log_format = "%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B"
                    meta_out = self.global_context.git_commands.get_commit_metadata(
                        commit, log_format
                    )

                    if not meta_out:
                        raise CleanCommandError(
                            f"Failed to get metadata for commit {commit[:7]}"
                        )

                    lines = meta_out.splitlines()
                    if len(lines) < 7:
                        raise CleanCommandError(
                            f"Invalid metadata for commit {commit[:7]}"
                        )

                    author_name = lines[0]
                    author_email = lines[1]
                    author_date = lines[2]
                    committer_name = lines[3]
                    committer_email = lines[4]
                    committer_date = lines[5]
                    message = "\n".join(lines[6:])

                    # Get the parent of the original commit
                    original_parent = (
                        self.global_context.git_commands.try_get_parent_hash(commit)
                    )
                    if not original_parent:
                        raise CleanCommandError(
                            f"Failed to get parent of commit {commit[:7]}"
                        )

                    # Use merge-tree to compute the new tree
                    # merge-tree --write-tree --merge-base <base> <branch1> <branch2>
                    # We want to replay commit's changes onto new_parent
                    new_tree = self.global_context.git_commands.merge_tree(
                        original_parent, new_parent, commit
                    )

                    if not new_tree:
                        raise CleanCommandError(
                            f"Failed to merge-tree for commit {commit[:7]}. May have conflicts."
                        )

                    # Create commit with the new tree
                    cmd_env = os.environ.copy()
                    cmd_env["GIT_AUTHOR_NAME"] = author_name
                    cmd_env["GIT_AUTHOR_EMAIL"] = author_email
                    cmd_env["GIT_AUTHOR_DATE"] = author_date
                    cmd_env["GIT_COMMITTER_NAME"] = committer_name
                    cmd_env["GIT_COMMITTER_EMAIL"] = committer_email
                    cmd_env["GIT_COMMITTER_DATE"] = committer_date

                    new_commit = self.global_context.git_commands.commit_tree(
                        new_tree, [new_parent], message, env=cmd_env
                    )

                    if not new_commit:
                        raise CleanCommandError(
                            f"Failed to create commit for {commit[:7]}"
                        )

                    new_parent = new_commit

                logger.success("Downstream commits successfully rebased.")
                current_base_hash = new_parent

            return current_base_hash
            
            

        except Exception as e:
            logger.error(f"Clean pipeline failed: {e}")
            logger.warning("No references were updated. Repository state is unchanged.")
            return None

    def _copy_commit_index_only(
        self, original_commit: str, new_base: str
    ) -> str | None:
        from loguru import logger

        """
        Replays 'original_commit' onto 'new_base' using index-only 3-way merge.
        Does not touch the working tree or global index.
        """
        original_parent = self.global_context.git_commands.try_get_parent_hash(
            original_commit
        )
        if not original_parent:
            return None

        # Gather metadata from the original commit
        # Format: Name%nEmail%nDate%nBody
        log_format = "%an%n%ae%n%aI%n%B"
        meta_out = self.global_context.git_commands.get_commit_metadata(
            original_commit, log_format
        )

        if not meta_out:
            return None

        lines = meta_out.splitlines()
        if len(lines) < 4:
            return None

        author_name = lines[0]
        author_email = lines[1]
        author_date = lines[2]
        message = "\n".join(lines[3:])

        # Create a temporary index file to build the backup commit
        temp_index_fd, temp_index_path = tempfile.mkstemp(
            prefix="codestory_clean_index_"
        )
        os.close(temp_index_fd)
        # Git read-tree -m fails if the index file exists but is empty (0 bytes).
        # We delete it so git can initialize it properly.
        if os.path.exists(temp_index_path):
            os.unlink(temp_index_path)

        try:
            # Prepare the environment for git commands
            cmd_env = os.environ.copy()
            cmd_env["GIT_INDEX_FILE"] = temp_index_path

            # 1. Read the 3-way merge into the TEMP index
            # read-tree -i -m --aggressive <base> <current> <target>
            res = self.global_context.git_commands.read_tree(
                "",
                index_only=True,
                merge=True,
                aggressive=True,
                base=original_parent,
                current=new_base,
                target=original_commit,
                env=cmd_env,
            )

            if not res:
                logger.error("Failed to read-tree for merge!")
                return None

            # 2. Write the temp index to a tree object
            tree_hash = self.global_context.git_commands.write_tree(env=cmd_env)
            if not tree_hash:
                logger.error("Failed to write-tree.")
                return None

            # 3. Create commit object from tree
            # Add author info to the env for commit-tree
            cmd_env["GIT_AUTHOR_NAME"] = author_name
            cmd_env["GIT_AUTHOR_EMAIL"] = author_email
            cmd_env["GIT_AUTHOR_DATE"] = author_date

            new_commit_hash = self.global_context.git_commands.commit_tree(
                tree_hash, [new_base], message, env=cmd_env
            )

            return new_commit_hash
        finally:
            # Cleanup the temporary index file
            if os.path.exists(temp_index_path):
                os.unlink(temp_index_path)

    def _get_linear_history(self, start_from: str | None = None) -> list[str]:
        """
        Returns a list of commit hashes from the start reference down to (but excluding)
        the first merge or the root. Order is Newest -> Oldest.
        """
        start_ref = start_from or self.global_context.current_branch
        if start_from:
            try:
                start_ref = self.global_context.git_commands.get_commit_hash(start_from)
            except ValueError:
                raise CleanCommandError(f"Could not resolve commit: {start_from}")

        stop_commits = self.global_context.git_commands.get_rev_list(
            start_ref, merges=True, n=1
        )

        range_spec = start_ref
        if stop_commits:
            stop_commit = stop_commits[0]
            range_spec = f"{stop_commit}..{start_ref}"

        commits = self.global_context.git_commands.get_rev_list(
            range_spec, first_parent=True
        )

        if commits:
            last = commits[-1]
            parents = self.global_context.git_commands.try_get_parent_hash(last)
            if not parents:
                commits.pop()

        return commits

    def _is_ignored(self, commit: str, ignore: Sequence[str] | None) -> bool:
        if not ignore:
            return False
        return any(commit.startswith(token) for token in ignore)

    def _count_line_changes(self, commit: str) -> int | None:
        out = self.global_context.git_commands.get_diff_numstat(f"{commit}^", commit)
        if out is None:
            return None
        total = 0
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                add = int(parts[0]) if parts[0] != "-" else 0
                dele = int(parts[1]) if parts[1] != "-" else 0
                total += add + dele
            except ValueError:
                continue
        return total
