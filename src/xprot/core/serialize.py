"""Deterministic byte emitters: canonical JSON and TSV.

Same logical content, same bytes: keys sorted recursively, UTF-8, LF line endings, no NaN/infinity,
exact numbers rendered as strings rather than floats.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from pathlib import PurePath
from typing import Any

__all__ = ["canonical_json", "to_builtin", "write_tsv"]

_FORBIDDEN_TSV = ("\t", "\n", "\r")


def to_builtin(obj: Any) -> Any:
    """Recursively convert ``obj`` to JSON-safe built-ins."""
    if isinstance(obj, Fraction):
        return f"{obj.numerator}/{obj.denominator}"
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Enum):
        return to_builtin(obj.value)
    if isinstance(obj, PurePath):
        return str(obj)
    if obj is None or isinstance(obj, (str, int, bool, float)):
        return obj
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump) and hasattr(type(obj), "model_fields"):
        return to_builtin(model_dump(mode="json"))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_builtin(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return sorted(to_builtin(x) for x in obj)
    if isinstance(obj, (Sequence, Iterable)):
        return [to_builtin(x) for x in obj]
    msg = f"cannot serialize {type(obj).__name__!r}"
    raise TypeError(msg)


def canonical_json(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical JSON bytes: sorted keys, compact, UTF-8, LF-terminated."""
    text = json.dumps(
        to_builtin(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8") + b"\n"


def write_tsv(header: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    """Render a TSV table: fixed column count, LF endings, trailing newline.

    Empty fields are the empty string. A tab, CR, or LF in any cell raises :class:`ValueError`, as
    does a row whose length differs from ``header``.
    """
    width = len(header)
    lines = ["\t".join(_cell(c) for c in header)]
    for index, row in enumerate(rows):
        row = list(row)
        if len(row) != width:
            msg = f"row {index} has {len(row)} fields, expected {width}"
            raise ValueError(msg)
        lines.append("\t".join(_cell(c) for c in row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    for bad in _FORBIDDEN_TSV:
        if bad in text:
            msg = f"TSV cell may not contain {bad!r}: {text!r}"
            raise ValueError(msg)
    return text
