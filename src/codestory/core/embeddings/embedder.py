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

from importlib.resources import files

from fastembed import TextEmbedding


class Embedder:
    def __init__(self):
        cache_dir = files("codestory").joinpath("resources/embedding_models")
        # load already downloaded model from cache dir
        self.embedding_model = TextEmbedding(
            "BAAI/bge-small-en-v1.5", cache_dir=str(cache_dir), local_files_only=True
        )

    def embed(self, documents: list[str]):
        return list(self.embedding_model.embed(documents))  # Generator
