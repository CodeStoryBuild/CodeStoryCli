import subprocess
from typing import List
from rich.progress import Progress
from rich.console import Console

from vibe.core.data import models
from vibe.core.data.r_diff_chunk import RenameDiffChunk
from ..git_interface.interface import GitInterface
from ..diff_extractor.interface import DiffExtractorInterface
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

    
    def apply_chunk_to_index(self, chunk: DiffChunk):
        patch_text = chunk.to_patch(file_header=True)
        proc = subprocess.run(
            ["git", "apply", "--cached", "--unidiff-zero"],
            input=patch_text.encode("utf-8"),
            capture_output=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Patch apply failed: {proc.stderr.decode()}")

    

    def run(self, target : str) -> List[CommitResult]:
        
        # Step 0: clean working area
        if self.git.need_reset():
                unstage = inquirer.confirm("Staged changes detected, you must unstage all changes. Do you accept?", default=False)
                
                if unstage:
                    self.git.reset()
                else:
                    console.print("[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]")

            

        if self.git.need_track_untracked(target):

            track = inquirer.confirm(f"Untracked files detected within \"{target}\"  Do you want to track these files?", default=False)
            
            if track:
                self.git.track_untracked(target)


        with Progress() as p:
            
            # Step 1: extract diff

            tr = p.add_task("Generating Diff", total=1)

            raw_diff: List[DiffChunk] = self.git.get_processed_diff(target)

            p.advance(tr, 1)

            ck = p.add_task("Chunking Diff", total=1)
            
            chunks: List[DiffChunk] = self.chunker.chunk(raw_diff)

            p.advance(ck, 1)

            clssfy = p.add_task("Grouping diff", total=1)

            grouped: List[CommitGroup] = self.grouper.group_chunks(chunks)

            p.advance(clssfy, 1)

        console = Console()
        results: List[CommitResult] = []

        for group in grouped:
            console.rule(f"[bold green]AI Commit Suggestion")
            console.print(f"[bold]Commit Message:[/bold] {group.commmit_message}")
            console.print(f"[bold]Branch Name:[/bold] {group.branch_name}")
            if group.extended_message:
                console.print(f"[bold]Extended Message:[/bold] {group.extended_message}")

            affected_files = {chunk.file_path for chunk in group.chunks}
            console.print(f"[bold]Affected Files:[/bold] {', '.join(affected_files)}")

            for chunk in group.chunks:
                console.print(f"[bold]File:[/bold] {chunk.file_path}")
                console.print(f"[bold]AI Diff JSON:[/bold]")
                console.print(chunk.format_json())
                console.print(f"[bold]Patch:[/bold]")
                console.print(f"[dim]{chunk.to_patch()}")

            accept = inquirer.confirm(f"Accept and commit this group?", default=True)
            if accept:
                commit_result = self.git.commit_to_new_branch(group)
                results.append(commit_result)
                console.print(f"[green]Committed: {commit_result.commit_hash}[/green]")
            else:
                console.print("[yellow]Skipped this group.[/yellow]")

        return results
