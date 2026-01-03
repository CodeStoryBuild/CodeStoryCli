# -----------------------------------------------------------------------------

# dslate - Dual Licensed Software

# Copyright (c) 2025 Adem Can

#

# This file is part of DSLATE.

#

# codestory is available under a dual-license:

#   1. AGPLv3 (Affero General Public License v3)

#      - See LICENSE.txt and LICENSE-AGPL.txt

#      - Online: https://www.gnu.org/licenses/agpl-3.0.html

#

#   2. Commercial License

#      - For proprietary or revenue-generating use,

#        including SaaS, embedding in closed-source software,

#        or avoiding AGPL obligations.

#      - See LICENSE.txt and COMMERCIAL-LICENSE.txt

#      - Contact: ademfcan@gmail.com

#

# By using this file, you agree to the terms of one of the two licenses above.

# -----------------------------------------------------------------------------



import contextlib
from typing import Literal


import inquirer
from loguru import logger

from rich.progress import Progress
from rich.text import Text
from rich import print as rprint


from ..context import CommitContext, GlobalContext

from ..core.chunker.interface import MechanicalChunker

from ..core.commands.git_commands import GitCommands

from ..core.data.chunk import Chunk

from ..core.data.commit_group import CommitGroup

from ..core.data.immutable_chunk import ImmutableChunk

from ..core.file_reader.file_parser import FileParser

from ..core.file_reader.protocol import FileReader

from ..core.git_interface.interface import GitInterface

from ..core.grouper.interface import LogicalGrouper

from ..core.logging.utils import log_chunks, time_block

from ..core.semantic_grouper.context_manager import ContextManager

from ..core.semantic_grouper.query_manager import QueryManager

from ..core.semantic_grouper.semantic_grouper import SemanticGrouper

from ..core.synthesizer.git_synthesizer import GitSynthesizer

from ..core.synthesizer.utils import get_patches



@contextlib.contextmanager
def progress_bar(p: Progress | None, step_name: str):
    if p:
        ck = p.add_task(step_name, total=1)

    try:
        yield

    finally:
        if p:
            p.advance(ck, 1)

def print_patch_cleanly(patch_content: str, max_length: int = 120):

    """

    Displays a patch/diff content cleanly using Rich styling.

    """

    styles = {

        # File headers (e.g., --- a/file.py, +++ b/file.py)

        'header': "bold bright_blue",

        # Hunks (e.g., @@ -1,5 +1,5 @@)

        'hunk': "bold white",

        # Deleted lines (starts with -)

        'removed': "bold bright_red on #4d1515", # Added a subtle background for contrast

        # Added lines (starts with +)

        'added': "bold bright_green on #18421b", # Added a subtle background for contrast

        # Context lines (starts with space or not present)

        'context': "dim white",

    }


    # Iterate through the patch content line by line

    for line in patch_content.splitlines()[:max_length]:

        style_key = None

        prefix = line[:3] # Check up to the first three characters


        if prefix.startswith('---') or prefix.startswith('+++'):

            style_key = 'header'

        elif prefix.startswith('@@'):

            style_key = 'hunk'

        elif prefix.startswith('-'):

            style_key = 'removed'

        elif prefix.startswith('+'):

            style_key = 'added'

        else:

            style_key = 'context'
        

        # Create a Rich Text object and print it

        rprint(Text(line, style=styles[style_key]))

    if len(patch_content.splitlines()) > max_length:
        rprint("[yellow](Diff truncated)[/yellow]\n")



