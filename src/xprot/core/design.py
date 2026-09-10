"""Transformation-event generation and comparison against a reference case."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from xprot.core.errors import DesignError
from xprot.core.models import DesignMode, Diagnostic, EventType, Severity, SubfamilyLabel
from xprot.core.structures import (
    Alignment,
    CanonicalPartition,
    FixtureComparison,
    ProfileSet,
    TransformationEvent,
    TransformedResult,
    TypicalStateSet,
)

__all__ = ["compare_with_fixture", "generate_transformation"]

_AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"


def generate_transformation(
    alignment: Alignment,
    partition: CanonicalPartition,
    profiles: ProfileSet,
    typical_states: TypicalStateSet,
    *,
    recipient: str,
    donor: str,
    mode: DesignMode = DesignMode.LITERAL,
    deletions: bool = False,
    class_table: Mapping[str, str] | None = None,
) -> TransformedResult:
    """Change the recipient representative toward the donor clade's conserved states.

    ``profiles`` and ``typical_states`` are computed upstream (from the global Henikoff weights).
    Events are emitted in ascending alignment-column order and numbered afterwards.
    """
    mode = DesignMode(mode)
    recipient_label = _subfamily_of(recipient, partition)
    donor_label = _subfamily_of(donor, partition)
    if recipient_label is donor_label:
        msg = "recipient and donor must be in different subfamilies"
        raise DesignError(msg)
    if mode is DesignMode.EXPANDED and not class_table:
        msg = "expanded mode needs a class_table"
        raise DesignError(msg)

    recipient_row = alignment.row(recipient)
    gap = alignment.gap

    events: list[TransformationEvent] = []
    diagnostics: list[Diagnostic] = []
    transformed: list[str] = []
    aligned_out: list[str] = []
    out_pos = 0  # length of the transformed sequence so far

    for column in range(1, alignment.length + 1):
        source_state = recipient_row.aligned[column - 1]
        target, rule, donor_freq = None, "", 0.0
        if column in profiles.included_columns:
            target, rule, donor_freq = _pick_target(
                column,
                source_state,
                recipient_label,
                donor_label,
                typical_states,
                profiles,
                mode,
                class_table or {},
                gap,
            )

        if target is None or target == source_state:
            aligned_out.append(source_state)
            if source_state != gap:
                transformed.append(source_state)
                out_pos += 1
            continue

        recipient_freq = _frequency(profiles, column, recipient_label, source_state)
        cmap = recipient_row.coordinate_map

        if source_state == gap:  # gap -> residue
            out_pos += 1
            transformed.append(target)
            aligned_out.append(target)
            events.append(
                _event(
                    column,
                    EventType.INSERTION,
                    None,
                    out_pos,
                    cmap.insertion_anchor(column),
                    source_state,
                    target,
                    donor_freq,
                    recipient_freq,
                    rule,
                )
            )
        elif target == gap:  # residue -> gap
            if not deletions:
                diagnostics.append(
                    Diagnostic(
                        code="DESIGN_DELETION_SKIPPED",
                        severity=Severity.INFO,
                        stage="design",
                        message=f"column {column}: deletion candidate skipped (deletions disabled)",
                        columns=(column,),
                    )
                )
                transformed.append(source_state)
                aligned_out.append(source_state)
                out_pos += 1
                continue
            aligned_out.append(gap)
            events.append(
                _event(
                    column,
                    EventType.DELETION,
                    cmap.source_position(column),
                    None,
                    None,
                    source_state,
                    target,
                    donor_freq,
                    recipient_freq,
                    rule,
                )
            )
        else:  # residue -> different residue
            out_pos += 1
            transformed.append(target)
            aligned_out.append(target)
            events.append(
                _event(
                    column,
                    EventType.SUBSTITUTION,
                    cmap.source_position(column),
                    out_pos,
                    None,
                    source_state,
                    target,
                    donor_freq,
                    recipient_freq,
                    rule,
                )
            )

    ordered = tuple(_with_ordinal(e, i) for i, e in enumerate(events, start=1))
    return TransformedResult(
        recipient_id=recipient,
        donor_id=donor,
        source_sequence=recipient_row.ungapped,
        transformed_sequence="".join(transformed),
        aligned_source=recipient_row.aligned,
        aligned_transformed="".join(aligned_out),
        events=ordered,
        diagnostics=(*profiles.diagnostics, *diagnostics),
    )


def _subfamily_of(canonical_id: str, partition: CanonicalPartition) -> SubfamilyLabel:
    if canonical_id in partition.subfamily_a_tips:
        return SubfamilyLabel.A
    if canonical_id in partition.subfamily_b_tips:
        return SubfamilyLabel.B
    msg = f"{canonical_id!r} is not a tip of either subfamily"
    raise DesignError(msg)


def _pick_target(
    column: int,
    source_state: str,
    recipient_label: SubfamilyLabel,
    donor_label: SubfamilyLabel,
    typical_states: TypicalStateSet,
    profiles: ProfileSet,
    mode: DesignMode,
    class_table: Mapping[str, str],
    gap: str,
) -> tuple[str | None, str, float]:
    donor_profile = profiles.residue_profile(column, donor_label)
    donor_freqs = donor_profile.frequencies if donor_profile else {}

    if mode is DesignMode.LITERAL:
        donor_typical = typical_states.for_column(column, donor_label)
        recipient_typical = typical_states.for_column(column, recipient_label)
        candidates = [r for r in donor_typical - recipient_typical if r != gap]
        if not candidates:
            return None, "", 0.0
        best = _rank_by_frequency(candidates, donor_freqs)
        return best, "literal", donor_freqs.get(best, 0.0)

    donor_classes = typical_states.classes_for_column(column, donor_label)
    recipient_classes = typical_states.classes_for_column(column, recipient_label)
    for class_name in sorted(donor_classes - recipient_classes):
        members = set(class_table.get(class_name, ""))
        if source_state in members:
            continue  # recipient already carries this property
        in_class = [r for r in members if donor_freqs.get(r, 0.0) > 0]
        if not in_class:
            continue
        best = _rank_by_frequency(in_class, donor_freqs)
        return best, class_name, donor_freqs.get(best, 0.0)
    return None, "", 0.0


def _rank_by_frequency(candidates: Sequence[str], freqs: Mapping[str, float]) -> str:
    return max(candidates, key=lambda r: (freqs.get(r, 0.0), -_aa_rank(r)))


def _frequency(profiles: ProfileSet, column: int, label: SubfamilyLabel, state: str) -> float:
    profile = profiles.residue_profile(column, label)
    return profile.frequencies.get(state, 0.0) if profile else 0.0


def _aa_rank(residue: str) -> int:
    return _AA_ORDER.index(residue) if residue in _AA_ORDER else len(_AA_ORDER)


def _event(
    column: int,
    event_type: EventType,
    source_position: int | None,
    transformed_position: int | None,
    insertion_anchor: int | None,
    source_state: str,
    transformed_state: str,
    donor_frequency: float,
    recipient_frequency: float,
    rule: str,
) -> TransformationEvent:
    return TransformationEvent(
        ordinal=0,
        alignment_column=column,
        event_type=event_type,
        source_position=source_position,
        transformed_position=transformed_position,
        insertion_anchor=insertion_anchor,
        source_state=source_state,
        transformed_state=transformed_state,
        donor_frequency=donor_frequency,
        recipient_frequency=recipient_frequency,
        rule=rule,
    )


def _with_ordinal(event: TransformationEvent, ordinal: int) -> TransformationEvent:
    fields = {f: getattr(event, f) for f in event.__dataclass_fields__}
    fields["ordinal"] = ordinal
    return TransformationEvent(**fields)


def compare_with_fixture(
    result: TransformedResult,
    expected_events: Sequence[tuple[int, str, str, str]],
    *,
    expected_transformed: str | None = None,
) -> FixtureComparison:
    """Score ``result`` against reference ``(aln_col, type, wt, mut)`` tokens + an optional seq."""
    got = [
        (e.alignment_column, e.event_type.value, e.source_state, e.transformed_state)
        for e in result.events
    ]
    want = [(int(c), str(t), str(w), str(m)) for c, t, w, m in expected_events]
    exact_events = got == want
    if expected_transformed is None:
        exact_transformed: bool | None = None
    else:
        exact_transformed = result.transformed_sequence == expected_transformed

    want_counts = {
        kind: sum(1 for _, t, _, _ in want if t == kind)
        for kind in ("substitution", "insertion", "deletion")
    }
    deltas = (
        abs(result.substitutions - want_counts["substitution"]),
        abs(result.insertions - want_counts["insertion"]),
        abs(result.deletions - want_counts["deletion"]),
    )
    reproduced = exact_events and exact_transformed is not False
    return FixtureComparison(
        exact_events=exact_events,
        exact_transformed=exact_transformed,
        event_edit_distance=_levenshtein(got, want),
        summary_deltas=deltas,
        reproduced=reproduced,
    )


def _levenshtein(a: Sequence[object], b: Sequence[object]) -> int:
    previous = list(range(len(b) + 1))
    for i, ai in enumerate(a, start=1):
        current = [i]
        for j, bj in enumerate(b, start=1):
            cost = 0 if ai == bj else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]
