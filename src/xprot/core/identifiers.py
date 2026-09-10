"""Identifier canonicalisation and the alignment/tree mapping.

Three concepts are kept distinct: the **raw** label (header text / tip name), the **parsed** label
(the chosen label source applied), and the **canonical** id (parsed label, optionally rewritten
through an alias table). The alignment rows and tree tips must map one-to-one over canonical ids.
"""

from __future__ import annotations

from xprot.core.models import Diagnostic, FrozenModel, LabelSource, Severity
from xprot.core.structures import Alignment, Phylogeny

__all__ = ["IdentifierMapping", "IdentifierRecord", "resolve_id_mapping"]


class IdentifierRecord(FrozenModel):
    source_kind: str  # "alignment_row" | "tree_tip"
    raw_label: str
    parsed_label: str
    canonical_id: str
    status: str  # "matched" | "unmatched"


class IdentifierMapping(FrozenModel):
    records: tuple[IdentifierRecord, ...]
    diagnostics: tuple[Diagnostic, ...]
    is_bijective: bool


def _parsed(raw: str, source: LabelSource) -> str:
    if source is LabelSource.FIRST_TOKEN:
        tokens = raw.split()
        return tokens[0] if tokens else raw
    return raw


def _build_side(
    raw_labels: list[str],
    source: LabelSource,
    aliases: dict[str, str],
    kind: str,
) -> tuple[list[tuple[str, str, str]], list[Diagnostic]]:
    """Return ``(raw, parsed, canonical)`` triples and any structural diagnostics for one side."""
    triples: list[tuple[str, str, str]] = []
    diagnostics: list[Diagnostic] = []
    seen_raw: set[str] = set()
    canonical_of: dict[str, str] = {}
    for raw in raw_labels:
        if raw in seen_raw:
            diagnostics.append(
                Diagnostic(
                    code="IDMAP_DUPLICATE_RAW",
                    severity=Severity.ERROR,
                    stage="identifiers",
                    message=f"{kind}: duplicate raw label {raw!r}",
                    ids=(raw,),
                )
            )
            continue
        seen_raw.add(raw)
        parsed = _parsed(raw, source)
        canonical = aliases.get(parsed, parsed)
        for other_raw, other_canonical in canonical_of.items():
            if other_canonical == canonical:
                diagnostics.append(
                    Diagnostic(
                        code="IDMAP_CANONICAL_COLLISION",
                        severity=Severity.ERROR,
                        stage="identifiers",
                        message=f"{kind}: {raw!r} and {other_raw!r} both map to {canonical!r}",
                        ids=(canonical,),
                    )
                )
        canonical_of[raw] = canonical
        triples.append((raw, parsed, canonical))
    return triples, diagnostics


def resolve_id_mapping(
    alignment: Alignment,
    tree: Phylogeny,
    *,
    alignment_label_source: LabelSource = LabelSource.FIRST_TOKEN,
    tree_label_source: LabelSource = LabelSource.FULL_LABEL,
    aliases: dict[str, str] | None = None,
) -> IdentifierMapping:
    """Canonicalise both sides and require an exact one-to-one alignment↔tree mapping."""
    alias_table = aliases or {}
    aln_raw = [row.raw_header for row in alignment.rows]
    tip_raw = list(tree.tips)
    aln_triples, diagnostics = _build_side(
        aln_raw, alignment_label_source, alias_table, "alignment_row"
    )
    tip_triples, tip_diags = _build_side(tip_raw, tree_label_source, alias_table, "tree_tip")
    diagnostics += tip_diags

    aln_ids = {canonical for _, _, canonical in aln_triples}
    tip_ids = {canonical for _, _, canonical in tip_triples}
    for missing in sorted(aln_ids - tip_ids):
        diagnostics.append(
            Diagnostic(
                code="IDMAP_ALIGNMENT_ROW_WITHOUT_TIP",
                severity=Severity.ERROR,
                stage="identifiers",
                message=f"alignment id {missing!r} has no matching tree tip",
                ids=(missing,),
            )
        )
    for missing in sorted(tip_ids - aln_ids):
        diagnostics.append(
            Diagnostic(
                code="IDMAP_TIP_WITHOUT_ALIGNMENT_ROW",
                severity=Severity.ERROR,
                stage="identifiers",
                message=f"tree tip {missing!r} has no matching alignment row",
                ids=(missing,),
            )
        )

    matched = aln_ids & tip_ids
    records = tuple(
        IdentifierRecord(
            source_kind=kind,
            raw_label=raw,
            parsed_label=parsed,
            canonical_id=canonical,
            status="matched" if canonical in matched else "unmatched",
        )
        for kind, triples in (("alignment_row", aln_triples), ("tree_tip", tip_triples))
        for raw, parsed, canonical in triples
    )
    is_bijective = not any(d.severity is Severity.ERROR for d in diagnostics)
    return IdentifierMapping(
        records=records, diagnostics=tuple(diagnostics), is_bijective=is_bijective
    )
