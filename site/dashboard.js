// dashboard.js
// Deals-4Me – Dashboard logic
// - Store summary cards (flip on hover desktop, tap on mobile)
// - "My Saved Deals This Week" list
// - Optional: shopping list status (Add / Bought) if TABLE_SHOPPING_LIST exists

console.log("[dashboard] dashboard.js loaded");

// ------------ Configuration ------------

const ITEMS_TABLE = "flyer_items";
const TABLE_SAVED_STORES = "user_saved_stores";
const TABLE_SAVED_ITEMS = "user_saved_items";

// OPTIONAL shopping list table (if you haven't created it yet, this will fail gracefully)
const TABLE_SHOPPING_LIST = "user_shopping_list"; // <-- change if your table name is different

// Stores you support today – keep in sync with flyers.html etc.
const AVAILABLE_STORES = [
  { id: "aldi",                     name: "Aldi" },
  { id: "big_y",                    name: "Big Y" },
  { id: "hannaford",                name: "Hannaford" },
  { id: "market_basket",            name: "Market Basket" },
  { id: "price_chopper_market_32",  name: "Price Chopper / Market 32" },
  { id: "pricerite",                name: "Price Rite" },
  { id: "roche_bros",               name: "Roche Bros." },
  { id: "shaws",                    name: "Shaw's" },
  { id: "stop_and_shop_ct",         name: "Stop & Shop (CT)" },
  { id: "stop_and_shop_mari",       name: "Stop & Shop (MA/RI)" },
  { id: "trucchis",                 name: "Trucchi's" },
  { id: "wegmans",                  name: "Wegmans" },
  { id: "whole_foods",              name: "Whole Foods" },
];

// Build quick lookup maps
const STORE_NAME_BY_SLUG = {};
const STORE_SLUG_BY_NAME = {};
for (const s of AVAILABLE_STORES) {
  STORE_NAME_BY_SLUG[s.id] = s.name;
  STORE_SLUG_BY_NAME[s.name] = s.id;
}

// DOM elements we expect to exist
const elements = {
  weekLabel: document.getElementById("current-week-label"),
  storeContainer: document.getElementById("store-cards-container"),
  statusBar: document.getElementById("dashboard-status"),
  noStoresMessage: document.getElementById("dashboard-no-stores-message"),
  savedDealsList: document.getElementById("saved-deals-list"),
  savedDealsError: document.getElementById("saved-deals-error"),
};

// ------------ Helpers ------------

function getSupabase() {
  const candidate = window.supabaseClient || window.supabase;
  if (!candidate || !candidate.from) {
    console.error("[dashboard] Supabase client not found. Make sure site/scripts/supabaseClient.js is loaded first.");
    return null;
  }
  return candidate;
}

function setStatus(message, isError = false) {
  if (!elements.statusBar) return;
  elements.statusBar.textContent = message;
  elements.statusBar.classList.toggle("error", !!isError);
}

