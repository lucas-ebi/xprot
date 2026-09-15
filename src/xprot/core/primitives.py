"""Shared typed primitives: a frozen model base, stable enums, and diagnostics.

Coordinate conventions, applied everywhere positions are recorded:

* **Alignment column** -- 1-based position in the original MSA. Earlier events never change it.
* **Source position** -- 1-based ungapped position in the selected recipient before transformation.
* **Transformed position** -- 1-based position in the emitted sequence.
* **Insertion** -- source position is absent; the insertion anchor is the preceding source
  position, with ``0`` meaning the N terminus.
* **Deletion** -- source position is present; transformed position is absent.
* **Substitution** -- both source and transformed positions are present.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "AmbiguityPolicy",
    "Denominator",
    "DesignMode",
    "Diagnostic",
    "EventType",
    "FrozenModel",
    "LabelSource",
    "RootingMethod",
    "Severity",
    "SubfamilyLabel",
]


# Closed choice sets. Standalone string enums used as function parameters (StrEnum, so callers may
# also pass the bare string).


class RootingMethod(StrEnum):
    AS_SUPPLIED = "as_supplied"
    MIDPOINT = "midpoint"
    SPECIFIED_OUTGROUP = "specified_outgroup"


class AmbiguityPolicy(StrEnum):
    REJECT = "reject"
    LITERAL = "literal"
    MAP = "map"


class Denominator(StrEnum):
    ALL_SUBFAMILY_WEIGHTS = "all_subfamily_weights"
    NON_GAP_WEIGHTS = "non_gap_weights"


class DesignMode(StrEnum):
    LITERAL = "literal"
    EXPANDED = "expanded"


class LabelSource(StrEnum):
    FIRST_TOKEN = "first_token"
    FULL_LABEL = "full_label"


class FrozenModel(BaseModel):
    """Immutable model that rejects unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class EventType(StrEnum):
    SUBSTITUTION = "substitution"
    INSERTION = "insertion"
    DELETION = "deletion"
    NO_EVENT = "no_event"


class SubfamilyLabel(StrEnum):
    A = "subfamily_a"
    B = "subfamily_b"


class Diagnostic(FrozenModel):
    """A stable, machine-keyed report of one validation or computation condition.

    ``code`` is the machine key; ``message`` is human text and must never be parsed. ``ids`` and
    ``columns`` locate the condition (canonical IDs and 1-based alignment columns).
    """

    code: str
    severity: Severity
    stage: str
    message: str
    ids: tuple[str, ...] = ()
    columns: tuple[int, ...] = ()
