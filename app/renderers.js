const MAX_TREE_PREVIEW_LEAVES = 1000;

// ── Parsers ────────────────────────────────────────────────────────────────
function parseNewick(s) {
  s = s.trim().replace(/;+$/, '').replace(/\s+/g, '');
  let i = 0;
  function node() {
    const n = {name: '', length: 0, children: []};
    if (s[i] === '(') {
      i++;
      n.children.push(node());
      while (s[i] === ',') { i++; n.children.push(node()); }
      i++;
    }
    const ls = i;
    while (i < s.length && ':,)'.indexOf(s[i]) === -1) i++;
    n.name = s.slice(ls, i);
    if (s[i] === ':') {
      i++;
      const ds = i;
      while (i < s.length && ',)'.indexOf(s[i]) === -1) i++;
      n.length = parseFloat(s.slice(ds, i)) || 0;
    }
    return n;
  }
  return node();
}

function layoutTree(root) {
  let idx = 0;
  function setY(n) {
    if (!n.children.length) { n._y = idx++; return; }
    n.children.forEach(setY);
    n._y = (n.children[0]._y + n.children[n.children.length - 1]._y) / 2;
  }
  function setX(n, x) { n._x = x + n.length; n.children.forEach(c => setX(c, n._x)); }
  setY(root); root.length = 0; setX(root, 0);
  let maxX = 0;
  function findMax(n) { if (n._x > maxX) maxX = n._x; n.children.forEach(findMax); }
  findMax(root);
  if (maxX < 1e-10) {
    function setDepth(n, d) { n._x = d; n.children.forEach(c => setDepth(c, d + 1)); }
    setDepth(root, 0); maxX = 0; findMax(root);
  }
  return {nLeaves: idx, maxX: maxX || 1};
}

// Leaf names under `n`, and the sorted-key form used to identify a node from its
// descendant-tip set (shared with app.js, which resolves clicks back to a node this way).
function leafNames(n) {
  return n.children.length ? n.children.flatMap(leafNames) : [n.name];
}
function nodeKey(n) {
  return leafNames(n).slice().sort().join(',');
}
function findNodeByKey(root, key) {
  if (!key) return null;
  const stack = [root];
  while (stack.length) {
    const n = stack.pop();
    if (n.children.length && nodeKey(n) === key) return n;
    stack.push(...n.children);
  }
  return null;
}

function countNewickLeaves(text) {
  const s = text.trim().replace(/\s+/g, '');
  let leaves = 0;
  for (let i = 0; i < s.length; i++) {
    const prev = s[i - 1];
    const cur = s[i];
    if ((prev === '(' || prev === ',') && cur !== '(' && cur !== ')' && cur !== ',' && cur !== ':' && cur !== ';') {
      leaves++;
    }
  }
  return leaves;
}

// ── Renderers ──────────────────────────────────────────────────────────────

