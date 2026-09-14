from __future__ import annotations

from typing import Any

import pytest

from xprot.core.alignment import parse_alignment
from xprot.core.primitives import Denominator, PartitionSemantics, SubfamilyLabel
from xprot.core.profile import calculate_profiles, determine_typical_states
from xprot.core.structures import CanonicalPartition, ProfileSet, ResidueProfile
from xprot.core.weights import calculate_henikoff_weights


def _profiles(fasta: str, a: tuple[str, ...], b: tuple[str, ...], **kw: Any) -> ProfileSet:
    aln = parse_alignment(fasta, "fasta")
    weights = calculate_henikoff_weights(aln)
    part = CanonicalPartition(
        selected_tips=tuple(sorted((*a, *b))),
        subfamily_a_tips=a,
        subfamily_b_tips=b,
        semantics=PartitionSemantics.TWO_CHILD_CLADES,
    )
    return calculate_profiles(aln, part, weights, **kw)


def test_all_subfamily_denominator_conserved_column() -> None:
    ps = _profiles(">s1\nAK\n>s2\nAK\n>s3\nDR\n", ("s1", "s2"), ("s3",))
    a_col1 = ps.residue_profile(1, SubfamilyLabel.A)
    assert a_col1 is not None
    assert a_col1.frequencies == pytest.approx({"A": 1.0})
    b_col1 = ps.residue_profile(1, SubfamilyLabel.B)
    assert b_col1 is not None
    assert b_col1.frequencies == pytest.approx({"D": 1.0})


def test_zero_denominator_gives_a_diagnostic_not_nan() -> None:
    # subfamily A is all-gap at column 2 -> non_gap denominator is zero there.
    ps = _profiles(
        ">s1\nA-\n>s2\nC-\n>s3\nGK\n",
        ("s1", "s2"),
        ("s3",),
        denominator=Denominator.NON_GAP_WEIGHTS,
    )
    assert any(d.code == "PROFILE_ZERO_DENOMINATOR" and d.columns == (2,) for d in ps.diagnostics)
    assert ps.residue_profile(2, SubfamilyLabel.A) is None  # column skipped for A, not NaN


def test_occupancy_threshold_filters_columns() -> None:
    # column 2 non-gap fraction = 1/4 -> excluded at threshold 0.5, kept at 0.25
    fasta = ">s1\nAA\n>s2\nA-\n>s3\nA-\n>s4\nA-\n"
    strict = _profiles(fasta, ("s1", "s2"), ("s3", "s4"), occupancy_threshold=0.5)
    assert strict.included_columns == frozenset({1})
    loose = _profiles(fasta, ("s1", "s2"), ("s3", "s4"), occupancy_threshold=0.25)
    assert loose.included_columns == frozenset({1, 2})


def _profile_set(frequency: float) -> ProfileSet:
    return ProfileSet(
        residues=(
            ResidueProfile(
                column=1,
                subfamily=SubfamilyLabel.A,
                frequencies={"A": frequency, "C": 1.0 - frequency},
                denominator=1.0,
                occupancy=1.0,
            ),
        ),
        classes=(),
        included_columns=frozenset({1}),
    )


@pytest.mark.parametrize(
    ("frequency", "expected_typical"),
    [(0.89, False), (0.9, False), (0.9 + 1e-9, True), (0.95, True)],
)
def test_typicality_is_strictly_greater_than_threshold(
    frequency: float, expected_typical: bool
) -> None:
    typical = determine_typical_states(_profile_set(frequency), threshold=0.9)
    assert ("A" in typical.for_column(1, SubfamilyLabel.A)) is expected_typical


def test_fully_conserved_column_is_typical_end_to_end() -> None:
    ps = _profiles(">s1\nA\n>s2\nA\n>s3\nD\n", ("s1", "s2"), ("s3",))
    typical = determine_typical_states(ps, threshold=0.9)
    assert "A" in typical.for_column(1, SubfamilyLabel.A)


def test_gap_typicality_is_gated() -> None:
    # column 1: gap x3, A x1; column 2 all-distinct so the gap rows keep enough weight.
    fasta = ">s1\n-A\n>s2\n-C\n>s3\n-G\n>s4\nAT\n"
    ps = _profiles(fasta, ("s1", "s2", "s3", "s4"), ())
    without = determine_typical_states(ps, threshold=0.5).for_column(1, SubfamilyLabel.A)
    assert "-" not in without
    with_gap = determine_typical_states(ps, threshold=0.5, typical_gap=True)
    assert "-" in with_gap.for_column(1, SubfamilyLabel.A)


def test_class_profiles_from_a_class_table() -> None:
    # subfamily A: column all H or K -> "Basic" class (HKR) frequency 1.0
    ps = _profiles(
        ">s1\nH\n>s2\nK\n>s3\nD\n",
        ("s1", "s2"),
        ("s3",),
        class_table={"Basic": "HKR", "Acidic": "DE"},
    )
    typical = determine_typical_states(ps, threshold=0.9)
    assert "Basic" in typical.classes_for_column(1, SubfamilyLabel.A)
