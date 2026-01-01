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

from codestory.core.diff.data.atomic_container import AtomicContainer
from codestory.core.logging.utils import describe_container


def describe_rejected_changes(rejected: list[AtomicContainer], custom_reason: str):
    from loguru import logger

    logger.info(f"Rejected {len(rejected)} changes due to {custom_reason}")

    logger.info("---------- affected changes ----------")
    for chunk in rejected:
        logger.info(describe_container(chunk))
    logger.info("These changes will not be commited\n")
