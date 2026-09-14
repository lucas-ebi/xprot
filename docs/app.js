function setStatus(msg, state = 'loading') {
  document.getElementById('status-text').textContent = msg;
  document.getElementById('status-dot').className = 'dot ' + state;
}

function addWarning(msg) {
  const container = document.getElementById('warnings');
  const div = document.createElement('div');
  div.className = 'warning';
  div.textContent = msg;
  container.appendChild(div);
  return div;
}

function switchTab(btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
}

// ── Worker setup ───────────────────────────────────────────────────────────
let worker = null;
try {
  worker = new Worker('worker.js');
} catch (_) {
  setStatus(
    'Cannot start worker — serve docs/ with a local HTTP server (e.g. python -m http.server).',
    'error'
  );
}
const _pending = new Map();
let _msgId = 0;

function workerRequest(msg) {
  if (!worker) return Promise.reject(new Error('Worker unavailable'));
  return new Promise((resolve, reject) => {
    const id = _msgId++;
    _pending.set(id, {resolve, reject});
    worker.postMessage({...msg, id});
  });
}

if (worker) {
  worker.onmessage = ({data}) => {
    const {type, id, ...rest} = data;
    if (type === 'status') { setStatus(rest.msg); return; }
    if (type === 'ready') {
      setStatus('Ready', 'ready');
      document.getElementById('run-btn').disabled = false;
      document.getElementById('btn-label').textContent = 'Run design';
      document.getElementById('design-form').addEventListener('submit', async e => {
        e.preventDefault();
        await runDesign();
      });
      return;
    }
    if (type === 'initError') { setStatus('Initialisation failed: ' + rest.message, 'error'); return; }
    const p = _pending.get(id);
    if (!p) return;
    _pending.delete(id);
    if (type === 'error') p.reject(new Error(rest.message));
    else p.resolve(rest);
  };

  worker.onerror = err => {
    setStatus('Worker error: ' + err.message, 'error');
    console.error(err);
    for (const {reject} of _pending.values()) reject(new Error(err.message || 'Worker error'));
    _pending.clear();
    worker = null;
  };
}

// ── File inputs: read an uploaded file into its paired textarea ────────────
function wireFileInput(fileId, textareaId) {
  document.getElementById(fileId).addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById(textareaId).value = await file.text();
  });
}
wireFileInput('aln-file', 'aln-text');
wireFileInput('tree-file', 'tree-text');

// ── Node-selector radio toggle ──────────────────────────────────────────────
function syncNodeMode() {
  const byTips = document.getElementById('node-mode-tips').checked;
  document.getElementById('node-tips').disabled = !byTips;
  document.getElementById('node-label').disabled = byTips;
}
document.getElementById('node-mode-tips').addEventListener('change', syncNodeMode);
document.getElementById('node-mode-label').addEventListener('change', syncNodeMode);

// ── File access (output files, written into Pyodide's virtual FS) ──────────
const textCache = new Map();
let activePreviewBtn = null;

async function getFileText(filename) {
  if (textCache.has(filename)) return textCache.get(filename);
  const {text} = await workerRequest({type: 'getText', filename});
  textCache.set(filename, text);
  return text;
}

