// stores.js — saved stores state, search, and rendering
export const state = {
  savedStores: [], // [{id, name, addr, isPrimary}]
  showPrimaryOnly: false,
  radius: 10,
  geo: null,
  quickSearchEnabled: false,
};

// --- Mock data until Supabase is wired ---
export const mockStores = [
  { id: 'shaw-001', name: "Shaw's Bridgewater", addr: '35 Bedford St, Bridgewater, MA' },
  { id: 'sns-002', name: 'Stop & Shop West Bridgewater', addr: '50 Main St, West Bridgewater, MA' },
  { id: 'tgt-003', name: 'Target Easton', addr: '41 Robert Dr, South Easton, MA' },
];

export function initStores(){
  loadSavedStores();
  if(state.savedStores.length === 0){
    state.savedStores = [{...mockStores[0], isPrimary:true}];
    saveStoresLocal();
  }
}

export function loadSavedStores(){
  try {
    const raw = localStorage.getItem('savedStores');
    state.savedStores = raw ? JSON.parse(raw) : [];
  } catch { state.savedStores = []; }
  renderSavedStores();
}

export function saveStoresLocal(){
  localStorage.setItem('savedStores', JSON.stringify(state.savedStores));
  renderSavedStores();
}

export function setPrimary(id){
  state.savedStores = state.savedStores.map(s => ({...s, isPrimary: s.id === id}));
  saveStoresLocal();
  // TODO: persist to Supabase profiles.primary_store_id
}

export function removeStore(id){
  state.savedStores = state.savedStores.filter(s=>s.id!==id);
  if(!state.savedStores.some(s=>s.isPrimary) && state.savedStores[0]){
    state.savedStores[0].isPrimary = true;
  }
  saveStoresLocal();
}

export function moveStore(id, dir){
  const i = state.savedStores.findIndex(s=>s.id===id);
  if(i<0) return;
  const j = i + (dir==='up'?-1:1);
  if(j<0 || j>=state.savedStores.length) return;
  const arr = state.savedStores;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  saveStoresLocal();
}

export function addStore(store){
  if(!state.savedStores.some(s=>s.id===store.id)){
    state.savedStores.push({ id: store.id, name: store.name, addr: store.addr, isPrimary: state.savedStores.length===0 });
    saveStoresLocal();
  }
}

export function renderStoreResults(results){
  const target = document.querySelector('#storeResults');
  target.innerHTML = '';
  results.forEach(r => {
    const row = document.createElement('div');
    row.className = 'row';
    row.style.cssText = 'align-items:center;justify-content:space-between;border-bottom:1px solid #e5e7eb;padding:.5rem 0';
    row.innerHTML = `<div><strong>${r.name}</strong><div class="muted">${r.addr}</div></div>`;
    const btn = document.createElement('button');
    btn.className = 'btn'; btn.type = 'button'; btn.textContent = 'Save';
    btn.onclick = () => addStore(r);
    row.appendChild(btn);
    target.appendChild(row);
  });
}

export function renderNoStoresEmpty(){
  document.querySelector('#storeResults').innerHTML = `
    <div class="empty">
      No results yet for your area. Try increasing the radius or different ZIP.<br/>
      <div style="margin-top:.5rem" class="row">
        <button class="btn ghost" type="button" onclick="window.suggestRadius(5)">+5 mi</button>
        <button class="btn ghost" type="button" onclick="window.suggestRadius(10)">+10 mi</button>
        <button class="btn ghost" type="button" onclick="window.loadSavedStoresUI()">Show Saved Stores</button>
      </div>
    </div>`;
}

export function enableQuickSearch(){
  if(state.quickSearchEnabled) return;
  state.quickSearchEnabled = true;
  const names = state.savedStores.map(s=>s.name).slice(0,2).join(' & ');
  document.querySelector('#quickQuery').placeholder = names ? `Search at ${names}…` : 'Search products at your saved stores…';
}

export function disableQuickSearch(){
  state.quickSearchEnabled = false;
}

export function renderSavedStores(){
  const list = document.querySelector('#savedStoresList');
  list.innerHTML = '';
  if(!state.savedStores.length){
    list.innerHTML = '<div class="muted">No saved stores yet.</div>';
    document.querySelector('#primaryBadge').textContent = 'Primary: —';
    disableQuickSearch();
    const car = document.querySelector('#flyerCarousel');
    car.className = 'empty';
    car.textContent = 'Top weekly deals will appear here once you’ve saved stores.';
    document.querySelector('#flyerGrid').innerHTML = '';
    return;
  }
  state.savedStores.slice(0,3).forEach(s => {
    const btn = document.createElement('button');
    btn.className = 'pill'; btn.type = 'button'; btn.title = 'Click to set as Primary';
    btn.textContent = s.name + (s.isPrimary ? ' ★' : '');
    btn.onclick = () => setPrimary(s.id);
    list.appendChild(btn);
  });
  const primary = state.savedStores.find(s=>s.isPrimary);
  document.querySelector('#primaryBadge').textContent = 'Primary: ' + (primary ? primary.name : '—');
  enableQuickSearch();
  if(window.renderFlyersUI){ window.renderFlyersUI(); }
}

// UI helpers for inline callbacks
window.suggestRadius = function(extra){
  const sel = document.querySelector('#radius');
  const cur = Number(sel.value);
  const next = Math.min(20, cur + extra);
  sel.value = String(next);
  state.radius = next;
}
window.loadSavedStoresUI = loadSavedStores;
