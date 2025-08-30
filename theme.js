// Robust loader for header/footer + year + active nav highlight
document.addEventListener('DOMContentLoaded', async () => {
  async function fetchText(paths){
    for(const p of paths){
      try{
        const res = await fetch(p, { cache: 'no-cache' });
        if(res.ok) return await res.text();
      }catch(_){}
    }
    return null;
  }

  const headerHTML = await fetchText(['/header.html','header.html','../header.html','../../header.html']);
  const footerHTML = await fetchText(['/footer.html','footer.html','../footer.html','../../footer.html']);

  const headerMount = document.getElementById('header');
  const footerMount = document.getElementById('footer');
  if(headerMount && headerHTML) headerMount.innerHTML = headerHTML;
  if(footerMount && footerHTML) footerMount.innerHTML = footerHTML;

  // Set year (works after injection too)
  const y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  // Highlight active nav
  const path = location.pathname.replace(/\/$/, '');
  document.querySelectorAll('.main-nav a').forEach(a=>{
    try{
      const url = new URL(a.getAttribute('href'), location.origin);
      const linkPath = url.pathname.replace(/\/$/, '');
      if (path === linkPath || (path.startsWith(linkPath) && linkPath !== '/')) {
        a.classList.add('active');
      }
    }catch(_){}
  });
});