async function downloadFile(filename) {
  const {buffer} = await workerRequest({type: 'getBytes', filename});
  const url = URL.createObjectURL(new Blob([buffer], {type: 'text/plain'}));
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// ── Run a design ─────────────────────────────────────────────────────────
async function runDesign() {
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.classList.add('running');
  document.getElementById('btn-label').textContent = 'Running…';
  setStatus('Running design…');
  textCache.clear();
  closePreview();
  document.getElementById('warnings').innerHTML = '';

  ['panel-tree', 'panel-pairwise', 'panel-events', 'panel-diagnostics'].forEach(id => {
    const el = document.getElementById(id);
    el.innerHTML = '';
    el.classList.remove('visible');
  });
  ['tree', 'pairwise', 'events', 'diagnostics'].forEach(t => {
    document.getElementById('empty-' + t).style.display = '';
  });
  document.getElementById('files-content').style.display = 'none';
  document.getElementById('empty-files').style.display = '';

  const byTips = document.getElementById('node-mode-tips').checked;
  const treeText = document.getElementById('tree-text').value;
  const request = {
    alignmentText: document.getElementById('aln-text').value,
    alignmentFormat: document.getElementById('aln-format').value,
    treeText,
    treeFormat: document.getElementById('tree-format').value,
    nodeTips: byTips ? document.getElementById('node-tips').value : '',
    nodeLabel: byTips ? '' : document.getElementById('node-label').value,
    recipient: document.getElementById('recipient').value,
    donor: document.getElementById('donor').value,
  };

  try {
    const {filenames} = await workerRequest({type: 'run', request});

    const tbody = document.getElementById('output-tbody');
    tbody.innerHTML = '';
    for (const filename of filenames) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="file-name">${filename}</td>
        <td style="text-align:center"><button type="button" class="icon-btn" onclick='showPreview(${JSON.stringify(filename)},this)'>view</button></td>
        <td style="text-align:center"><button type="button" class="icon-btn" onclick='downloadFile(${JSON.stringify(filename)})'>download</button></td>`;
      tbody.appendChild(tr);
    }
    document.getElementById('empty-files').style.display = 'none';
    document.getElementById('files-content').style.display = 'block';

    const summary = JSON.parse(await getFileText('summary.json'));
    if (!summary.is_bijective) {
      addWarning('The alignment and tree identifiers do not map one-to-one; see Diagnostics.');
    }

    const recipientInA = summary.subfamily_a_tips.includes(summary.recipient_id);
    const recipientTips = new Set(recipientInA ? summary.subfamily_a_tips : summary.subfamily_b_tips);
    const donorTips = new Set(recipientInA ? summary.subfamily_b_tips : summary.subfamily_a_tips);
    document.getElementById('empty-tree').style.display = 'none';
    const treePanel = document.getElementById('panel-tree');
    treePanel.classList.add('visible');
    renderTree(treeText, treePanel, [
      {tips: recipientTips, color: '#3b6fb6', label: `Recipient clade (${summary.recipient_id})`},
      {tips: donorTips, color: '#18974c', label: `Donor clade (${summary.donor_id})`},
    ]);

    document.getElementById('empty-pairwise').style.display = 'none';
    const pairwisePanel = document.getElementById('panel-pairwise');
    pairwisePanel.classList.add('visible');
    renderText(await getFileText('pairwise.txt'), pairwisePanel);

    document.getElementById('empty-events').style.display = 'none';
    const eventsPanel = document.getElementById('panel-events');
    eventsPanel.classList.add('visible');
    renderObjectTable(await getFileText('events.json'), eventsPanel, 'No changes proposed: the clades already agree at every position.');

    document.getElementById('empty-diagnostics').style.display = 'none';
    const diagPanel = document.getElementById('panel-diagnostics');
    diagPanel.classList.add('visible');
    renderObjectTable(await getFileText('diagnostics.json'), diagPanel, 'No diagnostics.');

    setStatus(
      `${summary.substitutions} substitutions, ${summary.insertions} insertions, ${summary.deletions} deletions`,
      'ready'
    );

  } catch (err) {
    setStatus('Error: ' + err.message, 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.classList.remove('running');
    document.getElementById('btn-label').textContent = 'Run design';
  }
}

// ── File preview (Output files tab) ─────────────────────────────────────────
async function showPreview(filename, btn) {
  const preview = document.getElementById('file-preview');
  if (activePreviewBtn === btn && preview.style.display !== 'none') {
    closePreview(); return;
  }
  if (activePreviewBtn) activePreviewBtn.classList.remove('active');
  activePreviewBtn = btn;
  btn.classList.add('active');
  document.getElementById('preview-title').textContent = filename;
  const content = document.getElementById('preview-content');
  content.innerHTML = '';
  const text = await getFileText(filename);
  if (filename.endsWith('.json')) renderJSON(text, content);
  else renderText(text, content);
  preview.style.display = 'block';
  preview.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function closePreview() {
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('preview-content').innerHTML = '';
  if (activePreviewBtn) { activePreviewBtn.classList.remove('active'); activePreviewBtn = null; }
}
