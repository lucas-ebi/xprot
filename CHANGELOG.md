# Changelog

## [Unreleased]

### Added

- `uv`-locked package (canonical Python 3.11); strict `ruff` and `mypy`.
- `xprot.core.models` — `Diagnostic`, `Severity`/`EventType`/`SubfamilyLabel` and the
  parameter enums (`PartitionSemantics`, `RootingMethod`, `AmbiguityPolicy`, `Denominator`,
  `DesignMode`, `LabelSource`).
- `xprot.core.errors` — one exception hierarchy (`XProtError` base; `AlignmentError`,
  `TreeError`, `DesignError`, `ClassTableError`).
- `xprot.core.structures` — frozen dataclasses for the pipeline (alignment, tree, partition,
  weights, profiles, typical states, transformation events and result).
- The analysis pipeline, all taking plain keyword parameters (no config object):
  - `alignment.load_alignment` / `parse_alignment` (FASTA/Stockholm/Clustal via Biopython),
    `build_coordinate_map`.
  - `tree.load_tree` / `parse_tree` (Newick/Nexus), `resolve_partition`
    (two-child-clades / selected-clade-vs-complement).
  - `identifiers.resolve_id_mapping` (strict + aliases).
  - `weights.calculate_henikoff_weights` (numpy; gap is always a state, weights normalized by
    construction).
  - `profile.calculate_profiles` / `determine_typical_states` (strict `> threshold`; Taylor
    class profiles).
  - `design.generate_transformation` (literal and expanded modes) / `compare_with_fixture`.
  - `classes.load_class_table`.
- `class_tables/taylor-1986.yaml` — amino-acid physicochemical classes, after Taylor (1986).

### Not yet done

- `xprot.app` orchestration (`run_design`), output rendering, the `x-prot` CLI, and a contract
  test against an external reference alignment/tree.
