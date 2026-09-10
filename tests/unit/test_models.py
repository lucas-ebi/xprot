from __future__ import annotations

import pytest
from pydantic import ValidationError

from xprot.core.models import (
    Diagnostic,
    PartitionSemantics,
    Severity,
    sort_diagnostics,
)


def test_diagnostic_is_frozen_and_rejects_unknown_fields() -> None:
    diag = Diagnostic(code="C", severity=Severity.ERROR, stage="s", message="m")
    with pytest.raises(ValidationError):
        diag.code = "D"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Diagnostic.model_validate(
            {"code": "C", "severity": "error", "stage": "s", "message": "m", "extra": 1}
        )


def test_diagnostic_round_trips_and_enum_serialises_to_value() -> None:
    diag = Diagnostic(code="C", severity=Severity.WARNING, stage="s", message="m", columns=(2,))
    dumped = diag.model_dump(mode="json")
    assert dumped["severity"] == "warning"
    assert Diagnostic.model_validate(dumped) == diag


def test_sort_diagnostics_order() -> None:
    unsorted = [
        Diagnostic(code="B", severity=Severity.WARNING, stage="s", message="m"),
        Diagnostic(code="A", severity=Severity.ERROR, stage="s", message="m", columns=(5,)),
        Diagnostic(code="A", severity=Severity.ERROR, stage="s", message="m", columns=(2,)),
    ]
    ordered = sort_diagnostics(unsorted)
    assert [(d.code, d.columns) for d in ordered] == [("A", (2,)), ("A", (5,)), ("B", ())]


def test_choice_enum_constructs_from_its_value() -> None:
    assert PartitionSemantics("two_child_clades") is PartitionSemantics.TWO_CHILD_CLADES
    assert PartitionSemantics.TWO_CHILD_CLADES.value == "two_child_clades"
    assert str(PartitionSemantics.TWO_CHILD_CLADES) == "two_child_clades"
