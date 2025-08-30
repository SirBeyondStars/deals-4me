// scripts/logout.js
import { supabase } from "./supabaseClient.js";

// Guard: if not logged in, bounce to login
supabase.auth.getSession().then(({ data: { session } }) => {
  if (!session?.user) window.location.href = "login.html";
});

// Logout button handler
const logoutBtn = document.querySelector("#logout-btn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await supabase.auth.signOut();
    window.location.href = "login.html";
  });
}
