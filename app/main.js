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

function showRunBanner(msg) {
  document.getElementById('run-banner-text').textContent = msg;
  document.getElementById('run-banner').hidden = false;
}
function hideRunBanner() {
  document.getElementById('run-banner').hidden = true;
}
document.getElementById('run-banner-close').addEventListener('click', hideRunBanner);

function switchTab(btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
}

function navigateToTab(tab) {
  switchTab(document.querySelector(`.tab-btn[data-tab="${tab}"]`));
}

// The Summary's quick-nav (links, tiles, the donor/recipient flow, the bijective warning)
// jumps into the Results page's relevant section, rather than switching a tab that no
// longer exists for it — Pairwise/Events/Diagnostics/Output files are one scrolling page.
function scrollToSection(section) {
  navigateToTab('results');
  const target = document.getElementById('section-' + section);
  if (target) target.scrollIntoView({behavior: 'smooth', block: 'start'});
}

// ── Worker setup ───────────────────────────────────────────────────────────
let worker = null;
try {
  worker = new Worker('worker.js');
} catch (_) {
  setStatus(
    'Cannot start worker — serve app/ with a local HTTP server (e.g. python -m http.server).',
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

// ── File inputs: read an uploaded (or dropped) file into its paired textarea ──
async function loadFileIntoTextarea(file, textareaId) {
  if (!file) return;
  const textarea = document.getElementById(textareaId);
  textarea.value = await file.text();
  textarea.dispatchEvent(new Event('input'));
}

function wireFileInput(fileId, textareaId) {
  document.getElementById(fileId).addEventListener('change', e => {
    loadFileIntoTextarea(e.target.files[0], textareaId);
  });
}

function wireDropZone(zoneId, textareaId) {
  const zone = document.getElementById(zoneId);
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    loadFileIntoTextarea(e.dataTransfer.files[0], textareaId);
  });
}

wireFileInput('aln-file', 'aln-text');
wireFileInput('tree-file', 'tree-text');
wireDropZone('aln-dropzone', 'aln-text');
wireDropZone('tree-dropzone', 'tree-text');

// ── Interactive tree: click an internal node, then click a leaf in each of its
// two child clades to set recipient/donor, instead of typing ids. ─────────────
const DEFAULT_TREE_MSG =
  'Paste or upload a Newick tree in the sidebar to preview it — click an internal node with ' +
  'two child clades to select it, then click a leaf in each clade to set the donor and recipient.';

let selectedNodeKey = null;
let recipientLeaf = null;
let donorLeaf = null;
let activeLeafPopover = null;
let currentStep = 1;
let viewStep = 1;

function resetTreeSelection() {
  selectedNodeKey = null;
  recipientLeaf = null;
  donorLeaf = null;
  document.getElementById('recipient').value = '';
  document.getElementById('donor').value = '';
}

function closeLeafPopover() {
  if (!activeLeafPopover) return;
  activeLeafPopover.el.remove();
  document.removeEventListener('click', activeLeafPopover.onDocClick);
  document.removeEventListener('keydown', activeLeafPopover.onKeydown);
  activeLeafPopover = null;
}

// Donor is always picked before recipient (the trait being brought in, before who receives
// it). A leaf already holding a role is "locked": clicking it only offers to clear that role,
// rather than re-opening the full set-as menu — reassigning happens by picking a *different*
// leaf in the same clade instead.
function openLeafPopover(name, cladeIdx, clientX, clientY, donorClade) {
  closeLeafPopover();
  const isRecipient = recipientLeaf === name;
  const isDonor = donorLeaf === name;

  const pop = document.createElement('div');
  pop.className = 'leaf-popover';
  pop.style.left = clientX + 'px';
  pop.style.top = clientY + 'px';

  const addBtn = (label, onClick) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = label;
    btn.addEventListener('click', () => {
      onClick();
      closeLeafPopover();
      renderTreePreview();
    });
    pop.appendChild(btn);
  };

  if (isDonor) {
    addBtn('Clear donor', () => { donorLeaf = null; document.getElementById('donor').value = ''; });
  } else if (isRecipient) {
    addBtn('Clear recipient', () => { recipientLeaf = null; document.getElementById('recipient').value = ''; });
  } else if (donorLeaf === null || donorClade === cladeIdx) {
    addBtn('Set as donor', () => { donorLeaf = name; document.getElementById('donor').value = name; });
  } else {
    addBtn('Set as recipient', () => { recipientLeaf = name; document.getElementById('recipient').value = name; });
  }

  document.body.appendChild(pop);
  const onDocClick = e => { if (!pop.contains(e.target)) closeLeafPopover(); };
  const onKeydown = e => { if (e.key === 'Escape') closeLeafPopover(); };
  setTimeout(() => {
    document.addEventListener('click', onDocClick);
    document.addEventListener('keydown', onKeydown);
  }, 0);
  activeLeafPopover = {el: pop, onDocClick, onKeydown};
}

