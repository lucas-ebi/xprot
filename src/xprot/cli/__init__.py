"""The ``x-prot`` command-line tool.

Exit codes: ``0`` success, ``2`` usage error (argparse itself), ``3`` the alignment, tree, or class
table could not be parsed, ``4`` the alignment/tree identifiers do not map one-to-one or the
requested node cannot be resolved, ``5`` the transformation could not be computed (e.g. recipient
and donor in the same subfamily).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from xprot.app import RunResult, run_design
from xprot.core.errors import (
    AlignmentError,
    ClassTableError,
    DesignError,
    IdentifierError,
    TreeError,
)
from xprot.core.models import NodeSelector
from xprot.render import (
    render_diagnostics_json,
    render_events_json,
    render_events_tsv,
    render_pairwise,
    render_summary_json,
    render_transformed_fasta,
)

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.dry_run and args.out is None:
        parser.error("--out is required unless --dry-run is set")
    return _design(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="x-prot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    design = subparsers.add_parser(
        "design", help="propose residue changes moving a recipient toward a donor clade"
    )
    design.add_argument("--alignment", required=True, type=Path)
    design.add_argument("--tree", required=True, type=Path)
    node = design.add_mutually_exclusive_group(required=True)
    node.add_argument("--node-tips", help="comma-separated tip ids of the internal node")
    node.add_argument("--node-label", help="label of the internal node")
    design.add_argument("--recipient", required=True)
    design.add_argument("--donor", required=True)
    design.add_argument("--out", type=Path, help="directory to write outputs into")
    design.add_argument("--dry-run", action="store_true", help="run without writing any files")
    return parser


def _design(args: argparse.Namespace) -> int:
    if args.node_tips is not None:
        tips = frozenset(t.strip() for t in args.node_tips.split(",") if t.strip())
        node = NodeSelector(tips=tips)
    else:
        node = NodeSelector(label=args.node_label)

    try:
        result = run_design(
            args.alignment, args.tree, node, recipient=args.recipient, donor=args.donor
        )
    except (AlignmentError, ClassTableError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except (TreeError, IdentifierError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except DesignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5

    if not args.dry_run:
        _write_outputs(args.out, result)
    _print_summary(result)
    return 0


def _write_outputs(out: Path, result: RunResult) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "transformed.fasta").write_bytes(render_transformed_fasta(result.transformed))
    (out / "events.tsv").write_bytes(render_events_tsv(result.transformed.events))
    (out / "events.json").write_bytes(render_events_json(result.transformed.events))
    (out / "pairwise.txt").write_bytes(render_pairwise(result.transformed))
    (out / "summary.json").write_bytes(
        render_summary_json(
            result.transformed, result.partition, is_bijective=result.id_mapping.is_bijective
        )
    )
    (out / "diagnostics.json").write_bytes(
        render_diagnostics_json(result.id_mapping.diagnostics, result.transformed.diagnostics)
    )


def _print_summary(result: RunResult) -> None:
    t = result.transformed
    print(
        f"{t.recipient_id} -> {t.donor_id}: "
        f"{t.substitutions} substitutions, {t.insertions} insertions, {t.deletions} deletions"
    )
