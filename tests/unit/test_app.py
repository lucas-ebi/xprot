from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from xprot.app import CachedRunner, run_design
from xprot.core.errors import IdentifierError
from xprot.core.primitives import DesignMode
from xprot.core.profile import calculate_profiles
from xprot.core.tree import resolve_partition
from xprot.core.weights import calculate_henikoff_weights

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


def test_run_design_with_vocabulary_path(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, ">r1\nD\n>a2\nD\n>d1\nK\n>b2\nK\n", "((r1,a2),(d1,b2));")
    table_path = tmp_path / "classes.yaml"
    table_path.write_text("classes:\n  Basic: HKR\n  Acidic: DE\n", encoding="utf-8")

    result = run_design(
        aln_path,
        tree_path,
        recipient="r1",
        donor="d1",
        mode=DesignMode.EXPANDED,
        vocabulary=table_path,
    )

    assert result.transformed.transformed_sequence == "K"
    assert result.transformed.events[0].rule == "Basic"


def test_run_design_rejects_unmapped_identifiers(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, "((r1,a2),(d1,ghost));")

    with pytest.raises(IdentifierError):
        run_design(aln_path, tree_path, recipient="r1", donor="d1")


def _counted(fn: Callable[..., Any]) -> tuple[Callable[..., Any], list[int]]:
    """Wrap `fn` so `calls` records one entry per invocation, for asserting a stage was skipped."""
    calls: list[int] = []

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return fn(*args, **kwargs)

    return wrapper, calls


def test_cached_runner_matches_run_design(tmp_path: Path) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)

    direct = run_design(aln_path, tree_path, recipient="r1", donor="d1")
    cached = CachedRunner().run(aln_path, tree_path, recipient="r1", donor="d1")

    assert cached.partition == direct.partition
    assert cached.transformed.transformed_sequence == direct.transformed.transformed_sequence


def test_cached_runner_reuses_weights_across_different_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)
    wrapper, calls = _counted(calculate_henikoff_weights)
    monkeypatch.setattr("xprot.app.calculate_henikoff_weights", wrapper)

    runner = CachedRunner()
    runner.run(aln_path, tree_path, recipient="r1", donor="d1")
    runner.run(aln_path, tree_path, recipient="a2", donor="b2")

    assert len(calls) == 1


def test_cached_runner_swap_reuses_partition_and_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)
    partition_wrapper, partition_calls = _counted(resolve_partition)
    profiles_wrapper, profiles_calls = _counted(calculate_profiles)
    monkeypatch.setattr("xprot.app.resolve_partition", partition_wrapper)
    monkeypatch.setattr("xprot.app.calculate_profiles", profiles_wrapper)

    runner = CachedRunner()
    forward = runner.run(aln_path, tree_path, recipient="r1", donor="d1")
    swapped = runner.run(aln_path, tree_path, recipient="d1", donor="r1")

    assert len(partition_calls) == 1
    assert len(profiles_calls) == 1
    # The swap edits the other representative now, so the two runs' results differ.
    assert forward.transformed.transformed_sequence != swapped.transformed.transformed_sequence


def test_cached_runner_different_pair_recomputes_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)
    wrapper, calls = _counted(calculate_profiles)
    monkeypatch.setattr("xprot.app.calculate_profiles", wrapper)

    runner = CachedRunner()
    runner.run(aln_path, tree_path, recipient="r1", donor="d1")
    runner.run(aln_path, tree_path, recipient="a2", donor="b2")

    assert len(calls) == 2


def test_cached_runner_detects_alignment_content_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aln_path, tree_path = _write(tmp_path, FASTA, NEWICK)
    wrapper, calls = _counted(calculate_henikoff_weights)
    monkeypatch.setattr("xprot.app.calculate_henikoff_weights", wrapper)

    runner = CachedRunner()
    runner.run(aln_path, tree_path, recipient="r1", donor="d1")
    aln_path.write_text(">r1\nMH-T\n>a2\nMHAT\n>d1\nMKGT\n>b2\nMKGA\n", encoding="utf-8")
    runner.run(aln_path, tree_path, recipient="r1", donor="d1")

    assert len(calls) == 2
