# Loading Animations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bouncing-dot loading state to all async buttons and a glowing top progress bar to all page navigation links.

**Architecture:** CSS keyframes + utility classes added to each template's `<style>` block; a `setLoading(btn, isLoading)` JS helper added to `app.js` and dashboard inline script wraps every async fetch in try/finally; a fixed `#nav-bar` div + `startNavBar()` listener handles page transition feedback.

**Tech Stack:** Vanilla JS, CSS keyframes/transitions, Flask Jinja2 templates, no new dependencies.

---

## Chunk 1: CSS + HTML scaffolding

### Task 1: Add nav-bar div + CSS to index.html

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add `#nav-bar` div as first child of `<body>`**

  Find the opening `<body>` tag in `templates/index.html` (line 269, bare tag with no class attribute) and insert the nav bar div immediately after it. Search for:
  ```html
  <body>

  <!-- ── APP SHELL
  ```
  Replace with:
  ```html
  <body>
  <div id="nav-bar"></div>

  <!-- ── APP SHELL
  ```

- [ ] **Step 2: Add nav bar + dot animation CSS to index.html `<style>` block**

  Find the closing `</style>` tag in `templates/index.html` (there is one main `<style>` block). Insert these rules just before `</style>`:
  ```css
  /* ── NAV PROGRESS BAR ─────────────────────────── */
  #nav-bar {
    position: fixed; top: 0; left: 0; height: 3px; width: 0;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    box-shadow: 0 0 8px #6366f188;
    transition: width .4s cubic-bezier(.4,0,.2,1);
    pointer-events: none; z-index: 9999;
  }
  /* ── BUTTON LOADING DOTS ──────────────────────── */
  @keyframes dotPulse {
    0%, 80%, 100% { transform: scale(.55); opacity: .4; }
    40%            { transform: scale(1);   opacity: 1; }
  }
  .btn-dots { display: flex; gap: 6px; align-items: center; justify-content: center; padding: 4px 0; }
  .btn-dot  { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.85); animation: dotPulse 1.2s ease-in-out infinite; }
  .btn-dot:nth-child(2) { animation-delay: .2s; }
  .btn-dot:nth-child(3) { animation-delay: .4s; }
  ```

- [ ] **Step 3: Add IDs to three buttons in index.html**

  **a) Generate report button** — find (around line 578):
  ```html
  <button onclick="generateReport()" class="btn btn-primary px-6 py-2.5">
  ```
  Replace with:
  ```html
  <button id="generateBtn" onclick="generateReport()" class="btn btn-primary px-6 py-2.5">
  ```

  **b) Reload contracts button** — find (around line 692):
  ```html
  <button onclick="reloadContracts()" class="btn btn-ghost btn-sm" title="Znovu načíst ze souboru">
  ```
  Replace with:
  ```html
  <button id="reloadBtn" onclick="reloadContracts()" class="btn btn-ghost btn-sm" title="Znovu načíst ze souboru">
  ```

  **c) Save contract button** — find (around line 815):
  ```html
  <button onclick="saveContract()" class="btn btn-primary">Uložit smlouvu</button>
  ```
  Replace with:
  ```html
  <button id="saveContractBtn" onclick="saveContract()" class="btn btn-primary">Uložit smlouvu</button>
  ```

- [ ] **Step 4: Update confirmDeleteContract onclick to pass `this`**

  In `templates/index.html`, find the delete button in `renderContractsTable` (the button is rendered via `row.innerHTML` in `app.js`, not in the HTML template — skip this step for the template; it is handled in Task 3).

- [ ] **Step 5: Verify HTML changes look correct**

  Open `templates/index.html` and confirm:
  - `<div id="nav-bar"></div>` is first child of `<body>`
  - `#nav-bar` CSS and `@keyframes dotPulse` / `.btn-dots` / `.btn-dot` exist in `<style>`
  - `id="generateBtn"`, `id="reloadBtn"`, `id="saveContractBtn"` present on the three buttons

---

