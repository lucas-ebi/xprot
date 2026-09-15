from __future__ import annotations

import json

from xprot.core.models import CanonicalPartition, TransformationEvent, TransformedResult
from xprot.core.primitives import Diagnostic, EventType, Severity
from xprot.render import (
    render_diagnostics_json,
    render_events_json,
    render_events_tsv,
    render_pairwise,
    render_pairwise_json,
    render_summary_json,
    render_transformed_fasta,
)

EVENTS = (
    TransformationEvent(
        ordinal=1,
        alignment_column=2,
        event_type=EventType.SUBSTITUTION,
        source_position=2,
        transformed_position=2,
        insertion_anchor=None,
        source_state="H",
        transformed_state="K",
        donor_frequency=1.0,
        recipient_frequency=0.0,
        rule="literal",
    ),
    TransformationEvent(
        ordinal=2,
        alignment_column=3,
        event_type=EventType.INSERTION,
        source_position=None,
        transformed_position=3,
        insertion_anchor=2,
        source_state="-",
        transformed_state="G",
        donor_frequency=1.0,
        recipient_frequency=0.0,
        rule="literal",
    ),
)

RESULT = TransformedResult(
    recipient_id="r1",
    donor_id="d1",
    source_sequence="MHT",
    transformed_sequence="MKGT",
    aligned_source="MH-T",
    aligned_transformed="MKGT",
    events=EVENTS,
)

PARTITION = CanonicalPartition(("a2", "b2", "d1", "r1"), ("a2", "r1"), ("b2", "d1"))


def test_render_events_tsv() -> None:
    text = render_events_tsv(EVENTS).decode("utf-8")
    lines = text.splitlines()
    assert lines[0].split("\t") == [
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
    ]
    assert lines[1].split("\t") == [
        "1",
        "2",
        "substitution",
        "2",
        "2",
        "",
        "H",
        "K",
        "1.000000",
        "0.000000",
        "literal",
    ]
    assert text.endswith("\n")


def test_render_events_json_round_trips() -> None:
    payload = json.loads(render_events_json(EVENTS))
    assert payload[0]["event_type"] == "substitution"
    assert payload[1]["insertion_anchor"] == 2
    assert payload[1]["source_position"] is None


def test_render_transformed_fasta_wraps() -> None:
    text = render_transformed_fasta(RESULT, width=2).decode("utf-8")
    assert text == ">r1_transformed_toward_d1\nMK\nGT\n"


def test_render_pairwise_marks_changes() -> None:
    text = render_pairwise(RESULT, width=80).decode("utf-8")
    lines = text.splitlines()
    assert lines[0] == "# recipient: r1  donor: d1"
    before_line = next(line for line in lines if line.startswith("before"))
    after_line = next(line for line in lines if line.startswith("after"))
    marker_line = lines[lines.index(before_line) + 1]
    assert before_line.endswith("MH-T")
    assert after_line.endswith("MKGT")
    expected_marker = "".join("*" if a != b else " " for a, b in zip("MH-T", "MKGT", strict=True))
    assert marker_line.endswith(expected_marker)
    assert marker_line[: len(marker_line) - len(expected_marker)] == " " * 17


def test_render_pairwise_json() -> None:
    payload = json.loads(render_pairwise_json(RESULT))
    assert payload == {
        "recipient_id": "r1",
        "donor_id": "d1",
        "aligned_source": "MH-T",
        "aligned_transformed": "MKGT",
    }


def test_render_summary_json() -> None:
    payload = json.loads(render_summary_json(RESULT, PARTITION, is_bijective=True))
    assert payload == {
        "recipient_id": "r1",
        "donor_id": "d1",
        "substitutions": 1,
        "insertions": 1,
        "deletions": 0,
        "is_bijective": True,
        "subfamily_a_tips": ["a2", "r1"],
        "subfamily_b_tips": ["b2", "d1"],
    }


def test_render_diagnostics_json_merges_groups() -> None:
    a = (Diagnostic(code="A", severity=Severity.WARNING, stage="s", message="m"),)
    b = (Diagnostic(code="B", severity=Severity.ERROR, stage="t", message="n"),)
    payload = json.loads(render_diagnostics_json(a, b))
    assert [d["code"] for d in payload] == ["A", "B"]
