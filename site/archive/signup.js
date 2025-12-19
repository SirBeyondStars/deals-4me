// === Firebase imports ===
import { auth, db } from './firebase-app.js';
import { createUserWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-auth.js";
import { doc, setDoc } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js";

// === Local helper imports ===
import { wirePinRow, show, setStatus, sha256Hex } from './pin-utils.js';

// STEP 1 — Email + password
const signupForm = document.getElementById('signupForm');
signupForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = /** @type {HTMLInputElement} */(document.getElementById('email')).value.trim();
  const pw    = /** @type {HTMLInputElement} */(document.getElementById('password')).value;

  if (!email || !pw) return setStatus('Please enter your email and a password.');

  setStatus('Creating account…');
  try {
    const cred = await createUserWithEmailAndPassword(auth, email, pw);
    const uid = cred.user.uid;

    // reveal the PIN step and remember uid for PIN save
    show('signupForm', false);
    show('setPinStep', true);
    document.body.dataset.signupUid = uid;
    setStatus('Now set your 6-digit PIN.');
  } catch (err) {
    console.error(err);
    setStatus(err?.message || 'Sign up failed.');
  }
});

// STEP 2 — Set PIN (create + confirm)
const getNewA = wirePinRow(['sp1','sp2','sp3','sp4','sp5','sp6']);
const getNewB = wirePinRow(['spc1','spc2','spc3','spc4','spc5','spc6']);

document.getElementById('setPinBtn')?.addEventListener('click', async () => {
  const uid = document.body.dataset.signupUid || '';
  if (!uid) return setStatus('Please complete email & password first.');

  const a = getNewA();
  const b = getNewB();

  if (a.length !== 6) return setStatus('Enter all 6 digits.');
  if (b.length !== 6) return setStatus('Please confirm all 6 digits.');
  if (a !== b)        return setStatus('PINs do not match.');

  setStatus('Saving PIN…');
  try {
    // optional salting with uid for extra safety
    const pinHash = await sha256Hex(`${uid}:${a}`);

    await setDoc(doc(db, 'users', uid), { pinHash }, { merge: true });

    setStatus('Account created! Redirecting to login…');
    // redirect to login page
    window.location.href = './login.html';
  } catch (err) {
    console.error(err);
    setStatus(err?.message || 'Could not save PIN.');
  }
});