### Task 2: Add nav-bar div + CSS to dashboard.html

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1: Add `#nav-bar` div as first child of `<body>`**

  Find the bare `<body>` tag in `templates/dashboard.html` and insert immediately after it:
  ```html
  <div id="nav-bar"></div>
  ```

- [ ] **Step 2: Add nav bar + dot animation CSS to dashboard.html `<style>` block**

  Insert just before the closing `</style>` tag in `dashboard.html`:
  ```css
  /* ── NAV PROGRESS BAR ─────────────────────────── */
  #nav-bar {
    position: fixed; top: 0; left: 0; height: 3px; width: 0;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    box-shadow: 0 0 8px #6366f188;
    transition: width .4s cubic-bezier(.4,0,.2,1);
    pointer-events: none; z-index: 9999;
  }
  /* ── BUTTON LOADING DOTS ──────────────────────── */
  @keyframes dotPulse {
    0%, 80%, 100% { transform: scale(.55); opacity: .4; }
    40%            { transform: scale(1);   opacity: 1; }
  }
  .btn-dots { display: flex; gap: 6px; align-items: center; justify-content: center; padding: 4px 0; }
  .btn-dot  { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.85); animation: dotPulse 1.2s ease-in-out infinite; }
  .btn-dot:nth-child(2) { animation-delay: .2s; }
  .btn-dot:nth-child(3) { animation-delay: .4s; }
  ```

---

### Task 3: Add nav-bar div + CSS to admin_users.html

**Files:**
- Modify: `templates/admin_users.html`

- [ ] **Step 1: Add `#nav-bar` div as first child of `<body>`**

  Find the bare `<body>` tag in `templates/admin_users.html` and insert immediately after it:
  ```html
  <div id="nav-bar"></div>
  ```

- [ ] **Step 2: Add nav bar CSS only (no dot animation needed — no async buttons)**

  Insert just before the closing `</style>` tag:
  ```css
  /* ── NAV PROGRESS BAR ─────────────────────────── */
  #nav-bar {
    position: fixed; top: 0; left: 0; height: 3px; width: 0;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    box-shadow: 0 0 8px #6366f188;
    transition: width .4s cubic-bezier(.4,0,.2,1);
    pointer-events: none; z-index: 9999;
  }
  ```

---

## Chunk 2: JS utilities + app.js async wrappers

> **app.js indentation note:** The file uses consistent 4-space indent for top-level declarations (function signatures, `const`/`let`) and **8-space** indent for function body lines. All code snippets below reflect this. If an Edit `old_string` fails to match, read the target function first and verify exact whitespace.

### Task 4: Add `setLoading` + `startNavBar` to app.js

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add `setLoading` utility at the top of app.js**

  Find the `// ── STATE ──` comment at line 1 of `app.js`. Insert the following block **before** the state comment:
  ```js
  // ── LOADING UTILITIES ─────────────────────────────────────────────────
  function setLoading(btn, isLoading) {
      if (!btn) return;
      if (isLoading) {
          btn.dataset.originalHtml = btn.innerHTML;
          btn.innerHTML = '<div class="btn-dots"><div class="btn-dot"></div><div class="btn-dot"></div><div class="btn-dot"></div></div>';
          btn.disabled = true;
      } else {
          btn.innerHTML = btn.dataset.originalHtml ?? btn.innerHTML;
          btn.disabled = false;
          lucide.createIcons({ nodes: [btn] });
      }
  }

  function startNavBar() {
      const bar = document.getElementById('nav-bar');
      if (bar) bar.style.width = '85%';
  }
  ```

- [ ] **Step 2: Wire startNavBar to all navigation links in DOMContentLoaded**

  The existing `DOMContentLoaded` listener in `app.js` (around line 28) is:
  ```js
  document.addEventListener('DOMContentLoaded', () => {
      lucide.createIcons();
      showPanel('panel-upload');
      setStep(1);
  });
  ```
  Replace with:
  ```js
  document.addEventListener('DOMContentLoaded', () => {
      lucide.createIcons();
      showPanel('panel-upload');
      setStep(1);
      document.querySelectorAll('a[href]').forEach(a => {
          const href = a.getAttribute('href');
          if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
              a.addEventListener('click', startNavBar);
          }
      });
  });
  ```

