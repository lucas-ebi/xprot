from __future__ import annotations

from pathlib import Path

import pytest

from xprot.core.alignment import (
    AlignmentError,
    build_coordinate_map,
    load_alignment,
    parse_alignment,
)
from xprot.core.models import AmbiguityPolicy

FASTA = ">s1 first\nA-CDE\n>s2 second\nARCDE\n>s3\nA-C.E\n"


def test_parse_fasta_canonicalises_gaps_and_keeps_headers() -> None:
    aln = parse_alignment(FASTA, "fasta")
    assert [r.canonical_id for r in aln.rows] == ["s1", "s2", "s3"]
    assert aln.rows[0].raw_header == "s1 first"
    assert aln.rows[2].aligned == "A-C-E"  # '.' normalised to '-'
    assert aln.length == 5
    assert aln.column_states(2) == ("-", "R", "-")
    assert aln.rows[0].coordinate_map.source_position(1) == 1
    assert aln.rows[0].coordinate_map.source_position(2) is None


def test_unequal_rows_rejected() -> None:
    with pytest.raises(AlignmentError):
        parse_alignment(">a\nACD\n>b\nAC\n", "fasta")


def test_empty_rejected() -> None:
    with pytest.raises(AlignmentError):
        parse_alignment("", "fasta")


def test_duplicate_id_rejected() -> None:
    with pytest.raises(AlignmentError):
        parse_alignment(">a\nAC\n>a\nGC\n", "fasta")


def test_unknown_character_rejected_by_default() -> None:
    with pytest.raises(AlignmentError):
        parse_alignment(">a\nAZ\n>b\nAC\n", "fasta")


def test_literal_policy_keeps_unknown_character() -> None:
    aln = parse_alignment(">a\nAX\n>b\nAC\n", "fasta", ambiguous=AmbiguityPolicy.LITERAL)
    assert aln.rows[0].aligned == "AX"


def test_ambiguity_map_translates() -> None:
    aln = parse_alignment(
        ">a\nAB\n>b\nAC\n", "fasta", ambiguous=AmbiguityPolicy.MAP, ambiguity_map={"B": "D"}
    )
    assert aln.rows[0].aligned == "AD"


def test_custom_alphabet_and_gap_symbols() -> None:
    aln = parse_alignment(">a\nAB*\n>b\nAB*\n", "fasta", alphabet="AB", gap_symbols=("*",))
    assert aln.rows[0].aligned == "AB-"


def test_load_alignment_infers_format_from_suffix(tmp_path: Path) -> None:
    path = tmp_path / "aln.fasta"
    path.write_text(FASTA, encoding="utf-8")
    assert load_alignment(path).length == 5
    bad = tmp_path / "aln.weird"
    bad.write_text(FASTA, encoding="utf-8")
    with pytest.raises(AlignmentError):
        load_alignment(bad)


def test_build_coordinate_map_delegates() -> None:
    cmap = build_coordinate_map("-A-C", frozenset("-"))
    assert cmap.source_position(2) == 1
    assert cmap.insertion_anchor(1) == 0
