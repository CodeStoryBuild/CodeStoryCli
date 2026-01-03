from importlib.resources import files

from rich.console import Console

from langchain_google_genai import ChatGoogleGenerativeAI

from vibe.core.file_reader.file_parser import FileParser
from vibe.core.synthesizer.git_synthesizer import GitSynthesizer
from vibe.core.commands.git_commands import GitCommands
from vibe.core.semantic_grouper.semantic_grouper import SemanticGrouper
from vibe.core.semantic_grouper.query_manager import QueryManager
from vibe.core.pipeline.runner import AIGitPipeline
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.chunker.atomic_chunker import AtomicChunker
from vibe.core.grouper.langchain_grouper import LangChainGrouper
from vibe.core.grouper.single_grouper import SingleGrouper
from vibe.core.file_reader.git_file_reader import GitFileReader


def create_expand_pipeline(
    repo_path: str,
    base_commit_hash: str,
    new_commit_hash: str,
    console: Console,
):
    """
    Create an AIGitPipeline configured to operate on an arbitrary commit range
    inside a temporary worktree, without touching the user's working branch.

    The diff is computed between base_commit_hash and new_commit_hash.
    """

    git_interface = SubprocessGitInterface(repo_path)
    commands = GitCommands(git_interface)

    chunker = AtomicChunker()
    # logical_grouper = SingleGrouper()
    logical_grouper = LangChainGrouper(ChatGoogleGenerativeAI(model="gemini-2.5-flash"))

    # For expand, we don't take a working backup; synthesizer writes to the current
    # checked-out temp branch within the worktree.
    synthesizer = GitSynthesizer(git_interface)

    file_reader = GitFileReader(git_interface, base_commit_hash, new_commit_hash)
    file_parser = FileParser()

    config_path = files("vibe") / "resources" / "language_config.json"
    query_manager = QueryManager(config_path)

    semantic_grouper = SemanticGrouper()

    # Determine branch names in the worktree via Git directly, but pass placeholders;
    # they are used only for logging in the pipeline.
    original_branch = "vibe-expand-tmp"
    new_branch = original_branch

    pipeline = AIGitPipeline(
        git_interface,
        console,
        commands,
        chunker,
        semantic_grouper,
        logical_grouper,
        synthesizer,
        branch_saver=None,  # not used in expand flows
        file_reader=file_reader,
        file_parser=file_parser,
        query_manager=query_manager,
        original_branch=original_branch,
        new_branch=new_branch,
        base_commit_hash=base_commit_hash,
        new_commit_hash=new_commit_hash,
    )

    return pipeline
