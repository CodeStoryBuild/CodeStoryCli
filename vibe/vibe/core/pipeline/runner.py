import subprocess
from typing import List
from rich.progress import Progress
from rich.console import Console

from vibe.core.data import models
from vibe.core.data.r_diff_chunk import RenameDiffChunk
from ..git_interface.interface import GitInterface
from ..commands.git_commands import GitCommands
from ..synthesizer.git_synthesizer import GitSynthesizer
from ..chunker.interface import ChunkerInterface
from ..grouper.interface import GrouperInterface
from ..data.models import DiffChunk, CommitGroup, CommitResult

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


    def run(self, target : str = None) -> List[CommitResult]:
        
        # Step 0: clean working area
        if self.commands.need_reset():
                print("needs reset")
                unstage = inquirer.confirm("Staged changes detected, you must unstage all changes. Do you accept?", default=False)
                
                if unstage:
                    self.commands.reset()
                else:
                    console.print("[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]")
                    return None

            

        if self.commands.need_track_untracked(target):
            print("needs track untracked")
            track = inquirer.confirm(f"Untracked files detected within \"{target}\"  Do you want to track these files?", default=False)
            
            if track:
                self.commands.track_untracked(target)


        with Progress() as p:
            
            # Step 1: extract diff

            tr = p.add_task("Generating Diff", total=1)

            raw_diff: List[DiffChunk] = self.commands.get_processed_diff(target)

            p.advance(tr, 1)

            ck = p.add_task("Chunking Diff", total=1)
            
            chunks: List[DiffChunk] = self.chunker.chunk(raw_diff)

            for chunk in chunks:
                print(chunk.to_patch())

            p.advance(ck, 1)

            clssfy = p.add_task("Grouping diff", total=1)

            grouped: List[CommitGroup] = self.grouper.group_chunks(chunks)

            p.advance(clssfy, 1)

        console = Console()

        final_groups = []
        for group in grouped:
            console.rule(f"[bold green]AI Commit Suggestion")
            console.print(f"[bold]Commit Message:[/bold] {group.commmit_message}")
            if group.extended_message:
                console.print(f"[bold]Extended Message:[/bold] {group.extended_message}")

            affected_files = set()
            for chunk in group.chunks:
                if hasattr(chunk, 'file_path'):
                    affected_files.add(chunk.file_path)
                elif hasattr(chunk, 'old_file_path') and hasattr(chunk, 'new_file_path'):
                    # Handle RenameDiffChunk
                    affected_files.add(f"{chunk.old_file_path} -> {chunk.new_file_path}")
            console.print(f"[bold]Affected Files:[/bold] {', '.join(affected_files)}")

            # for chunk in group.chunks:
            #     console.print(f"[bold]File:[/bold] {chunk.file_path}")
            #     console.print(f"[bold]AI Diff JSON:[/bold]")
            #     console.print(chunk.format_json())
            #     console.print(f"[bold]Patch:[/bold]")
            #     console.print(f"[dim]{chunk.to_patch()}")

            accept = inquirer.confirm(f"Accept this group?", default=True)
            if accept:
                final_groups.append(group)
                console.print(f"[green]Group added to queue[/green]")
            else:
                still_continue = inquirer.confirm(f"Do you still wish to continue with the other groups?", default=True)
                if not still_continue:
                    console.print("[yellow] Exiting without any changes [/yellow]")
                    return None
                
        return self.synthesizer.execute_plan(final_groups, self.commands.get_current_base_commit_hash(), self.commands.get_current_branch())
