// /site/scripts/login.js  (Supabase version — NO Firebase, NO PIN yet)
console.log("🔥 LOGIN.JS SERVED FILE = SUPABASE VERSION 🔥");
const form = document.getElementById("loginForm");
const statusEl = document.getElementById("loginStatus");

function setStatus(msg, isError = false) {
  if (!statusEl) return;
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("error", !!isError);
}

form?.addEventListener("submit", async (e) => {
  e.preventDefault();

  // header-auth.js must create window.supabase first
  const supabase = window.supabase;
  if (!supabase) {
    setStatus("Supabase not ready. Check header-auth.js loading first.", true);
    return;
  }

  const email = document.getElementById("email")?.value.trim();
  const password = document.getElementById("password")?.value;

  if (!email || !password) {
    setStatus("Enter email + password.", true);
    return;
  }

  setStatus("Signing in…");

  try {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (error) {
      setStatus(error.message || "Login failed.", true);
      return;
    }

    if (!data?.user) {
      setStatus("No user returned. Are you confirmed?", true);
      return;
    }

    setStatus("Success! Redirecting…");

    // go wherever makes sense for now
    window.location.href = "../flyers.html";
  } catch (err) {
    console.error(err);
    setStatus("Login crashed. Check console.", true);
  }
});
