"""Tree loading, rooting, and partitioning."""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from Bio import Phylo

from xprot.core.errors import TreeError
from xprot.core.models import CanonicalPartition, NodeSelector, Phylogeny, TreeNode
from xprot.core.primitives import PartitionSemantics, RootingMethod

__all__ = ["load_tree", "parse_tree", "resolve_partition"]

_FORMAT_BY_SUFFIX = {
    ".nwk": "newick",
    ".newick": "newick",
    ".tree": "newick",
    ".tre": "newick",
    ".nex": "nexus",
    ".nexus": "nexus",
}


def load_tree(
    source: Path | str,
    *,
    fmt: str | None = None,
    rooting: RootingMethod = RootingMethod.AS_SUPPLIED,
    outgroup: Sequence[str] = (),
) -> Phylogeny:
    """Read a local tree file and return a canonicalised :class:`Phylogeny`."""
    path = Path(source)
    resolved_fmt = fmt or _FORMAT_BY_SUFFIX.get(path.suffix.lower())
    if resolved_fmt is None:
        msg = f"cannot infer tree format from {path.name!r}; pass fmt="
        raise TreeError(msg)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"could not read {path}: {exc}"
        raise TreeError(msg) from exc
    return parse_tree(text, resolved_fmt, rooting=rooting, outgroup=outgroup)


def parse_tree(
    text: str,
    fmt: str,
    *,
    rooting: RootingMethod = RootingMethod.AS_SUPPLIED,
    outgroup: Sequence[str] = (),
) -> Phylogeny:
    """Parse tree ``text`` in ``fmt`` (``newick`` / ``nexus``) and apply the requested rooting."""
    rooting = RootingMethod(rooting)
    try:
        bio_tree = Phylo.read(io.StringIO(text), fmt)
    except Exception as exc:
        msg = f"could not parse {fmt} tree: {exc}"
        raise TreeError(msg) from exc

    tips = [leaf.name for leaf in bio_tree.get_terminals()]
    if not tips:
        raise TreeError("tree has no tips")
    if len(set(tips)) != len(tips):
        raise TreeError("tree has duplicate tip labels")

    if rooting is RootingMethod.MIDPOINT:
        bio_tree.root_at_midpoint()
    elif rooting is RootingMethod.SPECIFIED_OUTGROUP:
        if not outgroup:
            raise TreeError("rooting 'specified_outgroup' needs an outgroup")
        missing = sorted(set(outgroup) - set(tips))
        if missing:
            raise TreeError(f"outgroup ids not in the tree: {', '.join(missing)}")
        try:
            bio_tree.root_with_outgroup(*outgroup)
        except Exception as exc:
            msg = f"could not root with the specified outgroup: {exc}"
            raise TreeError(msg) from exc

    return Phylogeny(root=_convert(bio_tree.root))


def _convert(clade: Any) -> TreeNode:
    if not clade.clades:
        name = clade.name
        if name is None:
            raise TreeError("tree has an unnamed tip")
        return TreeNode(
            descendant_tips=(name,), children=(), label=name, branch_length=clade.branch_length
        )
    children = tuple(sorted((_convert(c) for c in clade.clades), key=lambda n: n.descendant_tips))
    descendant_tips = tuple(sorted(tip for child in children for tip in child.descendant_tips))
    return TreeNode(
        descendant_tips=descendant_tips,
        children=children,
        label=clade.name,
        branch_length=clade.branch_length,
    )


def resolve_partition(
    tree: Phylogeny,
    selector: NodeSelector,
    *,
    semantics: PartitionSemantics = PartitionSemantics.TWO_CHILD_CLADES,
) -> CanonicalPartition:
    """Resolve ``selector`` to an internal node and split it into two subfamilies."""
    semantics = PartitionSemantics(semantics)
    node = _resolve_node(tree, selector)

    if semantics is PartitionSemantics.TWO_CHILD_CLADES:
        if len(node.children) != 2:
            raise TreeError(
                f"two_child_clades needs a node with exactly two children, got {len(node.children)}"
            )
        a_tips, b_tips = node.children[0].descendant_tips, node.children[1].descendant_tips
    else:  # SELECTED_CLADE_VS_COMPLEMENT
        a_tips = node.descendant_tips
        b_tips = tuple(t for t in tree.tips if t not in set(a_tips))
        if not a_tips or not b_tips:
            raise TreeError("selected_clade_vs_complement needs both sides non-empty")

    return CanonicalPartition(
        selected_tips=node.descendant_tips,
        subfamily_a_tips=a_tips,
        subfamily_b_tips=b_tips,
        semantics=semantics,
    )


def _resolve_node(tree: Phylogeny, selector: NodeSelector) -> TreeNode:
    nodes = tree.iter_nodes()
    if selector.tips is not None:
        target = tuple(sorted(selector.tips))
        matches = [n for n in nodes if n.descendant_tips == target]
        if not matches:
            raise TreeError(f"no node has exactly the descendant tips {target}")
        return matches[0]

    matches = [n for n in nodes if n.label == selector.label and not n.is_leaf]
    if not matches:
        raise TreeError(f"no internal node is labelled {selector.label!r}")
    if len(matches) > 1:
        raise TreeError(f"internal label {selector.label!r} is ambiguous ({len(matches)} nodes)")
    return matches[0]