function handleSelectNode(key) {
  const reselecting = selectedNodeKey === key;
  resetTreeSelection();
  if (!reselecting) {
    selectedNodeKey = key;
    document.getElementById('node-mode-tips').checked = true;
    document.getElementById('node-tips').value = key;
    syncNodeMode();
  }
  renderTreePreview();
}

function renderTreePreview() {
  closeLeafPopover();
  const panel = document.getElementById('panel-tree');
  const emptyState = document.getElementById('empty-tree');
  const msg = document.getElementById('msg-tree');
  const treeText = document.getElementById('tree-text').value;
  const format = document.getElementById('tree-format').value;
  panel.innerHTML = '';
  panel.classList.remove('visible');

  if (!treeText.trim()) {
    msg.textContent = DEFAULT_TREE_MSG;
    emptyState.style.display = '';
    renderWizard();
    return;
  }
  if (format !== 'newick') {
    msg.textContent = 'Live preview is only available for Newick trees — run a design to see the result.';
    emptyState.style.display = '';
    renderWizard();
    return;
  }

  let root;
  try { root = parseNewick(treeText); }
  catch (e) {
    msg.textContent = 'Parse error: ' + e.message;
    emptyState.style.display = '';
    renderWizard();
    return;
  }

  const selectedNode = findNodeByKey(root, selectedNodeKey);
  if (selectedNodeKey && !selectedNode) resetTreeSelection();

  const highlights = [];
  const markers = [];
  let isPickable = null;
  let cladeOf = null;
  let hintText = 'Click an internal node with two child clades to select it.';
  let hintReady = false;

  if (selectedNode && selectedNode.children.length === 2) {
    const tips0 = new Set(leafNames(selectedNode.children[0]));
    const tips1 = new Set(leafNames(selectedNode.children[1]));
    cladeOf = name => (tips0.has(name) ? 0 : tips1.has(name) ? 1 : null);
    const donorClade = cladeOf(donorLeaf);
    const recipientClade = cladeOf(recipientLeaf);
    // Donor is picked first, so its clade claims the donor color as soon as it's known.
    const greenIdx = donorClade !== null ? donorClade : recipientClade !== null ? 1 - recipientClade : 1;
    const blueIdx = 1 - greenIdx;
    const cladeTips = [tips0, tips1];
    highlights.push({tips: cladeTips[blueIdx], color: '#3b6fb6', label: 'Clade ' + (blueIdx + 1)});
    highlights.push({tips: cladeTips[greenIdx], color: '#18974c', label: 'Clade ' + (greenIdx + 1)});
    if (recipientLeaf) markers.push({tips: new Set([recipientLeaf]), badge: 'R', color: '#193f90'});
    if (donorLeaf) markers.push({tips: new Set([donorLeaf]), badge: 'D', color: '#0a5032'});
    isPickable = cladeOf;

    if (!donorLeaf) {
      hintText = `Node selected: ${tips0.size + tips1.size} tips, split into clades of `
        + `${tips0.size} and ${tips1.size}. Click any leaf to set the donor.`;
    } else if (!recipientLeaf) {
      hintText = `Donor: ${donorLeaf} (green clade, ${cladeTips[greenIdx].size} tips). `
        + `Click a leaf in the blue clade (${cladeTips[blueIdx].size} tips) to set the recipient.`;
    } else {
      hintText = `Donor: ${donorLeaf} · Recipient: ${recipientLeaf} — ready to run.`;
      hintReady = true;
    }
  }

  emptyState.style.display = 'none';
  panel.classList.add('visible');
  const hint = document.createElement('div');
  hint.className = 'tree-hint' + (hintReady ? ' ready' : '');
  hint.textContent = hintText;
  panel.appendChild(hint);

  renderTree(treeText, panel, highlights, {
    markers,
    selectedKey: selectedNodeKey,
    isPickable,
    onSelectNode: handleSelectNode,
    onLeafClick: (name, cladeIdx, clientX, clientY) => {
      openLeafPopover(name, cladeIdx, clientX, clientY, cladeOf(donorLeaf));
    },
  });

  renderWizard();
}