function prettyStoreName(slug) {
  if (!slug) return "Unknown store";
  if (STORE_NAME_BY_SLUG[slug]) return STORE_NAME_BY_SLUG[slug];
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function escapeHTML(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Format something like "Dec 8 – Dec 14"
function formatDateRange(isoStart, isoEnd) {
  if (!isoStart && !isoEnd) return null;

  const opts = { month: "short", day: "numeric" };
  let startStr = null;
  let endStr = null;

  if (isoStart) {
    const d = new Date(isoStart);
    if (!Number.isNaN(d.getTime())) startStr = d.toLocaleDateString(undefined, opts);
  }

  if (isoEnd) {
    const d = new Date(isoEnd);
    if (!Number.isNaN(d.getTime())) endStr = d.toLocaleDateString(undefined, opts);
  }

  if (startStr && endStr) return `${startStr} – ${endStr}`;
  return startStr || endStr;
}

// Very simple "is this item on sale?" logic
function isItemOnSale(item) {
  if (typeof item.is_on_sale === "boolean") return item.is_on_sale;

  const sale = item.sale_price;
  const regular = item.regular_price;

  if (sale != null && regular != null) {
    const s = Number(sale);
    const r = Number(regular);
    if (!Number.isNaN(s) && !Number.isNaN(r)) return s < r;
  }
  return false;
}

function normalizeItemName(name) {
  return (name || "").trim().toLowerCase();
}

function listKey(storeId, itemName) {
  return `${storeId}::${normalizeItemName(itemName)}`;
}

// ------------ Data loading ------------

async function getActiveWeekCode(supabase) {
  const params = new URLSearchParams(window.location.search);
  const weekParam = params.get("week");

  if (weekParam) {
    if (/^week[\w\d_]+$/i.test(weekParam)) return weekParam.toLowerCase();
    if (/^\d+$/.test(weekParam)) return `week${weekParam}`;
  }

  try {
    const { data, error } = await supabase
      .from("flyer_weeks")
      .select("week_code, start_date")
      .not("start_date", "is", null)
      .order("start_date", { ascending: false })
      .limit(1);

    if (!error && data && data.length > 0 && data[0].week_code) return data[0].week_code;
    if (error) console.warn("[dashboard] getActiveWeekCode flyer_weeks error:", error);
  } catch (err) {
    console.warn("[dashboard] getActiveWeekCode unexpected error:", err);
  }

  return "week51";
}

async function getCurrentUserOrRedirect(supabase) {
  const { data, error } = await supabase.auth.getUser();
  if (error) throw error;
  if (!data.user) {
    window.location.href = "login.html";
    throw new Error("Not logged in");
  }
  return data.user;
}

async function loadSavedStores(supabase, userId) {
  const validIds = new Set(AVAILABLE_STORES.map((s) => s.id));

  const { data, error } = await supabase
    .from(TABLE_SAVED_STORES)
    .select("store_id")
    .eq("user_id", userId);

  if (error) throw error;

  const result = new Set();
  (data || []).forEach((row) => {
    if (row.store_id && validIds.has(row.store_id)) result.add(row.store_id);
  });

  return result;
}

async function loadWeekMetaForStores(supabase, weekCode, savedStoreIds) {
  if (!savedStoreIds || savedStoreIds.size === 0) return new Map();

  const storeSlugs = Array.from(savedStoreIds);

  const { data, error } = await supabase
    .from("flyer_weeks")
    .select("store_slug, week_code, start_date, end_date")
    .eq("week_code", weekCode)
    .in("store_slug", storeSlugs);

  if (error) return new Map();

  const map = new Map();
  for (const row of data || []) {
    map.set(row.store_slug, { weekStart: row.start_date, weekEnd: row.end_date });
  }
  return map;
}

async function loadSavedItems(supabase, userId) {
  const { data, error } = await supabase
    .from(TABLE_SAVED_ITEMS)
    .select("id, item_name")
    .eq("user_id", userId)
    .order("id", { ascending: true });

  if (error) throw error;
  return data || [];
}

async function loadFlyerItemsForStores(supabase, weekCode, savedStoreIds) {
  if (!savedStoreIds || savedStoreIds.size === 0) return [];

  const brandNames = Array.from(savedStoreIds)
    .map((slug) => STORE_NAME_BY_SLUG[slug])
    .filter(Boolean);

  if (brandNames.length === 0) return [];

  const { data, error } = await supabase
    .from(ITEMS_TABLE)
    .select("*")
    .eq("week_code", weekCode)
    .in("brand", brandNames);

  if (error) throw error;
  return data || [];
}

// Optional: load shopping list rows for week, but never hard-fail the dashboard if missing
async function loadShoppingListForWeek(supabase, userId, weekCode) {
  try {
    const { data, error } = await supabase
      .from(TABLE_SHOPPING_LIST)
      .select("store_id, week_code, item_name, status")
      .eq("user_id", userId)
      .eq("week_code", weekCode);

    if (error) {
      console.warn("[dashboard] Shopping list table not available (safe to ignore for now):", error);
      return [];
    }
    return data || [];
  } catch (err) {
    console.warn("[dashboard] Shopping list load failed (safe to ignore for now):", err);
    return [];
  }
}

async function upsertShoppingListStatus(supabase, { userId, weekCode, storeId, itemName, status }) {
  // status: "active" | "bought"
  try {
    const payload = {
      user_id: userId,
      week_code: weekCode,
      store_id: storeId,
      item_name: itemName,
      status,
      updated_at: new Date().toISOString(),
    };

    const { error } = await supabase
      .from(TABLE_SHOPPING_LIST)
      .upsert(payload, { onConflict: "user_id,week_code,store_id,item_name" });

    if (error) console.warn("[dashboard] shopping list upsert error:", error);
  } catch (err) {
    console.warn("[dashboard] shopping list upsert failed:", err);
  }
}

// ------------ Rendering ------------

function dealLine(item, slug, weekCode, listActiveSet, listBoughtSet) {
  const name = item.item_name || "(Unnamed item)";
  const sale = item.sale_price != null ? `$${item.sale_price}` : "";
  const reg = item.regular_price != null ? `$${item.regular_price}` : "";
  const key = listKey(slug, name);

  const isBought = !!(listBoughtSet && listBoughtSet.has(key));
  const isActive = !!((listActiveSet && listActiveSet.has(key)) || isBought);

  const addLabel = isActive ? "Added" : "Add";
  const boughtLabel = isBought ? "Bought ✓" : "Bought";

  const addClass = isActive ? "mini-btn mini-btn-on" : "mini-btn";
  const boughtClass = isBought ? "mini-btn mini-btn-on" : "mini-btn";

  return `
    <li class="mini-deal-row">
      <div class="mini-deal-text">
        <span class="mini-deal-name">${escapeHTML(name)}</span>
        <span class="mini-deal-prices">
          ${sale ? `${escapeHTML(sale)}` : ""}${sale && reg ? " • " : ""}${reg ? `Reg ${escapeHTML(reg)}` : ""}
        </span>
      </div>
      <div class="mini-deal-actions">
        <button class="${addClass}" data-action="add" data-slug="${escapeHTML(slug)}" data-week="${escapeHTML(weekCode)}" data-item="${escapeHTML(name)}" ${isActive ? "disabled" : ""}>${addLabel}</button>
        <button class="${boughtClass}" data-action="bought" data-slug="${escapeHTML(slug)}" data-week="${escapeHTML(weekCode)}" data-item="${escapeHTML(name)}" ${isBought ? "disabled" : ""}>${boughtLabel}</button>
      </div>
    </li>
  `;
}

function renderStoreCards(savedStoreIds, allFlyerItems, dealsByStore, weekCode, weekMetaByStore, listActiveSet, listBoughtSet) {
  const container = elements.storeContainer;
  if (!container) return;

  container.innerHTML = "";

  if (!savedStoreIds || savedStoreIds.size === 0) {
    container.innerHTML =
      '<p class="muted">You haven’t chosen any stores yet. Go to the Flyers page to pick up to 5 stores you shop at regularly.</p>';
    return;
  }

  // Group flyer items by brand
  const itemsByBrand = new Map();
  for (const item of allFlyerItems) {
    const brand = item.brand || "Unknown";
    if (!itemsByBrand.has(brand)) itemsByBrand.set(brand, []);
    itemsByBrand.get(brand).push(item);
  }

  for (const slug of savedStoreIds) {
    const storeName = prettyStoreName(slug);
    const brandName = STORE_NAME_BY_SLUG[slug];

    const storeItems = brandName ? itemsByBrand.get(brandName) || [] : [];
    const onSaleItems = storeItems.filter(isItemOnSale);

    const totalOnSale = onSaleItems.length;
    const matchedCount = dealsByStore.get(slug) || 0;

    // Back side (Top deals) – show up to 6 sale items for now
    const topStoreDeals = onSaleItems.slice(0, 6);

    const meta = weekMetaByStore ? weekMetaByStore.get(slug) : null;
    const dateRangeText =
      meta && (meta.weekStart || meta.weekEnd) ? formatDateRange(meta.weekStart, meta.weekEnd) : null;

    const dateDisplay = dateRangeText || weekCode;

    const card = document.createElement("div");
    card.className = "store-card dash-store-card";
    card.setAttribute("data-store-slug", slug);

    card.innerHTML = `
      <div class="store-card-flip">
        <div class="store-card-inner">

          <!-- FRONT -->
          <div class="store-card-face store-card-front">
            <div class="store-card-header">
              <h3 class="store-name">${escapeHTML(storeName)}</h3>
              <span class="store-week">${escapeHTML(dateDisplay)}</span>
            </div>

            <div class="store-card-body">
              <p><strong>Items on sale this week:</strong> ${totalOnSale}</p>
              <p><strong>Your items on sale here:</strong> ${matchedCount}</p>
            </div>
          </div>

          <!-- BACK -->
          <div class="store-card-face store-card-back">
            <div class="store-card-body">
              <div class="back-row">
                <div class="back-row-title">Top deals at this store</div>
                ${
                  topStoreDeals.length
                    ? `<ul class="mini-deal-list">${topStoreDeals.map((it) => dealLine(it, slug, weekCode, listActiveSet, listBoughtSet)).join("")}</ul>`
                    : `<div class="muted">No sale items detected for this store this week.</div>`
                }
              </div>

              <div class="back-row">
                <div class="back-row-title">Your saved deals on sale here</div>
                <div class="muted">None of your saved items matched here (yet).</div>
              </div>
            </div>
          </div>

        </div>
      </div>
    `;

    container.appendChild(card);
  }
}

function renderSavedDealsList(savedDeals, savedItems) {
  const listEl = elements.savedDealsList;
  const errorEl = elements.savedDealsError;
  if (!listEl || !errorEl) return;

  listEl.innerHTML = "";
  errorEl.style.display = "none";
  errorEl.textContent = "";

  if (!savedItems || savedItems.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "You haven’t added any items to track yet. Use the Flyers page to add items to your saved list.";
    listEl.appendChild(li);
    return;
  }

  if (!savedDeals || savedDeals.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent =
      "None of your saved items are on sale this week at your saved stores (yet). Check back when new flyers are ingested.";
    listEl.appendChild(li);
    return;
  }

  savedDeals.sort((a, b) => {
    if (a.storeName < b.storeName) return -1;
    if (a.storeName > b.storeName) return 1;
    const aName = (a.item.item_name || "").toLowerCase();
    const bName = (b.item.item_name || "").toLowerCase();
    if (aName < bName) return -1;
    if (aName > bName) return 1;
    return 0;
  });

  for (const deal of savedDeals) {
    const { storeName, item, matchedNames } = deal;
    const li = document.createElement("li");
    li.className = "saved-deal-row";

    const priceBits = [];
    if (item.sale_price != null) priceBits.push(`Sale: $${item.sale_price}`);
    if (item.regular_price != null) priceBits.push(`Reg: $${item.regular_price}`);

    const matchesSummary = matchedNames && matchedNames.length > 0 ? `Matches: ${matchedNames.join(", ")}` : "";

    li.innerHTML = `
      <div class="saved-deal-main">
        <div class="saved-deal-title">
          <strong>${escapeHTML(storeName)}</strong> – ${escapeHTML(item.item_name || "(Unnamed item)")}
        </div>
        <div class="saved-deal-meta">
          ${
            item.size
              ? `<span class="deal-size">${escapeHTML(item.size)}${item.unit ? " " + escapeHTML(item.unit) : ""}</span>`
              : ""
          }
          ${matchesSummary ? `<span class="deal-matches">${escapeHTML(matchesSummary)}</span>` : ""}
        </div>
      </div>
      <div class="saved-deal-prices">
        ${escapeHTML(priceBits.join(" • "))}
        ${isItemOnSale(item) ? '<span class="badge badge-sale">On Sale</span>' : ""}
      </div>
    `;

    listEl.appendChild(li);
  }
}

// Flip on tap (mobile) by toggling .is-flipped on the inner
function wireTapToFlip() {
  const container = elements.storeContainer;
  if (!container) return;

  container.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (btn) return; // let buttons handle separately

    const face = e.target.closest(".store-card-face");
    if (!face) return;

    const inner = e.target.closest(".store-card-inner");
    if (!inner) return;

    inner.classList.toggle("is-flipped");
  });
}

