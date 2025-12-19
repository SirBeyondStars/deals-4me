// footer.js — loads shared footer into #siteFooter using root-relative paths
document.addEventListener("DOMContentLoaded", async () => {
  const target = document.getElementById("siteFooter");
  if (!target) return;

  try {
    const res = await fetch(`/components/footer.html`);
    if (!res.ok) throw new Error(`Footer fetch failed: ${res.status}`);
    const html = await res.text();
    target.innerHTML = html;

    // fix links to be root-relative
    target.querySelectorAll("[data-root-href]").forEach(a => {
      const to = a.getAttribute("data-root-href");
      a.setAttribute("href", `/${to}`);
    });
  } catch (err) {
    console.error("Error loading footer:", err);
  }
});
