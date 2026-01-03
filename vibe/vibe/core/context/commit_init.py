from importlib.resources import files

import inquirer
from rich.console import Console


from vibe.core.file_reader.file_parser import FileParser
from vibe.core.branch_saver.branch_saver import BranchSaver
from vibe.core.synthesizer.git_synthesizer import GitSynthesizer
from vibe.core.commands.git_commands import GitCommands
from vibe.core.semantic_grouper.semantic_grouper import SemanticGrouper
from vibe.core.semantic_grouper.query_manager import QueryManager
from vibe.core.pipeline.runner import AIGitPipeline
from vibe.core.git_interface.SubprocessGitInterface import SubprocessGitInterface
from vibe.core.chunker.atomic_chunker import AtomicChunker
from vibe.core.grouper.single_grouper import SingleGrouper
from vibe.core.file_reader.git_file_reader import GitFileReader


def verify_repo(commands: GitCommands, console: Console, target: str) -> bool:
    # Step -1: ensure we're inside a git repository
    if not commands.is_git_repo():
        raise RuntimeError(
            "Not a git repository (or any of the parent directories). Please run this command inside a Git repo."
        )

    # Step 0: clean working area
    if commands.need_reset():
        unstage = inquirer.confirm(
            "Staged changes detected, you must unstage all changes. Do you accept?",
            default=False,
        )

        if unstage:
            commands.reset()
        else:
            console.print(
                "[yellow]Cannot proceed without unstaging changes, exiting.[/yellow]"
            )
            return False

    if commands.need_track_untracked(target):
        console.print(
            f'Untracked files detected within "{target}", temporarily staging changes',
        )

        commands.track_untracked(target)

    return True


def createPipeline(repo_path: str, target: str, console: Console):
    git_interface = SubprocessGitInterface(repo_path)
    commands = GitCommands(git_interface)

    chunker = AtomicChunker()
    logical_grouper = SingleGrouper()

    branch_saver = BranchSaver(git_interface)

    # first, we need to turn the verify the repo is in a certain state
    console.print("[green] Verifying Repo State... [/green]")
    if not verify_repo(commands, console, target):
        # cannot proceed
        return None

    console.print("[green] Creating backup of working state... [/green]")
    # next we create our base/new commits + backup branch for later
    base_branch, base_commit_hash, new_branch, new_commit_hash = (
        branch_saver.save_working_state()
    )

    if new_commit_hash is None:
        console.print("[red] Failed to backup working state, exiting. [/red]")
        return None

    file_reader = GitFileReader(git_interface, base_commit_hash, new_commit_hash)
    file_parser = FileParser()

    config_path = files("vibe") / "resources" / "language_config.json"
    query_manager = QueryManager(config_path)

    semantic_grouper = SemanticGrouper(file_parser, file_reader, query_manager)

    synthesizer = GitSynthesizer(git_interface)

    pipeline = AIGitPipeline(
        git_interface,
        console,
        commands,
        chunker,
        semantic_grouper,
        logical_grouper,
        synthesizer,
        branch_saver,
        base_branch,
        new_branch,
        base_commit_hash,
        new_commit_hash,
    )

    return pipeline
