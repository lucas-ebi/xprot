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
  // On narrow viewports the wizard sidebar otherwise eats up to 45vh, leaving almost no room
  // to see results -- follow the tab: Results collapses it, Tree (where the sidebar is still
  // needed to fill in inputs) expands it back. The toggle button overrides this at any time.
  if (isNarrowViewport()) setControlsCollapsed(btn.dataset.tab === 'results');
}

function isNarrowViewport() {
  return window.matchMedia('(max-width: 680px)').matches;
}

function setControlsCollapsed(collapsed) {
  const controls = document.querySelector('.controls');
  const toggle = document.getElementById('controls-toggle');
  controls.classList.toggle('collapsed', collapsed);
  toggle.textContent = collapsed ? '▾ Show inputs' : '▴ Hide inputs';
  toggle.setAttribute('aria-expanded', String(!collapsed));
}

document.getElementById('controls-toggle').addEventListener('click', () => {
  setControlsCollapsed(!document.querySelector('.controls').classList.contains('collapsed'));
});

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

// ── Interactive tree: click any leaf to set the donor, then any other leaf to
// set the recipient, instead of typing ids. The internal node is their most-
// recent-common-ancestor, resolved automatically once both are picked. ───────
const DEFAULT_TREE_MSG =
  'Paste or upload a Newick tree in the sidebar to preview it — click any leaf to set the ' +
  'donor, then any other leaf to set the recipient.';

let recipientLeaf = null;
let donorLeaf = null;
let currentStep = 1;
let viewStep = 1;

function resetTreeSelection() {
  recipientLeaf = null;
  donorLeaf = null;
  document.getElementById('recipient').value = '';
  document.getElementById('donor').value = '';
}

// A click acts immediately based on current state, instead of opening a "set as donor/set as
// recipient" confirmation popover: an unselected leaf fills whichever role is still empty
// (donor first); the currently-donor or currently-recipient leaf clears just that role; a third
// distinct leaf, once both roles are already filled, is refused with a warning rather than
// silently replacing one of them -- clear a role first, then pick again.
function handleLeafClick(name) {
  if (name === donorLeaf) {
    donorLeaf = null;
    document.getElementById('donor').value = '';
    renderTreePreview();
  } else if (name === recipientLeaf) {
    recipientLeaf = null;
    document.getElementById('recipient').value = '';
    renderTreePreview();
  } else if (donorLeaf === null) {
    donorLeaf = name;
    document.getElementById('donor').value = name;
    renderTreePreview();
  } else if (recipientLeaf === null) {
    recipientLeaf = name;
    document.getElementById('recipient').value = name;
    renderTreePreview();
  } else {
    showTreeWarning('Two tips already selected — click one to remove it, or click empty space to clear both.');
  }
}

function handleTreeBackgroundClick() {
  if (!donorLeaf && !recipientLeaf) return;
  resetTreeSelection();
  renderTreePreview();
}

let treeWarningTimeout = null;
function showTreeWarning(msg) {
  const hint = document.querySelector('#panel-tree .tree-hint');
  if (!hint) return;
  hint.textContent = msg;
  hint.className = 'tree-hint warning';
  clearTimeout(treeWarningTimeout);
  treeWarningTimeout = setTimeout(renderTreePreview, 2500);
}

