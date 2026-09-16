"""Every exception X-Prot raises on bad input, in one place.

All derive from :class:`XProtError` (itself a :class:`ValueError`), so a caller can catch the whole
family with one ``except`` while the CLI still maps each subclass to its own exit code. Import them
from here, not from the module that raises them.
"""

from __future__ import annotations

__all__ = [
    "AlignmentError",
    "DesignError",
    "IdentifierError",
    "TreeError",
    "VocabularyError",
    "XProtError",
]


class XProtError(ValueError):
    """Base class for every X-Prot input or computation error."""


class AlignmentError(XProtError):
    """An alignment cannot be parsed or fails validation."""


class TreeError(XProtError):
    """A tree cannot be parsed, or a partition cannot be resolved."""


class IdentifierError(XProtError):
    """The alignment and tree do not map one-to-one over canonical ids."""


class DesignError(XProtError):
    """A transformation cannot be generated (bad representative, missing vocabulary, ...)."""


class VocabularyError(XProtError):
    """A vocabulary file is malformed."""
