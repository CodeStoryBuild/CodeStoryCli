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
from codestory.core.diff.pipeline.filter import Filter
from codestory.core.embeddings.embedder import Embedder
from codestory.core.logging.progress_manager import ProgressBarManager
from codestory.core.semantic_analysis.summarization.chunk_summarizer import (
    ContainerSummarizer,
)


def cosine_similarity(a, b):
    import numpy as np

    # Calculate the dot product
    dot_product = np.dot(a, b)

    # Calculate the magnitude (norm) of each vector
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # Apply the formula
    return dot_product / (norm_a * norm_b)


class RelevanceFilter(Filter):
    def __init__(
        self,
        container_summarizer: ContainerSummarizer,
        embedder: Embedder,
        user_intent: str,
        similarify_threshold: float = 0.75,
    ):
        self.container_summarizer = container_summarizer
        self.embedder = embedder
        self.user_intent = user_intent
        self.similarity_threshold = similarify_threshold

    def filter(
        self,
        containers: list[AtomicContainer],
    ) -> tuple[list[AtomicContainer], list[AtomicContainer]]:
        if not containers:
            return [], []

        summaries = self.container_summarizer.summarize_containers(
            containers, self.user_intent
        )

        intent_vector = self.embedder.embed([self.user_intent])[0]
        vectors = self.embedder.embed(summaries)

        # filter by similarify to intent

        relevant_containers: list[AtomicContainer] = []
        irrelevant_containers: list[AtomicContainer] = []

        pbar = ProgressBarManager.get_pbar()
        if pbar is not None:
            pbar.set_postfix({"phase": f"filtering relevance 0/{len(containers)}"})

        for i, (container, vector) in enumerate(zip(containers, vectors, strict=False)):
            if pbar is not None:
                pbar.set_postfix(
                    {
                        "phase": f"filtering relevance {i + 1}/{len(containers)}",
                    }
                )
            similarity = cosine_similarity(vector, intent_vector)

            if similarity >= self.similarity_threshold:
                relevant_containers.append(container)
            else:
                irrelevant_containers.append(container)

        return relevant_containers, irrelevant_containers
