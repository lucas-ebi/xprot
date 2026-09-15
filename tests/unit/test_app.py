from __future__ import annotations

from pathlib import Path

import pytest

from xprot.app import run_design
from xprot.core.errors import IdentifierError
from xprot.core.primitives import DesignMode

FASTA = ">r1\nMH-T\n>a2\nMHAT\n>d1\nMKGT\n>b2\nMKGT\n"
NEWICK = "((r1,a2),(d1,b2));"


def _write(tmp_path: Path, fasta: str, newick: str) -> tuple[Path, Path]:
    aln_path = tmp_path / "aln.fasta"
    tree_path = tmp_path / "tree.nwk"
    aln_path.write_text(fasta, encoding="utf-8")
    tree_path.write_text(newick, encoding="utf-8")
    return aln_path, tree_path


def test_run_design_chains_the_pipeline(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)

    result = run_design(aln_path, tree_path, recipient="r1", donor="d1")

    assert result.id_mapping.is_bijective
    assert result.partition.subfamily_a_tips == ("a2", "r1")
    assert result.partition.subfamily_b_tips == ("b2", "d1")
    assert result.transformed.transformed_sequence == "MKGT"
    tokens = [
        (e.alignment_column, e.event_type.value, e.source_state, e.transformed_state)
        for e in result.transformed.events
    ]
    assert tokens == [(2, "substitution", "H", "K"), (3, "insertion", "-", "G")]


def test_run_design_with_class_table_path(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, ">r1\nD\n>a2\nD\n>d1\nK\n>b2\nK\n", "((r1,a2),(d1,b2));")
    table_path = tmp_path / "classes.yaml"
    table_path.write_text("classes:\n  Basic: HKR\n  Acidic: DE\n", encoding="utf-8")

    result = run_design(
        aln_path,
        tree_path,
        recipient="r1",
        donor="d1",
        mode=DesignMode.EXPANDED,
        class_table=table_path,
    )

    assert result.transformed.transformed_sequence == "K"
    assert result.transformed.events[0].rule == "Basic"


def test_run_design_rejects_unmapped_identifiers(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, "((r1,a2),(d1,ghost));")

    with pytest.raises(IdentifierError):
        run_design(aln_path, tree_path, recipient="r1", donor="d1")
