// includes.js — handles all shared includes on every page

function loadInclude(targetId, file, afterLoad) {
  const el = document.getElementById(targetId);
  if (!el) return;
  fetch(file, { cache: 'no-cache' })
    .then(r => r.text())
    .then(html => {
      el.innerHTML = html;
      if (typeof afterLoad === 'function') afterLoad();
    })
    .catch(err => console.error(`Error loading ${file}:`, err));
}

document.addEventListener("DOMContentLoaded", () => {
  // Toolbar + Footer (present on most pages)
  loadInclude("site-toolbar", "toolbar.html");
  loadInclude("site-footer", "footer.html");

  // Pricing partial (only present on pricing.html)
  loadInclude("pricing-block", "userTiers.html", () => {
    // Wire Stripe links here (once you have them)
    const goldLink = "https://buy.stripe.com/your-gold-link";         // TODO
    const platinumLink = "https://buy.stripe.com/your-platinum-link"; // TODO
    document.querySelectorAll('[data-plan="gold"]').forEach(a => a.href = goldLink);
    document.querySelectorAll('[data-plan="platinum"]').forEach(a => a.href = platinumLink);
  });
});
