// js/session.js
export function getCurrentUser() {
  const raw = localStorage.getItem("d4m_currentUser");
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch (err) {
    console.error("Bad d4m_currentUser in localStorage", err);
    return null;
  }
}

export function setCurrentUser(userObj) {
  localStorage.setItem("d4m_currentUser", JSON.stringify(userObj));
}

// Optional: where we store the "Store A/B/C" choice so other pages can use it
export function setTopStores(topStores) {
  localStorage.setItem("d4m_topStores", JSON.stringify(topStores));
}

export function getTopStores() {
  const raw = localStorage.getItem("d4m_topStores");
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}
