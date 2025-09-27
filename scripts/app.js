// app.js — wires events and page init (with ZIP "Go" arrow button)
import {
  state,
  mockStores,
  initStores,
  renderStoreResults,
  renderNoStoresEmpty,
  enableQuickSearch,
  setPrimary,
  removeStore,
  moveStore,
} from './stores.js';
import { renderFlyers } from './flyers.js';
import { renderShopping, exportCSV, printList, clearList } from './list.js';

function renderYear() {
  document.querySelector('#year').textContent = new Date().getFullYear();
}

/* ---------------------------
   Tabs (keyboard accessible)
---------------------------- */
function selectTab(id) {
  document.querySelectorAll('.tabs .tab').forEach((t) => {
    const active = t.dataset.tab === id;
    t.classList.toggle('active', active);
    t.setAttribute('aria-selected', String(active));
    document.getElementById(`tab-${t.dataset.tab}`).style.display = active ? 'block' : 'none';
  });
}
function tabsKeyboardNav() {
  const tabs = Array.from(document.querySelectorAll('.tabs .tab'));
  tabs.forEach((tab, idx) => {
    tab.addEventListener('keydown', (e) => {
      let nextIdx = idx;
      if (e.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
      if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
      if (e.key === 'Home') nextIdx = 0;
      if (e.key === 'End') nextIdx = tabs.length - 1;
      if (nextIdx !== idx) {
        e.preventDefault();
        tabs[nextIdx].focus();
        selectTab(tabs[nextIdx].dataset.tab);
      }
    });
  });
}

/* ---------------------------
   Sticky quick search
---------------------------- */
function setupSticky() {
  const sticky = document.querySelector('#stickySearch');
  const hero = document.querySelector('#heroCard');
  function toggle() {
    const pastHero = window.scrollY > hero.offsetTop + hero.offsetHeight - 16;
    const hasStore = state.savedStores.length > 0;
    sticky.style.display = pastHero && hasStore ? 'block' : 'none';
  }
  window.addEventListener('scroll', toggle, { passive: true });
  window.addEventListener('resize', toggle);
  toggle();
}

/* ---------------------------
   Utils
---------------------------- */
function debounce(fn, wait = 500) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

/* ---------------------------
   Store search trigger
---------------------------- */
async function triggerFindStores() {
  const zipEl = document.querySelector('#zip');
  const zip = (zipEl?.value || '').trim();
  const msg = document.querySelector('#zipMsg');
  if (msg) msg.textContent = '';
  if (zip && !/^[0-9]{5}$/.test(zip)) {
    if (msg) msg.textContent = 'Please enter a valid 5-digit ZIP.';
    zipEl?.focus();
    return;
  }
  const target = document.querySelector('#storeResults');
  if (target) target.innerHTML = '<div class="muted">Searching stores…</div>';
  try {
    // TODO: Replace with Supabase RPC: get stores within state.radius of ZIP or geo
    let results = mockStores; // demo data
    if (zip && zip !== '02324') results = []; // simulate “no rows returned”
    if (results.length === 0) {
      renderNoStoresEmpty();
      return;
    }
    renderStoreResults(results);
    enableQuickSearch();
  } catch (e) {
    if (target) target.innerHTML = '<div class="empty">There was an error fetching stores. Please try again.</div>';
  }
}

/* ---------------------------
   Manage Stores Modal
---------------------------- */
function openStoresModal() {
  const dlg = document.querySelector('#storesModal');
  const list = document.querySelector('#storesListModal');
  if (!dlg || !list) return;

  list.innerHTML = '';
  if (state.savedStores.length === 0) {
    list.innerHTML = '<div class="empty">No saved stores yet.</div>';
  } else {
    state.savedStores.forEach((s) => {
      const row = document.createElement('div');
      row.className = 'store-row';
      row.innerHTML = `
        <div>
          <div style="font-weight:700">${s.name}${s.isPrimary ? ' ★' : ''}</div>
          <div class="muted">${s.addr || ''}</div>
        </div>
        <div class="store-actions"><button class="pill" type="button" aria-label="Move up">⬆</button></div>
        <div
