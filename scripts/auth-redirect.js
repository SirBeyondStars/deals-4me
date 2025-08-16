// /scripts/auth-redirect.js
(() => {
  const publicPages = new Set([
    'login.html',
    'signup.html',
    'terms.html',
    'privacy.html',
    '404.html'
  ]);

  const currentPage = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  if (publicPages.has(currentPage)) return;

  const isAuth = localStorage.getItem('isAuthenticated') === 'true';
  if (!isAuth) {
    const next = encodeURIComponent(location.pathname + location.search + location.hash);
    location.href = `login.html?next=${next}`;
  }
})();
