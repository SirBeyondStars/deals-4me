// site/toolbar.js

function renderToolbar(activePage) {
  const root = document.getElementById("toolbar-root");
  if (!root) return;

  const userName = window.getActiveProfileName
    ? window.getActiveProfileName()
    : "Guest";

  const navItems = [
    { id: "dashboard", label: "Dashboard", href: "/site/dashboard.html" },
    { id: "flyers", label: "Flyers", href: "/site/flyers.html" },
    { id: "saved", label: "Saved Items", href: "/site/saved.html" },
    { id: "compare", label: "Compare", href: "/site/compare.html" },
    { id: "account", label: "Account", href: "/site/account.html" }
  ];

  const navHtml = navItems
    .map((item) => {
      const activeClass = item.id === activePage ? "active" : "";
      return `<a class="toolbar-link ${activeClass}" href="${item.href}">${item.label}</a>`;
    })
    .join("");

  root.innerHTML = `
    <header class="toolbar">
      <div class="toolbar-left">
        <div class="toolbar-logo">Deals-4Me</div>
        <div class="toolbar-beta">beta</div>
      </div>
      <nav class="toolbar-nav">
        ${navHtml}
      </nav>
      <div class="toolbar-right">
        <span>Hello, ${userName}</span>
        <button class="secondary" type="button" id="toolbar-logout-btn">
          Sign out
        </button>
      </div>
    </header>
  `;

  const logoutBtn = document.getElementById("toolbar-logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      if (window.logoutEverywhere) {
        window.logoutEverywhere();
      } else {
        window.location.href = "/site/login.html";
      }
    });
  }
}

window.renderToolbar = renderToolbar;
