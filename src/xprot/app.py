"""Orchestration: chain the core pipeline stages into one call."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from xprot.core.alignment import DEFAULT_ALPHABET, DEFAULT_GAP_SYMBOLS, load_alignment
from xprot.core.classes import load_class_table
from xprot.core.design import generate_transformation
from xprot.core.errors import IdentifierError
from xprot.core.identifiers import IdentifierMapping, resolve_id_mapping
from xprot.core.models import CanonicalPartition, TransformedResult
from xprot.core.primitives import (
    AmbiguityPolicy,
    Denominator,
    DesignMode,
    LabelSource,
    RootingMethod,
    Severity,
)
from xprot.core.profile import DEFAULT_THRESHOLD, calculate_profiles, determine_typical_states
from xprot.core.tree import load_tree, resolve_partition
from xprot.core.weights import calculate_henikoff_weights

__all__ = ["RunResult", "run_design"]


@dataclass(frozen=True, slots=True)
class RunResult:
    id_mapping: IdentifierMapping
    partition: CanonicalPartition
    transformed: TransformedResult


def run_design(
    alignment_source: Path | str,
    tree_source: Path | str,
    *,
    recipient: str,
    donor: str,
    alignment_fmt: str | None = None,
    tree_fmt: str | None = None,
    alphabet: str = DEFAULT_ALPHABET,
    gap_symbols: Sequence[str] = DEFAULT_GAP_SYMBOLS,
    ambiguous: AmbiguityPolicy = AmbiguityPolicy.REJECT,
    ambiguity_map: dict[str, str] | None = None,
    rooting: RootingMethod = RootingMethod.AS_SUPPLIED,
    outgroup: Sequence[str] = (),
    alignment_label_source: LabelSource = LabelSource.FIRST_TOKEN,
    tree_label_source: LabelSource = LabelSource.FULL_LABEL,
    aliases: dict[str, str] | None = None,
    denominator: Denominator = Denominator.ALL_SUBFAMILY_WEIGHTS,
    occupancy_threshold: float | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    typical_gap: bool = False,
    mode: DesignMode = DesignMode.LITERAL,
    deletions: bool = False,
    class_table: Mapping[str, str] | Path | str | None = None,
) -> RunResult:
    """Load, map, partition, weight, profile, and design a transformation, in one call.

    ``alignment_source`` and ``tree_source`` are local file paths. ``class_table`` may be a
    ``{name: residues}`` mapping or a path to a YAML file in the same shape as
    :func:`xprot.core.classes.load_class_table`. Raises :class:`IdentifierError` if the alignment
    and tree do not map one-to-one over canonical ids.
    """
    resolved_class_table = (
        load_class_table(class_table) if isinstance(class_table, (Path, str)) else class_table
    )

    alignment = load_alignment(
        alignment_source,
        fmt=alignment_fmt,
        alphabet=alphabet,
        gap_symbols=gap_symbols,
        ambiguous=ambiguous,
        ambiguity_map=ambiguity_map,
    )
    tree = load_tree(tree_source, fmt=tree_fmt, rooting=rooting, outgroup=outgroup)

    id_mapping = resolve_id_mapping(
        alignment,
        tree,
        alignment_label_source=alignment_label_source,
        tree_label_source=tree_label_source,
        aliases=aliases,
    )
    if not id_mapping.is_bijective:
        codes = sorted({d.code for d in id_mapping.diagnostics if d.severity is Severity.ERROR})
        msg = f"alignment and tree identifiers do not map one-to-one: {', '.join(codes)}"
        raise IdentifierError(msg)

    partition = resolve_partition(tree, recipient, donor)
    weights = calculate_henikoff_weights(alignment)
    profiles = calculate_profiles(
        alignment,
        partition,
        weights,
        denominator=denominator,
        occupancy_threshold=occupancy_threshold,
        class_table=resolved_class_table,
    )
    typical_states = determine_typical_states(
        profiles, threshold=threshold, typical_gap=typical_gap
    )
    transformed = generate_transformation(
        alignment,
        partition,
        profiles,
        typical_states,
        recipient=recipient,
        donor=donor,
        mode=mode,
        deletions=deletions,
        class_table=resolved_class_table,
    )
    return RunResult(id_mapping=id_mapping, partition=partition, transformed=transformed)
