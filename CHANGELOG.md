# Changelog

## [Unreleased]

### Not yet done

- A contract test against an external reference alignment/tree.

## [0.2.1] - 2026-09-15

### Added

- `app/main.js` now calls `registration.update()` whenever the tab regains focus
  (`visibilitychange`), not just on navigation. Previously a tab left open across a deploy had no
  way to learn about it until the next full page load, so the update banner (and the "Reload"
  button that activates the new service worker) could stay unreachable indefinitely in a
  long-lived tab.

### Fixed

- `pages.yml` triggered on every push to `main` touching `app/**` *and* on every `v*` tag push,
  sharing one `concurrency: group: pages` — tagging a release right after (or as part of) a normal
  push queued two deploys back-to-back instead of one clean one. Confirmed live: releasing v0.2.0
  produced two separate `github-pages` deployment records six minutes apart, and the footer kept
  showing the untagged `git describe` fallback (`v0.1.4-1-g9d64c27`) long after the tag deploy had
  actually succeeded, purely from GitHub's Pages CDN having cached the earlier branch-push deploy's
  response. Deploys now trigger only on `v*` tag pushes (plus manual `workflow_dispatch`), so
  `git describe --tags --always` always resolves to the clean tag with no fallback suffix, and each
  release is exactly one deploy.

## [0.2.0] - 2026-09-15

### Changed

- The CLI, browser UI, and `xprot.app.run_design` no longer take a separate internal-node
  selector. `x-prot design`'s `--node-tips`/`--node-label` flags are removed; `run_design` drops
  its `node`/`semantics` parameters. The internal node is now always the most-recent-common
  ancestor (MRCA) of `--recipient`/`--donor` in the tree, resolved by the new
  `xprot.core.tree.resolve_partition(tree, recipient, donor)`. This is more capable than the
  previous two-children-only resolution, not just shorter: the MRCA may have more than two
  children (a polytomy), and only the two children containing `recipient`/`donor` become the two
  subfamilies, ignoring any other sibling branches at that node — previously such a node was
  rejected outright. Migration: `--node-tips "a,b,c,d" --recipient a --donor c` becomes
  `--recipient a --donor c`. One consequence: since `--recipient`/`--donor` now always resolve to
  different subfamilies by construction, the CLI's "recipient and donor in the same subfamily"
  failure (exit code 5) is no longer reachable through it — it stays defined for library callers
  of `xprot.app.run_design` that pass `mode=EXPANDED` without a `class_table`, which the CLI
  doesn't expose either.
- The old label- and whole-clade-vs-complement node-selection API (`xprot.core.models.NodeSelector`,
  the old `resolve_partition(tree, NodeSelector, semantics=...)`, and
  `PartitionSemantics.SELECTED_CLADE_VS_COMPLEMENT`) is removed entirely, since nothing in the CLI
  or browser UI used it once the above landed. `PartitionSemantics` itself, and
  `CanonicalPartition.semantics`, are removed too — with only one resolution strategy left, the
  field was always the same constant and carried no information (it was never serialized into any
  output). `Phylogeny.iter_nodes()` and `TreeNode.is_leaf` are also removed, having existed only to
  support the old label-based lookup.
- The browser UI's tree preview no longer requires clicking an internal node before picking
  representatives: click any leaf to set the donor, then any other leaf to set the recipient, and
  the app derives and highlights the relevant two clades automatically. The "Node selected"
  checklist item is now a derived "Node resolved" indicator rather than a separate manual step.

- `design.py`'s literal-mode (and expanded-mode) transformation rule no longer excludes a
  donor-typical state just because the recipient subfamily's own weighted profile is *also*
  typical for it. Previously `_pick_target` computed candidates as
  `donor_typical - recipient_typical`; that exclusion was checked against the recipient
  subfamily's aggregate profile, not the specific recipient representative being edited, so a
  representative sequence that happened to be an outlier from a state both subfamilies otherwise
  share would silently keep that outlier residue instead of picking up the donor's conserved
  state. The donor side of the rule was already profile-only (no donor alignment row is ever
  read, only its clade's typical states/frequencies); the recipient side is representative-only
  (only `source_state`, this one sequence's own residue, matters). The rule is now simply: propose
  the donor clade's typical state at a column whenever the representative doesn't already carry
  it. Added `test_literal_uses_donor_typical_state_regardless_of_recipient_typicality` covering
  the case that changed; every existing `test_design.py` fixture already had donor/recipient
  typical states differing (or matching *and* the representative already carrying that state), so
  none of them exercised this edge case before.

## [0.1.4] - 2026-09-15

### Added

- `app/`'s Run step gets an "Advanced settings" panel: the typicality cutoff (θ, default 0.9) as
  a number input, and an "Allow deletions" checkbox — both wired through `worker.js` into
  `run_design`'s existing `threshold` and `deletions` parameters. Placed in step 4 (Run), not
  step 3 (Node & representatives): step 3 auto-collapses the instant node/donor/recipient are all
  filled, so a setting nested inside it would already be hidden again before most people could
  reach it.
- `x-prot design` gets matching `--threshold` and `--deletions` flags, for the same reason: the
  CLI is meant to be a full peer of the browser UI, not a subset.

### Fixed

- The `deletions` parameter of `xprot.app.run_design` did nothing when set — undetectable until
  now since neither the CLI nor the browser UI exposed it yet. Root cause:
  `xprot.core.design._pick_target` unconditionally filtered the gap out of its candidate list
  (`if r != gap`) before ever ranking a target, so a donor-typically-gapped column could never be
  selected as a deletion candidate in the first place — the `elif target == gap` branch a few
  lines below, and the `deletions` parameter gating it, were dead code. Found while wiring "Allow
  deletions" into the browser UI: the checkbox had no observable effect even with a test case
  engineered so the donor clade was clearly gapped where the recipient wasn't. Fixed by dropping
  the filter; added a regression test (`test_literal_deletion_when_donor_is_typically_gapped`)
  exercising both the skipped-without-`deletions` and emitted-with-`deletions` paths, plus CLI
  tests for both new flags. Also requires `typical_gap=True` (a separate, pre-existing parameter
  of `determine_typical_states`, off by default) — without it, gap can never be marked "typical"
  for a subfamily regardless of this fix, so both the browser's "Allow deletions" checkbox and the
  CLI's `--deletions` flag set `typical_gap` together rather than exposing it separately.

## [0.1.3] - 2026-09-15

### Fixed

- `v0.1.2`'s own fix didn't actually take effect: the deploy workflow's `sed` substitution is a
  blind text replace, and `app/worker.js` compared the injected ref against the placeholder's own
  literal text (`APP_REF === '__APP_REF__'`) in the same file `sed` rewrites — so that comparison
  string got substituted too, and the check always came back true, always falling back to the
  moving `main` branch URL it was meant to stop using. Detection is now shape-based (a 40-char hex
  SHA) instead of comparing against the placeholder text.

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
