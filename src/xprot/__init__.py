"""X-Prot: local, deterministic subfamily-conservation analysis for any protein family.

Pick an internal node of a phylogenetic tree and one representative leaf per child clade; X-Prot
proposes the residue changes that shift one representative toward the other based on how weighted
conservation differs between the clades. Every output is computational evidence, not a claim about
any real evolutionary or engineering process.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Label stamped on every result so a proposal is not mistaken for an empirical finding.
RECONSTRUCTION_EVIDENCE_LABEL = "computational evidence"

__all__ = ["RECONSTRUCTION_EVIDENCE_LABEL", "__version__"]
