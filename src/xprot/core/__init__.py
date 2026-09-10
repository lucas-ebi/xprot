"""Typed models and deterministic computational functions.

``xprot.core`` may import only the standard library, Biopython, Pydantic 2, and PyYAML. It must not
import ``xprot.evidence``, ``xprot.cli``, ``xprot.gui``, or any CLI/GUI framework. This boundary is
enforced by ``tests/unit/test_import_boundaries.py``.
"""