// Handle Add/Bought clicks
function wireMiniDealButtons(supabase, userId, weekCode, listActiveSet, listBoughtSet) {
  const container = elements.storeContainer;
  if (!container) return;

  container.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();

    const action = btn.getAttribute("data-action");
    const slug = btn.getAttribute("data-slug");
    const itemName = btn.getAttribute("data-item");
    if (!action || !slug || !itemName) return;

    const key = listKey(slug, itemName);

    if (action === "add") {
      // If already active/bought, do nothing (button should be disabled anyway)
      if ((listActiveSet && listActiveSet.has(key)) || (listBoughtSet && listBoughtSet.has(key))) return;

      listActiveSet && listActiveSet.add(key);

      btn.textContent = "Added";
      btn.classList.add("mini-btn-on");
      btn.disabled = true;

      await upsertShoppingListStatus(supabase, {
        userId,
        weekCode,
        storeId: slug,
        itemName,
        status: "active",
      });
      return;
    }

    if (action === "bought") {
      // If already bought, do nothing (button should be disabled anyway)
      if (listBoughtSet && listBoughtSet.has(key)) return;

      // Being bought implies active too
      listBoughtSet && listBoughtSet.add(key);
      listActiveSet && listActiveSet.add(key);

      btn.textContent = "Bought ✓";
      btn.classList.add("mini-btn-on");
      btn.disabled = true;

      // Disable the paired Add button too
      const row = btn.closest(".mini-deal-row");
      if (row) {
        const addBtn = row.querySelector('button[data-action="add"]');
        if (addBtn) {
          addBtn.textContent = "Added";
          addBtn.classList.add("mini-btn-on");
          addBtn.disabled = true;
        }
      }

      await upsertShoppingListStatus(supabase, {
        userId,
        weekCode,
        storeId: slug,
        itemName,
        status: "bought",
      });
    }
  });
}