// ── Sidebar wizard: stage Alignment / Tree / Node & representatives / Run,
// one step visible at a time, with the interactive tree in the workspace always
// live regardless of which step is expanded. ─────────────────────────────────
function countFastaSequences(text) {
  return (text.match(/^>/gm) || []).length;
}

function stepSummary(step) {
  if (step === 1) {
    const text = document.getElementById('aln-text').value;
    if (document.getElementById('aln-format').value === 'fasta') {
      const n = countFastaSequences(text);
      if (n) return `${n} sequence${n === 1 ? '' : 's'}`;
    }
    return 'content added';
  }
  if (step === 2) {
    const text = document.getElementById('tree-text').value;
    if (document.getElementById('tree-format').value === 'newick') {
      try {
        const n = leafNames(parseNewick(text)).length;
        return `${n} tip${n === 1 ? '' : 's'}`;
      } catch (e) { /* fall through to the generic summary below */ }
    }
    return 'content added';
  }
  const recipientVal = document.getElementById('recipient').value.trim();
  const donorVal = document.getElementById('donor').value.trim();
  return recipientVal && donorVal ? `${donorVal} → ${recipientVal}` : '';
}

// Whichever ids the run will actually use — the "Internal node" fields are shared between
// clicking the tree (which writes into them) and typing them directly (Manual entry).
function nodeSelectorFilled() {
  const byTips = document.getElementById('node-mode-tips').checked;
  return byTips
    ? document.getElementById('node-tips').value.trim() !== ''
    : document.getElementById('node-label').value.trim() !== '';
}

function stepReady(step) {
  if (step === 1) return document.getElementById('aln-text').value.trim() !== '';
  if (step === 2) {
    const text = document.getElementById('tree-text').value;
    if (!text.trim()) return false;
    if (document.getElementById('tree-format').value !== 'newick') return true;
    try { return leafNames(parseNewick(text)).length > 0; } catch (e) { return false; }
  }
  if (step === 3) {
    return nodeSelectorFilled()
      && document.getElementById('recipient').value.trim() !== ''
      && document.getElementById('donor').value.trim() !== '';
  }
  return true;
}

function goToStep(step) {
  currentStep = Math.max(currentStep, step);
  viewStep = step;
  renderWizard();
}

function renderWizard() {
  // The moment node+recipient+donor are all picked for the first time, move on to Run —
  // but only while step 3 is still the frontier, so navigating back to review/edit it
  // later doesn't keep bouncing the view forward.
  if (viewStep === 3 && currentStep === 3 && stepReady(3)) {
    goToStep(4);
    return;
  }

  document.querySelectorAll('.wiz-step').forEach(section => {
    const step = Number(section.dataset.step);
    const state = step > currentStep ? 'pending' : step === viewStep ? 'active' : 'done';
    section.dataset.state = state;
    section.querySelector('.wiz-summary').textContent = state === 'done' ? stepSummary(step) : '';
    section.querySelector('.wiz-num').textContent = state === 'done' ? '✓' : String(step);
    const nextBtn = section.querySelector('.wiz-next');
    if (nextBtn) nextBtn.disabled = !stepReady(step);
  });

  const recipientVal = document.getElementById('recipient').value.trim();
  const donorVal = document.getElementById('donor').value.trim();
  document.getElementById('check-node').classList.toggle('done', nodeSelectorFilled());
  document.getElementById('check-recipient').classList.toggle('done', !!recipientVal);
  document.getElementById('check-donor').classList.toggle('done', !!donorVal);

  const runSummary = document.getElementById('wiz-run-summary');
  if (nodeSelectorFilled() && recipientVal && donorVal) {
    const byTips = document.getElementById('node-mode-tips').checked;
    const nodeDesc = byTips
      ? `${document.getElementById('node-tips').value.split(',').filter(Boolean).length} tips`
      : `label "${document.getElementById('node-label').value}"`;
    runSummary.textContent = `Node: ${nodeDesc} · Donor: ${donorVal} · Recipient: ${recipientVal}`;
    runSummary.classList.add('ready');
  } else {
    runSummary.textContent = 'Select a node and representatives in the Tree tab.';
    runSummary.classList.remove('ready');
  }
}

