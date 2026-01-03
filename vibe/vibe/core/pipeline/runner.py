from typing import List

from rich.progress import Progress
from rich.console import Console

from importlib.resources import files

from ..data.composite_diff_chunk import CompositeDiffChunk
from ..data.chunk import Chunk
from ..git_interface.interface import GitInterface
from ..commands.git_commands import GitCommands
from ..synthesizer.git_synthesizer import GitSynthesizer
from .branch_saver import BranchSaver

from ..chunker.interface import MechanicalChunker
from ..grouper.interface import AIGrouper
from ..data.models import CommitGroup, CommitResult
from ..data.diff_chunk import DiffChunk
from ..checks.chunk_checks import chunks_disjoint

from ...semantic_grouping.semantic_grouper.semantic_grouper import SemanticGrouper
from ...semantic_grouping.semantic_grouper.query_manager import QueryManager
from ...semantic_grouping.file_reader.git_file_reader import GitFileReader
from ...semantic_grouping.file_reader.file_parser import FileParser


import inquirer


class AIGitPipeline:
    def __init__(
        self,
        git: GitInterface,
        mechanical_chunker: MechanicalChunker,
        ai_grouper: AIGrouper,
        console: Console
    ):
        self.git = git
        self.console = console

        self.mechanical_chunker: MechanicalChunker = mechanical_chunker
        self.ai_grouper: AIGrouper = ai_grouper

        self.commands = GitCommands(self.git)
        self.synthesizer = GitSynthesizer(self.git)
        self.branch_saver = BranchSaver(self.git)

    def verify_repo(self, target : str) -> bool:
        # Step 0: clean working area
        if self.commands.need_reset():
            unstage = inquirer.confirm(
                "Staged changes detected, you must unstage all changes. Do you accept?",
                default=False,
            )

            if unstage:
                self.commands.reset()
            else:
                self.console.print(
                    "[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]"
                )
                return False

        if self.commands.need_track_untracked(target):
            track = inquirer.confirm(
                f'Untracked files detected within "{target}"  Do you want to track these files?',
                default=False,
            )

            if track:
                self.commands.track_untracked(target)

        return True
    

    def run(self, target: str = None, message: str = None) -> List[CommitResult]:
        if not self.verify_repo(target):
            return

        base_commit_hash = self.commands.get_current_base_commit_hash()
        original_branch = self.commands.get_current_branch()

        new_commit_hash, backup_branch = self.branch_saver.save_working_state()

        if new_commit_hash is None:
            self.console.print("[red] Failed to save working directory! [/red]")
            return

        try:
            # Diff between the base commit and the backup branch commit
            # This gives us all changes that were in the working directory
            raw_diff: List[Chunk] = self.commands.get_processed_working_diff(base_commit_hash, new_commit_hash, target)

            if not raw_diff:
                self.console.print("[gray] No changes to process, exiting. [/gray]")
                return
            
            # start tracking progress
            with Progress() as p:
                # create smallest mechanically valid chunks
                ck = p.add_task("Creating smallest mechanical chunks...", total=1)
                mechanical_chunks : list[Chunk] = self.mechanical_chunker.chunk(raw_diff)
                p.advance(ck, 1)

                print("Mechanical chunk: \n".join([chunk.format_json() for chunk in mechanical_chunks]))

                

                # group semantically dependent chunks
                sem_grp = p.add_task("Linking semantically related chunks...", total=1)
                config_path = files("vibe") / "resources" / "language_config.json"
                sem_grouper = SemanticGrouper(FileParser(), GitFileReader(self.git, base_commit_hash, new_commit_hash), QueryManager(config_path))
                semantic_chunks = sem_grouper.group_chunks(mechanical_chunks)
                p.advance(sem_grp, 1)

                print("Semantic chunk: \n".join([chunk.format_json() for chunk in semantic_chunks]))

                
                ai_grp = p.add_task("Using AI to create meaningfull commits....", total=1)
                def on_progress(percent):
                    # percent is 0-100, progress bar expects 0-1
                    p.update(ai_grp, completed=percent / 100)

                # take these semantically valid chunks, and now group them into logical commits
                ai_groups : list[CompositeDiffChunk] = self.ai_grouper.group_chunks(semantic_chunks, message, on_progress=on_progress)


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
                self.console.print(f"[bold]Affected Files:[/bold] {', '.join(affected_files)}")

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
                return self.synthesizer.execute_plan(
                    final_groups,
                    self.commands.get_current_base_commit_hash(),
                    original_branch,
                )
            else:
                self.console.print("[yellow]No changes accepted, restoring working directory...[/yellow]")
                self.branch_saver.restore_from_backup()
                return False
            
        except Exception as e:
            self.console.print("[yellow]Attempting to restore working directory from backup...[/yellow]")
            
            if self.branch_saver.restore_from_backup():
                self.console.print("[green]Successfully restored working directory from backup[/green]")
            else:
                self.console.print(f"[red]Failed to restore from backup. You may need to manually cherry-pick from '{backup_branch}'[/red]")

            self.console.print(f"[red]Error during processing: {e}[/red]")
            raise RuntimeError(e)
            
            return None
