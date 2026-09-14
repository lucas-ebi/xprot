from __future__ import annotations

import pytest

from xprot.core.alignment import parse_alignment
from xprot.core.errors import AlignmentError
from xprot.core.models import Alignment
from xprot.core.weights import calculate_henikoff_weights


def _weights(fasta: str) -> dict[str, float]:
    aln = parse_alignment(fasta, "fasta")
    return {w.canonical_id: w.normalized for w in calculate_henikoff_weights(aln)}


def test_two_rows_one_variable_column() -> None:
    # col1: one state A (r=1) -> 1/2 each; col2: A,C (r=2) -> 1/2 each; per row 1/2 after /L.
    w = _weights(">s1\nAA\n>s2\nAC\n")
    assert w == pytest.approx({"s1": 0.5, "s2": 0.5})
    assert sum(w.values()) == pytest.approx(1.0)


def test_gap_is_a_state() -> None:
    w = _weights(">s1\nA-\n>s2\nC-\n")
    assert w == pytest.approx({"s1": 0.5, "s2": 0.5})
    w2 = _weights(">s1\nAA\n>s2\nA-\n")
    assert w2 == pytest.approx({"s1": 0.5, "s2": 0.5})


def test_weights_sum_to_one() -> None:
    w = _weights(">s1\nAAC\n>s2\nAAG\n>s3\nATG\n")
    assert sum(w.values()) == pytest.approx(1.0)
    # s1 and s3 are symmetric, s2 differs
    assert w["s1"] == pytest.approx(w["s3"])
    assert w["s2"] != pytest.approx(w["s1"])


def test_row_order_invariant() -> None:
    forward = _weights(">s1\nAAC\n>s2\nAAG\n>s3\nATG\n")
    reordered = _weights(">s3\nATG\n>s1\nAAC\n>s2\nAAG\n")
    assert forward == pytest.approx(reordered)


def test_empty_alignment_is_rejected() -> None:
    with pytest.raises(AlignmentError):
        calculate_henikoff_weights(Alignment(rows=(), alphabet="ACDEFGHIKLMNPQRSTVWY"))


def test_redundant_sequences_are_downweighted() -> None:
    # s1 and s2 identical, s3 distinct: the pair should carry less individual weight than s3.
    w = _weights(">s1\nAAAA\n>s2\nAAAA\n>s3\nCCCC\n")
    assert w["s1"] == pytest.approx(w["s2"])
    assert w["s1"] < w["s3"]
    assert sum(w.values()) == pytest.approx(1.0)
