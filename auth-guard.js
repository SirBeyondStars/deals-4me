(() => {
  const publicPages = new Set(['login.html','signup.html','terms.html','privacy.html','404.html']);
  const page = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  if (publicPages.has(page)) return;

  const isAuth = localStorage.getItem('isAuthenticated') === 'true';
  if (!isAuth) {
    const next = encodeURIComponent(location.pathname + location.search + location.hash);
    location.href = `login.html?next=${next}`;
  }
})();