function renderTreePreview() {
  clearTimeout(treeWarningTimeout);
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

  const treeLeaves = new Set(leafNames(root));
  if ((donorLeaf && !treeLeaves.has(donorLeaf)) || (recipientLeaf && !treeLeaves.has(recipientLeaf))) {
    resetTreeSelection();
  }

  const highlights = [];
  const markers = [];
  let hintText;
  let hintReady = false;

  if (donorLeaf && recipientLeaf) {
    const pair = findMRCAChildren(root, donorLeaf, recipientLeaf);
    if (pair) {
      const [donorChild, recipientChild] = pair;
      const tipsDonor = new Set(leafNames(donorChild));
      const tipsRecipient = new Set(leafNames(recipientChild));
      highlights.push({tips: tipsRecipient, color: '#3b6fb6', label: 'Recipient clade'});
      highlights.push({tips: tipsDonor, color: '#18974c', label: 'Donor clade'});
      markers.push({tips: new Set([recipientLeaf]), badge: 'R', color: '#193f90'});
      markers.push({tips: new Set([donorLeaf]), badge: 'D', color: '#0a5032'});
      hintText = `Donor: ${donorLeaf} (green clade, ${tipsDonor.size} tips) · `
        + `Recipient: ${recipientLeaf} (blue clade, ${tipsRecipient.size} tips) — ready to run.`;
      hintReady = true;
    }
  } else if (donorLeaf) {
    hintText = `Donor: ${donorLeaf}. Click any other leaf (or search above) to set the recipient.`;
  } else {
    hintText = 'Click any leaf, or search above, to set the donor.';
  }

  emptyState.style.display = 'none';
  panel.classList.add('visible');
  const hint = document.createElement('div');
  hint.className = 'tree-hint' + (hintReady ? ' ready' : '');
  hint.textContent = hintText;
  panel.appendChild(hint);

  // Every leaf stays clickable regardless of current selection state -- handleLeafClick decides
  // what a click does (pick, clear, or refuse a third selection) from donorLeaf/recipientLeaf.
  renderTree(treeText, panel, highlights, {
    markers,
    isPickable: () => 0,
    onLeafClick: name => handleLeafClick(name),
    onBackgroundClick: handleTreeBackgroundClick,
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

function stepReady(step) {
  if (step === 1) return document.getElementById('aln-text').value.trim() !== '';
  if (step === 2) {
    const text = document.getElementById('tree-text').value;
    if (!text.trim()) return false;
    if (document.getElementById('tree-format').value !== 'newick') return true;
    try { return leafNames(parseNewick(text)).length > 0; } catch (e) { return false; }
  }
  if (step === 3) {
    return document.getElementById('recipient').value.trim() !== ''
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
  // The moment recipient+donor are both picked for the first time, move on to Run — but
  // only while step 3 is still the frontier, so navigating back to review/edit it later
  // doesn't keep bouncing the view forward.
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
  const bothPicked = !!recipientVal && !!donorVal;
  document.getElementById('check-node').classList.toggle('done', bothPicked);
  document.getElementById('check-recipient').classList.toggle('done', !!recipientVal);
  document.getElementById('check-donor').classList.toggle('done', !!donorVal);

  const runSummary = document.getElementById('wiz-run-summary');
  if (bothPicked) {
    runSummary.textContent = `Donor: ${donorVal} · Recipient: ${recipientVal}`;
    runSummary.classList.add('ready');
  } else {
    runSummary.textContent = 'Select a donor and recipient in the Tree tab.';
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
['recipient', 'donor'].forEach(id => {
  document.getElementById(id).addEventListener('input', renderWizard);
});

// ── Donor/recipient search bars: a Maps-style pair of typeahead comboboxes over the current
// tree's tips, plus a swap button between them. Each bar commits a pick the same way a tree
// click does (updates donorLeaf/recipientLeaf and re-syncs the tree highlight); a bar's raw
// text still drives stepReady/runDesign directly via the 'input' listeners above, matching the
// tree click flow's tolerance for typos (surfaced by the backend as a "tip not in tree" error).
function currentTreeTips() {
  if (document.getElementById('tree-format').value !== 'newick') return [];
  try { return leafNames(parseNewick(document.getElementById('tree-text').value)); }
  catch (e) { return []; }
}

function setupTipCombobox(role) {
  const input = document.getElementById(role);
  const dropdown = document.getElementById(role + '-dropdown');
  let activeIndex = -1;

  function commit(name) {
    input.value = name;
    dropdown.hidden = true;
    if (role === 'donor') donorLeaf = name; else recipientLeaf = name;
    renderTreePreview();
  }

  function visibleOptions() {
    return Array.from(dropdown.querySelectorAll('li:not(.no-match)'));
  }

  function setActive(index) {
    const items = visibleOptions();
    activeIndex = Math.max(-1, Math.min(index, items.length - 1));
    items.forEach((li, i) => li.classList.toggle('active', i === activeIndex));
    if (items[activeIndex]) items[activeIndex].scrollIntoView({block: 'nearest'});
  }

  function open() {
    const tips = currentTreeTips();
    if (!tips.length) { dropdown.hidden = true; return; }
    const q = input.value.trim().toLowerCase();
    const matches = q ? tips.filter(name => name.toLowerCase().includes(q)) : tips;
    dropdown.innerHTML = '';
    activeIndex = -1;
    if (!matches.length) {
      const li = document.createElement('li');
      li.className = 'no-match';
      li.textContent = 'No matching tips';
      dropdown.appendChild(li);
    } else {
      matches.slice(0, 50).forEach(name => {
        const li = document.createElement('li');
        li.textContent = name;
        li.addEventListener('mousedown', e => { e.preventDefault(); commit(name); });
        dropdown.appendChild(li);
      });
    }
    const rect = input.getBoundingClientRect();
    dropdown.style.left = rect.left + 'px';
    dropdown.style.top = rect.bottom + 'px';
    dropdown.style.width = rect.width + 'px';
    dropdown.hidden = false;
  }

  input.addEventListener('focus', open);
  input.addEventListener('input', open);
  input.addEventListener('blur', () => {
    // A mousedown on an option fires (and calls commit, which hides the dropdown) before this
    // blur handler runs, so the short delay here only ever hides a still-open dropdown that the
    // user dismissed some other way (e.g. tabbing away).
    setTimeout(() => { dropdown.hidden = true; }, 150);
    const tips = currentTreeTips();
    const current = role === 'donor' ? donorLeaf : recipientLeaf;
    if (tips.includes(input.value) && input.value !== current) commit(input.value);
  });
  input.addEventListener('keydown', e => {
    if (dropdown.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(activeIndex + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(activeIndex - 1); }
    else if (e.key === 'Enter') {
      const items = visibleOptions();
      if (activeIndex >= 0 && items[activeIndex]) { e.preventDefault(); commit(items[activeIndex].textContent); }
    } else if (e.key === 'Escape') {
      dropdown.hidden = true;
    }
  });
}
setupTipCombobox('donor');
setupTipCombobox('recipient');

document.getElementById('swap-roles').addEventListener('click', () => {
  if (!donorLeaf && !recipientLeaf) return;
  [donorLeaf, recipientLeaf] = [recipientLeaf, donorLeaf];
  document.getElementById('donor').value = donorLeaf || '';
  document.getElementById('recipient').value = recipientLeaf || '';
  renderTreePreview();
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

// ── File access (output files, written into Pyodide's virtual FS) ──────────
const textCache = new Map();
let activePreviewBtn = null;

async function getFileText(filename) {
  if (textCache.has(filename)) return textCache.get(filename);
  const {text} = await workerRequest({type: 'getText', filename});
  textCache.set(filename, text);
  return text;
}

function saveBlob(buffer, filename, type) {
  const url = URL.createObjectURL(new Blob([buffer], {type}));
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function downloadFile(filename) {
  const {buffer} = await workerRequest({type: 'getBytes', filename});
  saveBlob(buffer, filename, 'text/plain');
}

async function downloadAllZip(btn) {
  btn.disabled = true;
  try {
    const {filename, buffer} = await workerRequest({type: 'getZip'});
    saveBlob(buffer, filename, 'application/zip');
  } catch (err) {
    setStatus('Error building zip: ' + err.message, 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
  }
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

  const treeText = document.getElementById('tree-text').value;
  const thresholdVal = parseFloat(document.getElementById('threshold').value);
  const alphabetVal = document.getElementById('alphabet').value.trim();
  const request = {
    alignmentText: document.getElementById('aln-text').value,
    alignmentFormat: document.getElementById('aln-format').value,
    treeText,
    treeFormat: document.getElementById('tree-format').value,
    recipient: document.getElementById('recipient').value,
    donor: document.getElementById('donor').value,
    threshold: Number.isFinite(thresholdVal) ? thresholdVal : 0.9,
    deletions: document.getElementById('deletions').checked,
    mode: document.getElementById('mode').value,
    alphabet: alphabetVal || null,
    ambiguous: document.getElementById('ambiguous').value,
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
    const eventsText = await getFileText('events.json');
    renderPairwise(await getFileText('pairwise.json'), eventsText, pairwisePanel);

    document.getElementById('empty-events').style.display = 'none';
    const eventsPanel = document.getElementById('panel-events');
    eventsPanel.classList.add('visible');
    renderEvents(eventsText, eventsPanel, 'No changes proposed: the clades already agree at every position.');

    document.getElementById('empty-diagnostics').style.display = 'none';
    const diagPanel = document.getElementById('panel-diagnostics');
    diagPanel.classList.add('visible');
    renderObjectTable(
      await getFileText('diagnostics.json'), diagPanel,
      'No issues — the alignment and tree identifiers matched exactly, and every column and change was used as proposed.'
    );

    const resultText = `${summary.substitutions} substitutions, ${summary.insertions} insertions, ${summary.deletions} deletions`;
    setStatus(resultText, 'ready');
    showRunBanner(`Design complete — ${resultText}`);

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

// Keep in sync with worker.js's own local-host list (used there to fetch xprot's source from
// the local project tree instead of GitHub).
const IS_LOCAL_DEV = [
  'localhost', '127.0.0.1', '::1', '::',
].includes(location.hostname);

if ('serviceWorker' in navigator) {
  if (IS_LOCAL_DEV) {
    // The shell cache's key never rolls over locally (__APP_VERSION__ stays a literal
    // placeholder outside of a real deploy), so a service worker installed during an earlier
    // local session would otherwise serve index.html/main.js/renderers.js/styles.css/worker.js
    // from that frozen precache forever -- surviving even a hard reload, since the browser
    // never gets to make the request at all. Local dev must always reflect disk, so never
    // register here, and clean up anything left over from before this fix existed.
    navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
    caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
  } else {
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

    // The browser only checks for a new service worker on navigation, so a tab left open
    // across a deploy would otherwise never learn about it until the next full reload. Ask
    // explicitly whenever the tab regains focus, so returning to an already-open tab surfaces
    // the update banner on its own.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') swRegistration?.update();
    });
  }
}