// ------------ Main init ------------

async function initDashboard() {
  console.log("[dashboard] initDashboard()");

  const supabase = getSupabase();
  if (!supabase) {
    setStatus("Supabase is not available. Are you offline?", true);
    return;
  }

  try {
    const user = await getCurrentUserOrRedirect(supabase);

    const weekCode = await getActiveWeekCode(supabase);
    if (elements.weekLabel) elements.weekLabel.textContent = weekCode;

    setStatus(`Loading your stores and deals for ${weekCode}...`);

    const savedStoreIds = await loadSavedStores(supabase, user.id);
    if (elements.noStoresMessage) {
      elements.noStoresMessage.style.display = savedStoreIds.size === 0 ? "block" : "none";
    }

    const savedItems = await loadSavedItems(supabase, user.id);
    const allFlyerItems = await loadFlyerItemsForStores(supabase, weekCode, savedStoreIds);
    const weekMetaByStore = await loadWeekMetaForStores(supabase, weekCode, savedStoreIds);

    // shopping list status sets (safe if table doesn't exist)
    const shoppingListRows = await loadShoppingListForWeek(supabase, user.id, weekCode);
    const listActiveSet = new Set();
    const listBoughtSet = new Set();
    for (const row of shoppingListRows) {
      const key = listKey(row.store_id, row.item_name);
      if ((row.status || "").toLowerCase() === "bought") listBoughtSet.add(key);
      else listActiveSet.add(key);
    }

    // Match saved items -> flyer items
    const savedDeals = [];
    const dealsByStore = new Map(); // slug -> count

    const loweredSavedItems = (savedItems || []).map((row) => ({
      id: row.id,
      name: row.item_name,
      nameLower: normalizeItemName(row.item_name),
    }));

    for (const flyerItem of allFlyerItems || []) {
      const itemNameLower = normalizeItemName(flyerItem.item_name);
      if (!itemNameLower) continue;

      const matchedNames = [];
      for (const si of loweredSavedItems) {
        if (!si.nameLower) continue;
        if (itemNameLower.includes(si.nameLower)) matchedNames.push(si.name);
      }

      if (matchedNames.length > 0) {
        const brandName = flyerItem.brand || "Unknown";
        const slug = STORE_SLUG_BY_NAME[brandName] || null;

        if (slug) dealsByStore.set(slug, (dealsByStore.get(slug) || 0) + 1);

        savedDeals.push({
          storeSlug: slug,
          storeName: brandName,
          item: flyerItem,
          matchedNames,
        });
      }
    }

    renderStoreCards(savedStoreIds, allFlyerItems, dealsByStore, weekCode, weekMetaByStore, listActiveSet, listBoughtSet);
    renderSavedDealsList(savedDeals, savedItems);

    // Wire interactions AFTER render
    wireTapToFlip();
    wireMiniDealButtons(supabase, user.id, weekCode, listActiveSet, listBoughtSet);

    // Status line
    const totalMatches = savedDeals.length;
    const storeCount = new Set(savedDeals.map((d) => d.storeSlug).filter(Boolean)).size;

    if (totalMatches > 0) {
      setStatus(`Found ${totalMatches} matching deal(s) across ${storeCount} store(s) for ${weekCode}.`);
    } else if ((savedItems || []).length === 0) {
      setStatus("No saved items yet. Add items on the Flyers page to start seeing matched deals here.");
    } else if (savedStoreIds.size === 0) {
      setStatus("You haven't chosen any stores yet. Go to the Flyers page to pick your regular stores.");
    } else if ((allFlyerItems || []).length === 0) {
      setStatus(`No flyer data found for your stores in ${weekCode} yet. Once ingestion runs, your deals will appear here.`);
    } else {
      setStatus(`We've checked your saved items and nothing is on sale this week (${weekCode}).`);
    }
  } catch (err) {
    console.error("[dashboard] initDashboard error:", err);
    setStatus("Error loading dashboard data. Check console for details, or try refreshing.", true);

    if (elements.savedDealsError) {
      elements.savedDealsError.style.display = "block";
      elements.savedDealsError.textContent = "There was a problem loading your saved deals.";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("[dashboard] DOMContentLoaded");
  initDashboard();
});
