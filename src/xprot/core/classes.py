"""Load a physicochemical-class table (a YAML mapping of class name -> residue letters)."""

from __future__ import annotations

from pathlib import Path

import yaml

from xprot.core.errors import XProtError

__all__ = ["ClassTableError", "load_class_table"]


class ClassTableError(XProtError):
    """A class-table file is malformed."""


def load_class_table(path: Path | str) -> dict[str, str]:
    """Return ``{class name: "residues"}`` from a YAML file with a top-level ``classes:`` mapping.

    Overlap between classes is expected. Duplicate names or an empty class are errors.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "classes" not in raw:
        raise ClassTableError("class table must be a mapping with a top-level 'classes' key")
    classes = raw["classes"]
    if not isinstance(classes, dict) or not classes:
        raise ClassTableError("'classes' must be a non-empty mapping")

    table: dict[str, str] = {}
    for name, members in classes.items():
        key = str(name)
        if key in table:
            raise ClassTableError(f"duplicate class name {key!r}")
        residues = "".join(str(members).split())
        if not residues:
            raise ClassTableError(f"class {key!r} has no residues")
        table[key] = residues
    return table