// `highlights` is an optional list of {tips: Set<string>, color, label} used to
// colour leaves by subfamily membership (the recipient/donor clades).
//
// `opts` wires up click interaction, all optional:
//   markers      — [{tips: Set<string>, badge, color}] small letter badge drawn by a leaf
//   selectedKey  — the sorted, comma-joined descendant-tip key of the currently selected
//                  internal node (matches what onSelectNode is called with)
//   isPickable   — name => cladeIndex (0/1) | null, whether/where a leaf can be clicked
//   onSelectNode — (key) => void, called when a two-child internal node is clicked
//   onLeafClick  — (name, cladeIndex, clientX, clientY) => void, called on a pickable leaf click
function renderTree(content, container, highlights = [], opts = {}) {
  const {markers = [], selectedKey = null, isPickable = null, onSelectNode = null, onLeafClick = null} = opts;
  const estimatedLeaves = countNewickLeaves(content);
  if (estimatedLeaves > MAX_TREE_PREVIEW_LEAVES) {
    container.textContent = `Tree preview skipped: ~${estimatedLeaves.toLocaleString()} leaves exceeds the ${MAX_TREE_PREVIEW_LEAVES.toLocaleString()} limit.`;
    return;
  }

  let root;
  try { root = parseNewick(content); }
  catch (e) { container.textContent = 'Parse error: ' + e.message; return; }
  const {nLeaves, maxX} = layoutTree(root);
  if (!nLeaves) { container.textContent = 'Empty tree.'; return; }

  // A leaf that's already been picked (has a marker) reads as "settled" — greyed out rather
  // than its bright clade color — so the still-open pick stays the one that stands out.
  const colorFor = name => {
    if (markers.some(m => m.tips.has(name))) return '#9a9d97';
    for (const h of highlights) if (h.tips.has(name)) return h.color;
    return '#3b6fb6';
  };

  const ROW = Math.max(14, Math.min(20, Math.floor(360 / nLeaves)));
  const TW = 360, LW = 130;
  const PAD = {t: 8, r: 10, b: 12, l: 16};
  const W = PAD.l + TW + 6 + LW + PAD.r;
  const H = PAD.t + nLeaves * ROW + PAD.b;
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('transform', `translate(${PAD.l},${PAD.t})`);
  svg.appendChild(g);
  const tx = x => x / maxX * TW;
  const ty = y => y * ROW + ROW / 2;

  function seg(x1, y1, x2, y2) {
    const el = document.createElementNS(NS, 'line');
    el.setAttribute('x1', x1); el.setAttribute('y1', y1);
    el.setAttribute('x2', x2); el.setAttribute('y2', y2);
    el.setAttribute('stroke', '#595c56'); el.setAttribute('stroke-width', '1');
    g.appendChild(el);
  }
  function draw(n) {
    const nx = tx(n._x), ny = ty(n._y);
    if (n.children.length) {
      seg(nx, ty(n.children[0]._y), nx, ty(n.children[n.children.length - 1]._y));
      n.children.forEach(c => { seg(nx, ty(c._y), tx(c._x), ty(c._y)); draw(c); });

      if (onSelectNode) {
        const selectable = n.children.length === 2;
        const selected = selectable && selectedKey !== null && nodeKey(n) === selectedKey;
        const hit = document.createElementNS(NS, 'circle');
        hit.setAttribute('cx', nx); hit.setAttribute('cy', ny);
        hit.setAttribute('r', '4');
        hit.setAttribute('fill', selected ? '#ffcf4d' : (selectable ? '#fff' : '#eee'));
        hit.setAttribute('stroke', selectable ? '#595c56' : '#c7c9c5');
        hit.setAttribute('stroke-width', selected ? '2' : '1');
        hit.style.cursor = selectable ? 'pointer' : 'not-allowed';
        const title = document.createElementNS(NS, 'title');
        title.textContent = selectable
          ? 'Click to select this internal node'
          : 'Needs exactly two child clades to select';
        hit.appendChild(title);
        if (selectable) {
          hit.addEventListener('click', e => { e.stopPropagation(); onSelectNode(nodeKey(n)); });
        }
        g.appendChild(hit);
      }
    } else {
      const marker = markers.find(m => m.tips.has(n.name));
      if (marker) {
        const ring = document.createElementNS(NS, 'circle');
        ring.setAttribute('cx', nx); ring.setAttribute('cy', ny);
        ring.setAttribute('r', '6'); ring.setAttribute('fill', 'none');
        ring.setAttribute('stroke', marker.color || colorFor(n.name));
        ring.setAttribute('stroke-width', '2');
        g.appendChild(ring);
        const badge = document.createElementNS(NS, 'text');
        badge.setAttribute('x', nx - 9); badge.setAttribute('y', ny);
        badge.setAttribute('font-size', '9'); badge.setAttribute('font-family', 'monospace');
        badge.setAttribute('font-weight', '700');
        badge.setAttribute('text-anchor', 'end');
        badge.setAttribute('dominant-baseline', 'middle');
        badge.setAttribute('fill', marker.color || colorFor(n.name));
        badge.textContent = marker.badge;
        g.appendChild(badge);
      }

      const dot = document.createElementNS(NS, 'circle');
      dot.setAttribute('cx', nx); dot.setAttribute('cy', ny);
      dot.setAttribute('r', '3'); dot.setAttribute('fill', colorFor(n.name));
      g.appendChild(dot);
      const txt = document.createElementNS(NS, 'text');
      txt.setAttribute('x', nx + 6); txt.setAttribute('y', ny);
      txt.setAttribute('font-size', ROW <= 14 ? '10' : '11');
      txt.setAttribute('font-family', 'monospace');
      txt.setAttribute('dominant-baseline', 'middle');
      txt.setAttribute('fill', colorFor(n.name));
      const isPicked = markers.some(m => m.tips.has(n.name));
      txt.setAttribute('font-weight', highlights.some(h => h.tips.has(n.name)) && !isPicked ? 'bold' : 'normal');
      txt.textContent = n.name;
      g.appendChild(txt);

      const cladeIdx = isPickable ? isPickable(n.name) : null;
      if (cladeIdx !== null && cladeIdx !== undefined && onLeafClick) {
        const pick = e => { e.stopPropagation(); onLeafClick(n.name, cladeIdx, e.clientX, e.clientY); };
        dot.style.cursor = 'pointer'; dot.addEventListener('click', pick);
        txt.style.cursor = 'pointer'; txt.addEventListener('click', pick);
      }
    }
  }
  draw(root);

  const wrap = document.createElement('div');
  wrap.className = 'tree-wrap';
  if (highlights.length) {
    const legend = document.createElement('div');
    legend.className = 'tree-legend';
    highlights.forEach(h => {
      const sp = document.createElement('span');
      sp.className = 'leg';
      sp.innerHTML = `<span class="leg-sw" style="background:${h.color}"></span>${h.label}`;
      legend.appendChild(sp);
    });
    wrap.appendChild(legend);
  }
  wrap.appendChild(svg);
  container.appendChild(wrap);
}

