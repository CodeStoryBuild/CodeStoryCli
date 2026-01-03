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


from ..git_interface.interface import GitInterface


class GitFileReader:
    def __init__(self, git: GitInterface, base_commit: str, patched_commit: str):
        self.git = git
        self.base_commit = base_commit
        self.patched_commit = patched_commit

    def read(self, path: str, old_content: bool = False) -> str | None:
        """
        Returns the file content from the specified commit using git cat-file.
        version: 'old' for base_commit, 'new' for patched_commit (HEAD by default)
        """
        commit = self.base_commit if old_content else self.patched_commit
        # Use git cat-file to get file content
        # rel_path should be in posix format for git
        rel_path_git = path.replace("\\", "/").strip()
        obj = f"{commit}:{rel_path_git}"
        return self.git.run_git_text_out(["cat-file", "-p", obj])
