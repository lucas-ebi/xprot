from __future__ import annotations

import pytest
from pydantic import ValidationError

from xprot.core.primitives import Diagnostic, RootingMethod, Severity


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


def test_choice_enum_constructs_from_its_value() -> None:
    assert RootingMethod("midpoint") is RootingMethod.MIDPOINT
    assert RootingMethod.MIDPOINT.value == "midpoint"
    assert str(RootingMethod.MIDPOINT) == "midpoint"
