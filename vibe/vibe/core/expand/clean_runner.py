from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Callable

from rich.console import Console

from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.expand.service import ExpandService


@dataclass
class CleanOptions:
    ignore: Sequence[str] | None = None
    min_size: Optional[int] = None
    auto_yes: bool = False


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
        git: Optional[SubprocessGitInterface] = None,
        expand_service: Optional[ExpandService] = None,
    ):
        self.repo_path = repo_path
        self.git = git or SubprocessGitInterface(repo_path)
        self.expand_service = expand_service or ExpandService(repo_path)

    def run(self, options: CleanOptions, console: Console) -> bool:
        commits = self._get_first_parent_commits()
        if len(commits) < 2:
            console.print(
                "[yellow]Nothing to do: fewer than 2 commits on branch.[/yellow]"
            )
            return True

        targets = commits[:-1]  # skip root
        total = len(targets)
        console.rule("[bold green]vibe clean")
        console.print(f"[green]Considering {total} commits (HEAD -> second).[/green]")

        expanded = 0
        skipped = 0

        for idx, commit in enumerate(targets, start=1):
            short = commit[:7]

            if self._is_merge(commit):
                console.print(f"[yellow]Skip merge commit {short}.[/yellow]")
                skipped += 1
                continue

            if self._is_ignored(commit, options.ignore):
                console.print(f"[yellow]Skip ignored {short}.[/yellow]")
                skipped += 1
                continue

            if options.min_size is not None:
                changes = self._count_line_changes(commit)
                if changes is None:
                    console.print(
                        f"[yellow]Skip {short}: unable to count changes.[/yellow]"
                    )
                    skipped += 1
                    continue
                if changes < options.min_size:
                    console.print(
                        f"[yellow]Skip {short}: {changes} < min-size {options.min_size}.[/yellow]"
                    )
                    skipped += 1
                    continue

            console.rule(f"[bold cyan]{idx}/{total} Expanding {short}")
            ok = self.expand_service.expand_commit(
                commit,
                console=console,
                auto_yes=options.auto_yes
            )
            if not ok:
                console.print(
                    f"[red]Expansion failed or declined at {short}. Stopping.[/red]"
                )
                return False
            expanded += 1

        console.print(
            f"[bold green]Clean complete.[/bold green] Expanded={expanded}, skipped={skipped}"
        )
        return True

    # --- helpers ---

    def _confirm(self, prompt: str) -> bool:
        try:
            import typer

            return typer.confirm(prompt, default=True)
        except Exception:
            return True

    def _get_first_parent_commits(self) -> list[str]:
        out = self.git.run_git_text(["rev-list", "--first-parent", "HEAD"]) or ""
        return [l.strip() for l in out.splitlines() if l.strip()]

    def _is_merge(self, commit: str) -> bool:
        line = self.git.run_git_text(["rev-list", "--parents", "-n", "1", commit]) or ""
        parts = line.strip().split()
        # format: <commit> <p1> [<p2> ...]
        return len(parts) > 2

    def _is_ignored(self, commit: str, ignore: Sequence[str] | None) -> bool:
        if not ignore:
            return False
        for token in ignore:
            if commit.startswith(token):
                return True
        return False

    def _count_line_changes(self, commit: str) -> Optional[int]:
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