---

### Task 5: Wrap processBtn click handler with setLoading

**Files:**
- Modify: `static/app.js`

The processBtn handler is around line 226. It already shows the big `loadingDiv` — keep that, and additionally disable the button with dots for immediate feedback.

- [ ] **Step 1: Add `setLoading(processBtn, true)` after the loadingDiv show**

  Find (around line 240):
  ```js
  loadingDiv.classList.remove('hidden');
  loadingDiv.classList.add('flex');
  errorMessage.classList.add('hidden');
  errorMessage.classList.remove('flex');
  document.getElementById('loadingText').textContent = 'Zpracovávám soubory a načítám data smluv...';
  ```
  Replace with:
  ```js
  loadingDiv.classList.remove('hidden');
  loadingDiv.classList.add('flex');
  errorMessage.classList.add('hidden');
  errorMessage.classList.remove('flex');
  document.getElementById('loadingText').textContent = 'Zpracovávám soubory a načítám data smluv...';
  setLoading(processBtn, true);
  ```

- [ ] **Step 2: Add `setLoading(processBtn, false)` in the existing finally block**

  Use the unique catch message to target the correct finally block (around line 282):
  ```js
        } catch (error) {
            showError('Chyba při zpracování souborů: ' + error.message);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
        }
    });
  ```
  Replace with:
  ```js
        } catch (error) {
            showError('Chyba při zpracování souborů: ' + error.message);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
            setLoading(processBtn, false);
        }
    });
  ```

---

### Task 6: Wrap generateReport with setLoading

**Files:**
- Modify: `static/app.js`

The `generateReport` function is around line 435. It also uses the big `loadingDiv`.

- [ ] **Step 1: Add `setLoading` calls around the fetch**

  Find (around line 439):
  ```js
  loadingDiv.classList.remove('hidden');
  loadingDiv.classList.add('flex');
  document.getElementById('loadingText').textContent = 'Generuji zprávu pro vybrané tiskárny...';
  showPanel('panel-upload');
  ```
  Replace with:
  ```js
  const generateBtn = document.getElementById('generateBtn');
  setLoading(generateBtn, true);
  loadingDiv.classList.remove('hidden');
  loadingDiv.classList.add('flex');
  document.getElementById('loadingText').textContent = 'Generuji zprávu pro vybrané tiskárny...';
  showPanel('panel-upload');
  ```

- [ ] **Step 2: Add `setLoading(generateBtn, false)` in the finally block**

  Use the unique catch content to target the correct finally block (around line 468):
  ```js
        } catch (error) {
            showError('Chyba při generování zprávy: ' + error.message);
            showPanel('panel-select');
            setStep(2);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
        }
    }
  ```
  Replace with:
  ```js
        } catch (error) {
            showError('Chyba při generování zprávy: ' + error.message);
            showPanel('panel-select');
            setStep(2);
        } finally {
            loadingDiv.classList.add('hidden');
            loadingDiv.classList.remove('flex');
            setLoading(generateBtn, false);
        }
    }
  ```

  > Note: `generateBtn` is declared with `const` inside the function body above, so it is in scope for `finally`.

---

### Task 7: Wrap saveContract with setLoading

**Files:**
- Modify: `static/app.js`

`saveContract` is around line 711.

- [ ] **Step 1: Add setLoading to saveContract**

  Find the function body start (around line 711):
  ```js
  async function saveContract() {
      const serial = document.getElementById('cf-serial').value.trim();
      if (!serial) { showToast('Sériové číslo je povinné', 'error'); return; }
      const payload = {
  ```
  Replace with:
  ```js
  async function saveContract() {
      const serial = document.getElementById('cf-serial').value.trim();
      if (!serial) { showToast('Sériové číslo je povinné', 'error'); return; }
      const btn = document.getElementById('saveContractBtn');
      setLoading(btn, true);
      const payload = {
  ```

