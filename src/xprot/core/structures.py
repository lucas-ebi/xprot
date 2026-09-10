"""Immutable data structures for the analysis pipeline.

Frozen, slotted dataclasses carrying ``float`` weights and frequencies. :mod:`xprot.render` turns
the result-facing ones into output bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xprot.core.models import Diagnostic, EventType, PartitionSemantics, SubfamilyLabel

__all__ = [
    "Alignment",
    "AlignmentRow",
    "CanonicalPartition",
    "ClassProfile",
    "CoordinateMap",
    "FixtureComparison",
    "NodeSelector",
    "Phylogeny",
    "ProfileSet",
    "ResidueProfile",
    "SequenceWeight",
    "TransformationEvent",
    "TransformedResult",
    "TreeNode",
    "TypicalState",
    "TypicalStateSet",
]


# --------------------------------------------------------------------------------------------------
# Alignment
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoordinateMap:
    """Alignment-column ↔ ungapped-position map for one row (columns are 1-based)."""

    positions: tuple[int | None, ...]  # per column: 1-based ungapped position, or None at a gap
    anchors: tuple[int, ...]  # per column: preceding ungapped position (0 = N-terminus)

    @classmethod
    def from_aligned(cls, aligned: str, gaps: frozenset[str]) -> CoordinateMap:
        positions: list[int | None] = []
        anchors: list[int] = []
        seen = 0
        for char in aligned:
            anchors.append(seen)
            if char in gaps:
                positions.append(None)
            else:
                seen += 1
                positions.append(seen)
        return cls(tuple(positions), tuple(anchors))

    def source_position(self, column: int) -> int | None:
        return self.positions[column - 1]

    def insertion_anchor(self, column: int) -> int:
        return self.anchors[column - 1]


@dataclass(frozen=True, slots=True)
class AlignmentRow:
    canonical_id: str
    raw_header: str
    aligned: str
    coordinate_map: CoordinateMap
    source_ordinal: int

    @property
    def ungapped(self) -> str:
        return self.aligned.replace("-", "")


@dataclass(frozen=True, slots=True)
class Alignment:
    rows: tuple[AlignmentRow, ...]
    alphabet: str
    gap: str = "-"

    @property
    def length(self) -> int:
        return len(self.rows[0].aligned) if self.rows else 0

    def column_states(self, column: int) -> tuple[str, ...]:
        """States at ``column`` (1-based) in canonical row order."""
        return tuple(row.aligned[column - 1] for row in self.rows)

    def row(self, canonical_id: str) -> AlignmentRow:
        for row in self.rows:
            if row.canonical_id == canonical_id:
                return row
        msg = f"no alignment row with canonical id {canonical_id!r}"
        raise KeyError(msg)


# --------------------------------------------------------------------------------------------------
# Tree
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TreeNode:
    descendant_tips: tuple[str, ...]  # sorted canonical tip ids
    children: tuple[TreeNode, ...]  # canonical order: by descendant_tips
    label: str | None = None
    branch_length: float | None = None

    @property
    def is_leaf(self) -> bool:
        return not self.children


@dataclass(frozen=True, slots=True)
class Phylogeny:
    root: TreeNode

    @property
    def tips(self) -> tuple[str, ...]:
        return self.root.descendant_tips

    def iter_nodes(self) -> list[TreeNode]:
        out: list[TreeNode] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(node.children)
        return out


@dataclass(frozen=True, slots=True)
class NodeSelector:
    """How the caller names the internal node: a descendant-tip set or a unique label."""

    tips: frozenset[str] | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if (self.tips is None) == (self.label is None):
            msg = "NodeSelector needs exactly one of `tips` or `label`"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CanonicalPartition:
    selected_tips: tuple[str, ...]
    subfamily_a_tips: tuple[str, ...]
    subfamily_b_tips: tuple[str, ...]
    semantics: PartitionSemantics

    def tips_for(self, label: SubfamilyLabel) -> tuple[str, ...]:
        return self.subfamily_a_tips if label is SubfamilyLabel.A else self.subfamily_b_tips


# --------------------------------------------------------------------------------------------------
# Weights, profiles, typicality
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SequenceWeight:
    canonical_id: str
    unnormalized: float  # summed per-column contribution
    normalized: float  # unnormalized / column count


@dataclass(frozen=True, slots=True)
class ResidueProfile:
    column: int
    subfamily: SubfamilyLabel
    frequencies: dict[str, float]  # state -> weighted frequency, canonical residue order
    denominator: float
    occupancy: float


@dataclass(frozen=True, slots=True)
class ClassProfile:
    column: int
    subfamily: SubfamilyLabel
    frequencies: dict[str, float]  # class name -> summed member frequency


@dataclass(frozen=True, slots=True)
class ProfileSet:
    residues: tuple[ResidueProfile, ...]
    classes: tuple[ClassProfile, ...]
    included_columns: frozenset[int]
    diagnostics: tuple[Diagnostic, ...] = ()

    def residue_profile(self, column: int, subfamily: SubfamilyLabel) -> ResidueProfile | None:
        for profile in self.residues:
            if profile.column == column and profile.subfamily is subfamily:
                return profile
        return None


@dataclass(frozen=True, slots=True)
class TypicalState:
    column: int
    subfamily: SubfamilyLabel
    state: str  # a residue, a class name, or the gap character
    is_class: bool
    frequency: float


@dataclass(frozen=True, slots=True)
class TypicalStateSet:
    states: tuple[TypicalState, ...]

    def for_column(self, column: int, subfamily: SubfamilyLabel) -> frozenset[str]:
        return frozenset(
            s.state
            for s in self.states
            if s.column == column and s.subfamily is subfamily and not s.is_class
        )

    def classes_for_column(self, column: int, subfamily: SubfamilyLabel) -> frozenset[str]:
        return frozenset(
            s.state
            for s in self.states
            if s.column == column and s.subfamily is subfamily and s.is_class
        )


# --------------------------------------------------------------------------------------------------
# Transformation result
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransformationEvent:
    ordinal: int
    alignment_column: int
    event_type: EventType
    source_position: int | None
    transformed_position: int | None
    insertion_anchor: int | None
    source_state: str
    transformed_state: str
    donor_frequency: float
    recipient_frequency: float
    rule: str  # "literal" or a class name


@dataclass(frozen=True, slots=True)
class TransformedResult:
    recipient_id: str
    donor_id: str
    source_sequence: str  # recipient representative, ungapped
    transformed_sequence: str  # result, ungapped
    aligned_source: str  # recipient representative in alignment coordinates
    aligned_transformed: str  # result in alignment coordinates (same length as aligned_source)
    events: tuple[TransformationEvent, ...]
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def substitutions(self) -> int:
        return sum(1 for e in self.events if e.event_type is EventType.SUBSTITUTION)

    @property
    def insertions(self) -> int:
        return sum(1 for e in self.events if e.event_type is EventType.INSERTION)

    @property
    def deletions(self) -> int:
        return sum(1 for e in self.events if e.event_type is EventType.DELETION)


@dataclass(frozen=True, slots=True)
class FixtureComparison:
    """How a :class:`TransformedResult` scores against a reference case."""

    exact_events: bool
    exact_transformed: bool | None  # None when no expected transformed sequence was supplied
    event_edit_distance: int
    summary_deltas: tuple[int, int, int]  # |Δ substitutions|, |Δ insertions|, |Δ deletions|
    reproduced: bool
