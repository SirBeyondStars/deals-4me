console.log("[toolbar] toolbar.js loaded");

async function loadToolbar() {
  // FIX: look for #toolbar instead of #toolbar-container
  const container = document.getElementById("toolbar");
  if (!container) {
    console.log("[toolbar] no #toolbar on this page");
    return;
  }

  try {
    const response = await fetch("toolbar.html");
    const html = await response.text();
    container.innerHTML = html;

    // Active profile pill
    try {
      const raw = localStorage.getItem("d4m_active_profile");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.profileName) {
          const pill = document.getElementById("toolbar-user-pill");
          if (pill) pill.textContent = parsed.profileName;
        }
      }
    } catch (e) {
      console.warn("[toolbar] error reading active profile", e);
    }

   // Logout button
const logoutBtn = document.getElementById("toolbar-logout-btn");

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    // Clear PIN / profile session only
    localStorage.removeItem("d4m_active_profile");

    // Keep Supabase session alive (email stays authenticated)
    window.location.href = "pin.html";
  });
}


  } catch (err) {
    console.error("[toolbar] failed to load toolbar.html", err);
  }
}

document.addEventListener("DOMContentLoaded", loadToolbar);
