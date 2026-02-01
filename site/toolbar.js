// site/scripts/toolbar.js
console.log("[toolbar] toolbar.js loaded");

(function () {
  // Pages that should NOT show the toolbar
  const HIDE_ON = new Set(["login", "signup", "pin", "profile_pin"]);

  function getPageKeyFromBody() {
    // If you ever add body classes like: <body class="saved-items-page">
    // we can map those. For now we keep it simple.
    const path = (window.location.pathname || "").toLowerCase();
    const file = path.split("/").pop() || "";
    if (file.includes("login")) return "login";
    if (file.includes("signup")) return "signup";
    if (file.includes("pin")) return "pin";
    if (file.includes("saved")) return "saved";
    if (file.includes("dashboard")) return "dashboard";
    if (file.includes("flyers")) return "flyers";
    if (file.includes("account")) return "account";
    return "app";
  }

  async function renderToolbar(pageKey) {
    // Respect "no toolbar on login/signup/pin screens"
    const key = (pageKey || getPageKeyFromBody() || "").toLowerCase();
    if (HIDE_ON.has(key)) {
      console.log("[toolbar] hidden on page:", key);
      return;
    }

    // Standard mount (must match pages)
    const container = document.getElementById("toolbar-root");
    if (!container) {
      console.log("[toolbar] no #toolbar-root on this page");
      return;
    }

    try {
      const response = await fetch("toolbar.html", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status} fetching toolbar.html`);
      const html = await response.text();
      container.innerHTML = html;

      // Highlight active nav
const active = (pageKey || "").toLowerCase();
document.querySelectorAll(".d4m-toolbar__link[data-page]").forEach((a) => {
  const p = (a.getAttribute("data-page") || "").toLowerCase();
  a.classList.toggle("is-active", p === active);
});

      // Active profile pill (optional)
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

      // Logout button: clear profile PIN only, keep Supabase session
      const logoutBtn = document.getElementById("toolbar-logout-btn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
          localStorage.removeItem("d4m_active_profile");
          window.location.href = "pin.html";
        });
      }
    } catch (err) {
      console.error("[toolbar] failed to load toolbar.html", err);
    }
  }

  // Expose API expected by pages
  window.renderToolbar = renderToolbar;

  // Back-compat: auto-mount when DOM is ready
  document.addEventListener("DOMContentLoaded", () => renderToolbar());
})();
