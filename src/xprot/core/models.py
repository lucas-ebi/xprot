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
    "Direction",
    "EventType",
    "FrozenModel",
    "LabelSource",
    "PartitionSemantics",
    "Role",
    "RootingMethod",
    "Severity",
    "SubfamilyLabel",
    "sort_diagnostics",
]


# Closed choice sets. Standalone string enums used as function parameters (StrEnum, so callers may
# also pass the bare string).


class PartitionSemantics(StrEnum):
    TWO_CHILD_CLADES = "two_child_clades"
    SELECTED_CLADE_VS_COMPLEMENT = "selected_clade_vs_complement"


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


class Direction(StrEnum):
    A_RECEIVES_B = "A_receives_B"
    B_RECEIVES_A = "B_receives_A"


class Role(StrEnum):
    RECIPIENT = "recipient"
    DONOR = "donor"


class Diagnostic(FrozenModel):
    """A stable, machine-keyed report of one validation or computation condition.

    ``code`` is the machine key; ``message`` and ``remediation`` are human text and must never be
    parsed. ``ids`` and ``columns`` locate the condition (canonical IDs and 1-based alignment
    columns).
    """

    code: str
    severity: Severity
    stage: str
    message: str
    ids: tuple[str, ...] = ()
    columns: tuple[int, ...] = ()
    remediation: str | None = None

    @property
    def sort_key(self) -> tuple[int, str, tuple[str, ...], tuple[int, ...], str]:
        """Canonical order key: severity, then code, ids, columns, message."""
        severity_rank = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}[self.severity]
        return (severity_rank, self.code, self.ids, self.columns, self.message)


def sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    """Return ``diagnostics`` in canonical order without mutating the input."""
    return sorted(diagnostics, key=lambda diagnostic: diagnostic.sort_key)
