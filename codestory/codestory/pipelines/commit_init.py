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


from typing import Literal
from codestory.context import CommitContext, GlobalContext
from codestory.core.chunker.atomic_chunker import AtomicChunker
from codestory.core.exceptions import GitError
from codestory.core.file_reader.file_parser import FileParser
from codestory.core.file_reader.git_file_reader import GitFileReader
from codestory.core.grouper.langchain_grouper import LangChainGrouper
from codestory.core.grouper.single_grouper import SingleGrouper
from codestory.core.semantic_grouper.query_manager import QueryManager
from codestory.core.semantic_grouper.semantic_grouper import SemanticGrouper
from codestory.core.synthesizer.git_synthesizer import GitSynthesizer
from codestory.pipelines.commit_pipeline import CommitPipeline
from loguru import logger


def create_commit_pipeline(
    global_ctx: GlobalContext,
    commit_ctx: CommitContext,
    base_commit_hash: str,
    new_commit_hash: str,
    source: Literal["commit", "fix"]
):
    chunker = AtomicChunker(global_ctx.aggresiveness != "Conservative")

    if global_ctx.model is not None:
        logical_grouper = LangChainGrouper(global_ctx.model)
    else:
        logger.warning("Using no ai grouping as commit_pipeline recieved no model!")
        logical_grouper = SingleGrouper()

    if new_commit_hash is None:
        raise GitError("Failed to backup working state, exiting.")

    file_reader = GitFileReader(
        global_ctx.git_interface, base_commit_hash, new_commit_hash
    )
    file_parser = FileParser()

    query_manager = QueryManager()

    semantic_grouper = SemanticGrouper()

    synthesizer = GitSynthesizer(global_ctx.git_interface)

    pipeline = CommitPipeline(
        global_ctx,
        commit_ctx,
        global_ctx.git_interface,
        global_ctx.git_commands,
        chunker,
        semantic_grouper,
        logical_grouper,
        synthesizer,
        file_reader,
        file_parser,
        query_manager,
        base_commit_hash,
        new_commit_hash,
        source
    )

    return pipeline
