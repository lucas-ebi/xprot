"""Orchestration: chain the core pipeline stages into one call."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from xprot.core.alignment import DEFAULT_ALPHABET, DEFAULT_GAP_SYMBOLS, load_alignment
from xprot.core.design import generate_transformation
from xprot.core.errors import AlignmentError, IdentifierError, TreeError
from xprot.core.identifiers import IdentifierMapping, resolve_id_mapping
from xprot.core.models import (
    Alignment,
    CanonicalPartition,
    Phylogeny,
    ProfileSet,
    SequenceWeight,
    TransformedResult,
    TypicalStateSet,
)
from xprot.core.primitives import (
    AmbiguityPolicy,
    Denominator,
    DesignMode,
    LabelSource,
    RootingMethod,
    Severity,
)
from xprot.core.profile import DEFAULT_THRESHOLD, calculate_profiles, determine_typical_states
from xprot.core.tree import load_tree, resolve_partition
from xprot.core.vocabulary import load_vocabulary
from xprot.core.weights import calculate_henikoff_weights

__all__ = ["CachedRunner", "RunResult", "run_design"]


@dataclass(frozen=True, slots=True)
class RunResult:
    id_mapping: IdentifierMapping
    partition: CanonicalPartition
    transformed: TransformedResult


def run_design(
    alignment_source: Path | str,
    tree_source: Path | str,
    *,
    recipient: str,
    donor: str,
    alignment_fmt: str | None = None,
    tree_fmt: str | None = None,
    alphabet: str = DEFAULT_ALPHABET,
    gap_symbols: Sequence[str] = DEFAULT_GAP_SYMBOLS,
    ambiguous: AmbiguityPolicy = AmbiguityPolicy.REJECT,
    ambiguity_map: dict[str, str] | None = None,
    rooting: RootingMethod = RootingMethod.AS_SUPPLIED,
    outgroup: Sequence[str] = (),
    alignment_label_source: LabelSource = LabelSource.FIRST_TOKEN,
    tree_label_source: LabelSource = LabelSource.FULL_LABEL,
    aliases: dict[str, str] | None = None,
    denominator: Denominator = Denominator.ALL_SUBFAMILY_WEIGHTS,
    occupancy_threshold: float | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    typical_gap: bool = False,
    mode: DesignMode = DesignMode.LITERAL,
    deletions: bool = False,
    vocabulary: Mapping[str, str] | Path | str | None = None,
) -> RunResult:
    """Load, map, partition, weight, profile, and design a transformation, in one call.

    ``alignment_source`` and ``tree_source`` are local file paths. ``vocabulary`` may be a
    ``{name: residues}`` mapping or a path to a YAML file in the same shape as
    :func:`xprot.core.vocabulary.load_vocabulary`. Raises :class:`IdentifierError` if the alignment
    and tree do not map one-to-one over canonical ids.

    A single call needs nothing from :class:`CachedRunner` beyond this one pipeline run, which is
    all this function is: a throwaway ``CachedRunner`` whose cache never gets a second chance to
    be used.
    """
    return CachedRunner().run(
        alignment_source,
        tree_source,
        recipient=recipient,
        donor=donor,
        alignment_fmt=alignment_fmt,
        tree_fmt=tree_fmt,
        alphabet=alphabet,
        gap_symbols=gap_symbols,
        ambiguous=ambiguous,
        ambiguity_map=ambiguity_map,
        rooting=rooting,
        outgroup=outgroup,
        alignment_label_source=alignment_label_source,
        tree_label_source=tree_label_source,
        aliases=aliases,
        denominator=denominator,
        occupancy_threshold=occupancy_threshold,
        threshold=threshold,
        typical_gap=typical_gap,
        mode=mode,
        deletions=deletions,
        vocabulary=vocabulary,
    )


class CachedRunner:
    """Same pipeline as :func:`run_design`, with each stage memoized against its own inputs.

    Useful for a caller making many related calls -- a threshold sweep, or comparing several
    donor/recipient pairs on one alignment/tree -- where repeating the whole chain from scratch
    every time is wasted work. The tree partition and weighted profiles are symmetric in which of
    the two tips plays donor vs. recipient, so swapping ``recipient``/``donor`` between two calls
    reuses both untouched and only reruns the transformation itself.

    Each instance holds its own cache and is not safe to call from multiple threads at once. A
    single call to :func:`run_design` needs nothing from this class -- it exists for repeated use
    across the lifetime of one ``CachedRunner`` instance.
    """

    def __init__(self) -> None:
        self._aln_key: object = None
        self._aln_value: tuple[Alignment, tuple[SequenceWeight, ...]] | None = None
        self._tree_key: object = None
        self._tree_value: Phylogeny | None = None
        self._profile_key: object = None
        self._profile_value: tuple[CanonicalPartition, ProfileSet] | None = None
        self._typical_key: object = None
        self._typical_value: TypicalStateSet | None = None

    def run(
        self,
        alignment_source: Path | str,
        tree_source: Path | str,
        *,
        recipient: str,
        donor: str,
        alignment_fmt: str | None = None,
        tree_fmt: str | None = None,
        alphabet: str = DEFAULT_ALPHABET,
        gap_symbols: Sequence[str] = DEFAULT_GAP_SYMBOLS,
        ambiguous: AmbiguityPolicy = AmbiguityPolicy.REJECT,
        ambiguity_map: dict[str, str] | None = None,
        rooting: RootingMethod = RootingMethod.AS_SUPPLIED,
        outgroup: Sequence[str] = (),
        alignment_label_source: LabelSource = LabelSource.FIRST_TOKEN,
        tree_label_source: LabelSource = LabelSource.FULL_LABEL,
        aliases: dict[str, str] | None = None,
        denominator: Denominator = Denominator.ALL_SUBFAMILY_WEIGHTS,
        occupancy_threshold: float | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        typical_gap: bool = False,
        mode: DesignMode = DesignMode.LITERAL,
        deletions: bool = False,
        vocabulary: Mapping[str, str] | Path | str | None = None,
    ) -> RunResult:
        """Same parameters and return type as :func:`run_design`."""
        resolved_vocabulary = (
            load_vocabulary(vocabulary) if isinstance(vocabulary, (Path, str)) else vocabulary
        )
        vocabulary_key = tuple(sorted(resolved_vocabulary.items())) if resolved_vocabulary else None

        # Both sides key on the path *and* its current text: a caller reusing the same path for
        # successive edits (as the browser worker does) can't be told apart by path alone -- and
        # the path still matters on its own, since it's what alignment_fmt/tree_fmt being unset
        # falls back to for format detection. Wrapped the same way load_alignment/load_tree wrap
        # their own read, so a missing/unreadable file raises the same error type either way.
        try:
            alignment_text = Path(alignment_source).read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"could not read {alignment_source}: {exc}"
            raise AlignmentError(msg) from exc
        aln_key = (
            str(alignment_source),
            alignment_text,
            alignment_fmt,
            alphabet,
            tuple(gap_symbols),
            AmbiguityPolicy(ambiguous),
            tuple(sorted((ambiguity_map or {}).items())),
        )
        if aln_key != self._aln_key:
            alignment = load_alignment(
                alignment_source,
                fmt=alignment_fmt,
                alphabet=alphabet,
                gap_symbols=gap_symbols,
                ambiguous=ambiguous,
                ambiguity_map=ambiguity_map,
            )
            weights = calculate_henikoff_weights(alignment)
            self._aln_key, self._aln_value = aln_key, (alignment, weights)
        assert self._aln_value is not None
        alignment, weights = self._aln_value

        try:
            tree_text = Path(tree_source).read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"could not read {tree_source}: {exc}"
            raise TreeError(msg) from exc
        tree_key = (str(tree_source), tree_text, tree_fmt, rooting, tuple(outgroup))
        if tree_key != self._tree_key:
            tree = load_tree(tree_source, fmt=tree_fmt, rooting=rooting, outgroup=outgroup)
            self._tree_key, self._tree_value = tree_key, tree
        assert self._tree_value is not None
        tree = self._tree_value

        id_mapping = resolve_id_mapping(
            alignment,
            tree,
            alignment_label_source=alignment_label_source,
            tree_label_source=tree_label_source,
            aliases=aliases,
        )
        if not id_mapping.is_bijective:
            codes = sorted({d.code for d in id_mapping.diagnostics if d.severity is Severity.ERROR})
            msg = f"alignment and tree identifiers do not map one-to-one: {', '.join(codes)}"
            raise IdentifierError(msg)

        # frozenset, not a tuple: the partition and per-clade profiles are symmetric in which
        # tip plays donor vs. recipient, so a swap hits this cache exactly like an unchanged
        # rerun.
        profile_key = (
            aln_key,
            tree_key,
            frozenset({recipient, donor}),
            denominator,
            occupancy_threshold,
            vocabulary_key,
        )
        if profile_key != self._profile_key:
            partition = resolve_partition(tree, recipient, donor)
            profiles = calculate_profiles(
                alignment,
                partition,
                weights,
                denominator=denominator,
                occupancy_threshold=occupancy_threshold,
                vocabulary=resolved_vocabulary,
            )
            self._profile_key, self._profile_value = profile_key, (partition, profiles)
        assert self._profile_value is not None
        partition, profiles = self._profile_value

        typical_key = (profile_key, threshold, typical_gap)
        if typical_key != self._typical_key:
            typical_states = determine_typical_states(
                profiles, threshold=threshold, typical_gap=typical_gap
            )
            self._typical_key, self._typical_value = typical_key, typical_states
        assert self._typical_value is not None
        typical_states = self._typical_value

        transformed = generate_transformation(
            alignment,
            partition,
            profiles,
            typical_states,
            recipient=recipient,
            donor=donor,
            mode=mode,
            deletions=deletions,
            vocabulary=resolved_vocabulary,
        )
        return RunResult(id_mapping=id_mapping, partition=partition, transformed=transformed)
