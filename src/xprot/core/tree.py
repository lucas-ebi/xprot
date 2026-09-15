"""Tree loading, rooting, and partitioning."""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from Bio import Phylo

from xprot.core.errors import TreeError
from xprot.core.models import CanonicalPartition, Phylogeny, TreeNode
from xprot.core.primitives import RootingMethod

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


def resolve_partition(tree: Phylogeny, recipient: str, donor: str) -> CanonicalPartition:
    """Resolve the MRCA of ``recipient`` and ``donor`` and split it into their two subfamilies.

    The MRCA may have more than two children (a polytomy) -- only the two children that
    respectively contain ``recipient`` and ``donor`` become the two subfamilies; any other sibling
    children at that node are ignored. By definition of MRCA this always yields two *distinct*
    children: if both tips were under the same child, that child would itself be a deeper common
    ancestor, contradicting the node being the *most recent* common ancestor.
    """
    tips = set(tree.tips)
    missing = sorted(t for t in {recipient, donor} if t not in tips)
    if missing:
        raise TreeError(f"tip ids not in the tree: {', '.join(missing)}")
    if recipient == donor:
        raise TreeError("recipient and donor must be different tips")

    node = _mrca(tree.root, recipient, donor)
    child_a = _child_containing(node, recipient)
    child_b = _child_containing(node, donor)

    return CanonicalPartition(
        selected_tips=tuple(sorted({*child_a.descendant_tips, *child_b.descendant_tips})),
        subfamily_a_tips=child_a.descendant_tips,
        subfamily_b_tips=child_b.descendant_tips,
    )


def _mrca(node: TreeNode, tip_a: str, tip_b: str) -> TreeNode:
    for child in node.children:
        if tip_a in child.descendant_tips and tip_b in child.descendant_tips:
            return _mrca(child, tip_a, tip_b)
    return node


def _child_containing(node: TreeNode, tip: str) -> TreeNode:
    for child in node.children:
        if tip in child.descendant_tips:
            return child
    raise TreeError(f"internal error: {tip!r} not found under its own MRCA")  # unreachable
