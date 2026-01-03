from typing import List

from rich.progress import Progress
from rich.console import Console

from importlib.resources import files

from ..data.composite_diff_chunk import CompositeDiffChunk
from ..data.chunk import Chunk
from ..git_interface.interface import GitInterface
from ..commands.git_commands import GitCommands
from ..synthesizer.git_synthesizer import GitSynthesizer
from ..branch_saver.branch_saver import BranchSaver

from ..chunker.interface import MechanicalChunker
from ..grouper.interface import LogicalGrouper
from ..data.models import CommitGroup, CommitResult
from ..checks.chunk_checks import chunks_disjoint

from ..semantic_grouper.semantic_grouper import SemanticGrouper


import inquirer


class AIGitPipeline:
    def __init__(
        self,
        git: GitInterface,
        console: Console,
        commands: GitCommands,
        mechanical_chunker: MechanicalChunker,
        semantic_grouper: SemanticGrouper,
        logical_grouper: LogicalGrouper,
        synthesizer: GitSynthesizer,
        branch_saver: BranchSaver,
        original_branch: str,
        new_branch: str,
        base_commit_hash: str,
        new_commit_hash: str,
    ):
        self.git = git
        self.commands = commands
        self.console = console

        self.mechanical_chunker = mechanical_chunker
        self.semantic_grouper = semantic_grouper
        self.logical_grouper = logical_grouper

        self.synthesizer = synthesizer
        self.branch_saver = branch_saver

        self.original_branch = original_branch
        self.new_branch = new_branch

        self.base_commit_hash = base_commit_hash
        self.new_commit_hash = new_commit_hash

    def run(self, target: str = None, message: str = None) -> List[CommitResult]:
        # Diff between the base commit and the backup branch commit
        # This gives us all changes that were in the working directory
        raw_diff: List[Chunk] = self.commands.get_processed_working_diff(
            self.base_commit_hash, self.new_commit_hash, target
        )

        print("raw_diff: \n".join([chunk.format_json() for chunk in raw_diff]))

        if not raw_diff:
            self.console.print("[gray] No changes to process, exiting. [/gray]")
            return

        # start tracking progress
        with Progress() as p:
            # create smallest mechanically valid chunks
            ck = p.add_task("Creating smallest mechanical chunks...", total=1)
            mechanical_chunks: list[Chunk] = self.mechanical_chunker.chunk(raw_diff)
            p.advance(ck, 1)

            print(
                "Mechanical chunk: \n".join(
                    [chunk.format_json() for chunk in mechanical_chunks]
                )
            )

            # group semantically dependent chunks
            sem_grp = p.add_task("Linking semantically related chunks...", total=1)
            semantic_chunks = self.semantic_grouper.group_chunks(mechanical_chunks)
            p.advance(sem_grp, 1)

            print(
                "Semantic chunk: \n".join(
                    [chunk.format_json() for chunk in semantic_chunks]
                )
            )

            ai_grp = p.add_task("Using AI to create meaningfull commits....", total=1)

            def on_progress(percent):
                # percent is 0-100, progress bar expects 0-1
                p.update(ai_grp, completed=percent / 100)

            # take these semantically valid chunks, and now group them into logical commits
            ai_groups: list[CompositeDiffChunk] = self.logical_grouper.group_chunks(
                semantic_chunks, message, on_progress=on_progress
            )

        final_groups = []
        for group in ai_groups:
            self.console.rule(f"[bold green]AI Commit Suggestion")
            self.console.print(f"[bold]Commit Message:[/bold] {group.commit_message}")
            if group.extended_message:
                self.console.print(
                    f"[bold]Extended Message:[/bold] {group.extended_message}"
                )

            affected_files = set()
            for chunk in group.chunks:
                for diff_chunk in chunk.get_chunks():
                    if diff_chunk.is_file_rename:
                        # Handle RenameDiffChunk
                        affected_files.add(
                            f"{diff_chunk.old_file_path} -> {diff_chunk.new_file_path}"
                        )
                    else:
                        affected_files.add(diff_chunk.canonical_path())
            self.console.print(
                f"[bold]Affected Files:[/bold] {', '.join(affected_files)}"
            )

            for chunk in group.chunks:
                self.console.print(f"[bold]File:[/bold] {chunk.canonical_paths()}")
                self.console.print(f"[bold]AI Diff JSON:[/bold]")
                content = chunk.format_json()
                if len(content) > 1000:
                    self.console.print(content[:1000] + "\n...(truncated)...")
                else:
                    self.console.print(content)

            accept = inquirer.confirm(f"Accept this group?", default=True)

            if accept:
                final_groups.append(group)
                self.console.print(f"[green]Group added to queue[/green]")
            else:
                still_continue = inquirer.confirm(
                    f"Do you still wish to continue with the other groups?",
                    default=True,
                )
                if not still_continue:
                    self.console.print("[yellow] Exiting without any changes [/yellow]")
                    return None

        if final_groups:
            plan_success = self.synthesizer.execute_plan(
                final_groups,
                self.commands.get_current_base_commit_hash(),
                self.original_branch,
            )

            if plan_success and target != ".":
                # we have overriden main branch with plan changes
                # if the target is not the whole repo (eg "."), then we want to bring back the other changes
                self.branch_saver.restore_from_backup(exclude_path=target)

            return plan_success
        else:
            self.console.print("[yellow]No changes accepted, not proceeding.[/yellow]")
            return False
