// === Firebase imports ===
import { auth } from './firebase-app.js';
import { sendPasswordResetEmail } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-auth.js";

// === Helpers ===
function setStatus(msg, kind='info') {
  const el = document.getElementById('status');
  el.className = '';
  if (kind === 'error') el.style.color = '#dc2626';
  else if (kind === 'success') el.style.color = '#16a34a';
  else el.style.color = '#555';
  el.textContent = msg;
}

const form = document.getElementById('forgotForm');
const sendBtn = document.getElementById('sendBtn');
const afterSend = document.getElementById('afterSend');

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = /** @type {HTMLInputElement} */(document.getElementById('email')).value.trim();
  if (!email) return setStatus('Please enter your email.', 'error');

  setStatus('Sending reset email…');
  sendBtn.disabled = true;

try {
  const actionSettings = {
    url: 'http://127.0.0.1:5500/site/auth/login.html',
    handleCodeInApp: false
  };

  await sendPasswordResetEmail(auth, email, actionSettings);
  setStatus('Reset email sent. Check your inbox for the link.', 'success');
  afterSend.classList.remove('hidden');
} catch (err) {
  ...
}


    // Friendly error handling
    const code = err?.code || '';
    if (code === 'auth/invalid-email') setStatus('That email address looks invalid.', 'error');
    else if (code === 'auth/user-not-found') setStatus('No account found with that email.', 'error');
    else if (code === 'auth/too-many-requests') setStatus('Too many attempts. Try again in a few minutes.', 'error');
    else if (code === 'auth/network-request-failed') setStatus('Network error. Check your connection.', 'error');
    else setStatus('Could not send reset email. Please try again.', 'error');

    sendBtn.disabled = false;
    return;
  }
});
