// Helper utilities shared by login & signup

// at top of pin-utils.js
import { db } from './firebase-app.js';
import { doc, getDoc, setDoc } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js";

export async function savePinHashForEmail(email, pinHash) {
  const ref = doc(db, 'users', email.toLowerCase());
  await setDoc(ref, { pinHash }, { merge: true });
}
export async function getPinHashForEmail(email) {
  const snap = await getDoc(doc(db, 'users', email.toLowerCase()));
  return snap.exists() ? (snap.data().pinHash || null) : null;
}

export function wirePinRow(ids) {
  const inputs = ids.map(id => /** @type {HTMLInputElement} */(document.getElementById(id)));
  inputs.forEach((inp, idx) => {
    inp.addEventListener('input', () => {
      inp.value = inp.value.replace(/\D/g, '').slice(0, 1);
      if (inp.value && idx < inputs.length - 1) inputs[idx + 1].focus();
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !inp.value && idx > 0) inputs[idx - 1].focus();
    });
  });
  return () => inputs.map(i => i.value).join('');
}

export function clearPinRow(ids) {
  ids.forEach(id => { const el = /** @type {HTMLInputElement} */(document.getElementById(id)); if (el) el.value = ''; });
  const first = document.getElementById(ids[0]);
  if (first) first.focus();
}

export function show(elOrId, showIt = true) {
  const el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId;
  if (!el) return;
  el.classList.toggle('hidden', !showIt);
}

export function setStatus(msg) {
  const el = document.getElementById('status');
  if (el) el.textContent = msg;
}

export async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hashBuf = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hashBuf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

/* ------------------------------------------------------------------
   Simple storage that works now; swap these to Firestore later.
   Keyed by email. Stores pinHash only.
-------------------------------------------------------------------*/
const KEY = 'd4m_pin_hash_by_email';

function readMap() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); }
  catch { return {}; }
}
function writeMap(map) { localStorage.setItem(KEY, JSON.stringify(map)); }

/** Save hash for an email */
export async function savePinHashForEmail(email, pinHash) {
  const map = readMap();
  map[email.toLowerCase()] = { pinHash };
  writeMap(map);
}

/** Get hash for an email (null if none) */
export async function getPinHashForEmail(email) {
  const map = readMap();
  const rec = map[email.toLowerCase()];
  return rec?.pinHash || null;
}
