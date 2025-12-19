// site/auth.js

const AUTH_STORAGE_KEYS = {
  activeProfileName: "d4mActiveProfileName",
  activeProfileId: "d4mActiveProfileId"
};

async function requireAuth() {
  if (!window.supabaseClient) {
    redirectToLogin();
    return;
  }

  const {
    data: { user },
    error
  } = await supabaseClient.auth.getUser();

  if (error || !user) {
    redirectToLogin();
    return null;
  }
  return user;
}

function redirectToLogin() {
  window.location.href = "/site/login.html";
}

function getActiveProfileName() {
  return localStorage.getItem(AUTH_STORAGE_KEYS.activeProfileName) || "Guest";
}

function setActiveProfile(name, id) {
  localStorage.setItem(AUTH_STORAGE_KEYS.activeProfileName, name || "Guest");
  if (id) localStorage.setItem(AUTH_STORAGE_KEYS.activeProfileId, id);
}

function clearActiveProfile() {
  localStorage.removeItem(AUTH_STORAGE_KEYS.activeProfileName);
  localStorage.removeItem(AUTH_STORAGE_KEYS.activeProfileId);
}

async function logoutEverywhere() {
  clearActiveProfile();
  if (supabaseClient) {
    await supabaseClient.auth.signOut();
  }
  redirectToLogin();
}

window.requireAuth = requireAuth;
window.getActiveProfileName = getActiveProfileName;
window.setActiveProfile = setActiveProfile;
window.logoutEverywhere = logoutEverywhere;
