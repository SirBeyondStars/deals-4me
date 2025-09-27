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
        <div class="store-actions"><button class="pill" type="button" aria-label="Move down">⬇</button></div>
        <div class="store-actions">
          <button class="pill" type="button" aria-label="Set primary">Primary</button>
          <button class="pill" type="button" aria-label="Remove">Remove</button>
        </div>`;
      const [up, down, primaryBtn, removeBtn] = row.querySelectorAll('button');
      up.addEventListener('click', () => window.moveStoreUI(s.id, 'up'));
      down.addEventListener('click', () => window.moveStoreUI(s.id, 'down'));
      primaryBtn.addEventListener('click', () => window.setPrimaryUI(s.id));
      removeBtn.addEventListener('click', () => window.removeStoreUI(s.id));
      list.appendChild(row);
    });
  }
  dlg.showModal();
}

/* ---------------------------
   Event wiring
---------------------------- */
function wireEvents() {
  // Radius
  document.querySelector('#radius')?.addEventListener('change', (e) => {
    state.radius = Number(e.target.value);
  });

  // Geolocation
  document.querySelector('#useLocation')?.addEventListener('click', () => {
    if (!navigator.geolocation) {
      alert('Geolocation not supported.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        state.geo = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      },
      () => alert('Could not get your location.')
    );
  });

  // ZIP “Go” arrow button + form submit (Enter)
  document.querySelector('#goFindStores')?.addEventListener('click', triggerFindStores);
  document.querySelector('#storeFinderForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    triggerFindStores();
  });

  // Manage stores modal
  document.querySelector('#manageStores')?.addEventListener('click', () => openStoresModal());

  // Tabs
  document.querySelectorAll('.tabs .tab').forEach((tab) => {
    tab.addEventListener('click', () => selectTab(tab.dataset.tab));
  });
  tabsKeyboardNav();

  // Flyer category pills
  document.querySelectorAll('#flyerCats .pill').forEach((pill) => {
    pill.addEventListener('click', () => renderFlyers(pill.dataset.cat));
  });

  // Shopping list actions
  document.querySelector('#exportList')?.addEventListener('click', exportCSV);
  document.querySelector('#clearList')?.addEventListener('click', clearList);
  document.querySelector('#printList')?.addEventListener('click', printList);

  // Quick search (debounced) + Enter
  const doSearch = debounce((q) => {
    renderFlyers(null, q || null);
  }, 500);
  document.querySelector('#quickQuery')?.addEventListener('input', (e) =>
    doSearch(e.currentTarget.value.trim())
  );
  document.querySelector('#quickQuery')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      renderFlyers(null, e.currentTarget.value.trim() || null);
    }
  });
}

/* ---------------------------
   Init
---------------------------- */
function init() {
  renderYear();
  initStores();
  renderShopping();
  renderFlyers();
  setupSticky();
}

// expose for other modules & inline callbacks
window.selectTabUI = selectTab;
window.openStoresModal = openStoresModal;
window.setPrimaryUI = (id) => {
  setPrimary(id);
  openStoresModal();
};
window.removeStoreUI = (id) => {
  removeStore(id);
  openStoresModal();
};
window.moveStoreUI = (id, dir) => {
  moveStore(id, dir);
  openStoresModal();
};

// Kickoff
window.addEventListener('DOMContentLoaded', () => {
  wireEvents();
  init();
});
