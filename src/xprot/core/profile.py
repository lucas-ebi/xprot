"""Weighted residue and class profiles, column occupancy, and typicality."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np

from xprot.core.models import (
    Alignment,
    CanonicalPartition,
    ClassProfile,
    ProfileSet,
    ResidueProfile,
    SequenceWeight,
    TypicalState,
    TypicalStateSet,
)
from xprot.core.primitives import Denominator, Diagnostic, Severity, SubfamilyLabel

__all__ = ["DEFAULT_THRESHOLD", "calculate_profiles", "determine_typical_states"]

DEFAULT_THRESHOLD = 0.9


def calculate_profiles(
    alignment: Alignment,
    partition: CanonicalPartition,
    weights: tuple[SequenceWeight, ...],
    *,
    denominator: Denominator = Denominator.ALL_SUBFAMILY_WEIGHTS,
    occupancy_threshold: float | None = None,
    vocabulary: Mapping[str, Iterable[str]] | None = None,
) -> ProfileSet:
    """Per-column weighted residue (and optional class) profiles for both subfamilies.

    ``weights`` are the global normalized Henikoff weights; each subfamily reuses the restricted
    slice. Rows are matched to tips by ``AlignmentRow.canonical_id``.
    """
    denominator = Denominator(denominator)
    weight_by_id = {w.canonical_id: w.normalized for w in weights}
    gap = alignment.gap
    states_full = np.array([list(row.aligned) for row in alignment.rows])  # (n_rows, length)
    length = alignment.length
    residue_order = [*alignment.alphabet, gap]

    # Column occupancy over the whole alignment (raw non-gap row fraction).
    non_gap_full = (states_full != gap).sum(axis=0) / states_full.shape[0]
    if occupancy_threshold is None:
        included = frozenset(range(1, length + 1))
    else:
        included = frozenset(
            j for j in range(1, length + 1) if non_gap_full[j - 1] >= occupancy_threshold
        )

    residue_profiles: list[ResidueProfile] = []
    class_profiles: list[ClassProfile] = []
    diagnostics: list[Diagnostic] = []

    for label, tips in (
        (SubfamilyLabel.A, partition.subfamily_a_tips),
        (SubfamilyLabel.B, partition.subfamily_b_tips),
    ):
        member_rows = [i for i, row in enumerate(alignment.rows) if row.canonical_id in set(tips)]
        if not member_rows:
            continue
        member_states = states_full[member_rows, :]  # (m, length)
        member_w = np.array(
            [weight_by_id.get(alignment.rows[i].canonical_id, 0.0) for i in member_rows]
        )
        total_w = float(member_w.sum())
        non_gap_w = (member_states != gap).T @ member_w  # (length,)
        non_gap_count = (member_states != gap).sum(axis=0)  # (length,)

        numerators = {residue: (member_states == residue).T @ member_w for residue in residue_order}

        for column in sorted(included):
            j = column - 1
            denom = (
                total_w if denominator is Denominator.ALL_SUBFAMILY_WEIGHTS else float(non_gap_w[j])
            )
            if denom == 0.0:
                diagnostics.append(
                    Diagnostic(
                        code="PROFILE_ZERO_DENOMINATOR",
                        severity=Severity.WARNING,
                        stage="profile",
                        message=f"{label.value} column {column}: denominator is zero; skipped",
                        ids=(label.value,),
                        columns=(column,),
                    )
                )
                continue
            frequencies = {
                residue: float(numerators[residue][j]) / denom
                for residue in residue_order
                if numerators[residue][j] > 0
            }
            residue_profiles.append(
                ResidueProfile(
                    column=column,
                    subfamily=label,
                    frequencies=frequencies,
                    denominator=denom,
                    occupancy=float(non_gap_count[j]) / len(member_rows),
                )
            )
            if vocabulary:
                class_freqs = {
                    name: sum(frequencies.get(r, 0.0) for r in members)
                    for name, members in vocabulary.items()
                }
                class_profiles.append(
                    ClassProfile(
                        column=column,
                        subfamily=label,
                        frequencies={n: f for n, f in class_freqs.items() if f > 0},
                    )
                )

    return ProfileSet(
        residues=tuple(residue_profiles),
        classes=tuple(class_profiles),
        included_columns=included,
        diagnostics=tuple(diagnostics),
    )


def determine_typical_states(
    profiles: ProfileSet,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    typical_gap: bool = False,
    gap: str = "-",
) -> TypicalStateSet:
    """States whose weighted frequency is strictly greater than ``threshold``."""
    states: list[TypicalState] = []
    for residue_profile in profiles.residues:
        for state, frequency in residue_profile.frequencies.items():
            if frequency > threshold and (typical_gap or state != gap):
                states.append(
                    TypicalState(
                        residue_profile.column, residue_profile.subfamily, state, False, frequency
                    )
                )
    for class_profile in profiles.classes:
        for name, frequency in class_profile.frequencies.items():
            if frequency > threshold:
                states.append(
                    TypicalState(
                        class_profile.column, class_profile.subfamily, name, True, frequency
                    )
                )
    return TypicalStateSet(states=tuple(states))
