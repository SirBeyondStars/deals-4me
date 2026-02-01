// site/account.js

async function initAccount() {
  // 1) Auth gate
  if (window.requireAuth) {
    await window.requireAuth();
  }

  // 2) Toolbar (call ONCE)
  if (window.renderToolbar) {
    window.renderToolbar("account");
  }

  // 3) Page content
  const profileEl = document.getElementById("account-profile");
  if (!profileEl) {
    console.warn('[account] Missing element: #account-profile');
    return;
  }

  const profileName =
    typeof window.getActiveProfileName === "function"
      ? window.getActiveProfileName()
      : "Guest";

  // TODO: Load more details (household, adults vs kids, tier) from Supabase
  profileEl.textContent =
    `You’re currently signed in as ${profileName}. ` +
    `In the future, this page will let you manage household members, reset PINs, ` +
    `and change your subscription tier.`;
}

document.addEventListener("DOMContentLoaded", () => {
  initAccount().catch((err) => console.error("[account] init error", err));
});
