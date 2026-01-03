import contextlib

import inquirer
from loguru import logger
from rich.console import Console
from rich.progress import Progress

from ..branch_saver.branch_saver import BranchSaver
from ..chunker.interface import MechanicalChunker
from ..commands.git_commands import GitCommands
from ..data.chunk import Chunk
from ..data.immutable_chunk import ImmutableChunk
from ..data.commit_group import CommitGroup
from ..file_reader.file_parser import FileParser
from ..file_reader.protocol import FileReader
from ..git_interface.interface import GitInterface
from ..grouper.interface import LogicalGrouper
from ..semantic_grouper.context_manager import ContextManager
from ..semantic_grouper.query_manager import QueryManager
from ..semantic_grouper.semantic_grouper import SemanticGrouper
from ..synthesizer.git_synthesizer import GitSynthesizer
from ..synthesizer.utils import get_patches
from ..logging.utils import time_block, log_chunks


@contextlib.contextmanager
def progress_bar(p: Progress, step_name: str):
    ck = p.add_task(step_name, total=1)

    try:
        yield
    finally:
        p.advance(ck, 1)


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
        branch_saver: BranchSaver | None,
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

    def run(self, target: str = None, message: str = None, auto_yes: bool = False):
        # Initial invocation summary
        logger.info(
            "Pipeline run started: target={target} message_present={msg_present} base_commit={base} new_commit={new}",
            target=target,
            msg_present=message is not None,
            base=self.base_commit_hash,
            new=self.new_commit_hash,
        )
        # Diff between the base commit and the backup branch commit - all working directory changes
        with time_block("raw_diff_generation_ms"):
            raw_chunks, immmutable_chunks = self.commands.get_processed_working_diff(
                self.base_commit_hash, self.new_commit_hash, target
            )

        log_chunks(
            "raw_diff_generation_ms (with immutable groups)",
            raw_chunks,
            immmutable_chunks,
        )

        if not (raw_chunks or immmutable_chunks):
            logger.info("No changes to process, exiting")
            return

        # start tracking progress
        with Progress() as p:
            # init context_manager
            if raw_chunks:
                flat_chunks = [
                    diff_chunk
                    for chunk in raw_chunks
                    for diff_chunk in chunk.get_chunks()
                ]
                context_manager = ContextManager(
                    self.file_parser, self.file_reader, self.query_manager, flat_chunks
                )

                # create smallest mechanically valid chunks
                with progress_bar(p, "Creating Mechanical Chunks"):
                    with time_block("mechanical_chunking"):
                        mechanical_chunks: list[Chunk] = self.mechanical_chunker.chunk(
                            raw_chunks, context_manager
                        )

                log_chunks(
                    "mechanical_chunks (without immutable groups)",
                    mechanical_chunks,
                    [],
                )

                with progress_bar(p, "Creating Semantic Groups"):
                    with time_block("semantic_grouping"):
                        semantic_chunks = self.semantic_grouper.group_chunks(
                            mechanical_chunks, context_manager
                        )

                log_chunks(
                    "Semantic Chunks (without immutable groups)", semantic_chunks, []
                )
            else:
                semantic_chunks = []

            ai_grp = p.add_task("Using AI to create meaningfull commits....", total=1)

            def on_progress(percent):
                # percent is 0-100, progress bar expects 0-1
                p.update(ai_grp, completed=percent / 100)

            # take these semantically valid chunks, and now group them into logical commits
            with time_block("semantic_grouping"):
                ai_groups: list[CommitGroup] = self.logical_grouper.group_chunks(
                    semantic_chunks, immmutable_chunks, message, on_progress=on_progress
                )

        if not ai_groups:
            logger.warning("No proposed commits to apply")
            logger.info("No AI groups proposed; aborting pipeline")
            return

        logger.info("Proposed commits preview")
        # Prepare pretty diffs for each proposed group

        all_affected_files = set()

        patch_map = get_patches(ai_groups)
        for idx, group in enumerate(ai_groups):
            num = idx + 1
            logger.debug(
                "Proposed commit #{num}: {message}",
                num=num,
                message=group.commit_message,
            )
            if group.extended_message:
                logger.debug(
                    "Extended message: {message}", message=group.extended_message
                )

            affected_files = set()
            for chunk in group.chunks:
                if isinstance(chunk, ImmutableChunk):
                    affected_files.add(
                        chunk.canonical_path.decode("utf-8", errors="replace")
                    )
                else:
                    for diff_chunk in chunk.get_chunks():
                        if diff_chunk.is_file_rename:
                            old_path = (
                                diff_chunk.old_file_path.decode(
                                    "utf-8", errors="replace"
                                )
                                if isinstance(diff_chunk.old_file_path, bytes)
                                else diff_chunk.old_file_path
                            )
                            new_path = (
                                diff_chunk.new_file_path.decode(
                                    "utf-8", errors="replace"
                                )
                                if isinstance(diff_chunk.new_file_path, bytes)
                                else diff_chunk.new_file_path
                            )
                            affected_files.add(f"{old_path} -> {new_path}")
                        else:
                            path = diff_chunk.canonical_path()
                            affected_files.add(
                                path.decode("utf-8", errors="replace")
                                if isinstance(path, bytes)
                                else path
                            )

            all_affected_files.update(affected_files)

            files_preview = ", ".join(sorted(affected_files))
            if len(files_preview) > 120:
                files_preview = files_preview[:117] + "..."
            logger.debug("Files: {files}", files=files_preview)

            # Log the diff for this group at debug level
            diff_text = patch_map.get(idx, "") or "(no diff)"
            logger.info("Diff for #{num}:\n{diff}", num=num, diff=diff_text)

            logger.info(
                "Group preview: idx={idx} chunks={chunk_count} files={files}",
                idx=idx,
                chunk_count=len(group.chunks),
                files=len(affected_files),
            )

        # Single confirmation for all groups
        if auto_yes:
            apply_all = True
            logger.info("Auto-confirm: Applying all proposed commits")
        else:
            apply_all = inquirer.confirm(
                "Apply all proposed commits?",
                default=False,
            )

        if not apply_all:
            logger.info("No changes applied")
            logger.info("User declined applying commits")
            return

        logger.info(
            "Accepted groups summary: accepted_groups={groups}",
            groups=len(ai_groups),
        )

        with time_block("Executing Synthesizer Pipeline"):
            plan_success = self.synthesizer.execute_plan(
                ai_groups,
                self.commands.get_current_base_commit_hash(),
                self.original_branch,
            )

        # Final pipeline summary
        commit_count = len(plan_success) if isinstance(plan_success, list) else 0
        logger.info(
            "Pipeline summary: input_chunks={raw} mechanical={mech} semantic_groups={sem} final_groups={acc} commits_created={commits} files_changed={files}",
            raw=len(raw_chunks) + len(immmutable_chunks),
            mech=len(
                mechanical_chunks if raw_chunks else []
            ),  # if only immutable chunks, there are no mechanical chunks
            sem=len(
                semantic_chunks if raw_chunks else []
            ),  # if only immutable chunks, there are no semantic chunks
            acc=len(ai_groups),
            commits=commit_count,
            files=len(all_affected_files),
        )

        if plan_success and target != "." and self.branch_saver is not None:
            # we have overriden main branch with plan changes
            # if the target is not the whole repo (eg "."), then we want to bring back the other changes
            self.branch_saver.restore_from_backup(exclude_path=target)

        return plan_success
