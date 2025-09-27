// list.js — shopping list state, rendering, export/print (with persistence)
import { money } from './flyers.js';

const LS_KEY = 'd4m.shopping';

export const listState = { items: [] }; // [{id,title,store,price,reg,qty}]

// ---------- persistence ----------
function loadList(){
  try { listState.items = JSON.parse(localStorage.getItem(LS_KEY) || '[]'); }
  catch { listState.items = []; }
}
function saveList(){
  localStorage.setItem(LS_KEY, JSON.stringify(listState.items));
}

// ---------- mutators ----------
export function addToList(serialized, jump=false){
  const d = JSON.parse(serialized);
  const existing = listState.items.find(x=>x.id===d.id);
  if(existing){ existing.qty += 1; }
  else { listState.items.push({ id:d.id, title:d.title, store:d.store, price:d.price, reg:d.reg, qty:1 }); }
  saveList(); renderShopping();
  if(jump) window.selectTabUI('shopping');
}

export function incQty(id){
  const it = listState.items.find(i=>i.id===id);
  if(it){ it.qty += 1; saveList(); renderShopping(); }
}

export function decQty(id){
  const it = listState.items.find(i=>i.id===id);
  if(!it) return;
  it.qty -= 1;
  if(it.qty<=0){ listState.items = listState.items.filter(i=>i.id!==id); }
  saveList(); renderShopping();
}

export function clearList(){
  if(!listState.items.length) return;
  if(confirm('Clear your entire shopping list?')){ listState.items = []; saveList(); renderShopping(); }
}

// ---------- render ----------
export function renderShopping(){
  const root = document.querySelector('#shoppingList');
  root.innerHTML = '';
  if(listState.items.length === 0){
    root.innerHTML = '<div class="span-12 empty">Nothing saved yet. Add items from Flyers.</div>';
    document.querySelector('#shoppingTotals').textContent = 'Est. savings: $0.00';
    return;
  }
  let est = 0;
  listState.items.forEach(item => {
    est += Math.max(item.reg - item.price, 0) * item.qty;
    const row = document.createElement('div');
    row.className = 'span-6';
    row.innerHTML = `
      <div class="list-item">
        <div>
          <div style="font-weight:700">${item.title}</div>
          <div class="muted">${item.store}</div>
          <div><strong>${money(item.price)}</strong> <span class="muted">Reg ${money(item.reg)}</span></div>
        </div>
        <div class="qty">
          <button type="button" aria-label="Decrease quantity" onclick="window.decQtyUI('${item.id}')">−</button>
          <span aria-live="polite">${item.qty}</span>
          <button type="button" aria-label="Increase quantity" onclick="window.incQtyUI('${item.id}')">+</button>
        </div>
      </div>`;
    root.appendChild(row);
  });
  document.querySelector('#shoppingTotals').textContent = `Est. savings: ${money(est)}`;
}

// ---------- utilities ----------
export function exportCSV(){
  const rows = [['Title','Store','Price','Reg','Qty']];
  listState.items.forEach(i => rows.push([i.title, i.store, i.price, i.reg, i.qty]));
  const csv = rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type:'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'shopping_list.csv';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
export function printList(){ window.print(); }

// expose for inline handlers
window.addToListUI = addToList;
window.incQtyUI   = incQty;
window.decQtyUI   = decQty;

// load on import
loadList();
