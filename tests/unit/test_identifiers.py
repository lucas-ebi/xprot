from __future__ import annotations

from xprot.core.alignment import parse_alignment
from xprot.core.identifiers import resolve_id_mapping
from xprot.core.primitives import LabelSource
from xprot.core.structures import Alignment, Phylogeny
from xprot.core.tree import parse_tree


def _aln(fasta: str) -> Alignment:
    return parse_alignment(fasta, "fasta")


def _tree(newick: str) -> Phylogeny:
    return parse_tree(newick, "newick")


def test_strict_bijection() -> None:
    mapping = resolve_id_mapping(_aln(">a x\nAA\n>b y\nAC\n"), _tree("(a,b);"))
    assert mapping.is_bijective
    aln_ids = {r.canonical_id for r in mapping.records if r.source_kind == "alignment_row"}
    assert aln_ids == {"a", "b"}
    assert all(r.status == "matched" for r in mapping.records)


def test_missing_tree_tip_is_a_distinct_diagnostic() -> None:
    mapping = resolve_id_mapping(_aln(">a\nAA\n>b\nAC\n>c\nGC\n"), _tree("(a,b);"))
    assert not mapping.is_bijective
    codes = {d.code for d in mapping.diagnostics}
    assert codes == {"IDMAP_ALIGNMENT_ROW_WITHOUT_TIP"}
    assert next(d for d in mapping.diagnostics).ids == ("c",)


def test_missing_alignment_row_is_a_distinct_diagnostic() -> None:
    mapping = resolve_id_mapping(_aln(">a\nAA\n>b\nAC\n"), _tree("((a,b),c);"))
    assert {d.code for d in mapping.diagnostics} == {"IDMAP_TIP_WITHOUT_ALIGNMENT_ROW"}


def test_first_token_label_source_strips_description() -> None:
    # header "sp|P1|NAME desc" -> first token; tree tip is the bare accession-ish token
    mapping = resolve_id_mapping(
        _aln(">A1 human alpha\nAA\n>B1 mouse beta\nAC\n"),
        _tree("(A1,B1);"),
    )
    assert mapping.is_bijective


def test_full_label_source_keeps_whole_header() -> None:
    mapping = resolve_id_mapping(
        _aln(">a b\nAA\n>c d\nAC\n"),
        _tree("('a b','c d');"),
        alignment_label_source=LabelSource.FULL_LABEL,
    )
    assert mapping.is_bijective


def test_aliases_rewrite_canonical_id() -> None:
    mapping = resolve_id_mapping(
        _aln(">seqA\nAA\n>seqB\nAC\n"),
        _tree("(A,B);"),
        aliases={"seqA": "A", "seqB": "B"},
    )
    assert mapping.is_bijective


def test_canonical_collision_is_reported() -> None:
    mapping = resolve_id_mapping(
        _aln(">x\nAA\n>y\nAC\n"),
        _tree("(A,B);"),
        aliases={"x": "same", "y": "same"},
    )
    assert not mapping.is_bijective
    assert "IDMAP_CANONICAL_COLLISION" in {d.code for d in mapping.diagnostics}
