// toolbar.js — inject shared header using root-relative paths
async function injectHeader() {
  const target = document.getElementById("siteHeader");
  if (!target) return;

  try {
    const res = await fetch(`/components/header.html`);
    if (!res.ok) throw new Error(`Header fetch failed: ${res.status}`);
    const html = await res.text();
    target.innerHTML = html;

    // normalize links in the injected header
    target.querySelectorAll("[data-root-href]").forEach(a => {
      const to = a.getAttribute("data-root-href");
      a.setAttribute("href", `/${to}`);
    });
  } catch (err) {
    console.error("Error loading header:", err);
  }
}

// Run now if DOM is ready, otherwise wait for DOMContentLoaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", injectHeader);
} else {
  injectHeader();
}
