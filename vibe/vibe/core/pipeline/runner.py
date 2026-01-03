from typing import List
from ..git_interface.interface import GitInterface
from ..diff_extractor.interface import DiffExtractorInterface
from ..chunker.interface import ChunkerInterface
from ..grouper.interface import GrouperInterface
from ..commiter.interface import CommitterInterface
from ..data.models import DiffChunk, ChunkGroup, CommitResult

class AIGitPipeline:
    def __init__(
        self,
        git: GitInterface,
        diff_extractor: DiffExtractorInterface,
        chunker: ChunkerInterface,
        grouper: GrouperInterface,
        committer: CommitterInterface
    ):
        self.git: GitInterface = git
        self.diff_extractor: DiffExtractorInterface = diff_extractor
        self.chunker: ChunkerInterface = chunker
        self.grouper: GrouperInterface = grouper
        self.committer: CommitterInterface = committer

    def run(self) -> List[CommitResult]:
        # Step 0: clean working area
        self.git.reset()

        # Step 1: extract diff
        raw_diff: List[DiffChunk] = self.diff_extractor.extract_diff(self.git)

        # Step 2: split into chunks
        chunks: List[DiffChunk] = self.chunker.chunk(raw_diff)

        # Step 3: group chunks
        grouped: List[ChunkGroup] = self.grouper.group_chunks(chunks)

        # Step 4: commit each group
        results: List[CommitResult] = []
        for group in grouped:
            commit_result = self.committer.create_commit(group, self.git)
            results.append(commit_result)
            print(f"Created commit {commit_result.commit_hash} for group {group.group_id}")

        return results