function renderText(content, container) {
  const pre = document.createElement('pre');
  pre.className = 'text-view';
  pre.textContent = content;
  container.appendChild(pre);
}

function renderJSON(content, container) {
  const pre = document.createElement('pre');
  pre.className = 'json-view';
  try { pre.textContent = JSON.stringify(JSON.parse(content), null, 2); }
  catch { pre.textContent = content; }
  container.appendChild(pre);
}

// `summary` is the parsed contents of summary.json: recipient/donor ids, substitution/
// insertion/deletion counts, and whether the alignment/tree identifiers were bijective.
// `onNavigate(tab)` is called when the user clicks a piece of the summary that has a
// natural "see the detail" destination — the summary acts as a hub into the other tabs
// rather than a dead end next to them.
function renderSummary(summary, container, onNavigate) {
  const wrap = document.createElement('div');
  wrap.className = 'summary-wrap';

  const mkButton = (cls, onClick) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = cls;
    if (onClick) btn.addEventListener('click', onClick);
    return btn;
  };

  const flow = mkButton('summary-flow', () => onNavigate('pairwise'));
  const mkId = (cls, text) => {
    const span = document.createElement('span');
    span.className = 'summary-id ' + cls;
    const dot = document.createElement('span');
    dot.className = 'summary-dot';
    span.appendChild(dot);
    span.appendChild(document.createTextNode(text));
    return span;
  };
  flow.appendChild(mkId('donor', summary.donor_id));
  const arrow = document.createElement('span');
  arrow.className = 'summary-arrow';
  arrow.textContent = '→';
  flow.appendChild(arrow);
  flow.appendChild(mkId('recipient', summary.recipient_id));
  wrap.appendChild(flow);

  const tiles = document.createElement('div');
  tiles.className = 'summary-tiles';
  [
    ['Substitutions', summary.substitutions],
    ['Insertions', summary.insertions],
    ['Deletions', summary.deletions],
  ].forEach(([label, value]) => {
    const tile = mkButton('summary-tile', () => onNavigate('events'));
    const val = document.createElement('div');
    val.className = 'summary-tile-value';
    val.textContent = String(value);
    const lab = document.createElement('div');
    lab.className = 'summary-tile-label';
    lab.textContent = label;
    tile.appendChild(val);
    tile.appendChild(lab);
    tiles.appendChild(tile);
  });
  wrap.appendChild(tiles);

  if (!summary.is_bijective) {
    const note = mkButton('warning summary-warning', () => onNavigate('diagnostics'));
    note.textContent = 'The alignment and tree identifiers do not map one-to-one — see Diagnostics →';
    wrap.appendChild(note);
  }

  const links = document.createElement('div');
  links.className = 'summary-links';
  [['pairwise', 'Pairwise'], ['events', 'Events'], ['diagnostics', 'Diagnostics'], ['files', 'Output files']]
    .forEach(([tab, label]) => {
      const a = mkButton('summary-link', () => onNavigate(tab));
      a.textContent = label + ' →';
      links.appendChild(a);
    });
  wrap.appendChild(links);

  container.appendChild(wrap);
}

