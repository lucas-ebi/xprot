"""Deterministic byte renderers for a design run: events, transformed sequence, pairwise view."""

from __future__ import annotations

import json
from collections.abc import Sequence

from xprot.core.models import CanonicalPartition, TransformationEvent, TransformedResult
from xprot.core.primitives import Diagnostic

__all__ = [
    "DEFAULT_WRAP_WIDTH",
    "render_diagnostics_json",
    "render_events_json",
    "render_events_tsv",
    "render_pairwise",
    "render_summary_json",
    "render_transformed_fasta",
]

DEFAULT_WRAP_WIDTH = 80

_EVENT_COLUMNS = (
    "ordinal",
    "alignment_column",
    "event_type",
    "source_position",
    "transformed_position",
    "insertion_anchor",
    "source_state",
    "transformed_state",
    "donor_frequency",
    "recipient_frequency",
    "rule",
)


def _event_row(event: TransformationEvent) -> dict[str, object]:
    return {
        "ordinal": event.ordinal,
        "alignment_column": event.alignment_column,
        "event_type": str(event.event_type),
        "source_position": event.source_position,
        "transformed_position": event.transformed_position,
        "insertion_anchor": event.insertion_anchor,
        "source_state": event.source_state,
        "transformed_state": event.transformed_state,
        "donor_frequency": event.donor_frequency,
        "recipient_frequency": event.recipient_frequency,
        "rule": event.rule,
    }


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def render_events_tsv(events: Sequence[TransformationEvent]) -> bytes:
    """One row per event, in ``TransformationEvent`` field order."""
    lines = ["\t".join(_EVENT_COLUMNS)]
    for event in events:
        row = _event_row(event)
        lines.append("\t".join(_cell(row[c]) for c in _EVENT_COLUMNS))
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_events_json(events: Sequence[TransformationEvent]) -> bytes:
    """The same event rows as :func:`render_events_tsv`, as a JSON array."""
    return _dump([_event_row(e) for e in events])


def render_transformed_fasta(
    result: TransformedResult, *, width: int = DEFAULT_WRAP_WIDTH
) -> bytes:
    """The transformed (ungapped) sequence as one FASTA record."""
    header = f">{result.recipient_id}_transformed_toward_{result.donor_id}"
    body = _wrap(result.transformed_sequence, width)
    return f"{header}\n{body}\n".encode()


def render_pairwise(result: TransformedResult, *, width: int = DEFAULT_WRAP_WIDTH) -> bytes:
    """Recipient vs. transformed, in alignment coordinates, with a marker line over each change."""
    length = len(result.aligned_source)
    blocks = [f"# recipient: {result.recipient_id}  donor: {result.donor_id}", ""]
    for start in range(0, length, width):
        end = min(start + width, length)
        before = result.aligned_source[start:end]
        after = result.aligned_transformed[start:end]
        marker = "".join("*" if a != b else " " for a, b in zip(before, after, strict=True))
        blocks.append(f"{'before':<10}{start + 1:>6} {before}")
        blocks.append(f"{'':<17}{marker}")
        blocks.append(f"{'after':<10}{start + 1:>6} {after}")
        blocks.append("")
    return ("\n".join(blocks)).rstrip("\n").encode("utf-8") + b"\n"


def render_summary_json(
    transformed: TransformedResult,
    partition: CanonicalPartition,
    *,
    is_bijective: bool,
) -> bytes:
    """Event counts, subfamily membership, and whether the identifier mapping was bijective."""
    payload = {
        "recipient_id": transformed.recipient_id,
        "donor_id": transformed.donor_id,
        "substitutions": transformed.substitutions,
        "insertions": transformed.insertions,
        "deletions": transformed.deletions,
        "is_bijective": is_bijective,
        "subfamily_a_tips": list(partition.subfamily_a_tips),
        "subfamily_b_tips": list(partition.subfamily_b_tips),
    }
    return _dump(payload)


def render_diagnostics_json(*groups: Sequence[Diagnostic]) -> bytes:
    """Every diagnostic across ``groups`` (e.g. identifier mapping and design), as a JSON array."""
    return _dump([d.model_dump(mode="json") for group in groups for d in group])


def _dump(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _wrap(sequence: str, width: int) -> str:
    return "\n".join(sequence[i : i + width] for i in range(0, len(sequence), width))
