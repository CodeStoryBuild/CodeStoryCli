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
