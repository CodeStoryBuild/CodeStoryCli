# -----------------------------------------------------------------------------
# dslate - Dual Licensed Software
# Copyright (c) 2025 Adem Can
#
# This file is part of codestory.
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


from typing import Protocol


class FileReader(Protocol):
    """An interface for reading file content."""

    def read(self, path: str, old_content: bool = False) -> str | None:
        """
        Reads the content of a file.

        Args:
            path: The canonical path to the file.
            old_content: If True, read the 'before' version of the file.
                         If False, read the 'after' version.

        Returns:
            The file content as a string, or None if it doesn't exist
            (e.g., reading the 'old' version of a newly added file).
        """
        ...
