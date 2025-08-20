// includes.js (debug version)
function inject(id, file) {
  let host = document.getElementById(id);
  if (!host) {
    host = document.createElement("div");
    host.id = id;
    document.body.insertAdjacentElement(
      id === "site-toolbar" ? "afterbegin" : "beforeend",
      host
    );
    console.log(`[includes] created placeholder #${id}`);
  } else {
    console.log(`[includes] found placeholder #${id}`);
  }

  console.log(`[includes] fetching ${file}…`);
  fetch(file, { cache: "no-cache" })
    .then(r => {
      console.log(`[includes] ${file} status:`, r.status);
      if (!r.ok) throw new Error(`${file} ${r.status}`);
      return r.text();
    })
    .then(html => {
      host.innerHTML = html;
      console.log(`[includes] injected ${file} into #${id}`);
    })
    .catch(err => console.warn("[includes] ERROR:", err.message));
}

document.addEventListener("DOMContentLoaded", () => {
  inject("site-toolbar", "toolbar.html");
  inject("site-footer",  "footer.html");
});
