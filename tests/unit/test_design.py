from __future__ import annotations

import pytest

from xprot.core.alignment import parse_alignment
from xprot.core.design import compare_with_fixture, generate_transformation
from xprot.core.errors import DesignError
from xprot.core.models import (
    CanonicalPartition,
    NodeSelector,
    SequenceWeight,
    TransformedResult,
)
from xprot.core.primitives import DesignMode
from xprot.core.profile import calculate_profiles, determine_typical_states
from xprot.core.tree import parse_tree, resolve_partition
from xprot.core.weights import calculate_henikoff_weights

# subfamily A = {r1, a2}, subfamily B = {d1, b2}
FASTA = ">r1\nMH-T\n>a2\nMHAT\n>d1\nMKGT\n>b2\nMKGT\n"
NEWICK = "((r1,a2),(d1,b2));"


def _setup(
    fasta: str = FASTA, newick: str = NEWICK
) -> tuple[object, tuple[SequenceWeight, ...], CanonicalPartition]:
    aln = parse_alignment(fasta, "fasta")
    weights = calculate_henikoff_weights(aln)
    tree = parse_tree(newick, "newick")
    part = resolve_partition(tree, NodeSelector(tips=frozenset(t.canonical_id for t in aln.rows)))
    return aln, weights, part


def _run(fasta: str, newick: str, **kw: object) -> TransformedResult:
    aln, weights, part = _setup(fasta, newick)
    table = kw.get("class_table")
    profiles = calculate_profiles(aln, part, weights, class_table=table)  # type: ignore[arg-type]
    typical = determine_typical_states(profiles, threshold=0.9)
    return generate_transformation(aln, part, profiles, typical, **kw)  # type: ignore[arg-type]


def test_literal_substitution_and_insertion() -> None:
    result = _run(FASTA, NEWICK, recipient="r1", donor="d1", mode=DesignMode.LITERAL)
    assert result.transformed_sequence == "MKGT"
    assert result.source_sequence == "MHT"
    tokens = [
        (e.alignment_column, e.event_type.value, e.source_state, e.transformed_state)
        for e in result.events
    ]
    assert tokens == [(2, "substitution", "H", "K"), (3, "insertion", "-", "G")]
    assert [e.ordinal for e in result.events] == [1, 2]
    assert result.events[0].source_position == 2
    assert result.events[1].insertion_anchor == 2
    assert (result.substitutions, result.insertions, result.deletions) == (1, 1, 0)


def test_expanded_mode_uses_class_and_picks_a_member() -> None:
    table = {"Basic": "HKR", "Acidic": "DE"}
    result = _run(
        ">r1\nD\n>a2\nD\n>d1\nK\n>b2\nK\n",
        "((r1,a2),(d1,b2));",
        recipient="r1",
        donor="d1",
        mode=DesignMode.EXPANDED,
        class_table=table,
    )
    assert result.transformed_sequence == "K"
    assert result.events[0].rule == "Basic"
    assert result.events[0].transformed_state == "K"


def test_no_event_where_subfamilies_agree() -> None:
    result = _run(
        ">r1\nMM\n>a2\nMM\n>d1\nMM\n>b2\nMM\n", "((r1,a2),(d1,b2));", recipient="r1", donor="d1"
    )
    assert result.events == ()
    assert result.transformed_sequence == "MM"


def test_recipient_and_donor_must_be_in_different_subfamilies() -> None:
    with pytest.raises(DesignError):
        _run(FASTA, NEWICK, recipient="r1", donor="a2")
    with pytest.raises(DesignError):
        _run(FASTA, NEWICK, recipient="r1", donor="ghost")


def test_compare_with_fixture_exact_and_near() -> None:
    result = _run(FASTA, NEWICK, recipient="r1", donor="d1")
    exact = compare_with_fixture(
        result,
        [(2, "substitution", "H", "K"), (3, "insertion", "-", "G")],
        expected_transformed="MKGT",
    )
    assert exact.exact_events and exact.exact_transformed and exact.reproduced
    assert exact.event_edit_distance == 0

    near = compare_with_fixture(result, [(2, "substitution", "H", "R"), (3, "insertion", "-", "G")])
    assert not near.exact_events
    assert near.exact_transformed is None
    assert not near.reproduced
    assert near.event_edit_distance == 1
    assert near.summary_deltas == (0, 0, 0)
