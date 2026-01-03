from codestory.context import FixContext, GlobalContext
from codestory.core.exceptions import FixCommitError
from codestory.pipelines.commit_pipeline import CommitPipeline
from loguru import logger


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
        commit_pipeline: CommitPipeline,
    ):
        self.global_context = global_context
        self.fix_context = fix_context
        self.commit_pipeline = commit_pipeline
        # Use the abstract interface as requested
        self.git = self.global_context.git_interface

    def run(self) -> str:
        base_hash = self.commit_pipeline.base_commit_hash

        logger.debug(
            "Starting expansion for base {base}",
            base=_short(base_hash),
        )

        # 1. Run the expansion pipeline
        # This generates the new commit(s) in the object database.
        # Returns the hash of the *last* commit in the new sequence.
        new_commit_hash = self.commit_pipeline.run()

        if not new_commit_hash:
            raise FixCommitError("Commit pipeline returned no hash. Aborting.")

        # 2. Identify the downstream commits to reparent
        # We need the list of commits strictly after the base_hash.
        # The first commit in this list is the one we just fixed/replaced (resolved).
        # We want to keep everything *after* that first one.
        try:
            # --ancestry-path ensures we follow the direct chain
            rev_list_out = self.global_context.git_interface.run_git_text_out(
                [
                    "rev-list",
                    "--reverse",
                    "--ancestry-path",
                    f"{base_hash}..HEAD",
                ]
            )
            original_chain = rev_list_out.splitlines() if rev_list_out else []
        except RuntimeError as e:
            raise FixCommitError("Failed to read commit history.") from e

        if not original_chain:
            # Edge case: The base was HEAD (or detached), nothing to replay.
            # We simply update HEAD to the new result.
            logger.debug("No downstream history found. Updating HEAD directly.")
            final_head = new_commit_hash
        else:
            # original_chain[0] is the commit we just fixed (resolved).
            # original_chain[1:] are the commits we need to move (reparent).
            commits_to_reparent = original_chain[1:]

            if not commits_to_reparent:
                logger.debug("No additional downstream commits to preserve.")
                final_head = new_commit_hash
            else:
                logger.debug(
                    "Reparenting {count} downstream commits...",
                    count=len(commits_to_reparent),
                )

                current_parent = new_commit_hash

                for commit in commits_to_reparent:
                    # 3. Extract metadata from the existing commit
                    # %T  = Tree Hash (we preserve this exactly)
                    # %an = Author Name
                    # %ae = Author Email
                    # %ad = Author Date
                    # %B  = Raw Body (Commit Message)
                    meta = self.global_context.git_interface.run_git_text_out(
                        [
                            "show",
                            "-s",
                            "--format=%T%n%an%n%ae%n%ad%n%cn%n%ce%n%cd%n%B",
                            commit,
                        ]
                    )

                    lines = meta.splitlines()
                    # Safety check on output format
                    if len(lines) < 7:
                        raise FixCommitError(
                            f"Failed to parse metadata for commit {commit}"
                        )

                    tree_hash = lines[0]
                    author_name = lines[1]
                    author_email = lines[2]
                    author_date = lines[3]
                    committer_name = lines[4]
                    committer_email = lines[5]
                    committer_date = lines[6]
                    # Reassemble message (lines 4 to end), preserving newlines
                    message = "\n".join(lines[7:])

                    # 4. Create new commit object in ODB
                    # We inject the original author info via env vars so the
                    # resulting commit looks identical to the original, just moved.
                    env = {
                        "GIT_AUTHOR_NAME": author_name,
                        "GIT_AUTHOR_EMAIL": author_email,
                        "GIT_AUTHOR_DATE": author_date,
                        "GIT_COMMITTER_NAME": committer_name,
                        "GIT_COMMITTER_EMAIL": committer_email,
                        "GIT_COMMITTER_DATE": committer_date,
                    }

                    # git commit-tree <tree> -p <new_parent>
                    # Input is the commit message
                    current_parent = self.global_context.git_interface.run_git_text_out(
                        ["commit-tree", tree_hash, "-p", current_parent],
                        input_text=message,
                        env=env,
                    ).strip()  # git commit tree add trailing newline

                final_head = current_parent

        return final_head
