from dslate.context import CommitContext, GlobalContext
from dslate.core.chunker.atomic_chunker import AtomicChunker
from dslate.core.exceptions import GitError
from dslate.core.file_reader.file_parser import FileParser
from dslate.core.file_reader.git_file_reader import GitFileReader
from dslate.core.grouper.langchain_grouper import LangChainGrouper
from dslate.core.grouper.single_grouper import SingleGrouper
from dslate.core.semantic_grouper.query_manager import QueryManager
from dslate.core.semantic_grouper.semantic_grouper import SemanticGrouper
from dslate.core.synthesizer.git_synthesizer import GitSynthesizer
from dslate.pipelines.commit_pipeline import CommitPipeline
from loguru import logger


def create_commit_pipeline(
    global_ctx: GlobalContext,
    commit_ctx: CommitContext,
    base_commit_hash: str,
    new_commit_hash: str,
):
    chunker = AtomicChunker(global_ctx.aggresiveness != "Conservative")

    if global_ctx.model is not None:
        logical_grouper = LangChainGrouper(global_ctx.model)
    else:
        logger.warning("Using no ai grouping as commit_pipeline recieved no model!")
        logical_grouper = SingleGrouper()

    if new_commit_hash is None:
        logger.info("[red] Failed to backup working state, exiting. [/red]")
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
    )

    return pipeline
