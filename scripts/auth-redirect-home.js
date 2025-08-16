// /scripts/auth-redirect-home.js
(() => {
  const isAuth = localStorage.getItem('isAuthenticated') === 'true';
  if (!isAuth) return;

  const params = new URLSearchParams(location.search);
  const next = params.get('next') || 'index.html';
  location.replace(next); // prevents user hitting Back to login
})();
