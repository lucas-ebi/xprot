from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Committed project artifacts must not carry absolute source-machine paths.
SCANNED_DIRS = ["src", "class_tables"]
NEEDLES = ("/Users/", "/home/", "\\Users\\", "XPROT_HISTORY_DIR=/", "/private/tmp/")


@pytest.mark.parametrize("subdir", SCANNED_DIRS)
def test_no_absolute_machine_paths(subdir: str) -> None:
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / subdir).rglob("*")):
        if not path.is_file() or path.suffix in {".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle in NEEDLES:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {needle!r}")
    assert offenders == []
