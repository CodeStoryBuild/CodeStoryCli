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

"""Tests for Signature.is_empty() and ContainerSignature.has_valid_sig()."""

from codestory.core.semantic_analysis.annotation.chunk_lableler import (
    ContainerSignature,
    Signature,
    TypedFQN,
)
from collections import Counter

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


def make_signature(
    new_structural_scopes=None,
    old_structural_scopes=None,
    new_fqns=None,
    old_fqns=None,
    def_new_symbols=None,
    def_old_symbols=None,
    extern_new_symbols=None,
    extern_old_symbols=None,
    def_new_symbols_filtered=None,
    def_old_symbols_filtered=None,
    extern_new_symbols_filtered=None,
    extern_old_symbols_filtered=None,
    new_comments=None,
    old_comments=None,
) -> Signature:
    """Helper to create a Signature with defaults."""
    return Signature(
        file_names={"test.py"},
        commit_hashes={"base", "new"},
        languages={"python"},
        new_structural_scopes=new_structural_scopes or set(),
        old_structural_scopes=old_structural_scopes or set(),
        new_fqns=Counter(new_fqns) if new_fqns else Counter(),
        old_fqns=Counter(old_fqns) if old_fqns else Counter(),
        def_new_symbols=Counter(def_new_symbols) if def_new_symbols else Counter(),
        def_old_symbols=Counter(def_old_symbols) if def_old_symbols else Counter(),
        extern_new_symbols=Counter(extern_new_symbols)
        if extern_new_symbols
        else Counter(),
        extern_old_symbols=Counter(extern_old_symbols)
        if extern_old_symbols
        else Counter(),
        def_new_symbols_filtered=Counter(def_new_symbols_filtered)
        if def_new_symbols_filtered
        else Counter(),
        def_old_symbols_filtered=Counter(def_old_symbols_filtered)
        if def_old_symbols_filtered
        else Counter(),
        extern_new_symbols_filtered=Counter(extern_new_symbols_filtered)
        if extern_new_symbols_filtered
        else Counter(),
        extern_old_symbols_filtered=Counter(extern_old_symbols_filtered)
        if extern_old_symbols_filtered
        else Counter(),
        new_comments=Counter(new_comments) if new_comments else Counter(),
        old_comments=Counter(old_comments) if old_comments else Counter(),
    )


# -----------------------------------------------------------------------------
# Signature.is_empty() Tests
# -----------------------------------------------------------------------------


class TestSignatureIsEmpty:
    """Tests for Signature.is_empty() method."""

    def test_empty_signature_is_empty(self):
        """A signature with no differences should be empty."""
        sig = make_signature()
        assert sig.is_empty() is True

    def test_same_values_both_sides_is_empty(self):
        """Signature with identical values on both sides should be empty."""
        sig = make_signature(
            new_structural_scopes={"ClassA"},
            old_structural_scopes={"ClassA"},
            new_fqns={TypedFQN("test.py:ClassA", "class")},
            old_fqns={TypedFQN("test.py:ClassA", "class")},
            def_new_symbols={"foo"},
            def_old_symbols={"foo"},
            extern_new_symbols={"bar"},
            extern_old_symbols={"bar"},
            new_comments={"# comment"},
            old_comments={"# comment"},
        )
        assert sig.is_empty() is True

    def test_different_fqns_not_empty(self):
        """Signature with different FQNs is not empty."""
        sig = make_signature(
            new_fqns={TypedFQN("test.py:ClassA.method_new", "function")},
            old_fqns={TypedFQN("test.py:ClassA.method_old", "function")},
        )
        assert sig.is_empty() is False

    def test_different_def_symbols_not_empty(self):
        """Signature with different defined symbols is not empty."""
        sig = make_signature(
            def_new_symbols={"foo", "bar"},
            def_old_symbols={"foo"},
        )
        assert sig.is_empty() is False

    def test_different_extern_symbols_not_empty(self):
        """Signature with different external symbols is not empty."""
        sig = make_signature(
            extern_new_symbols={"external_func"},
            extern_old_symbols=set(),
        )
        assert sig.is_empty() is False

    def test_different_comments_not_empty(self):
        """Signature with different comments is not empty (comment-only change)."""
        sig = make_signature(
            new_comments={"# new comment"},
            old_comments={"# old comment"},
        )
        assert sig.is_empty() is False

    def test_added_comment_not_empty(self):
        """Adding a comment makes signature not empty."""
        sig = make_signature(
            new_comments={"# added comment"},
            old_comments=set(),
        )
        assert sig.is_empty() is False

    def test_removed_comment_not_empty(self):
        """Removing a comment makes signature not empty."""
        sig = make_signature(
            new_comments=set(),
            old_comments={"# removed comment"},
        )
        assert sig.is_empty() is False

    def test_whitespace_only_change_is_empty(self):
        """
        A whitespace-only change should result in an empty signature.

        When only whitespace is changed, all semantic content (symbols, scopes,
        FQNs, comments) stays the same, so is_empty() returns True.
        """
        # Simulating a whitespace change inside ClassA
        sig = make_signature(
            new_structural_scopes={"ClassA"},
            old_structural_scopes={"ClassA"},
            new_fqns={TypedFQN("test.py:ClassA", "class")},
            old_fqns={TypedFQN("test.py:ClassA", "class")},
            def_new_symbols={"x"},
            def_old_symbols={"x"},
        )
        assert sig.is_empty() is True

    def test_duplicate_symbols_change_is_not_empty(self):
        """
        Duplicate symbols change (e.g., removing one occurrence) should not be empty.
        """
        sig = make_signature(
            def_new_symbols={"foo": 2},
            def_old_symbols={"foo": 1},
        )
        assert sig.is_empty() is False

    def test_duplicate_symbols_same_both_sides_is_empty(self):
        """
        Duplicate symbols that are same on both sides should be empty.
        """
        sig = make_signature(
            def_new_symbols={"foo": 2},
            def_old_symbols={"foo": 2},
        )
        assert sig.is_empty() is True


