// flyers.js — flyer data, rendering, and product search
import { state } from './stores.js';

// Mock flyer items until backend is ready
const mockFlyers = [
  { id:'f1', storeId:'shaw-001', store:"Shaw's", title:'Cheerios 10.8oz', price:2.49, reg:3.99, cat:'Groceries' },
  { id:'f2', storeId:'sns-002', store:'Stop & Shop', title:'2% Milk Gallon', price:3.29, reg:3.79, cat:'Groceries' },
  { id:'f3', storeId:'tgt-003', store:'Target', title:'Paper Towels 6-roll', price:5.99, reg:7.49, cat:'Household' },
  { id:'f4', storeId:'shaw-001', store:"Shaw's", title:'Ibuprofen 100ct', price:6.99, reg:8.99, cat:'Pharmacy' },
  { id:'f5', storeId:'sns-002', store:'Stop & Shop', title:'Coke 12-pack (2/$5)', price:2.50, reg:6.49, cat:'Specials' },
  { id:'f6', storeId:'tgt-003', store:'Target', title:'Pasta 16oz', price:0.99, reg:1.49, cat:'Groceries' },
];

export function money(n){ return `$${n.toFixed(2)}`; }
export function activeStoreIds(){
  return state.showPrimaryOnly
    ? state.savedStores.filter(s=>s.isPrimary).map(s=>s.id)
    : state.savedStores.map(s=>s.id);
}

function skeleton(n=6){
  const grid = document.querySelector('#flyerGrid');
  grid.innerHTML = '';
  for(let i=0;i<n;i++){
    const col = document.createElement('div');
    col.className = 'span-4';
    col.innerHTML = '<div class="skeleton"></div>';
    grid.appendChild(col);
  }
  const car = document.querySelector('#flyerCarousel');
  car.className = '';
  car.textContent = 'Loading deals…';
}

export function getFlyers({cat=null, q=null}={}){
  // TODO: Replace with Supabase select using active store ids + week + optional category/search
  let data = mockFlyers.filter(f => activeStoreIds().includes(f.storeId));
  if(cat) data = data.filter(d => d.cat === cat);
  if(q){
    const t = q.toLowerCase();
    data = data.filter(d => d.title.toLowerCase().includes(t) || d.store.toLowerCase().includes(t));
  }
  return new Promise(resolve => setTimeout(()=>resolve(data), 400)); // mimic network
}

export async function renderFlyers(cat=null, q=null){
  const grid = document.querySelector('#flyerGrid');
  const carousel = document.querySelector('#flyerCarousel');

  if(!state.savedStores.length){
    grid.innerHTML = '';
    carousel.className = 'empty';
    carousel.textContent = 'Top weekly deals will appear here once you’ve saved stores.';
    return;
  }

  skeleton();
  const data = await getFlyers({cat, q});
  if(data.length === 0){
    carousel.className = 'empty';
    carousel.textContent = q ? 'No products matched your search. Try another term or clear search.' : 'No active flyers for the selected filters. Try a different category or show all stores.';
    grid.innerHTML = '';
    return;
  }

  carousel.className = '';
  carousel.textContent = q ? `Results for “${q}”` : 'Top weekly deals';
  grid.innerHTML = '';

  data.forEach(d => {
    const col = document.createElement('div');
    col.className = 'span-4';
    col.innerHTML = `
      <div class="card flyer-card">
        <div class="flyer-img">${d.store[0]||'S'}</div>
        <div class="flyer-meta">
          <div style="font-weight:700">${d.title}</div>
          <div class="muted" style="margin:.1rem 0">${d.store} • ${d.cat}</div>
          <div><strong>${money(d.price)}</strong> <span class="muted">Reg ${money(d.reg)}</span></div>
          <div class="row mt05">
            <button class="btn ghost" type="button" onclick='window.addToListUI(${JSON.stringify(JSON.stringify(d))})'>Save</button>
            <button class="btn" type="button" onclick='window.addToListUI(${JSON.stringify(JSON.stringify(d))}, true)'>Add to List</button>
          </div>
        </div>
      </div>`;
    grid.appendChild(col);
  });
}

window.renderFlyersUI = () => renderFlyers();
