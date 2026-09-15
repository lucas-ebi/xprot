// Web Worker: owns Pyodide, runs xprot.app.run_design, serves output files.
// Communicates with the main thread via postMessage. Runs the same, unmodified
// xprot package the CLI uses -- this file is the only web-specific code.
//
// Spontaneous messages (no id):
//   {type:'status', msg}     — loading progress
//   {type:'ready'}           — Pyodide + xprot initialised
//   {type:'initError', message}
//
// Request/response (matching id):
//   run      → done     {filenames}
//   getText  → text     {filename, text}
//   getBytes → bytes    {filename, buffer}   (buffer is Transferable)
//   any      → error    {message}

importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js');

// __APP_REF__ is substituted by the GitHub Actions Pages workflow at deploy time with the exact
// commit SHA (see .github/workflows/pages.yml) -- sw.js's runtime cache is cache-first and keyed
// only by URL, so fetching from a moving ref like `main` would mean the first-ever cached copy of
// xprot's source wins forever, silently going stale on every later release. Pinning to the exact
// commit makes each deploy's fetch a fresh cache key instead, the same way the Pyodide/pip URLs
// below are already safe to cache-first because they're pinned to specific versions.
const APP_REF = '__APP_REF__';

// On localhost serve files from the local project tree so changes are reflected
// immediately without a GitHub push. On any other host (e.g. GitHub Pages) fall
// back to fetching from the exact deployed commit (or `main`, for a local static preview that
// hasn't been through the deploy step's substitution).
const BASE = (
  location.hostname === 'localhost'  ||
  location.hostname === '127.0.0.1' ||
  location.hostname === '::1'        ||   // IPv6 loopback
  location.hostname === '::'              // IPv6 any-address (python -m http.server default)
)
  ? '../src/xprot/'
  : `https://raw.githubusercontent.com/lucas-ebi/xprot/${APP_REF === '__APP_REF__' ? 'main' : APP_REF}/src/xprot/`;

const XPROT_FILES = [
  '__init__.py', 'app.py', 'render.py',
  'core/__init__.py', 'core/errors.py', 'core/primitives.py', 'core/models.py',
  'core/alignment.py', 'core/tree.py', 'core/identifiers.py', 'core/weights.py',
  'core/profile.py', 'core/design.py', 'core/classes.py',
];

// Extension xprot's format auto-detection recognises, keyed by the <select> values used below.
const ALIGNMENT_EXT = {fasta: 'fasta', stockholm: 'sto', clustal: 'aln'};
const TREE_EXT = {newick: 'nwk', nexus: 'nex'};

let pyodide;

async function init() {
  postMessage({type: 'status', msg: 'Initialising Pyodide…'});
  pyodide = await loadPyodide();

  postMessage({type: 'status', msg: 'Installing packages…'});
  await pyodide.loadPackage(['numpy', 'micropip']);
  await pyodide.runPythonAsync(
    'import micropip\nawait micropip.install(["pydantic","pyyaml","biopython"])'
  );

  postMessage({type: 'status', msg: 'Loading xprot…'});
  for (const dir of ['xprot', 'xprot/core', 'work', 'output']) {
    try { pyodide.FS.mkdir('/' + dir); } catch (_) {}
  }
  await Promise.all(XPROT_FILES.map(async file => {
    // no-store: the local-dev BASE promises edits are reflected immediately, but with no
    // Cache-Control header from `python -m http.server`, Chrome's heuristic freshness would
    // otherwise keep serving whatever it first fetched, across reloads and even new tabs.
    const res = await fetch(BASE + file, {cache: 'no-store'});
    if (!res.ok) throw new Error(`Failed to fetch xprot/${file} (${res.status})`);
    pyodide.FS.writeFile('/xprot/' + file, await res.text());
  }));
  pyodide.runPython('import sys\nif "/" not in sys.path: sys.path.insert(0, "/")');
  await pyodide.runPythonAsync('import xprot.app, xprot.render');

  postMessage({type: 'ready'});
}

self.onmessage = async ({data}) => {
  const {id, type, ...args} = data;
  try {
    if (type === 'run') {
      const r = args.request;

      try {
        pyodide.FS.readdir('/output')
          .filter(f => f !== '.' && f !== '..')
          .forEach(f => pyodide.FS.unlink('/output/' + f));
      } catch (_) {}

      const alnPath = '/work/alignment.' + ALIGNMENT_EXT[r.alignmentFormat];
      const treePath = '/work/tree.' + TREE_EXT[r.treeFormat];
      pyodide.FS.writeFile(alnPath, r.alignmentText);
      pyodide.FS.writeFile(treePath, r.treeText);

      const nodeArg = r.nodeTips
        ? `NodeSelector(tips=frozenset(${JSON.stringify(r.nodeTips.split(',').map(t => t.trim()).filter(Boolean))}))`
        : `NodeSelector(label=${JSON.stringify(r.nodeLabel)})`;

      await pyodide.runPythonAsync(`
from pathlib import Path
from xprot.core.models import NodeSelector
from xprot.app import run_design
from xprot.render import (
    render_events_tsv, render_events_json, render_transformed_fasta,
    render_pairwise, render_pairwise_json, render_summary_json, render_diagnostics_json,
)

_result = run_design(
    ${JSON.stringify(alnPath)}, ${JSON.stringify(treePath)}, ${nodeArg},
    recipient=${JSON.stringify(r.recipient)}, donor=${JSON.stringify(r.donor)},
)
Path("/output/transformed.fasta").write_bytes(render_transformed_fasta(_result.transformed))
Path("/output/events.tsv").write_bytes(render_events_tsv(_result.transformed.events))
Path("/output/events.json").write_bytes(render_events_json(_result.transformed.events))
Path("/output/pairwise.txt").write_bytes(render_pairwise(_result.transformed))
Path("/output/pairwise.json").write_bytes(render_pairwise_json(_result.transformed))
Path("/output/summary.json").write_bytes(render_summary_json(
    _result.transformed, _result.partition, is_bijective=_result.id_mapping.is_bijective
))
Path("/output/diagnostics.json").write_bytes(render_diagnostics_json(
    _result.id_mapping.diagnostics, _result.transformed.diagnostics
))
`);

      const filenames = pyodide.FS.readdir('/output').filter(f => f !== '.' && f !== '..');
      postMessage({type: 'done', id, filenames});

    } else if (type === 'getText') {
      const raw = pyodide.FS.readFile('/output/' + args.filename);
      const text = new TextDecoder().decode(raw);
      postMessage({type: 'text', id, filename: args.filename, text});

    } else if (type === 'getBytes') {
      const raw = pyodide.FS.readFile('/output/' + args.filename);
      const buf = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
      postMessage({type: 'bytes', id, filename: args.filename, buffer: buf}, [buf]);
    }

  } catch (err) {
    postMessage({type: 'error', id, message: err.message});
  }
};

init().catch(err => postMessage({type: 'initError', message: err.message}));
