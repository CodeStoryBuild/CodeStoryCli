# -----------------------------------------------------------------------------
# /*
#  * Copyright (C) 2025 CodeStory
#  *
#  * This program is free software; you can redistribute it and/or modify
#  * it under the terms of the GNU General Public License as published by
#  * the Free Software Foundation; Version 2.
#  *
#  * This program is distributed in the hope that it will be useful,
#  * but WITHOUT ANY WARRANTY; without even the implied warranty of
#  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  * GNU General Public License for more details.
#  *
#  * You should have received a copy of the GNU General Public License
#  * along with this program; if not, you can contact us at support@codestory.build
#  */
# -----------------------------------------------------------------------------

import contextlib
from time import perf_counter

from codestory.core.diff.data.atomic_container import AtomicContainer


@contextlib.contextmanager
def time_block(block_name: str):
    """A context manager to time the execution of a code block and log the result."""
    from loguru import logger

    logger.debug(f"Starting {block_name}")
    start_time = perf_counter()

    try:
        yield
    finally:
        end_time = perf_counter()
        duration_ms = int((end_time - start_time) * 1000)

        logger.debug(
            f"Finished {block_name}. Timing(ms)={duration_ms}",
        )


def log_changes(process_step: str, containers: list[AtomicContainer]):
    from loguru import logger

    num_changes = 0
    unique_files = set()
    for container in containers:
        unique_files.update(container.canonical_paths())
        num_changes += len(container.get_atomic_chunks())

    logger.debug(
        "{process_step}: chunks={count} files={files}",
        process_step=process_step,
        count=num_changes,
        files=len(unique_files),
    )


def grammar(path, num):
    if num == 1:
        return f"A change in {path}"
    else:
        return f"{num} changes in {path}"


def describe_container(data: AtomicContainer) -> str:
    files: dict[bytes, int] = {}
    for chunk in data.get_atomic_chunks():
        path = chunk.canonical_path()
        files[path] = files.get(path, 0) + 1

    return "\n".join([grammar(path, num) for path, num in files.items()])