document.querySelectorAll('.wiz-header').forEach(header => {
  header.addEventListener('click', () => {
    const section = header.closest('.wiz-step');
    if (section.dataset.state === 'done') goToStep(Number(section.dataset.step));
  });
});
document.querySelectorAll('.wiz-next').forEach(btn => {
  btn.addEventListener('click', () => goToStep(Number(btn.dataset.next)));
});
document.getElementById('aln-text').addEventListener('input', renderWizard);
document.getElementById('aln-format').addEventListener('change', renderWizard);
['node-tips', 'node-label', 'recipient', 'donor'].forEach(id => {
  document.getElementById(id).addEventListener('input', renderWizard);
});
['node-mode-tips', 'node-mode-label'].forEach(id => {
  document.getElementById(id).addEventListener('change', renderWizard);
});

let treePreviewDebounce = null;
document.getElementById('tree-text').addEventListener('input', () => {
  resetTreeSelection();
  clearTimeout(treePreviewDebounce);
  treePreviewDebounce = setTimeout(renderTreePreview, 150);
});
document.getElementById('tree-format').addEventListener('change', () => {
  resetTreeSelection();
  renderTreePreview();
});
renderTreePreview();

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
  hideRunBanner();
  document.getElementById('warnings').innerHTML = '';

  ['panel-summary', 'panel-pairwise', 'panel-events', 'panel-diagnostics'].forEach(id => {
    const el = document.getElementById(id);
    el.innerHTML = '';
    el.classList.remove('visible');
  });
  ['summary', 'pairwise', 'events', 'diagnostics'].forEach(t => {
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

    selectedNodeKey = [...summary.subfamily_a_tips, ...summary.subfamily_b_tips].sort().join(',');
    recipientLeaf = summary.recipient_id;
    donorLeaf = summary.donor_id;
    renderTreePreview();

    document.getElementById('empty-summary').style.display = 'none';
    const summaryPanel = document.getElementById('panel-summary');
    summaryPanel.classList.add('visible');
    renderSummary(summary, summaryPanel, scrollToSection);
    navigateToTab('results');

    document.getElementById('empty-pairwise').style.display = 'none';
    const pairwisePanel = document.getElementById('panel-pairwise');
    pairwisePanel.classList.add('visible');
    renderText(await getFileText('pairwise.txt'), pairwisePanel);

    document.getElementById('empty-events').style.display = 'none';
    const eventsPanel = document.getElementById('panel-events');
    eventsPanel.classList.add('visible');
    renderEvents(await getFileText('events.json'), eventsPanel, 'No changes proposed: the clades already agree at every position.');

    document.getElementById('empty-diagnostics').style.display = 'none';
    const diagPanel = document.getElementById('panel-diagnostics');
    diagPanel.classList.add('visible');
    renderObjectTable(
      await getFileText('diagnostics.json'), diagPanel,
      'No issues — the alignment and tree identifiers matched exactly, and every column and change was used as proposed.'
    );

    const resultText = `${summary.substitutions} substitutions, ${summary.insertions} insertions, ${summary.deletions} deletions`;
    setStatus(resultText, 'ready');
    showRunBanner(`✓ Design complete — ${resultText}`);

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

// ── PWA: version display, service worker registration, update banner ───────
(function displayVersion() {
  const meta = document.querySelector('meta[name="app-version"]');
  const raw = meta ? meta.content : '';
  document.getElementById('app-version').textContent =
    raw && raw !== '__APP_VERSION__' ? raw : 'dev';
})();

let swRegistration = null;

function showUpdateBanner() {
  document.getElementById('update-banner').hidden = false;
}
document.getElementById('update-banner-reload').addEventListener('click', () => {
  swRegistration?.waiting?.postMessage({type: 'SKIP_WAITING'});
});
document.getElementById('update-banner-close').addEventListener('click', () => {
  document.getElementById('update-banner').hidden = true;
});

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').then(reg => {
    swRegistration = reg;
    // A waiting worker already sitting there (e.g. installed while this tab was closed).
    if (reg.waiting && navigator.serviceWorker.controller) showUpdateBanner();
    reg.addEventListener('updatefound', () => {
      const installing = reg.installing;
      if (!installing) return;
      installing.addEventListener('statechange', () => {
        if (installing.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateBanner();
        }
      });
    });
  }).catch(err => console.error('Service worker registration failed:', err));

  // Fires once the SKIP_WAITING'd worker actually takes control -- pick up its assets.
  navigator.serviceWorker.addEventListener('controllerchange', () => location.reload());
}
