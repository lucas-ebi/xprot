from __future__ import annotations

from pathlib import Path

import pytest

from xprot.core.errors import VocabularyError
from xprot.core.vocabulary import load_vocabulary

TAYLOR = Path(__file__).resolve().parents[2] / "src" / "xprot" / "vocabulary" / "taylor-1986.yaml"


def test_load_taylor_vocabulary() -> None:
    table = load_vocabulary(TAYLOR)
    assert table["Basic"] == "HKR"
    assert set(table["Aromatic"]) == set("FYW")
    assert len(table) == 18


def test_rejects_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "b.yaml"
    bad.write_text("not: a vocabulary\n", encoding="utf-8")
    with pytest.raises(VocabularyError):
        load_vocabulary(bad)
    empty = tmp_path / "e.yaml"
    empty.write_text("classes: {}\n", encoding="utf-8")
    with pytest.raises(VocabularyError):
        load_vocabulary(empty)
