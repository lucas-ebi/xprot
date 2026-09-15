# Changelog

## [Unreleased]

### Not yet done

- A contract test against an external reference alignment/tree.

## [0.1.2] - 2026-09-15

### Fixed

- `app/worker.js` fetched xprot's own Python source from the `main` branch by URL, and
  `app/sw.js`'s runtime cache is cache-first keyed only by URL — so the first-ever cached copy of
  e.g. `render.py` would keep being served forever, silently going stale on every later release
  (this broke `v0.1.1` in production: an `ImportError: cannot import name 'render_pairwise_json'`
  from a `render.py` cached before that function existed). Now pinned to the exact deployed commit
  SHA (`__APP_REF__`, injected the same way as `__APP_VERSION__`), so each release's fetch is a
  fresh cache key instead of overwriting a stale one — matching how the Pyodide/pip URLs are
  already safe to cache-first, since those are pinned to specific versions.

## [0.1.1] - 2026-09-15

### Added

- `xprot.render.render_pairwise_json` — recipient vs. transformed alignment, as JSON alongside
  the existing `pairwise.txt`, so the browser UI can render it as a colored diff.
- `app/`'s Pairwise tab now colors each differing residue in place (blue/green-dark/amber,
  matching the Events tab's badge colors) instead of a flat `*` marker row; hovering a colored
  residue shows the same donor/recipient-frequency detail the Events tab shows.

### Fixed

- `app/worker.js` fetches `xprot`'s Python source with `cache: 'no-store'` in local dev — without
  it, Chrome's heuristic HTTP caching (there's no `Cache-Control` header from
  `python -m http.server`) could keep serving a stale copy across reloads and even new tabs.
- `app/main.js` no longer registers the service worker on `localhost`/`127.0.0.1`/`::1`/`::`, and
  actively unregisters/clears caches there; `app/sw.js` self-destructs if it finds itself running
  on a local-dev host anyway (a registration left over from before this fix existed). Since
  `__APP_VERSION__` stays a literal placeholder outside of a real deploy, the shell cache's key
  never rolls over locally, so a previously-installed service worker would otherwise freeze
  `index.html`/`main.js`/`renderers.js`/`styles.css`/`worker.js` at whatever they were when it
  first installed, surviving even a hard reload.
- README: a LaTeX formula in the Transformation section was hard-wrapped across two source lines,
  which broke inline-math rendering in some previewers; it's back on one line.

## [0.1.0] - 2026-09-15

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