- [ ] **Step 2: Wrap the try/catch in saveContract with finally**

  Find (around line 729):
  ```js
      try {
          const res  = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
          const data = await res.json();
          if (data.error) { showToast(data.error, 'error'); return; }
          showToast(editingSerial ? 'Smlouva aktualizována' : 'Smlouva přidána', 'success');
          closeContractModal();
          loadContracts();
      } catch (e) {
          showToast('Chyba při ukládání', 'error');
      }
  ```
  Replace with:
  ```js
      try {
          const res  = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
          const data = await res.json();
          if (data.error) { showToast(data.error, 'error'); return; }
          showToast(editingSerial ? 'Smlouva aktualizována' : 'Smlouva přidána', 'success');
          closeContractModal();
          loadContracts();
      } catch (e) {
          showToast('Chyba při ukládání', 'error');
      } finally {
          setLoading(btn, false);
      }
  ```

---

### Task 8: Update confirmDeleteContract to accept btn + setLoading

**Files:**
- Modify: `static/app.js`
- Modify: `templates/index.html` (rendered inline in app.js renderContractsTable)

- [ ] **Step 1: Update function signature and add setLoading**

  Find (around line 741):
  ```js
  async function confirmDeleteContract(serial) {
      if (!confirm(`Opravdu smazat smlouvu pro sériové číslo ${serial}?`)) return;
      try {
          const res  = await fetch(`/contracts/delete/${encodeURIComponent(serial)}`, { method: 'POST' });
          const data = await res.json();
          if (data.error) { showToast(data.error, 'error'); return; }
          showToast('Smlouva smazána', 'warning');
          loadContracts();
      } catch (e) {
          showToast('Chyba při mazání', 'error');
      }
  }
  ```
  Replace with:
  ```js
  async function confirmDeleteContract(btn, serial) {
      if (!confirm(`Opravdu smazat smlouvu pro sériové číslo ${serial}?`)) return;
      setLoading(btn, true);
      try {
          const res  = await fetch(`/contracts/delete/${encodeURIComponent(serial)}`, { method: 'POST' });
          const data = await res.json();
          if (data.error) { showToast(data.error, 'error'); return; }
          showToast('Smlouva smazána', 'warning');
          loadContracts();
      } catch (e) {
          showToast('Chyba při mazání', 'error');
      } finally {
          setLoading(btn, false);
      }
  }
  ```

- [ ] **Step 2: Update the inline onclick in renderContractsTable to pass `this`**

  In `static/app.js`, find (around line 662):
  ```js
  <button onclick="confirmDeleteContract('${serialEsc}')" class="btn btn-sm"
  ```
  Replace with:
  ```js
  <button onclick="confirmDeleteContract(this,'${serialEsc}')" class="btn btn-sm"
  ```

---

### Task 9: Wrap reloadContracts with setLoading

**Files:**
- Modify: `static/app.js`

`reloadContracts` is around line 754.

- [ ] **Step 1: Add setLoading to reloadContracts**

  Find:
  ```js
  async function reloadContracts() {
      try {
          const res  = await fetch('/contracts/reload', { method: 'POST' });
          const data = await res.json();
          showToast(`Znovu načteno: ${data.count} smluv`, 'success');
          loadContracts();
      } catch (e) {
          showToast('Chyba při načítání', 'error');
      }
  }
  ```
  Replace with:
  ```js
  async function reloadContracts() {
      const btn = document.getElementById('reloadBtn');
      setLoading(btn, true);
      try {
          const res  = await fetch('/contracts/reload', { method: 'POST' });
          const data = await res.json();
          showToast(`Znovu načteno: ${data.count} smluv`, 'success');
          loadContracts();
      } catch (e) {
          showToast('Chyba při načítání', 'error');
      } finally {
          setLoading(btn, false);
      }
  }
  ```

