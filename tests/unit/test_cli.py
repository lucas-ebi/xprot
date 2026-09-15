from __future__ import annotations

import json
from pathlib import Path

import pytest

from xprot.cli import main

FASTA = ">r1\nMH-T\n>a2\nMHAT\n>d1\nMKGT\n>b2\nMKGT\n"
NEWICK = "((r1,a2),(d1,b2));"


def _write(tmp_path: Path, fasta: str = FASTA, newick: str = NEWICK) -> tuple[Path, Path]:
    aln_path = tmp_path / "aln.fasta"
    tree_path = tmp_path / "tree.nwk"
    aln_path.write_text(fasta, encoding="utf-8")
    tree_path.write_text(newick, encoding="utf-8")
    return aln_path, tree_path


def test_design_writes_all_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    aln_path, tree_path = _write(tmp_path)
    out_dir = tmp_path / "out"

    code = main(
        [
            "design",
            "--alignment",
            str(aln_path),
            "--tree",
            str(tree_path),
            "--node-tips",
            "r1,a2,d1,b2",
            "--recipient",
            "r1",
            "--donor",
            "d1",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    written = {p.name for p in out_dir.iterdir()}
    assert written == {
        "transformed.fasta",
        "events.tsv",
        "events.json",
        "pairwise.txt",
        "pairwise.json",
        "summary.json",
        "diagnostics.json",
    }
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary["substitutions"] == 1
    assert summary["insertions"] == 1
    out = capsys.readouterr().out
    assert "r1 -> d1" in out


def test_design_threshold_flag_is_forwarded(tmp_path: Path) -> None:
    # threshold=0.5 doesn't change this fixture's outcome, just confirms the flag parses and
    # reaches run_design without error.
    aln_path, tree_path = _write(tmp_path)
    out_dir = tmp_path / "out"

    code = main(
        [
            "design",
            "--alignment",
            str(aln_path),
            "--tree",
            str(tree_path),
            "--node-tips",
            "r1,a2,d1,b2",
            "--recipient",
            "r1",
            "--donor",
            "d1",
            "--threshold",
            "0.5",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary["substitutions"] == 1
    assert summary["insertions"] == 1


def test_design_deletions_flag_emits_a_deletion(tmp_path: Path) -> None:
    # Donor clade (d1, b2) is gapped at column 2; recipient clade (r1, a2) is not.
    aln_path, tree_path = _write(
        tmp_path, fasta=">r1\nMK\n>a2\nMK\n>d1\nM-\n>b2\nM-\n", newick="((r1,a2),(d1,b2));"
    )
    out_dir = tmp_path / "out"

    code = main(
        [
            "design",
            "--alignment",
            str(aln_path),
            "--tree",
            str(tree_path),
            "--node-tips",
            "r1,a2,d1,b2",
            "--recipient",
            "r1",
            "--donor",
            "d1",
            "--deletions",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary["deletions"] == 1


def test_design_dry_run_writes_nothing(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path)

    code = main(
        [
            "design",
            "--alignment",
            str(aln_path),
            "--tree",
            str(tree_path),
            "--node-label",
            "",
            "--recipient",
            "r1",
            "--donor",
            "d1",
            "--dry-run",
        ]
    )

    assert code == 4  # no internal node labelled ""


def test_design_requires_out_or_dry_run(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "design",
                "--alignment",
                str(aln_path),
                "--tree",
                str(tree_path),
                "--node-tips",
                "r1,a2,d1,b2",
                "--recipient",
                "r1",
                "--donor",
                "d1",
            ]
        )
    assert exc_info.value.code == 2


def test_design_reports_exit_code_for_bad_alignment_path(tmp_path: Path) -> None:
    _, tree_path = _write(tmp_path)
    code = main(
        [
            "design",
            "--alignment",
            str(tmp_path / "missing.fasta"),
            "--tree",
            str(tree_path),
            "--node-tips",
            "r1,a2,d1,b2",
            "--recipient",
            "r1",
            "--donor",
            "d1",
            "--dry-run",
        ]
    )
    assert code == 3


def test_design_reports_exit_code_for_same_subfamily(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path)
    code = main(
        [
            "design",
            "--alignment",
            str(aln_path),
            "--tree",
            str(tree_path),
            "--node-tips",
            "r1,a2,d1,b2",
            "--recipient",
            "r1",
            "--donor",
            "a2",
            "--dry-run",
        ]
    )
    assert code == 5
