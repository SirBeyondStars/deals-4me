// site/account.js

(async function initAccount() {
  if (window.requireAuth) {
    await window.requireAuth();
  }
  if (window.renderToolbar) {
    window.renderToolbar("account");
  }

  const profileEl = document.getElementById("account-profile");
  const profileName = window.getActiveProfileName
    ? window.getActiveProfileName()
    : "Guest";

  // TODO: Load more details (household, adults vs kids, tier) from Supabase
  profileEl.textContent = `You’re currently signed in as ${profileName}. In the future, this page will let you manage household members, reset PINs, and change your subscription tier.`;
})();
