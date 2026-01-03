import contextlib
from time import perf_counter

from loguru import logger

from ..data.chunk import Chunk
from ..data.immutable_chunk import ImmutableChunk


@contextlib.contextmanager
def time_block(block_name: str):
    """
    A context manager to time the execution of a code block and log the result.
    """

    logger.debug(f"Starting {block_name}")
    start_time = perf_counter()

    try:
        yield
    finally:
        end_time = perf_counter()
        duration_ms = int((end_time - start_time) * 1000)

        logger.info(
            f"Finished {block_name}. Timing(ms)={duration_ms}",
        )


def log_chunks(
    process_step: str, chunks: list[Chunk], immut_chunks: list[ImmutableChunk]
):
    unique_files = {
        (path.decode("utf-8", errors="replace") if isinstance(path, bytes) else path)
        for c in chunks
        for path in c.canonical_paths()
    }

    for immut_chunk in immut_chunks:
        unique_files.add(immut_chunk.canonical_path)

    logger.info(
        "{process_step}: chunks={count} files={files}",
        process_step=process_step,
        count=len(chunks) + len(immut_chunks),
        files=len(unique_files),
    )
