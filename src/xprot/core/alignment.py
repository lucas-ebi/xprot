"""Alignment loading and the alignment-column coordinate map."""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from Bio import AlignIO

from xprot.core.errors import AlignmentError
from xprot.core.primitives import AmbiguityPolicy
from xprot.core.structures import Alignment, AlignmentRow, CoordinateMap

__all__ = [
    "CANONICAL_GAP",
    "DEFAULT_ALPHABET",
    "DEFAULT_GAP_SYMBOLS",
    "build_coordinate_map",
    "load_alignment",
    "parse_alignment",
]

CANONICAL_GAP = "-"
DEFAULT_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
DEFAULT_GAP_SYMBOLS: tuple[str, ...] = ("-", ".")

_FORMAT_BY_SUFFIX = {
    ".fasta": "fasta",
    ".fa": "fasta",
    ".faa": "fasta",
    ".fna": "fasta",
    ".afa": "fasta",
    ".sto": "stockholm",
    ".stk": "stockholm",
    ".stockholm": "stockholm",
    ".aln": "clustal",
    ".clustal": "clustal",
    ".clw": "clustal",
}


def build_coordinate_map(aligned: str, gap_symbols: frozenset[str]) -> CoordinateMap:
    """Map each 1-based column of ``aligned`` to an ungapped position and insertion anchor."""
    return CoordinateMap.from_aligned(aligned, gap_symbols)


def load_alignment(
    source: Path | str,
    *,
    fmt: str | None = None,
    alphabet: str = DEFAULT_ALPHABET,
    gap_symbols: Sequence[str] = DEFAULT_GAP_SYMBOLS,
    ambiguous: AmbiguityPolicy = AmbiguityPolicy.REJECT,
    ambiguity_map: dict[str, str] | None = None,
) -> Alignment:
    """Read a local MSA file and return an :class:`Alignment` in canonical form."""
    path = Path(source)
    resolved_fmt = fmt or _FORMAT_BY_SUFFIX.get(path.suffix.lower())
    if resolved_fmt is None:
        msg = f"cannot infer alignment format from {path.name!r}; pass fmt="
        raise AlignmentError(msg)
    return parse_alignment(
        path.read_text(encoding="utf-8"),
        resolved_fmt,
        alphabet=alphabet,
        gap_symbols=gap_symbols,
        ambiguous=ambiguous,
        ambiguity_map=ambiguity_map,
    )


def parse_alignment(
    text: str,
    fmt: str,
    *,
    alphabet: str = DEFAULT_ALPHABET,
    gap_symbols: Sequence[str] = DEFAULT_GAP_SYMBOLS,
    ambiguous: AmbiguityPolicy = AmbiguityPolicy.REJECT,
    ambiguity_map: dict[str, str] | None = None,
) -> Alignment:
    """Parse alignment ``text`` in ``fmt`` (``fasta`` / ``stockholm`` / ``clustal``)."""
    ambiguous = AmbiguityPolicy(ambiguous)
    try:
        records = list(AlignIO.read(io.StringIO(text), fmt))
    except Exception as exc:
        msg = f"could not parse {fmt} alignment: {exc}"
        raise AlignmentError(msg) from exc

    if not records:
        raise AlignmentError("alignment has no sequences")

    residues = set(alphabet)
    input_gaps = set(gap_symbols)
    mapping = ambiguity_map or {}
    lengths = {len(record.seq) for record in records}
    if len(lengths) != 1:
        raise AlignmentError(f"rows have unequal lengths: {sorted(lengths)}")
    if lengths == {0}:
        raise AlignmentError("alignment rows are empty")

    rows: list[AlignmentRow] = []
    seen_ids: set[str] = set()
    for ordinal, record in enumerate(records):
        parsed_id = record.id
        if parsed_id in seen_ids:
            raise AlignmentError(f"duplicate sequence id {parsed_id!r}")
        seen_ids.add(parsed_id)
        aligned = _canonicalise_row(
            str(record.seq),
            parsed_id=parsed_id,
            residues=residues,
            input_gaps=input_gaps,
            ambiguous=ambiguous,
            mapping=mapping,
        )
        rows.append(
            AlignmentRow(
                canonical_id=parsed_id,
                raw_header=record.description or parsed_id,
                aligned=aligned,
                coordinate_map=CoordinateMap.from_aligned(aligned, frozenset(CANONICAL_GAP)),
                source_ordinal=ordinal,
            )
        )

    return Alignment(rows=tuple(rows), alphabet=alphabet, gap=CANONICAL_GAP)


def _canonicalise_row(
    seq: str,
    *,
    parsed_id: str,
    residues: set[str],
    input_gaps: set[str],
    ambiguous: AmbiguityPolicy,
    mapping: dict[str, str],
) -> str:
    out: list[str] = []
    for column, char in enumerate(seq, start=1):
        if char in input_gaps:
            out.append(CANONICAL_GAP)
        elif char in residues:
            out.append(char)
        elif char in mapping:
            out.append(mapping[char])
        elif ambiguous is AmbiguityPolicy.LITERAL:
            out.append(char)
        else:
            msg = f"{parsed_id!r} column {column}: character {char!r} is not in the alphabet"
            raise AlignmentError(msg)
    return "".join(out)
