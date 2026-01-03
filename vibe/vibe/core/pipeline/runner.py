from typing import List
from time import perf_counter

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
from ..data.models import CommitResult

from ..file_reader.protocol import FileReader
from ..file_reader.file_parser import FileParser
from ..semantic_grouper.query_manager import QueryManager
from ..semantic_grouper.context_manager import ContextManager

from ..semantic_grouper.semantic_grouper import SemanticGrouper


import inquirer
from loguru import logger


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
        file_reader: FileReader,
        file_parser: FileParser,
        query_manager: QueryManager,
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
        self.file_reader = file_reader
        self.file_parser = file_parser
        self.query_manager = query_manager

        self.original_branch = original_branch
        self.new_branch = new_branch

        self.base_commit_hash = base_commit_hash
        self.new_commit_hash = new_commit_hash

    def run(self, target: str = None, message: str = None) -> List[CommitResult]:
        _t_start = perf_counter()
        # Initial invocation summary
        logger.info(
            "Pipeline run started: target={target} message_present={msg_present} base_commit={base} new_commit={new}",
            target=target,
            msg_present=message is not None,
            base=self.base_commit_hash,
            new=self.new_commit_hash,
        )
        # Diff between the base commit and the backup branch commit - all working directory changes
        t0 = perf_counter()
        raw_diff: List[Chunk] = self.commands.get_processed_working_diff(
            self.base_commit_hash, self.new_commit_hash, target
        )
        t1 = perf_counter()

        logger.info(
            "Raw diff summary: chunks={count} files={files}",
            count=len(raw_diff),
            files=len({path for c in raw_diff for path in c.canonical_paths()}),
        )
        logger.info("Timing: raw_diff_generation_ms={ms}", ms=int((t1 - t0) * 1000))

        if not raw_diff:
            self.console.print("[gray] No changes to process, exiting. [/gray]")
            return

        # start tracking progress
        with Progress() as p:
            # init context_manager
            flat_chunks = [
                diff_chunk for chunk in raw_diff for diff_chunk in chunk.get_chunks()
            ]
            context_manager = ContextManager(
                self.file_parser, self.file_reader, self.query_manager, flat_chunks
            )

            # create smallest mechanically valid chunks
            ck = p.add_task("Creating smallest mechanical chunks...", total=1)
            t_mech0 = perf_counter()
            mechanical_chunks: list[Chunk] = self.mechanical_chunker.chunk(
                raw_diff, context_manager
            )
            t_mech1 = perf_counter()
            p.advance(ck, 1)

            logger.debug(f"{mechanical_chunks=}")

            logger.info(
                "Mechanical chunking summary: mechanical_chunks={count}",
                count=len(mechanical_chunks),
            )
            logger.info(
                "Timing: mechanical_chunking_ms={ms}",
                ms=int((t_mech1 - t_mech0) * 1000),
            )

            # group semantically dependent chunks
            sem_grp = p.add_task("Linking semantically related chunks...", total=1)
            t_sem0 = perf_counter()
            semantic_chunks = self.semantic_grouper.group_chunks(
                mechanical_chunks, context_manager
            )
            t_sem1 = perf_counter()
            p.advance(sem_grp, 1)
            logger.debug(f"{semantic_chunks=}")

            logger.info(
                "Semantic grouping summary: semantic_groups={groups}",
                groups=len(semantic_chunks),
            )
            logger.info(
                "Timing: semantic_grouping_ms={ms}",
                ms=int((t_sem1 - t_sem0) * 1000),
            )

            ai_grp = p.add_task("Using AI to create meaningfull commits....", total=1)

            def on_progress(percent):
                # percent is 0-100, progress bar expects 0-1
                p.update(ai_grp, completed=percent / 100)

            # take these semantically valid chunks, and now group them into logical commits
            t_ai0 = perf_counter()
            ai_groups: list[CompositeDiffChunk] = self.logical_grouper.group_chunks(
                semantic_chunks, message, on_progress=on_progress
            )
            t_ai1 = perf_counter()
            logger.info(
                "Logical grouping (AI) summary: proposed_groups={groups}",
                groups=len(ai_groups),
            )
            logger.info(
                "Timing: logical_grouping_ms={ms}",
                ms=int((t_ai1 - t_ai0) * 1000),
            )

        final_groups = []
        for group in ai_groups:
            self.console.rule(f"[bold green]AI Commit Suggestion")
            self.console.print(f"[bold]Commit Message:[/bold] {group.commit_message}")
            if group.extended_message:
                self.console.print(
                    f"[bold]Extended Message:[/bold] {group.extended_message}"
                )
            logger.info(
                "Group suggestion: group_id={gid} chunks={chunk_count} commit_msg_len={mlen} extended_present={ext}",
                gid=getattr(group, "group_id", None),
                chunk_count=len(group.chunks),
                mlen=len(group.commit_message or ""),
                ext=group.extended_message is not None,
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
            logger.info(
                "Group affected files: group_id={gid} files={files}",
                gid=getattr(group, "group_id", None),
                files=len(affected_files),
            )

            for chunk in group.chunks:
                self.console.print(f"[bold]File:[/bold] {chunk.canonical_paths()}")
                self.console.print(f"[bold]AI Diff JSON:[/bold]")
                content = chunk.format_json()
                if len(content) > 1000:
                    self.console.print(content[:1000] + "\n...(truncated)...")
                else:
                    self.console.print(content)
                logger.debug(
                    "Chunk detail logged: group_id={gid} chunk_paths={paths} content_len={clen}",
                    gid=getattr(group, "group_id", None),
                    paths=chunk.canonical_paths(),
                    clen=len(content),
                )

            accept = inquirer.confirm(f"Accept this group?", default=True)

            if accept:
                final_groups.append(group)
                self.console.print(f"[green]Group added to queue[/green]")
                logger.info(
                    "Group accepted: group_id={gid} total_accepted={accepted}",
                    gid=getattr(group, "group_id", None),
                    accepted=len(final_groups),
                )
            else:
                still_continue = inquirer.confirm(
                    f"Do you still wish to continue with the other groups?",
                    default=True,
                )
                if not still_continue:
                    self.console.print("[yellow] Exiting without any changes [/yellow]")
                    logger.info(
                        "Pipeline aborted by user: accepted_groups={accepted}",
                        accepted=len(final_groups),
                    )
                    return None

        if final_groups:
            logger.info(
                "Accepted groups summary: accepted_groups={groups}",
                groups=len(final_groups),
            )
            t_plan0 = perf_counter()
            plan_success = self.synthesizer.execute_plan(
                final_groups,
                self.commands.get_current_base_commit_hash(),
                self.original_branch,
            )
            t_plan1 = perf_counter()
            total_ms = int((perf_counter() - _t_start) * 1000)
            # Final pipeline summary
            affected_files_summary = set()
            for group in final_groups:
                for ch in group.chunks:
                    for dc in ch.get_chunks():
                        if dc.is_file_rename:
                            affected_files_summary.add(
                                f"{dc.old_file_path} -> {dc.new_file_path}"
                            )
                        else:
                            affected_files_summary.add(dc.canonical_path())
            commit_count = len(plan_success) if isinstance(plan_success, list) else 0
            logger.info(
                "Pipeline summary: raw_chunks={raw} mechanical={mech} semantic_groups={sem} proposed_groups={prop} accepted_groups={acc} commits_created={commits} files_changed={files} total_ms={total}",
                raw=len(raw_diff),
                mech=len(mechanical_chunks),
                sem=len(semantic_chunks),
                prop=len(ai_groups),
                acc=len(final_groups),
                commits=commit_count,
                files=len(affected_files_summary),
                total=total_ms,
            )
            logger.info(
                "Timing breakdown: diff_ms={diff} mech_ms={mech} sem_ms={sem} ai_ms={ai} plan_ms={plan}",
                diff=int((t1 - t0) * 1000),
                mech=int((t_mech1 - t_mech0) * 1000),
                sem=int((t_sem1 - t_sem0) * 1000),
                ai=int((t_ai1 - t_ai0) * 1000),
                plan=int((t_plan1 - t_plan0) * 1000),
            )

            if plan_success and target != ".":
                # we have overriden main branch with plan changes
                # if the target is not the whole repo (eg "."), then we want to bring back the other changes
                self.branch_saver.restore_from_backup(exclude_path=target)

            return plan_success
        else:
            self.console.print("[yellow]No changes accepted, not proceeding.[/yellow]")
            logger.info("Pipeline completed with no accepted groups")
            return False
