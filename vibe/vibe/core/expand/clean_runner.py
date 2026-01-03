from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loguru import logger
from rich.console import Console
from vibe.core.expand.service import ExpandService
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface


@dataclass
class CleanOptions:
    ignore: Sequence[str] | None = None
    min_size: int | None = None
    auto_yes: bool = False
    start_from: str | None = None


class CleanRunner:
    """Iteratively expand commits from HEAD down to the second commit.

    Filtering rules:
    - ignore: any commit whose hash starts with any ignore token will be skipped
    - min_size: if provided, skip commits whose (additions + deletions) < min_size
    - merge commits are skipped (only single-parent commits are supported)
    """

    def __init__(
        self,
        repo_path: str = ".",
        git: SubprocessGitInterface | None = None,
        expand_service: ExpandService | None = None,
    ):
        self.repo_path = repo_path
        self.git = git or SubprocessGitInterface(repo_path)
        self.expand_service = expand_service or ExpandService(repo_path)

    def run(self, options: CleanOptions, console: Console) -> bool:
        commits = self._get_first_parent_commits(options.start_from)
        if len(commits) < 2:
            logger.info("Nothing to do: fewer than 2 commits on branch")
            return True

        targets = commits[:-1]  # skip root
        total = len(targets)
        logger.info("Starting vibe clean operation on {total} commits", total=total)

        expanded = 0
        skipped = 0

        for idx, commit in enumerate(targets, start=1):
            short = commit[:7]

            if self._is_merge(commit):
                logger.debug("Skipping merge commit {commit}", commit=short)
                skipped += 1
                continue

            if self._is_ignored(commit, options.ignore):
                logger.debug("Skipping ignored commit {commit}", commit=short)
                skipped += 1
                continue

            if options.min_size is not None:
                changes = self._count_line_changes(commit)
                if changes is None:
                    logger.debug(
                        "Skipping {commit}: unable to count changes", commit=short
                    )
                    skipped += 1
                    continue
                if changes < options.min_size:
                    logger.debug(
                        "Skipping {commit}: {changes} < min-size {min_size}",
                        commit=short,
                        changes=changes,
                        min_size=options.min_size,
                    )
                    skipped += 1
                    continue

            logger.info(
                "Expanding commit {commit} ({idx}/{total})",
                commit=short,
                idx=idx,
                total=total,
            )
            ok = self.expand_service.expand_commit(
                commit, console=console, auto_yes=options.auto_yes
            )
            if not ok:
                logger.error(
                    "Expansion failed or declined at {commit}. Stopping", commit=short
                )
                return False
            expanded += 1

        logger.info(
            "Clean operation complete: expanded={expanded}, skipped={skipped}",
            expanded=expanded,
            skipped=skipped,
        )
        return True

    # --- helpers ---

    def _confirm(self, prompt: str) -> bool:
        try:
            import typer

            return typer.confirm(prompt, default=True)
        except Exception:
            return True

    def _get_first_parent_commits(self, start_from: str | None = None) -> list[str]:
        start_ref = start_from or "HEAD"
        if start_from:
            # Resolve the commit hash first to ensure it exists
            resolved = self.git.run_git_text(["rev-parse", start_from])
            if resolved is None:
                raise ValueError(f"Could not resolve commit: {start_from}")
            start_ref = resolved.strip()

        out = self.git.run_git_text(["rev-list", "--first-parent", start_ref]) or ""
        return [l.strip() for l in out.splitlines() if l.strip()]

    def _is_merge(self, commit: str) -> bool:
        line = self.git.run_git_text(["rev-list", "--parents", "-n", "1", commit]) or ""
        parts = line.strip().split()
        # format: <commit> <p1> [<p2> ...]
        return len(parts) > 2

    def _is_ignored(self, commit: str, ignore: Sequence[str] | None) -> bool:
        if not ignore:
            return False
        return any(commit.startswith(token) for token in ignore)

    def _count_line_changes(self, commit: str) -> int | None:
        # Sum additions + deletions between parent and commit.
        # Use numstat for robust parsing; binary files show '-' which we treat as 0.
        out = self.git.run_git_text(["diff", "--numstat", f"{commit}^", commit])
        if out is None:
            return None
        total = 0
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            a, d = parts[0], parts[1]
            try:
                add = int(a)
            except ValueError:
                add = 0
            try:
                dele = int(d)
            except ValueError:
                dele = 0
            total += add + dele
        return total
