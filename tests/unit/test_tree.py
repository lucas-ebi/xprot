from __future__ import annotations

from pathlib import Path

import pytest

from xprot.core.errors import TreeError
from xprot.core.models import PartitionSemantics, RootingMethod
from xprot.core.structures import NodeSelector, Phylogeny
from xprot.core.tree import load_tree, parse_tree, resolve_partition


def _tree(newick: str) -> Phylogeny:
    return parse_tree(newick, "newick")


def test_parse_and_canonical_tip_order() -> None:
    tree = _tree("((d,c),(b,a));")
    assert tree.tips == ("a", "b", "c", "d")
    assert [c.descendant_tips for c in tree.root.children] == [("a", "b"), ("c", "d")]


def test_two_child_clades_partition() -> None:
    tree = _tree("((a,b),(c,d));")
    part = resolve_partition(tree, NodeSelector(tips=frozenset("abcd")))
    assert {part.subfamily_a_tips, part.subfamily_b_tips} == {("a", "b"), ("c", "d")}
    assert part.selected_tips == ("a", "b", "c", "d")


def test_selected_clade_vs_complement() -> None:
    tree = _tree("((a,b),(c,d));")
    part = resolve_partition(
        tree,
        NodeSelector(tips=frozenset({"a", "b"})),
        semantics=PartitionSemantics.SELECTED_CLADE_VS_COMPLEMENT,
    )
    assert part.subfamily_a_tips == ("a", "b")
    assert part.subfamily_b_tips == ("c", "d")


def test_polytomy_rejected_under_two_child() -> None:
    with pytest.raises(TreeError):
        resolve_partition(_tree("(a,b,c);"), NodeSelector(tips=frozenset("abc")))


def test_descendant_tip_identity_is_reorder_stable() -> None:
    left = resolve_partition(_tree("((a,b),(c,d));"), NodeSelector(tips=frozenset("abcd")))
    right = resolve_partition(_tree("((d,c),(b,a));"), NodeSelector(tips=frozenset("abcd")))
    assert {left.subfamily_a_tips, left.subfamily_b_tips} == {
        right.subfamily_a_tips,
        right.subfamily_b_tips,
    }


def test_label_selector() -> None:
    tree = _tree("((a,b)AB,(c,d)CD)root;")
    part = resolve_partition(tree, NodeSelector(label="AB"))
    assert part.selected_tips == ("a", "b")
    with pytest.raises(TreeError):
        resolve_partition(tree, NodeSelector(label="nope"))


def test_unknown_tip_set_rejected() -> None:
    with pytest.raises(TreeError):
        resolve_partition(_tree("((a,b),(c,d));"), NodeSelector(tips=frozenset({"a", "c"})))


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
