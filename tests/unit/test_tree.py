from __future__ import annotations

from pathlib import Path

import pytest

from xprot.core.errors import TreeError
from xprot.core.models import Phylogeny
from xprot.core.primitives import RootingMethod
from xprot.core.tree import load_tree, parse_tree, resolve_partition


def _tree(newick: str) -> Phylogeny:
    return parse_tree(newick, "newick")


def test_parse_and_canonical_tip_order() -> None:
    tree = _tree("((d,c),(b,a));")
    assert tree.tips == ("a", "b", "c", "d")
    assert [c.descendant_tips for c in tree.root.children] == [("a", "b"), ("c", "d")]


def test_resolve_partition_two_child_clades() -> None:
    tree = _tree("((a,b),(c,d));")
    part = resolve_partition(tree, "a", "c")
    assert {part.subfamily_a_tips, part.subfamily_b_tips} == {("a", "b"), ("c", "d")}
    assert part.selected_tips == ("a", "b", "c", "d")


def test_resolve_partition_tolerates_polytomy() -> None:
    # The root is a 3-way polytomy. "a" and "b" are each their own child of it; "c" is an
    # uninvolved sibling, excluded from both subfamilies.
    tree = _tree("(a,b,c);")
    part = resolve_partition(tree, "a", "b")
    assert part.subfamily_a_tips == ("a",)
    assert part.subfamily_b_tips == ("b",)
    assert part.selected_tips == ("a", "b")


def test_resolve_partition_deeper_polytomy() -> None:
    # MRCA(a, c) is the root (a 3-child polytomy: (a,b), c, d). Recipient's child is (a,b),
    # donor's is the leaf c; the uninvolved sibling d is excluded from both subfamilies.
    tree = _tree("((a,b),c,d);")
    part = resolve_partition(tree, "a", "c")
    assert part.subfamily_a_tips == ("a", "b")
    assert part.subfamily_b_tips == ("c",)
    assert part.selected_tips == ("a", "b", "c")


def test_resolve_partition_descendant_tip_identity_is_reorder_stable() -> None:
    left = resolve_partition(_tree("((a,b),(c,d));"), "a", "c")
    right = resolve_partition(_tree("((d,c),(b,a));"), "a", "c")
    assert {left.subfamily_a_tips, left.subfamily_b_tips} == {
        right.subfamily_a_tips,
        right.subfamily_b_tips,
    }


def test_resolve_partition_unknown_tip_rejected() -> None:
    with pytest.raises(TreeError):
        resolve_partition(_tree("((a,b),(c,d));"), "a", "ghost")


def test_resolve_partition_same_tip_rejected() -> None:
    with pytest.raises(TreeError):
        resolve_partition(_tree("((a,b),(c,d));"), "a", "a")


def test_duplicate_tip_labels_rejected() -> None:
    with pytest.raises(TreeError):
        _tree("((a,b),(a,d));")


def test_specified_outgroup_needs_ids() -> None:
    with pytest.raises(TreeError):
        parse_tree("((a,b),(c,d));", "newick", rooting=RootingMethod.SPECIFIED_OUTGROUP)


def test_load_tree_infers_format(tmp_path: Path) -> None:
    path = tmp_path / "t.nwk"
    path.write_text("((a,b),(c,d));", encoding="utf-8")
    assert load_tree(path).tips == ("a", "b", "c", "d")
    bad = tmp_path / "t.xyz"
    bad.write_text("((a,b),(c,d));", encoding="utf-8")
    with pytest.raises(TreeError):
        load_tree(bad)


def test_load_tree_missing_file_is_a_tree_error(tmp_path: Path) -> None:
    with pytest.raises(TreeError):
        load_tree(tmp_path / "missing.nwk")
