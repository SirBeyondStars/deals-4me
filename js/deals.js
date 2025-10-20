// js/deals.js
console.log("✅ deals.js loaded");

const storeSelect = document.getElementById("storeSelect");
const weekSelect  = document.getElementById("weekSelect");
const searchInput = document.getElementById("searchInput");
const statusEl    = document.getElementById("status");
const tbody       = document.querySelector("#dealsTable tbody");

// Pretty labels for the dropdown
const STORE_LABEL = {
  hannaford:        "Hannaford",
  shaws:            "Shaw’s",
  rochebros:        "Roche Bros",
  pricechopper:     "Price Chopper / Market 32",
  marketbasket:     "Market Basket",
  stopandshop_mari: "Stop & Shop – MA/RI",
  stopandshop_ct:   "Stop & Shop – CT",
  bigy:             "Big Y",
};

// Files live in /exports/, but deals.html is under /site/ → use ../exports/...
async function listExports() {
  return [
    { store: "hannaford",        date: "2025-10-16", path: "../exports/hannaford_2025-10-16_combined.csv" },
    { store: "shaws",            date: "2025-10-10", path: "../exports/shaws_2025-10-10_combined.csv" },
    { store: "rochebros",        date: "2025-10-10", path: "../exports/rochebros_2025-10-10_combined.csv" },
    { store: "pricechopper",     date: "2025-10-10", path: "../exports/pricechopper_2025-10-10_combined.csv" },
    { store: "marketbasket",     date: "2025-10-10", path: "../exports/marketbasket_2025-10-10_combined.csv" },
    { store: "stopandshop_mari", date: "2025-10-10", path: "../exports/stopandshop_mari_2025-10-10_combined.csv" },
    { store: "stopandshop_ct",   date: "2025-10-10", path: "../exports/stopandshop_ct_2025-10-10_combined.csv" },
    { store: "bigy",             date: "2025-10-10", path: "../exports/bigy_2025-10-10_combined.csv" },
  ];
}

// ---- helpers ----
function parseCSV(text) {
  return text.trim().split(/\r?\n/).map(line => line.split(","));
}

function unique(arr) { return [...new Set(arr)]; }

function fillDropdowns(data) {
  const stores = unique(data.map(d => d.store));
  storeSelect.innerHTML = stores
    .map(s => `<option value="${s}">${STORE_LABEL[s] || s}</option>`)
    .join("");

  updateWeeks(data, stores[0]);
}

function updateWeeks(data, storeKey) {
  const weeks = data.filter(d => d.store === storeKey);
  // newest date first (string compare is fine for YYYY-MM-DD)
  weeks.sort((a,b) => b.date.localeCompare(a.date));
  weekSelect.innerHTML = weeks
    .map(d => `<option value="${d.path}">${d.date}</option>`)
    .join("");
}

function renderRows(rows, query = "") {
  const data = rows.slice(1); // drop header
  const q = query.trim().toLowerCase();
  tbody.innerHTML = "";

  const matches = q ? data.filter(r => r.some(c => c.toLowerCase().includes(q))) : data;

  for (const r of matches) {
    const tr = document.createElement("tr");
    for (const cell of r) {
      const td = document.createElement("td");
      td.textContent = cell;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  statusEl.textContent = `${matches.length} item(s)`;
}

async function loadCSV(path) {
  try {
    console.log("📥 loading:", path);
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const text = await res.text();
    const rows = parseCSV(text);
    renderRows(rows, searchInput.value);
  } catch (err) {
    console.error("❌ fetch error:", err);
    statusEl.textContent = `Error loading ${path}`;
    tbody.innerHTML = "";
  }
}

async function init() {
  try {
    const exportsData = await listExports();
    console.log("📦 exports list:", exportsData);
    fillDropdowns(exportsData);

    if (weekSelect.value) await loadCSV(weekSelect.value);

    storeSelect.addEventListener("change", async () => {
      updateWeeks(exportsData, storeSelect.value);
      if (weekSelect.value) await loadCSV(weekSelect.value);
    });

    weekSelect.addEventListener("change", async () => {
      if (weekSelect.value) await loadCSV(weekSelect.value);
    });

    searchInput.addEventListener("input", async () => {
      if (weekSelect.value) await loadCSV(weekSelect.value);
    });
  } catch (e) {
    console.error(e);
    statusEl.textContent = "Init error";
  }
}

// Module scripts are deferred, but this is extra-safe:
window.addEventListener("DOMContentLoaded", init);
