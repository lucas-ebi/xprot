"""Full-alignment Henikoff & Henikoff position-based sequence weights.

The canonical gap is a state like any other, so every column's contributions sum to one and the
per-row weight is just its mean per-column contribution — normalized by construction.
"""

from __future__ import annotations

import numpy as np

from xprot.core.structures import Alignment, SequenceWeight

__all__ = ["calculate_henikoff_weights"]


def calculate_henikoff_weights(alignment: Alignment) -> tuple[SequenceWeight, ...]:
    """One :class:`SequenceWeight` per row (canonical order); normalized weights sum to one."""
    n_rows = len(alignment.rows)
    length = alignment.length
    if n_rows == 0 or length == 0:
        msg = "alignment has no residues to weight"
        raise ValueError(msg)

    matrix = np.array([list(row.aligned) for row in alignment.rows])  # (n_rows, length), '<U1'
    contributions = np.zeros((n_rows, length), dtype=np.float64)
    for column in range(length):
        _, inverse, counts = np.unique(matrix[:, column], return_inverse=True, return_counts=True)
        distinct = counts.size
        contributions[:, column] = 1.0 / (distinct * counts[inverse])

    unnormalized = contributions.sum(axis=1)
    normalized = unnormalized / length
    return tuple(
        SequenceWeight(
            canonical_id=row.canonical_id,
            unnormalized=float(unnormalized[i]),
            normalized=float(normalized[i]),
        )
        for i, row in enumerate(alignment.rows)
    )
