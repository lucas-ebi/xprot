from __future__ import annotations

import pytest

from xprot.core.primitives import EventType, PartitionSemantics, SubfamilyLabel
from xprot.core.structures import (
    Alignment,
    AlignmentRow,
    CanonicalPartition,
    CoordinateMap,
    NodeSelector,
    SequenceWeight,
    TransformationEvent,
    TransformedResult,
    TypicalState,
    TypicalStateSet,
)

GAPS = frozenset("-")


@pytest.mark.parametrize(
    ("aligned", "column", "expected"),
    [("-AC", 1, None), ("-AC", 2, 1), ("A--C", 3, None), ("AC-", 3, None), ("AC", 2, 2)],
)
def test_coordinate_map_source_position(aligned: str, column: int, expected: int | None) -> None:
    assert CoordinateMap.from_aligned(aligned, GAPS).source_position(column) == expected


def test_coordinate_map_insertion_anchor() -> None:
    cmap = CoordinateMap.from_aligned("-A-C", GAPS)
    assert cmap.insertion_anchor(1) == 0  # N-terminal insertion
    assert cmap.insertion_anchor(3) == 1  # after the first residue


def test_alignment_helpers() -> None:
    rows = (
        AlignmentRow("s1", "s1", "A-C", CoordinateMap.from_aligned("A-C", GAPS), 0),
        AlignmentRow("s2", "s2", "AGC", CoordinateMap.from_aligned("AGC", GAPS), 1),
    )
    aln = Alignment(rows, "ACG")
    assert aln.length == 3
    assert aln.column_states(2) == ("-", "G")
    assert aln.row("s1").ungapped == "AC"
    with pytest.raises(KeyError):
        aln.row("nope")


def test_node_selector_requires_exactly_one() -> None:
    NodeSelector(tips=frozenset({"a", "b"}))
    NodeSelector(label="n1")
    with pytest.raises(ValueError):
        NodeSelector()
    with pytest.raises(ValueError):
        NodeSelector(tips=frozenset({"a"}), label="n1")


def test_partition_tips_for() -> None:
    part = CanonicalPartition(
        ("a", "b", "c"), ("a", "b"), ("c",), PartitionSemantics.TWO_CHILD_CLADES
    )
    assert part.tips_for(SubfamilyLabel.A) == ("a", "b")
    assert part.tips_for(SubfamilyLabel.B) == ("c",)


def test_typical_state_set_lookup() -> None:
    tss = TypicalStateSet(
        (
            TypicalState(1, SubfamilyLabel.A, "H", False, 0.95),
            TypicalState(1, SubfamilyLabel.A, "Basic", True, 0.99),
            TypicalState(1, SubfamilyLabel.B, "K", False, 0.92),
        )
    )
    assert tss.for_column(1, SubfamilyLabel.A) == frozenset({"H"})
    assert tss.classes_for_column(1, SubfamilyLabel.A) == frozenset({"Basic"})
    assert tss.for_column(1, SubfamilyLabel.B) == frozenset({"K"})


def test_transformed_result_counts() -> None:
    events = (
        TransformationEvent(
            ordinal=1,
            alignment_column=3,
            event_type=EventType.SUBSTITUTION,
            source_position=3,
            transformed_position=3,
            insertion_anchor=None,
            source_state="I",
            transformed_state="A",
            donor_frequency=0.9,
            recipient_frequency=0.05,
            rule="literal",
        ),
        TransformationEvent(
            ordinal=2,
            alignment_column=5,
            event_type=EventType.INSERTION,
            source_position=None,
            transformed_position=6,
            insertion_anchor=3,
            source_state="-",
            transformed_state="G",
            donor_frequency=0.95,
            recipient_frequency=0.0,
            rule="literal",
        ),
    )
    result = TransformedResult("recip", "donor", "AAII", "AAAIG", "AA-II", "AAAIG", events)
    assert (result.substitutions, result.insertions, result.deletions) == (1, 1, 0)


def test_sequence_weight_is_frozen() -> None:
    weight = SequenceWeight("s1", 3.0, 0.5)
    with pytest.raises(AttributeError):
        weight.normalized = 1.0  # type: ignore[misc]
