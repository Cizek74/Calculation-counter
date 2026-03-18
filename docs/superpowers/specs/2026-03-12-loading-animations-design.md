# Loading Animations — Design Spec
Date: 2026-03-12

## Overview

Add loading feedback to all async button actions and page navigation transitions across the Flask web app (Kalkulačka tisků). The goal is to give the user clear visual feedback that something is happening after every click.

## Chosen Styles

- **Buttons**: Bouncing dots (3 white/violet dots, `dotPulse` keyframe) — replaces button content while loading
- **Page navigation**: Slim glowing top progress bar (indigo→violet gradient, 3px, fixed) — runs on every navigation link click

---

## 1. Button Loading — Bouncing Dots

### Behavior
- Clicking any async button swaps its inner HTML for 3 bouncing dots
- Button is disabled (`disabled` attribute) while loading
- On completion (success or error), original HTML is restored and button re-enabled
- `setLoading(btn, false)` is **always called in `finally`** — never only on success or only on error
- For dynamically-rendered buttons (dashboard download/delete rows), the button element is passed via `this` in the `onclick` attribute

### CSS
Add `@keyframes dotPulse` + `.btn-dots/.btn-dot` to **both** `index.html` and `dashboard.html` `<style>` blocks:

```css
@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(.55); opacity: .4; }
  40%            { transform: scale(1);   opacity: 1; }
}
.btn-dots { display: flex; gap: 6px; align-items: center; justify-content: center; padding: 4px 0; }
.btn-dot  { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.85); animation: dotPulse 1.2s ease-in-out infinite; }
.btn-dot:nth-child(2) { animation-delay: .2s; }
.btn-dot:nth-child(3) { animation-delay: .4s; }
```

### JS Utility — `setLoading()` in `app.js`

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
    // Re-render Lucide icons in case originalHtml contained <i data-lucide="..."> placeholders
    // (safe to call even if icons are already SVGs — it's a no-op on SVG nodes)
    lucide.createIcons({ nodes: [btn] });
  }
}
```

> **Note on Lucide:** `btn.dataset.originalHtml` is captured at click time, after `lucide.createIcons()` has already run on page load. At that point button HTML already contains rendered `<svg>` elements, so the restore is safe. The `lucide.createIcons({ nodes: [btn] })` call is a safety net for any edge case where a `<i data-lucide>` placeholder slipped through.

### Buttons in `index.html` / `app.js`

Three buttons currently have no `id` and must have one added to the HTML:

| Button element | Add `id` | Handler |
|----------------|----------|---------|
| Zpracovat soubory | already has `id="processBtn"` | `processFiles()` |
| Generovat zprávy | add `id="generateBtn"` | `generateReport()` |
| Reload smlouvy (icon button) | add `id="reloadBtn"` | `reloadContracts()` |
| Uložit smlouvu (modal) | add `id="saveContractBtn"` | `saveContract()` |

Usage pattern in each async function:

```js
async function generateReport() {
  const btn = document.getElementById('generateBtn');
  setLoading(btn, true);
  try {
    // ... fetch ...
  } finally {
    setLoading(btn, false);
  }
}
```

**Contract delete button** — there is no modal; the delete uses a native `confirm()` dialog. The trash icon button is rendered inline in each table row. Pass `this` from the `onclick`:

```html
<!-- rendered in renderContractsTable() -->
<button onclick="confirmDeleteContract(this, '${serial}')">...</button>
```

Update function signature:
```js
async function confirmDeleteContract(btn, serial) {
  if (!confirm('...')) return;
  setLoading(btn, true);
  try { /* fetch */ } finally { setLoading(btn, false); }
}
```

### Buttons in `dashboard.html` (inline script)

Download and delete buttons are dynamically rendered inside `renderHistoryTable()` via `tr.innerHTML`. Pass `this`:

```html
<button onclick="downloadReport(this, '${entry.id}', 'pdf')">...</button>
<button onclick="downloadReport(this, '${entry.id}', 'details')">...</button>
<button onclick="downloadReport(this, '${entry.id}', 'invoice')">...</button>
<button onclick="downloadReport(this, '${entry.id}', 'all')">...</button>
<button onclick="openDeleteModal('${entry.id}', this)">...</button>  <!-- passes btn for confirmDelete -->
```

`downloadReport` and `confirmDelete` updated to accept `btn` as first parameter and call `setLoading` in `finally`.

A local `setLoading(btn, isLoading)` function (same implementation, no Lucide call needed since dashboard buttons use only text/SVG icons from Lucide that are pre-rendered) is defined in `dashboard.html`'s inline `<script>`.

---

## 2. Page Navigation — Top Progress Bar

### Behavior
- A fixed 3px bar sits at `top:0; left:0` of every page, hidden at `width:0`
- On any `<a href>` click that navigates to another page, the bar animates to `width: 85%` over ~400ms
- Browser navigates naturally; no "complete" animation needed
- Covered links across all templates: Dashboard, Zpět do aplikace, Uživatelé, Odhlásit

### HTML — add as first child of `<body>` in all three templates

```html
<div id="nav-bar"></div>
```

### CSS — add to each template's `<style>` block

```css
#nav-bar {
  position: fixed; top: 0; left: 0; height: 3px; width: 0;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  box-shadow: 0 0 8px #6366f188;
  transition: width .4s cubic-bezier(.4,0,.2,1);
  pointer-events: none; z-index: 9999;
}
```

### JS — `startNavBar()` in `app.js` (index.html) and inline `<script>` (dashboard.html, admin_users.html)

```js
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
```

> **Note:** Download links in `index.html` start with `href="#"` and are updated to real URLs only after report generation. The `DOMContentLoaded` listener-attachment catches them at `#`, so they are excluded. They are plain `<a download>` links that don't navigate the page anyway.

### Templates to update

| Template | Nav bar `<div>` | CSS | JS |
|----------|-----------------|-----|----|
| `templates/index.html` | ✓ | ✓ | in `app.js` |
| `templates/dashboard.html` | ✓ | ✓ | inline `<script>` |
| `templates/admin_users.html` | ✓ | ✓ | inline `<script>` |

---

## Files Changed

| File | Change |
|------|--------|
| `static/app.js` | Add `setLoading()` + `startNavBar()`; wrap 5 async functions; add `id` refs; update `confirmDeleteContract` signature |
| `templates/index.html` | Add `id` to 3 buttons; add `#nav-bar` div; add nav bar + dots CSS |
| `templates/dashboard.html` | Add `#nav-bar` div; add nav bar + dots CSS + `dotPulse` keyframe; update `downloadReport` + `confirmDelete` signatures; add inline JS |
| `templates/admin_users.html` | Add `#nav-bar` div; add nav bar CSS + inline JS only |

## Out of Scope
- Login page (no async actions, single form submit)
- `admin_users.html` form submit buttons (full page reload, no JS async)