# -----------------------------------------------------------------------------
# ContainerSignature.has_valid_sig() Tests
# -----------------------------------------------------------------------------


class TestContainerSignatureHasValidSig:
    """Tests for ContainerSignature.has_valid_sig() method."""

    def test_none_signature_not_valid(self):
        """ContainerSignature with None total_signature is not valid."""
        container_sig = ContainerSignature(
            total_signature=None,
            signatures=[None],
        )
        assert container_sig.has_valid_sig() is False

    def test_valid_signature_is_valid(self):
        """ContainerSignature with non-None total_signature is valid."""
        sig = make_signature(def_new_symbols={"foo"})
        container_sig = ContainerSignature(
            total_signature=sig,
            signatures=[sig],
        )
        assert container_sig.has_valid_sig() is True

    def test_empty_signature_is_still_valid(self):
        """
        ContainerSignature with empty Signature is still valid.

        has_valid_sig() only checks for None. The is_empty() check
        is done separately in SemanticGrouper.
        """
        sig = make_signature()  # Empty signature
        container_sig = ContainerSignature(
            total_signature=sig,
            signatures=[sig],
        )
        assert container_sig.has_valid_sig() is True
        assert sig.is_empty() is True


# -----------------------------------------------------------------------------
# Signature.from_signatures() Tests
# -----------------------------------------------------------------------------


class TestSignatureFromSignatures:
    """Tests for Signature.from_signatures() method."""

    def test_empty_list_returns_empty_signature(self):
        """from_signatures with empty list returns empty signature."""
        result = Signature.from_signatures([])
        assert result.is_empty() is True
        assert len(result.new_comments) == 0
        assert len(result.old_comments) == 0

    def test_merges_comments(self):
        """from_signatures correctly merges comments from multiple signatures."""
        sig1 = make_signature(
            new_comments={"# comment 1"},
            old_comments={"# old 1"},
        )
        sig2 = make_signature(
            new_comments={"# comment 2"},
            old_comments={"# old 2"},
        )

        result = Signature.from_signatures([sig1, sig2])

        assert result.new_comments == Counter({"# comment 1", "# comment 2"})
        assert result.old_comments == Counter({"# old 1", "# old 2"})

    def test_merges_all_fields(self):
        """from_signatures correctly merges all signature fields."""
        sig1 = make_signature(
            new_structural_scopes={"ClassA"},
            def_new_symbols={"foo"},
            new_comments={"# c1"},
        )
        sig2 = make_signature(
            new_structural_scopes={"ClassB"},
            def_new_symbols={"bar"},
            new_comments={"# c2"},
        )

        result = Signature.from_signatures([sig1, sig2])

        assert result.new_structural_scopes == {"ClassA", "ClassB"}
        assert result.def_new_symbols == Counter({"foo", "bar"})
        assert result.new_comments == Counter({"# c1", "# c2"})

    def test_handles_none_in_list(self):
        """from_signatures handles None values in the list."""
        sig1 = make_signature(def_new_symbols={"foo"})

        result = Signature.from_signatures([sig1, None])

        assert result.def_new_symbols == Counter({"foo"})
