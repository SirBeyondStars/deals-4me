// header-auth.js — toggle Login/Logout in the injected header

// 1) Configure Supabase once here (same values you use on index.html)
const SUPABASE_URL  = "https://YOUR-PROJECT.supabase.co";
const SUPABASE_ANON = "YOUR-ANON-KEY";
const supabaseClient = window.supabase
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON)
  : null;

// 2) Hook up header controls after header fragment exists
(async function wireAuthControls() {
  const loginLink  = document.getElementById("loginLink");
  const logoutBtn  = document.getElementById("logoutBtn");

  if (!loginLink || !logoutBtn) return; // header not yet injected

  // Ensure default state (hide logout by default)
  logoutBtn.classList.add("hidden");
  loginLink.style.display = "";

  if (!supabaseClient) return; // Supabase not on this page

  // Get current user
  const { data } = await supabaseClient.auth.getUser();
  const user = data?.user;

  if (user) {
    // Logged in: show Logout, hide Login
    loginLink.style.display = "none";
    logoutBtn.classList.remove("hidden");
  } else {
    // Logged out
    loginLink.style.display = "";
    logoutBtn.classList.add("hidden");
  }

  // Bind logout
  logoutBtn.addEventListener("click", async () => {
    try {
      await supabaseClient.auth.signOut();
      // simple refresh to reset UI
      location.href = "/index.html";
    } catch (e) {
      console.error("Logout failed:", e);
      alert("Could not log out. Please try again.");
    }
  });
})();