---

## Chunk 3: Dashboard updates

### Task 10: Add setLoading + startNavBar to dashboard.html inline script

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1: Add `setLoading` + `startNavBar` to the inline script**

  Find the opening of the `<script>` block in `dashboard.html` (it starts with `let historyData` or similar). Insert these functions at the very top of the script block, before any `let`/`const` declarations:

  ```js
  function setLoading(btn, isLoading) {
      if (!btn) return;
      if (isLoading) {
          btn.dataset.originalHtml = btn.innerHTML;
          btn.innerHTML = '<div class="btn-dots"><div class="btn-dot"></div><div class="btn-dot"></div><div class="btn-dot"></div></div>';
          btn.disabled = true;
      } else {
          btn.innerHTML = btn.dataset.originalHtml ?? btn.innerHTML;
          btn.disabled = false;
      }
  }

  function startNavBar() {
      const bar = document.getElementById('nav-bar');
      if (bar) bar.style.width = '85%';
  }
  ```

- [ ] **Step 2: Wire startNavBar in DOMContentLoaded in dashboard.html**

  Find the existing `DOMContentLoaded` listener (around line 637) — note 4-space outer / 8-space inner indentation:
  ```
    document.addEventListener('DOMContentLoaded', () => {
        lucide.createIcons();
        loadData();
    });
  ```
  Replace with (preserve the same 4/8-space indentation):
  ```
    document.addEventListener('DOMContentLoaded', () => {
        lucide.createIcons();
        loadData();
        document.querySelectorAll('a[href]').forEach(a => {
            const href = a.getAttribute('href');
            if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
                a.addEventListener('click', startNavBar);
            }
        });
    });
  ```

---

### Task 11: Update downloadReport in dashboard.html to accept + use btn

**Files:**
- Modify: `templates/dashboard.html`

- [ ] **Step 1: Update the four download buttons in renderHistoryTable to pass `this`**

  In `renderHistoryTable()` (around lines 541–555), find each button:
  ```js
  <button onclick="downloadReport('${entry.id}', 'pdf')"
  ```
  Replace with:
  ```js
  <button onclick="downloadReport(this,'${entry.id}','pdf')"
  ```

  Do the same for `details`, `invoice`, and `all`:
  ```js
  <button onclick="downloadReport('${entry.id}', 'details')"
  ```
  → `<button onclick="downloadReport(this,'${entry.id}','details')"`

  ```js
  <button onclick="downloadReport('${entry.id}', 'invoice')"
  ```
  → `<button onclick="downloadReport(this,'${entry.id}','invoice')"`

  ```js
  <button onclick="downloadReport('${entry.id}', 'all')"
  ```
  → `<button onclick="downloadReport(this,'${entry.id}','all')"`

- [ ] **Step 2: Update downloadReport function signature and add setLoading**

  Find (around line 595):
  ```js
  async function downloadReport(sessionId, fileType) {
      const url = fileType === 'all'
          ? `/download_all/${sessionId}`
          : `/download/${sessionId}/${fileType}`;
      try {
          const res = await fetch(url);
          if (res.status === 404) {
              showToast('Soubory nejsou dostupné — automaticky smazány po 24 hodinách od vytvoření.', 'error');
              return;
          }
          if (!res.ok) {
              showToast('Chyba při stahování souboru.', 'error');
              return;
          }
          const blob = await res.blob();
          const disposition = res.headers.get('Content-Disposition') || '';
          const nameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          const filename = nameMatch ? nameMatch[1].replace(/['"]/g, '') : `report_${sessionId}`;
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(a.href);
      } catch (e) {
          showToast('Chyba při stahování souboru.', 'error');
          console.error(e);
      }
  }
  ```
  Replace with:
  ```js
  async function downloadReport(btn, sessionId, fileType) {
      const url = fileType === 'all'
          ? `/download_all/${sessionId}`
          : `/download/${sessionId}/${fileType}`;
      setLoading(btn, true);
      try {
          const res = await fetch(url);
          if (res.status === 404) {
              showToast('Soubory nejsou dostupné — automaticky smazány po 24 hodinách od vytvoření.', 'error');
              return;
          }
          if (!res.ok) {
              showToast('Chyba při stahování souboru.', 'error');
              return;
          }
          const blob = await res.blob();
          const disposition = res.headers.get('Content-Disposition') || '';
          const nameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          const filename = nameMatch ? nameMatch[1].replace(/['"]/g, '') : `report_${sessionId}`;
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(a.href);
      } catch (e) {
          showToast('Chyba při stahování souboru.', 'error');
          console.error(e);
      } finally {
          setLoading(btn, false);
      }
  }
  ```

