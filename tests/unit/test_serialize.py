from __future__ import annotations

import json
from fractions import Fraction

import pytest

from xprot.core.models import Diagnostic, Severity
from xprot.core.serialize import canonical_json, to_builtin, write_tsv


def test_canonical_json_is_key_order_invariant() -> None:
    a = {"b": 1, "a": 2, "n": {"z": 1, "y": 2}}
    b = {"n": {"y": 2, "z": 1}, "a": 2, "b": 1}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_shape() -> None:
    out = canonical_json({"k": "café", "n": 1})
    assert out.endswith(b"\n")
    assert b": " not in out and b", " not in out
    assert "café".encode() in out and b"\\u" not in out


def test_canonical_json_rejects_nonfinite() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            canonical_json({"x": bad})


def test_fraction_renders_as_string() -> None:
    assert json.loads(canonical_json({"f": Fraction(1, 3)})) == {"f": "1/3"}


def test_pydantic_and_sets() -> None:
    assert to_builtin({"s": {"c", "a", "b"}}) == {"s": ["a", "b", "c"]}
    d = Diagnostic(code="X", severity=Severity.WARNING, stage="t", message="m")
    assert json.loads(canonical_json(d))["severity"] == "warning"


def test_write_tsv() -> None:
    assert write_tsv(("a", "b"), [(1, 2), ("x", None)]) == b"a\tb\n1\t2\nx\t\n"
    with pytest.raises(ValueError):
        write_tsv(("a", "b"), [(1,)])
    with pytest.raises(ValueError):
        write_tsv(("a",), [("has\ttab",)])
