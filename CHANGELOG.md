# Changelog

## [Unreleased]

### Added

- `uv`-locked package (canonical Python 3.11); strict `ruff` and `mypy`.
- `xprot.core.primitives` — `Diagnostic`, `Severity`/`EventType`/`SubfamilyLabel` and the
  parameter enums (`PartitionSemantics`, `RootingMethod`, `AmbiguityPolicy`, `Denominator`,
  `DesignMode`, `LabelSource`).
- `xprot.core.errors` — one exception hierarchy (`XProtError` base; `AlignmentError`,
  `TreeError`, `DesignError`, `ClassTableError`).
- `xprot.core.models` — frozen dataclasses for the pipeline (alignment, tree, partition,
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
- `xprot.app.run_design` — chains the pipeline (load → id-map → partition → weights → profiles →
  typicality → transformation) behind one call; `class_table` accepts a mapping or a path.
  Raises `IdentifierError` if the alignment and tree do not map one-to-one.
- `xprot.render` — deterministic byte renderers: `render_events_tsv` / `render_events_json`,
  `render_transformed_fasta`, `render_pairwise` (recipient vs. transformed, with a marker line
  over each change), `render_summary_json`, `render_diagnostics_json`.
- `x-prot design` — the CLI (stdlib `argparse`, no dependency added): `--alignment`, `--tree`,
  `--node-tips`/`--node-label`, `--recipient`, `--donor`, `--out`, `--dry-run`. Exit codes:
  `0` success, `2` usage, `3` alignment/tree/class-table parse failure, `4` identifiers don't map
  one-to-one or the node can't be resolved, `5` the transformation can't be computed.
- `load_alignment` / `load_tree` now wrap a missing or unreadable file in `AlignmentError` /
  `TreeError` instead of letting `OSError` escape uncaught.
- `app/` — a static browser UI (no build step, no server) running the unmodified `xprot` package
  in a Web Worker via Pyodide: `worker.js` fetches `src/xprot/**.py` into Pyodide's virtual
  filesystem and calls `run_design` and `xprot.render`'s renderers directly; `main.js`/`index.html`
  provide the form and results tabs (tree with recipient/donor clades highlighted, pairwise view,
  events, diagnostics, output files); `renderers.js` draws the tree as a hand-rolled SVG cladogram
  (no charting library). Published on GitHub Pages from `/app`.

### Not yet done

- A contract test against an external reference alignment/tree.
