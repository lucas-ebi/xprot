from __future__ import annotations

import pytest

from xprot.core.alignment import parse_alignment
from xprot.core.design import compare_with_fixture, generate_transformation
from xprot.core.errors import DesignError
from xprot.core.models import (
    Alignment,
    AlignmentRow,
    CanonicalPartition,
    CoordinateMap,
    ProfileSet,
    ResidueProfile,
    SequenceWeight,
    TransformedResult,
    TypicalState,
    TypicalStateSet,
)
from xprot.core.primitives import DesignMode, SubfamilyLabel
from xprot.core.profile import calculate_profiles, determine_typical_states
from xprot.core.tree import parse_tree, resolve_partition
from xprot.core.weights import calculate_henikoff_weights

# subfamily A = {r1, a2}, subfamily B = {d1, b2}
FASTA = ">r1\nMH-T\n>a2\nMHAT\n>d1\nMKGT\n>b2\nMKGT\n"
NEWICK = "((r1,a2),(d1,b2));"


def _setup(
    fasta: str, newick: str, recipient: str, donor: str
) -> tuple[Alignment, tuple[SequenceWeight, ...], CanonicalPartition]:
    aln = parse_alignment(fasta, "fasta")
    weights = calculate_henikoff_weights(aln)
    tree = parse_tree(newick, "newick")
    part = resolve_partition(tree, recipient, donor)
    return aln, weights, part


def _run(
    fasta: str,
    newick: str,
    *,
    recipient: str,
    donor: str,
    typical_gap: bool = False,
    **kw: object,
) -> TransformedResult:
    aln, weights, part = _setup(fasta, newick, recipient, donor)
    table = kw.get("class_table")
    profiles = calculate_profiles(aln, part, weights, class_table=table)  # type: ignore[arg-type]
    typical = determine_typical_states(profiles, threshold=0.9, typical_gap=typical_gap)
    return generate_transformation(
        aln,
        part,
        profiles,
        typical,
        recipient=recipient,
        donor=donor,
        **kw,  # type: ignore[arg-type]
    )


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


def test_literal_deletion_when_donor_is_typically_gapped() -> None:
    # Donor clade (d1, b2) is gapped at column 2; recipient clade (r1, a2) is not.
    fasta = ">r1\nMK\n>a2\nMK\n>d1\nM-\n>b2\nM-\n"
    newick = "((r1,a2),(d1,b2));"

    skipped = _run(fasta, newick, recipient="r1", donor="d1", typical_gap=True, deletions=False)
    assert skipped.events == ()
    assert skipped.transformed_sequence == "MK"
    assert (skipped.substitutions, skipped.insertions, skipped.deletions) == (0, 0, 0)
    assert any(d.code == "DESIGN_DELETION_SKIPPED" for d in skipped.diagnostics)

    result = _run(fasta, newick, recipient="r1", donor="d1", typical_gap=True, deletions=True)
    assert result.transformed_sequence == "M"
    tokens = [
        (e.alignment_column, e.event_type.value, e.source_state, e.transformed_state)
        for e in result.events
    ]
    assert tokens == [(2, "deletion", "K", "-")]
    assert result.events[0].source_position == 2
    assert result.events[0].transformed_position is None
    assert (result.substitutions, result.insertions, result.deletions) == (0, 0, 1)


def test_literal_uses_donor_typical_state_regardless_of_recipient_typicality() -> None:
    # Both subfamilies' weighted profiles are "typical" for K at column 1, but the recipient
    # representative itself carries a different residue (R) there -- an outlier relative to its
    # own subfamily's consensus. The donor side is deliberately profile-only: no donor alignment
    # row is ever read, only its clade's typical states, so a minimal ProfileSet/TypicalStateSet
    # is enough without going through calculate_profiles/determine_typical_states.
    row = AlignmentRow(
        canonical_id="r1",
        raw_header="r1",
        aligned="R",
        coordinate_map=CoordinateMap.from_aligned("R", frozenset({"-"})),
        source_ordinal=0,
    )
    alignment = Alignment(rows=(row,), alphabet="ACDEFGHIKLMNPQRSTVWY", gap="-")
    partition = CanonicalPartition(
        selected_tips=("r1", "d1"),
        subfamily_a_tips=("r1",),
        subfamily_b_tips=("d1",),
    )
    profiles = ProfileSet(
        residues=(
            ResidueProfile(
                column=1,
                subfamily=SubfamilyLabel.B,
                frequencies={"K": 1.0},
                denominator=1.0,
                occupancy=1.0,
            ),
        ),
        classes=(),
        included_columns=frozenset({1}),
    )
    typical_states = TypicalStateSet(
        states=(
            TypicalState(1, SubfamilyLabel.A, "K", False, 0.95),
            TypicalState(1, SubfamilyLabel.B, "K", False, 0.95),
        )
    )

    result = generate_transformation(
        alignment, partition, profiles, typical_states, recipient="r1", donor="d1"
    )

    assert result.transformed_sequence == "K"
    tokens = [
        (e.alignment_column, e.event_type.value, e.source_state, e.transformed_state)
        for e in result.events
    ]
    assert tokens == [(1, "substitution", "R", "K")]


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
    # generate_transformation must reject a partition where recipient and donor share a
    # subfamily, independent of how the partition was built. resolve_partition always places
    # recipient and donor in different subfamilies (each is under a different child of their own
    # MRCA -- see test_tree.py), so this partition is constructed by hand to exercise the guard.
    aln, weights, _ = _setup(FASTA, NEWICK, recipient="r1", donor="d1")
    degenerate = CanonicalPartition(
        selected_tips=("a2", "b2", "d1", "r1"),
        subfamily_a_tips=("a2", "r1"),
        subfamily_b_tips=("b2", "d1"),
    )
    profiles = calculate_profiles(aln, degenerate, weights)
    typical = determine_typical_states(profiles, threshold=0.9)
    with pytest.raises(DesignError):
        generate_transformation(aln, degenerate, profiles, typical, recipient="r1", donor="a2")


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
