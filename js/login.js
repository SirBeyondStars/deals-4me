// === Firebase imports ===
import { auth, db } from './firebase-app.js';
import { signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-auth.js";
import { doc, getDoc } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js";

// === Local helper imports ===
import { wirePinRow, clearPinRow, show, setStatus, sha256Hex } from './pin-utils.js';

// STEP 1 — Email + password
const emailPassForm = document.getElementById('emailPassForm');
emailPassForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = /** @type {HTMLInputElement} */(document.getElementById('email')).value.trim();
  const pw    = /** @type {HTMLInputElement} */(document.getElementById('password')).value;

  if (!email || !pw) return setStatus('Please enter your email and password.');

  setStatus('Checking account…');
  try {
    const cred = await signInWithEmailAndPassword(auth, email, pw);
    const uid = cred.user.uid;

    // reveal PIN step and remember uid
    show('emailPassForm', false);
    show('pinStep', true);
    document.body.dataset.loginUid = uid;
    setStatus('Enter your 6-digit PIN and confirm it.');
  } catch (err) {
    console.error(err);
    setStatus(err?.message || 'Login failed.');
  }
});

// STEP 2 — PIN (enter + confirm)
const getA = wirePinRow(['pin1','pin2','pin3','pin4','pin5','pin6']);
const getB = wirePinRow(['pinc1','pinc2','pinc3','pinc4','pinc5','pinc6']);

document.getElementById('pinSubmitBtn')?.addEventListener('click', async () => {
  const uid = document.body.dataset.loginUid || '';
  if (!uid) return setStatus('Please start with your email and password.');

  const pinA = getA();
  const pinB = getB();

  if (pinA.length !== 6) return setStatus('Enter all 6 digits.');
  if (pinB.length !== 6) return setStatus('Please confirm all 6 digits.');
  if (pinA !== pinB)     return setStatus('PINs do not match.');

  setStatus('Checking PIN…');
  try {
    const snap = await getDoc(doc(db, 'users', uid));
    const storedHash = snap.exists() ? snap.data().pinHash : null;

    if (!storedHash) {
      setStatus('No stored PIN for this account.');
      return;
    }

    const enteredHash = await sha256Hex(`${uid}:${pinA}`);
    if (enteredHash !== storedHash) {
      setStatus('Incorrect PIN. Try again.');
      clearPinRow(['pin1','pin2','pin3','pin4','pin5','pin6']);
      clearPinRow(['pinc1','pinc2','pinc3','pinc4','pinc5','pinc6']);
      return;
    }

    setStatus('Success! Redirecting…');
    // go to your app
    window.location.href = '../dashboard.html';
  } catch (err) {
    console.error(err);
    setStatus(err?.message || 'PIN check failed.');
  }
});

document.getElementById('switchBtn')?.addEventListener('click', () => {
  show('pinStep', false);
  show('emailPassForm', true);
  setStatus('');
  clearPinRow(['pin1','pin2','pin3','pin4','pin5','pin6']);
  clearPinRow(['pinc1','pinc2','pinc3','pinc4','pinc5','pinc6']);
});