---

### Task 12: Update confirmDelete in dashboard.html to use modal button

**Files:**
- Modify: `templates/dashboard.html`

The dashboard delete confirmation uses a modal. The modal "Smazat" button (line 329) is a static element — we give it an id and use it in `confirmDelete()`. No need to thread a btn reference through `openDeleteModal`.

- [ ] **Step 1: Add `id="dashConfirmDeleteBtn"` to the modal confirm button**

  Find (around line 329):
  ```html
  <button onclick="confirmDelete()" class="btn btn-danger text-sm">Smazat</button>
  ```
  Replace with:
  ```html
  <button id="dashConfirmDeleteBtn" onclick="confirmDelete()" class="btn btn-danger text-sm">Smazat</button>
  ```

- [ ] **Step 2: Add setLoading to confirmDelete**

  Find (around line 581):
  ```js
  async function confirmDelete() {
      if (!pendingDeleteId) return;
      try {
          const res  = await fetch(`/history/delete/${pendingDeleteId}`, { method: 'POST' });
          const data = await res.json();
          if (data.success) {
              closeDeleteModal();
              await loadData();
          }
      } catch (e) {
          console.error('Chyba při mazání záznamu:', e);
      }
  }
  ```
  Replace with:
  ```js
  async function confirmDelete() {
      if (!pendingDeleteId) return;
      const btn = document.getElementById('dashConfirmDeleteBtn');
      setLoading(btn, true);
      try {
          const res  = await fetch(`/history/delete/${pendingDeleteId}`, { method: 'POST' });
          const data = await res.json();
          if (data.success) {
              closeDeleteModal();
              await loadData();
          }
      } catch (e) {
          console.error('Chyba při mazání záznamu:', e);
      } finally {
          setLoading(btn, false);
      }
  }
  ```

---

### Task 13: Add startNavBar inline script to admin_users.html

**Files:**
- Modify: `templates/admin_users.html`

- [ ] **Step 1: Add startNavBar script to admin_users.html**

  Find the closing `</body>` tag in `templates/admin_users.html`. Insert just before it:
  ```html
  <script>
  function startNavBar() {
      const bar = document.getElementById('nav-bar');
      if (bar) bar.style.width = '85%';
  }
  document.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('a[href]').forEach(a => {
          const href = a.getAttribute('href');
          if (href && !href.startsWith('#') && !href.startsWith('javascript')) {
              a.addEventListener('click', startNavBar);
          }
      });
  });
  </script>
  ```

---

## Final verification

- [ ] Start the app: `python app.py`
- [ ] Open http://localhost:5000 and log in
- [ ] Upload a CSV file → confirm processBtn shows bouncing dots while uploading
- [ ] On step 2, click "Generovat zprávy" → confirm button shows dots while generating
- [ ] Click "Smlouvy" in sidebar → confirm contracts load; click the reload icon → dots appear
- [ ] Add or edit a contract → save button shows dots
- [ ] Delete a contract → trash button shows dots while deleting
- [ ] Click "Dashboard" link in top bar → confirm indigo progress bar sweeps across top
- [ ] On dashboard, click a download button → dots appear while downloading
- [ ] On dashboard, click trash → open modal → click "Smazat" → button shows dots
- [ ] Click "Zpět do aplikace" on dashboard → progress bar appears
