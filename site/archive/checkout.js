// /js/checkout.js
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

/** ⬇️ Fill these 2 with your real project values (NO angle brackets) */
const SUPABASE_URL = "https://acoqndggldnrsjmonlge.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjb3FuZGdnbGRucnNqbW9ubGdlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ3ODk5NjMsImV4cCI6MjA3MDM2NTk2M30.ka4l5Xnwwcl913awGdjyfXY_Y-DE3gyg6Nndg7gih4o";

/** ⬇️ Your deployed function URL */
const FUNCTION_URL = "https://acoqndggldnrsjmonlge.supabase.co/functions/v1/create-checkout-session";

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function refreshStatus() {
  const { data: { session } } = await supabase.auth.getSession();
  const el = document.getElementById("status");
  if (el) el.textContent = session ? `Signed in as ${session.user.email}` : "Not signed in";
}

async function startCheckout(planKey = "gold_monthly") {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    alert("Please sign in first.");
    return;
  }
  const res = await fetch(FUNCTION_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${session.access_token}`
    },
    body: JSON.stringify({ planKey })
  });
  if (!res.ok) {
    const msg = await res.text();
    alert("Checkout failed: " + msg);
    return;
  }
  const { url } = await res.json();
  location.href = url; // Stripe Checkout
}

// Optional quick auth helpers for testing:
async function signIn() {
  const email = document.getElementById("email")?.value?.trim();
  const password = document.getElementById("password")?.value;
  if (!email || !password) return alert("Enter email + password");

  let { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    const { error: signUpErr } = await supabase.auth.signUp({ email, password });
    if (signUpErr) return alert("Auth error: " + signUpErr.message);
  }
  await refreshStatus();
  alert("Signed in.");
}
async function signOut() { await supabase.auth.signOut(); await refreshStatus(); }

window.startCheckout = startCheckout; // expose for buttons
window.signIn = signIn;
window.signOut = signOut;
window.addEventListener("load", refreshStatus);

// Attach listeners once DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  const gold = document.getElementById("btn-gold");
  const plat = document.getElementById("btn-platinum");

  if (gold) gold.addEventListener("click", () => startCheckout("gold_monthly"));
  if (plat) plat.addEventListener("click", () => startCheckout("platinum_monthly"));

  console.log("checkout.js loaded; buttons wired");
});

// (Optional) keep these if you use the quick auth box
window.signIn = signIn;
window.signOut = signOut;
