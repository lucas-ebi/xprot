from __future__ import annotations

from pathlib import Path

import pytest

from xprot.core.classes import load_class_table
from xprot.core.errors import ClassTableError

TAYLOR = Path(__file__).resolve().parents[2] / "class_tables" / "taylor-1986.yaml"


def test_load_taylor_table() -> None:
    table = load_class_table(TAYLOR)
    assert table["Basic"] == "HKR"
    assert set(table["Aromatic"]) == set("FYW")
    assert len(table) == 18


def test_rejects_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "b.yaml"
    bad.write_text("not: a class table\n", encoding="utf-8")
    with pytest.raises(ClassTableError):
        load_class_table(bad)
    empty = tmp_path / "e.yaml"
    empty.write_text("classes: {}\n", encoding="utf-8")
    with pytest.raises(ClassTableError):
        load_class_table(empty)
