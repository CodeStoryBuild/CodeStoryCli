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


from codestory.core.git.git_const import EMPTYTREEHASH
from codestory.core.git.git_interface import GitInterface


class GitCommands:
    def __init__(self, git: GitInterface):
        self.git = git

    def reset(self) -> None:
        """Reset staged changes (keeping working directory intact)"""
        self.git.run_git_text_out(["reset"])

    def track_untracked(self, target: str | list[str] | None = None) -> None:
        """Make untracked files tracked without staging their content, using 'git add
        -N'."""
        if target:
            targets = [target] if isinstance(target, str) else target
            self.git.run_git_text_out(["add", "-N"] + targets)
        else:
            # Track all untracked files
            untracked = self.git.run_git_text_out(
                ["ls-files", "--others", "--exclude-standard"]
            ).splitlines()
            if not untracked:
                return
            self.git.run_git_text_out(["add", "-N"] + untracked)

    def need_reset(self) -> bool:
        """Checks if there are staged changes that need to be reset."""
        # 'git diff --cached --quiet' exits with 1 if there are staged changes, 0 otherwise
        return self.git.run_git_text(["diff", "--cached", "--quiet"]) is None

    def need_track_untracked(self, target: str | list[str] | None = None) -> bool:
        """Checks if there are any untracked files within a target that need to be
        tracked."""
        if isinstance(target, str):
            path_args = [target]
        elif target is None:
            path_args = []
        else:
            path_args = target

        untracked_files = self.git.run_git_text_out(
            ["ls-files", "--others", "--exclude-standard"] + path_args
        )
        return bool(untracked_files.strip())

    def get_commit_hash(self, ref: str) -> str:
        """Returns the commit hash of the given reference (branch, tag, or SHA)."""
        res = self.git.run_git_text_out(["rev-parse", ref])
        if res is None:
            raise ValueError(f"Could not resolve reference: {ref}")
        return res.strip()

    def get_rev_list(
        self,
        range_spec: str,
        first_parent: bool = False,
        merges: bool = False,
        n: int | None = None,
        reverse: bool = False,
    ) -> list[str]:
        """Returns a list of commit hashes matching the range and criteria."""
        args = ["rev-list"]
        if first_parent:
            args.append("--first-parent")
        if merges:
            args.append("--merges")
        if reverse:
            args.append("--reverse")
        if n is not None:
            args.extend(["-n", str(n)])
        args.append(range_spec)

        out = self.git.run_git_text_out(args)
        if out is None:
            raise ValueError("Rev List Returned None for range: ", range_spec)
        return [line.strip() for line in out.splitlines() if line.strip()]

    def get_commit_message(self, commit_hash: str) -> str:
        """Returns the full commit message for a given commit."""
        res = self.git.run_git_text_out(["log", "-1", "--pretty=%B", commit_hash])
        if res is None:
            return ""
        return res.strip()

    def get_commit_metadata(self, commit_hash: str, log_format: str) -> str | None:
        """Returns metadata for a commit using the specified git log format."""
        return self.git.run_git_text_out(
            ["log", "-1", f"--format={log_format}", commit_hash]
        )

    def update_ref(self, ref: str, new_hash: str) -> bool:
        """Updates a reference (e.g., refs/heads/main) to a new commit hash."""
        # Ensure we use the full ref path if it's a branch
        if not ref.startswith("refs/") and ref != "HEAD":
            ref = f"refs/heads/{ref}"

        res = self.git.run_git_text(["update-ref", ref, new_hash])
        return res is not None

    def read_tree(
        self,
        tree_ish: str,
        index_only: bool = False,
        merge: bool = False,
        aggressive: bool = False,
        base: str | None = None,
        current: str | None = None,
        target: str | None = None,
        env: dict | None = None,
    ) -> bool:
        """Runs git read-tree with various options."""
        args = ["read-tree"]
        if index_only:
            args.append("-i")
        if merge:
            args.append("-m")
        if aggressive:
            args.append("--aggressive")

        if base and current and target:
            args.extend([base, current, target])
        else:
            args.append(tree_ish)

        res = self.git.run_git_text_out(args, env=env)
        return res is not None

    def write_tree(self, env: dict | None = None) -> str | None:
        """Writes the current index to a tree object."""
        res = self.git.run_git_text_out(["write-tree"], env=env)
        return res.strip() if res else None

    def commit_tree(
        self,
        tree_hash: str,
        parent_hashes: list[str],
        message: str,
        env: dict | None = None,
    ) -> str | None:
        """Creates a new commit object from a tree and parents."""
        args = ["commit-tree", tree_hash]
        for p in parent_hashes:
            args.extend(["-p", p])
        args.extend(["-m", message])

        res = self.git.run_git_text_out(args, env=env)
        return res.strip() if res else None

    def merge_tree(self, base: str, branch1: str, branch2: str) -> str | None:
        """Runs git merge-tree --write-tree to compute a merge tree without touching the
        working dir."""
        res = self.git.run_git_text_out(
            ["merge-tree", "--write-tree", "--merge-base", base, branch1, branch2]
        )
        return res.strip() if res else None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Returns True if 'ancestor' is an ancestor of 'descendant'."""
        res = self.git.run_git_text(
            ["merge-base", "--is-ancestor", ancestor, descendant]
        )
        return res is not None

    def get_show_current_branch(self) -> str | None:
        """Returns the name of the current branch."""
        res = self.git.run_git_text_out(["branch", "--show-current"])
        return res.strip() if res else None

    def get_diff_numstat(self, base: str, new: str) -> str | None:
        """Returns the output of git diff --numstat between two commits."""
        return self.git.run_git_text_out(["diff", "--numstat", base, new])

    def cat_file(self, obj: str) -> str | None:
        """Returns the content of a git object (e.g., commit:path)."""
        return self.git.run_git_text_out(["cat-file", "-p", obj])

    def cat_file_batch(self, objs: list[bytes]) -> list[bytes | None]:
        """Returns the content of multiple git objects using git cat-file --batch.

        Returns a list of bytes or None if an object doesn't exist.
        """
        if not objs:
            return []

        # We use --batch to get both headers and content.
        # Format is: <object> SP <type> SP <size> LF <contents> LF
        input_data = b"\n".join(objs) + b"\n"
        output = self.git.run_git_binary_out(
            ["cat-file", "--batch"], input_bytes=input_data
        )

        if not output:
            return [None] * len(objs)

        results = []
        offset = 0
        output_len = len(output)

        for _ in range(len(objs)):
            if offset >= output_len:
                results.append(None)
                continue

            # Find the end of the header line
            header_end = output.find(b"\n", offset)
            if header_end == -1:
                results.append(None)
                break

            header = output[offset:header_end].split()
            # If object is missing, header will be "<object> missing"
            if len(header) < 3 or header[1] == b"missing":
                results.append(None)
                offset = header_end + 1
                continue

            try:
                size = int(header[2])
            except (ValueError, IndexError):
                results.append(None)
                offset = header_end + 1
                continue

            content_start = header_end + 1
            content_end = content_start + size
            content = output[content_start:content_end]

            results.append(content)

            # Move offset past content and the trailing newline
            offset = content_end + 1

        return results

    def add(self, args: list[str], env: dict | None = None) -> bool:
        """Run git add with the given arguments."""
        return self.git.run_git_text(["add"] + args, env=env) is not None

    def apply(
        self, diff_content: bytes, args: list[str], env: dict | None = None
    ) -> bool:
        """Run git apply with the given diff content."""
        return (
            self.git.run_git_binary_out(
                ["apply"] + args, input_bytes=diff_content, env=env
            )
            is not None
        )

    def is_git_repo(self) -> bool:
        """Return True if current cwd is inside a git work tree, else False."""
        result = self.git.run_git_text_out(["rev-parse", "--is-inside-work-tree"])
        # When not a repo, run_git_text returns None; treat as False
        return bool(result and result.strip() == "true")

    def get_repo_root(self) -> str | None:
        """Returns the absolute path to the top-level directory of the repository."""
        res = self.git.run_git_text_out(["rev-parse", "--show-toplevel"])
        return res.strip() if res else None

    def is_bare_repository(self) -> bool:
        """Checks if the current repository is bare."""
        res = self.git.run_git_text_out(["rev-parse", "--is-bare-repository"])
        return res.strip() == "true" if res else False

    def try_get_parent_hash(
        self, commit_hash: str, empty_on_fail: bool = False
    ) -> str | None:
        """Attempts to get the parent hash of a commit."""
        parent_hash_result = self.git.run_git_text_out(
            ["rev-parse", "--verify", f"{commit_hash}^"]
        )
        if parent_hash_result is None:
            return EMPTYTREEHASH if empty_on_fail else None
        return parent_hash_result.strip()
