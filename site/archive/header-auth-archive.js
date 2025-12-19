// /site/scripts/header-auth.js
// Purpose:
// 1) Create a global Supabase client (window.supabase)
// 2) Toggle Login/Logout buttons when toolbar is present
// Safe to include on ANY auth page.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// --- CONFIG (real values) ---
const SUPABASE_URL  = "https://acqondggldnrsjmonlge.supabase.co";
const SUPABASE_ANON = "sb_publishable_0spAIB_glwzHk84bklBFdgg_CkJNwUYF";
// ----------------------------

// DEBUG: prove what this file is actually using
console.log("[header-auth] SUPABASE_URL =", SUPABASE_URL);
console.log("[header-auth] SUPABASE_ANON starts with =", SUPABASE_ANON.slice(0, 14));

if (!SUPABASE_URL || !/^https?:\/\//i.test(SUPABASE_URL)) {
  throw new Error("[header-auth] Bad SUPABASE_URL at runtime: " + SUPABASE_URL);
}

// Create global client once
if (!window.supabase) {
  window.supabase = createClient(SUPABASE_URL, SUPABASE_ANON);
  console.log("[header-auth] window.supabase created ✅");
}

// 2) Helper to wait a bit for injected header/toolbar to appear
function waitForEl(id, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const tick = () => {
      const el = document.getElementById(id);
      if (el) return resolve(el);
      if (Date.now() - start > timeoutMs) return resolve(null);
      requestAnimationFrame(tick);
    };
    tick();
  });
}

// 3) Wire login/logout UI if those elements exist
(async function wireAuthControls() {
  const loginLink = await waitForEl("loginLink");
  const logoutBtn = await waitForEl("logoutBtn");

  // If this page doesn’t have a toolbar, bail quietly.
  if (!loginLink || !logoutBtn) return;

  // Default state
  logoutBtn.classList.add("hidden");
  loginLink.style.display = "";

  try {
    const { data, error } = await window.supabase.auth.getUser();
    const user = data?.user;

    if (!error && user) {
      // Logged in
      loginLink.style.display = "none";
      logoutBtn.classList.remove("hidden");
    } else {
      // Logged out
      loginLink.style.display = "";
      logoutBtn.classList.add("hidden");
    }
  } catch (err) {
    console.warn("Auth UI init failed (non-fatal):", err);
  }

  // Logout click handler
  logoutBtn.addEventListener("click", async () => {
    try {
      await window.supabase.auth.signOut();
      location.href = "/index.html";
    } catch (err) {
      console.error("Logout failed:", err);
      alert("Could not log out. Please try again.");
    }
  });
})();
