// includes.js — inject favicon (HEAD) + toolbar/footer (BODY) with logs

function injectFavicons(file) {
  if (document.head.querySelector('meta[name="injected-favicons"]')) return;
  fetch(file, { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error(`${file} ${r.status}`); return r.text(); })
    .then(html => {
      const wrap = document.createElement("div");
      wrap.innerHTML = html;
      Array.from(wrap.childNodes).forEach(n => { if (n.nodeType === 1) document.head.appendChild(n); });
      const marker = document.createElement("meta");
      marker.name = "injected-favicons";
      document.head.appendChild(marker);
      console.log("[includes] favicons injected");
    })
    .catch(err => console.warn("[includes] favicon FAILED:", err.message));
}

function injectIntoBody(id, file, position /* 'afterbegin' | 'beforeend' */) {
  let host = document.getElementById(id);
  if (!host) {
    host = document.createElement("div");
    host.id = id;
    document.body.insertAdjacentElement(position === "afterbegin" ? "afterbegin" : "beforeend", host);
  }
  fetch(file, { cache: "no-cache" })
    .then(r => { if (!r.ok) throw new Error(`${file} ${r.status}`); return r.text(); })
    .then(html => { host.innerHTML = html; })
    .catch(err => console.warn("[includes]", file, "FAILED:", err.message));
}

document.addEventListener("DOMContentLoaded", () => {
  injectFavicons("favicon.html");
  injectIntoBody("site-toolbar", "toolbar.html", "afterbegin");
  injectIntoBody("site-footer",  "footer.html",  "beforeend");
});