const EVENT_TYPE_LABEL = {substitution: 'Substitution', insertion: 'Insertion', deletion: 'Deletion'};

// A compact, readable view of transformation events — the on-screen counterpart to the
// full machine-oriented schema in events.tsv/events.json (still available as a download),
// rather than that same raw column dump rendered as a table.
function renderEvents(jsonText, container, emptyMessage) {
  const rows = JSON.parse(jsonText);
  if (!rows.length) {
    const p = document.createElement('p');
    p.className = 'muted-note';
    p.textContent = emptyMessage;
    container.appendChild(p);
    return;
  }

  const list = document.createElement('div');
  list.className = 'events-list';
  rows.forEach(e => {
    const row = document.createElement('div');
    row.className = 'event-row';

    const pos = document.createElement('span');
    pos.className = 'event-pos';
    pos.textContent = 'Col ' + e.alignment_column;
    row.appendChild(pos);

    const change = document.createElement('span');
    change.className = 'event-change';
    const from = document.createElement('span');
    from.className = 'event-state';
    from.textContent = e.source_state;
    const arrow = document.createElement('span');
    arrow.className = 'event-arrow';
    arrow.textContent = '→';
    const to = document.createElement('span');
    to.className = 'event-state';
    to.textContent = e.transformed_state;
    change.appendChild(from);
    change.appendChild(arrow);
    change.appendChild(to);
    row.appendChild(change);

    const badge = document.createElement('span');
    badge.className = 'event-badge ' + e.event_type;
    badge.textContent = EVENT_TYPE_LABEL[e.event_type] || e.event_type;
    row.appendChild(badge);

    const detail = document.createElement('span');
    detail.className = 'event-detail';
    let text = `donor ${Number(e.donor_frequency).toFixed(2)} · recipient ${Number(e.recipient_frequency).toFixed(2)}`;
    if (e.rule && e.rule !== 'literal') text += ` · class "${e.rule}"`;
    detail.textContent = text;
    row.appendChild(detail);

    list.appendChild(row);
  });
  container.appendChild(list);
}

// Renders a JSON array of flat objects (events, diagnostics) as a table, columns
// taken from the union of keys across all rows so an absent field just renders empty.
function renderObjectTable(jsonText, container, emptyMessage) {
  const rows = JSON.parse(jsonText);
  if (!rows.length) {
    const p = document.createElement('p');
    p.className = 'muted-note';
    p.textContent = emptyMessage;
    container.appendChild(p);
    return;
  }
  const columns = [...new Set(rows.flatMap(Object.keys))];
  const wrap = document.createElement('div');
  wrap.className = 'table-wrap';
  const table = document.createElement('table');
  table.className = 'data-table';
  const thead = document.createElement('thead');
  const hRow = document.createElement('tr');
  columns.forEach(c => { const th = document.createElement('th'); th.textContent = c; hRow.appendChild(th); });
  thead.appendChild(hRow); table.appendChild(thead);
  const tbody = document.createElement('tbody');
  rows.forEach(row => {
    const tr = document.createElement('tr');
    columns.forEach(c => {
      const td = document.createElement('td');
      const v = row[c];
      td.textContent = v === null || v === undefined ? '' : String(v);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody); wrap.appendChild(table); container.appendChild(wrap);
}