class CommitPipeline:

    def __init__(

        self,

        global_context: GlobalContext,

        commit_context: CommitContext,

        git: GitInterface,

        commands: GitCommands,

        mechanical_chunker: MechanicalChunker,

        semantic_grouper: SemanticGrouper,

        logical_grouper: LogicalGrouper,

        synthesizer: GitSynthesizer,

        file_reader: FileReader,

        file_parser: FileParser,

        query_manager: QueryManager,

        base_commit_hash: str,

        new_commit_hash: str,
        source: Literal["commit", "fix"]

    ):

        self.global_context = global_context

        self.commit_context = commit_context


        self.git = git

        self.commands = commands


        self.mechanical_chunker = mechanical_chunker

        self.semantic_grouper = semantic_grouper

        self.logical_grouper = logical_grouper


        self.synthesizer = synthesizer

        self.file_reader = file_reader

        self.file_parser = file_parser

        self.query_manager = query_manager


        self.base_commit_hash = base_commit_hash

        self.new_commit_hash = new_commit_hash

        self.source = source


    def run(self) -> str | None:

        # Initial invocation summary

        logger.debug(

            "Pipeline run started: target={target} message_present={msg_present} base_commit={base} new_commit={new}",

            target=self.commit_context.target,

            msg_present=self.commit_context.message is not None,

            base=self.base_commit_hash,

            new=self.new_commit_hash,

        )

        # Diff between the base commit and the backup branch commit - all working directory changes

        with time_block("raw_diff_generation_ms"):

            raw_chunks, immutable_chunks = self.commands.get_processed_working_diff(

                self.base_commit_hash,

                self.new_commit_hash,

                str(self.commit_context.target) if self.commit_context.target else None,

            )


        log_chunks(

            "raw_diff_generation_ms (with immutable groups)",

            raw_chunks,

            immutable_chunks,

        )


        if not (raw_chunks or immutable_chunks):

            logger.info("No changes to process.")

            if self.source == "commit":
                logger.info("[yellow]If you meant to modify existing git history, please use dslate fix or dslate clean commands[/yellow]")

            return None

        # start tracking progress
        p = Progress() if not self.global_context.silent else None

    
        # init context_manager

        if raw_chunks:

            flat_chunks = [

                diff_chunk

                for chunk in raw_chunks

                for diff_chunk in chunk.get_chunks()

            ]

            context_manager = ContextManager(

                self.file_parser,

                self.file_reader,

                self.query_manager,

                flat_chunks,

            )


            # create smallest mechanically valid chunks

            with (

                progress_bar(p, "Creating Mechanical Chunks"),

                time_block("mechanical_chunking"),

            ):

                mechanical_chunks: list[Chunk] = self.mechanical_chunker.chunk(

                    raw_chunks, context_manager

                )


            log_chunks(

                "mechanical_chunks (without immutable groups)",

                mechanical_chunks,

                [],

            )


            with (

                progress_bar(p, "Creating Semantic Groups"),

                time_block("semantic_grouping"),

            ):

                semantic_chunks = self.semantic_grouper.group_chunks(

                    mechanical_chunks, context_manager

                )


            log_chunks(

                "Semantic Chunks (without immutable groups)",

                semantic_chunks,

                [],

            )

        else:

            semantic_chunks = []


        if p:
            ai_grp = p.add_task("Using AI to create meaningfull commits....", total=1)


            def on_progress(percent):

                # percent is 0-100, progress bar expects 0-1

                p.update(ai_grp, completed=percent / 100)
        else:
            on_progress = None


        # take these semantically valid chunks, and now group them into logical commits

        with time_block("logical_grouping"):

            ai_groups: list[CommitGroup] = self.logical_grouper.group_chunks(

                semantic_chunks,

                immutable_chunks,

                self.commit_context.message,

                on_progress=on_progress,

            )

        if p:
            p.stop()


        if not ai_groups:

            logger.warning("No proposed commits to apply")

            logger.info("No AI groups proposed; aborting pipeline")

            return None


        logger.info("Proposed commits preview")

        # Prepare pretty diffs for each proposed group


        all_affected_files = set()


        patch_map = get_patches(ai_groups)

        for idx, group in enumerate(ai_groups):

            num = idx + 1

            logger.info(

                "\nProposed commit #{num}: {message}",

                num=num,

                message=group.commit_message,

            )

            if group.extended_message:

                logger.info(

                    "Extended message: {message}",

                    message=group.extended_message,

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

            logger.info("Files: {files}\n", files=files_preview)


            # Log the diff for this group at debug level

            diff_text = patch_map.get(idx, "") or "(no diff)"

            if not (self.global_context.silent and self.global_context.auto_accept):
                rprint(f"Diff for #{num}:")
                if diff_text != "(no diff)":
                    print_patch_cleanly(diff_text, max_length=120)
                else:
                    rprint("[yellow](no diff)[/yellow]")

            logger.debug(

                "Group preview: idx={idx} chunks={chunk_count} files={files}",

                idx=idx,

                chunk_count=len(group.chunks),

                files=len(affected_files),

            )

            logger.info("")


        # Single confirmation for all groups

        if self.global_context.auto_accept:

            apply_all = True

            logger.debug("Auto-confirm: Applying all proposed commits")

        else:

            apply_all = inquirer.confirm(

                "Apply all proposed commits?",

                default=False,

            )


        if not apply_all:

            logger.info("No changes applied")

            logger.info("User declined applying commits")

            return None


        logger.debug(

            "Num accepted groups: {groups}",

            groups=len(ai_groups),

        )


        with time_block("Executing Synthesizer Pipeline"):

            new_commit_hash = self.synthesizer.execute_plan(

                ai_groups, self.base_commit_hash

            )


        # Final pipeline summary

        logger.debug(

            "Pipeline summary: input_chunks={raw} mechanical={mech} semantic_groups={sem} final_groups={acc} files_changed={files}",

            raw=len(raw_chunks) + len(immutable_chunks),

            mech=len(

                mechanical_chunks if raw_chunks else []

            ),  # if only immutable chunks, there are no mechanical chunks

            sem=len(

                semantic_chunks if raw_chunks else []

            ),  # if only immutable chunks, there are no semantic chunks

            acc=len(ai_groups),

            files=len(all_affected_files),

        )

        return new_commit_hash  

