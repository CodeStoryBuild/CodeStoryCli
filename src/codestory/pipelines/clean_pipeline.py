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

from codestory.context import GlobalContext
from codestory.core.exceptions import CleanCommandError
from codestory.pipelines.standard_cli_pipeline import StandardCLIPipeline


class CleanPipeline:
    """Rewrites a linear segment of git history atomically and safely for bare
    repositories.

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
        start_from: str | None,
        end_at: str | None,
        ignore: list[str],
        min_size: int | None,
        unpushed: bool = False,
    ):
        self.global_context = global_context
        self.start_from = start_from
        self.end_at = end_at
        self.ignore = ignore
        self.min_size = min_size
        self.unpushed = unpushed

    def run(self) -> str | None:
        from loguru import logger

        # ------------------------------------------------------------------
        # 1. Determine linear history window candidates
        # ------------------------------------------------------------------
        # Pass end_at from context
        commits_to_rewrite = self._get_linear_history(self.start_from, self.end_at)

        if not commits_to_rewrite:
            logger.warning("No commits eligible for cleaning.")
            return None

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

        pipeline = StandardCLIPipeline(
            self.global_context, allow_filtering=False, source="clean"
        )

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
                if self._is_ignored(commit_hash, self.ignore):
                    should_skip_clean = True
                elif self.min_size is not None:
                    if changes is not None and changes < self.min_size:
                        should_skip_clean = True
                        logger.debug(
                            "Commit {commit} size {changes} < min {min_size}, skipping clean.",
                            commit=short,
                            changes=changes,
                            min_size=self.min_size,
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

                    new_commit_hash = pipeline.run(current_base_hash, commit_hash)

                    if new_commit_hash:
                        current_base_hash = new_commit_hash
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
            logger.success("History rewrite complete.")

            # Check for downstream commits (rebase required if end_at != branch_tip)
            # We look at what the original end_at was supposed to be vs current branch tip

            original_branch_head = self.global_context.git_commands.get_commit_hash(
                self.global_context.current_branch
            )

            # end_commit is the last commit we rewrote.
            # If we were cleaning up to end_at, end_commit should correspond to end_at.

            if end_commit != original_branch_head:
                logger.info("Rebasing downstream commits...")
                # We need to rebase from (old) end_commit ... tip
                downstream_commits = self.global_context.git_commands.get_rev_list(
                    f"{end_commit}..{self.global_context.current_branch}", reverse=True
                )

                if downstream_commits:
                    new_parent = current_base_hash
                    for commit in downstream_commits:
                        new_parent = self._rebase_commit(commit, new_parent)
                    current_base_hash = new_parent
                    logger.success("Downstream commits successfully rebased.")

            return current_base_hash

        except Exception as e:
            logger.error(f"Clean pipeline failed: {e}")
            return None

    def _get_linear_history(
        self, start_from: str | None = None, end_at: str | None = None
    ) -> list[str]:
        """Returns a list of commit hashes to rewrite (Oldest -> Newest).

        Ensures the root commit is excluded (cannot be rewritten).
        """
        # Resolve end
        if end_at:
            end_sha = self.global_context.git_commands.get_commit_hash(end_at)
        else:
            end_sha = self.global_context.git_commands.get_commit_hash(
                self.global_context.current_branch
            )

        range_spec = None

        if start_from:
            start_sha = self.global_context.git_commands.get_commit_hash(start_from)
            parent = self.global_context.git_commands.try_get_parent_hash(start_sha)

            range_spec = f"{parent}...{end_sha}" if parent else end_sha
        else:
            # Auto-detect mode: clean from last merge up to end
            candidates = []

            # 1. Last merge
            stop_commits = self.global_context.git_commands.get_rev_list(
                end_sha, merges=True, n=1
            )
            if stop_commits:
                candidates.append(stop_commits[0])

            # 2. Upstream if requested
            if self.unpushed:
                try:
                    upstream = self.global_context.git_commands.get_commit_hash(
                        f"{self.global_context.current_branch}@{{u}}"
                    )
                    candidates.append(upstream)
                except ValueError:
                    # No upstream, just use others
                    pass

            if candidates:
                # We want the candidate that is CLOSEST to end_sha.
                # This is the one that is a descendant of all others.
                boundary = candidates[0]
                for c in candidates[1:]:
                    if self.global_context.git_commands.is_ancestor(boundary, c):
                        boundary = c
                range_spec = f"{boundary}..{end_sha}"
            else:
                range_spec = end_sha

        # Get commits Oldest -> Newest
        commits = self.global_context.git_commands.get_rev_list(
            range_spec, first_parent=True, reverse=True
        )

        # We cannot rewrite the root commit because we need a parent to serve as the base.
        if commits:
            first_commit = commits[0]
            if not self.global_context.git_commands.try_get_parent_hash(first_commit):
                # Remove root commit from list to be rewritten.
                # It will act as the immutable base for the next commit in the list.
                commits.pop(0)

        return commits

    def _rebase_commit(self, commit: str, new_parent: str) -> str:
        # (Included for completeness of logic flow)
        log_format = "%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B"
        meta_out = self.global_context.git_commands.get_commit_metadata(
            commit, log_format
        )
        if not meta_out:
            raise CleanCommandError(f"Failed to get metadata for {commit}")

        lines = meta_out.splitlines()
        if len(lines) < 7:
            raise CleanCommandError(f"Invalid metadata for {commit}")

        author_name, author_email, author_date = lines[0], lines[1], lines[2]
        committer_name, committer_email, committer_date = lines[3], lines[4], lines[5]
        message = "\n".join(lines[6:])

        original_parent = self.global_context.git_commands.try_get_parent_hash(commit)
        if not original_parent:
            raise CleanCommandError(f"Failed to get parent of {commit}")

        new_tree = self.global_context.git_commands.merge_tree(
            original_parent, new_parent, commit
        )
        if not new_tree:
            raise CleanCommandError(f"Failed to merge-tree for {commit}")

        cmd_env = os.environ.copy()
        cmd_env["GIT_AUTHOR_NAME"] = author_name
        cmd_env["GIT_AUTHOR_EMAIL"] = author_email
        cmd_env["GIT_AUTHOR_DATE"] = author_date
        cmd_env["GIT_COMMITTER_NAME"] = committer_name
        cmd_env["GIT_COMMITTER_EMAIL"] = committer_email
        cmd_env["GIT_COMMITTER_DATE"] = committer_date

        return (
            self.global_context.git_commands.commit_tree(
                new_tree, [new_parent], message, env=cmd_env
            )
            or ""
        )

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
