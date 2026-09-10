"""Typed data structures and the deterministic analysis functions.

``xprot.core`` imports only the standard library, Biopython, NumPy, Pydantic, and PyYAML. It must
not import ``xprot.app``, ``xprot.cli``, ``xprot.gui``, or any CLI/GUI/server framework. This
boundary is checked by ``tests/unit/test_import_boundaries.py``.
"""
