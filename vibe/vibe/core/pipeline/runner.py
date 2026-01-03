import subprocess
from typing import List
from rich.progress import Progress
from rich.console import Console

from vibe.core.data import models
from vibe.core.data.r_diff_chunk import RenameDiffChunk
from ..git_interface.interface import GitInterface
from ..commands.git_commands import GitCommands
from ..synthesizer.git_synthesizer_porcelain import GitSynthesizer

# from ..synthesizer.git_synthesizer_opt import GitSynthesizer
from ..chunker.interface import ChunkerInterface
from ..grouper.interface import GrouperInterface
from ..data.models import DiffChunk, CommitGroup, CommitResult
from ..data.s_diff_chunk import StandardDiffChunk
from ..checks.chunk_checks import chunks_disjoint

import inquirer


class AIGitPipeline:
    def __init__(
        self,
        git: GitInterface,
        chunker: ChunkerInterface,
        grouper: GrouperInterface,
    ):
        self.git: GitInterface = git
        self.chunker: ChunkerInterface = chunker
        self.grouper: GrouperInterface = grouper
        self.commands = GitCommands(self.git)
        self.synthesizer = GitSynthesizer(self.git)

    def run(self, target: str = None, message: str = None) -> List[CommitResult]:

        # Step 0: clean working area
        if self.commands.need_reset():
            print("needs reset")
            unstage = inquirer.confirm(
                "Staged changes detected, you must unstage all changes. Do you accept?",
                default=False,
            )

            if unstage:
                self.commands.reset()
            else:
                console.print(
                    "[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]"
                )
                return None

        if self.commands.need_track_untracked(target):
            print("needs track untracked")
            track = inquirer.confirm(
                f'Untracked files detected within "{target}"  Do you want to track these files?',
                default=False,
            )

            if track:
                self.commands.track_untracked(target)

        with Progress() as p:

            # Step 1: extract diff

            tr = p.add_task("Generating Diff", total=1)

            raw_diff: List[DiffChunk] = self.commands.get_processed_diff(target)

            if not chunks_disjoint(
                [chunk for chunk in raw_diff if isinstance(chunk, StandardDiffChunk)]
            ):
                raise RuntimeError("initial diff chunks are not disjoint!")
            else:
                for chunk in raw_diff:
                    print("Chunk status right from diff")
                    print(chunk.format_json())

            p.advance(tr, 1)

            ck = p.add_task("Chunking Diff", total=1)

            chunks: List[DiffChunk] = self.chunker.chunk(raw_diff)

            if not chunks_disjoint(
                [chunk for chunk in chunks if isinstance(chunk, StandardDiffChunk)]
            ):
                raise RuntimeError("Chunked chunks are not disjoint!")
            else:
                for chunk in chunks:
                    print("chunk status after splitting chunks further")
                    print(chunk.format_json())

            p.advance(ck, 1)

            clssfy = p.add_task("Grouping diff", total=1)

            def on_progress(percent):
                # percent is 0-100, progress bar expects 0-1
                p.update(clssfy, completed=percent / 100)

            grouped: List[CommitGroup] = self.grouper.group_chunks(
                chunks, message, on_progress=on_progress
            )

            # Ensure progress bar is complete at the end
            p.update(clssfy, completed=1)

        full_chunks = []

        for group in grouped:
            full_chunks.extend(group.chunks)

        if not chunks_disjoint(
            [chunk for chunk in full_chunks if isinstance(chunk, StandardDiffChunk)]
        ):
            raise RuntimeError("Grouped chunks are not disjoint!")
        else:
            for chunk in full_chunks:
                print("chunk status after grouping chunks")
                print(chunk.format_json())

        console = Console()

        final_groups = []
        for group in grouped:
            console.rule(f"[bold green]AI Commit Suggestion")
            console.print(f"[bold]Commit Message:[/bold] {group.commmit_message}")
            if group.extended_message:
                console.print(
                    f"[bold]Extended Message:[/bold] {group.extended_message}"
                )

            affected_files = set()
            for chunk in group.chunks:
                if isinstance(chunk, RenameDiffChunk):
                    # Handle RenameDiffChunk
                    affected_files.add(
                        f"{chunk.old_file_path} -> {chunk.new_file_path}"
                    )
                else:
                    affected_files.add(chunk.file_path())
            console.print(f"[bold]Affected Files:[/bold] {', '.join(affected_files)}")

            # for chunk in group.chunks:
            #     console.print(f"[bold]File:[/bold] {chunk.file_path}")
            #     console.print(f"[bold]AI Diff JSON:[/bold]")
            #     console.print(chunk.format_json())

            accept = inquirer.confirm(f"Accept this group?", default=True)
            if accept:
                final_groups.append(group)
                console.print(f"[green]Group added to queue[/green]")
            else:
                still_continue = inquirer.confirm(
                    f"Do you still wish to continue with the other groups?",
                    default=True,
                )
                if not still_continue:
                    console.print("[yellow] Exiting without any changes [/yellow]")
                    return None

        return self.synthesizer.execute_plan(
            final_groups,
            self.commands.get_current_base_commit_hash(),
            self.commands.get_current_branch(),
        )
