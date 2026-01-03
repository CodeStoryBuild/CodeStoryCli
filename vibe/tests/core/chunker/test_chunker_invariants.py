import pytest
from vibe.core.chunker.interface import ChunkerInterface
from vibe.core.data.s_diff_chunk import StandardDiffChunk
from vibe.core.data.c_diff_chunk import CompositeDiffChunk
from vibe.core.data.models import Addition, Removal
from vibe.core.checks.chunk_checks import chunks_disjoint as check_disjoint
import importlib


# Helper: flatten parsed_content to (type, line_number, content) tuples
def flatten_chunk(chunk):
    """Flatten a chunk (including CompositeDiffChunk) to tuples."""
    if isinstance(chunk, CompositeDiffChunk):
        result = []
        for sub_chunk in chunk.chunks:
            result.extend(flatten_chunk(sub_chunk))
        return result
    elif isinstance(chunk, StandardDiffChunk):
        return [
            (type(item).__name__, item.line_number, item.content)
            for item in chunk.parsed_content
        ]
    return []


def chunks_disjoint(chunks):
    """Check that chunks are disjoint using official checker."""
    standard_chunks = []
    for chunk in chunks:
        if isinstance(chunk, StandardDiffChunk):
            standard_chunks.append(chunk)
        elif isinstance(chunk, CompositeDiffChunk):
            standard_chunks.extend(chunk.chunks)
    return check_disjoint(standard_chunks)


def chunks_reconstruct_input(chunks, original):
    # Flatten all output chunks
    out_items = []
    for chunk in chunks:
        out_items.extend(flatten_chunk(chunk))
    # Flatten original
    orig_items = flatten_chunk(original)
    # Compare as multisets (order and content must match)
    return sorted(out_items) == sorted(orig_items)


CHUNKERS = [
    (
        "vibe.core.chunker.predicate_chunker.PredicateChunker",
        {"split_predicate": lambda x: x.strip() == ""},
    ),
    ("vibe.core.chunker.max_line_chunker.MaxLineChunker", {"max_chunks": 3}),
]


def run_chunker_invariants(chunker, orig):
    out_chunks = chunker.chunk([orig])
    assert chunks_reconstruct_input(
        out_chunks, orig
    ), "Output chunks do not reconstruct input"
    assert chunks_disjoint(out_chunks), "Output chunks are not pairwise disjoint"


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_chunker_invariants_overlap(chunker_cls, chunker_kwargs):
    # Additions and removals overlap (same line numbers)
    mod_name, cls_name = chunker_cls.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    Chunker = getattr(mod, cls_name)
    chunker = Chunker(**chunker_kwargs)
    orig = StandardDiffChunk(
        _file_path="foo.py",
        parsed_content=[
            Addition(content="a", line_number=1),
            Removal(content="b", line_number=1),
            Addition(content="c", line_number=2),
            Removal(content="d", line_number=2),
        ],
        old_start=1,
        new_start=1,
    )
    run_chunker_invariants(chunker, orig)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_chunker_invariants_pure_additions(chunker_cls, chunker_kwargs):
    # Only additions
    mod_name, cls_name = chunker_cls.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    Chunker = getattr(mod, cls_name)
    chunker = Chunker(**chunker_kwargs)
    orig = StandardDiffChunk(
        _file_path="foo.py",
        parsed_content=[
            Addition(content="a", line_number=1),
            Addition(content="b", line_number=2),
            Addition(content="c", line_number=3),
        ],
        old_start=0,
        new_start=1,
    )
    run_chunker_invariants(chunker, orig)


@pytest.mark.parametrize("chunker_cls,chunker_kwargs", CHUNKERS)
def test_chunker_invariants_pure_removals(chunker_cls, chunker_kwargs):
    # Only removals
    mod_name, cls_name = chunker_cls.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    Chunker = getattr(mod, cls_name)
    chunker = Chunker(**chunker_kwargs)
    orig = StandardDiffChunk(
        _file_path="foo.py",
        parsed_content=[
            Removal(content="a", line_number=10),
            Removal(content="b", line_number=11),
            Removal(content="c", line_number=12),
        ],
        old_start=10,
        new_start=0,
    )
    run_chunker_invariants(chunker, orig)
