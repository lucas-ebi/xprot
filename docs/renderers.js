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
function renderTree(content, container, highlights = []) {
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

  const colorFor = name => {
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
    } else {
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
      txt.setAttribute('font-weight', highlights.some(h => h.tips.has(n.name)) ? 'bold' : 'normal');
      txt.textContent = n.name;
      g.appendChild(txt);
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
