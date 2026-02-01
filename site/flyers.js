// flyers.js
// Deals-4Me – Flyers page logic
// PURPOSE:
// - Saved STORES (stores you shop at)
// IMPORTANT:
// - Flyers page does NOT show deal results.
// - Dashboard is responsible for showing “where your saved items are on sale”.
// - Saved items are managed elsewhere (Saved page / Dashboard), not here.

// ----------------- Constants & metadata -----------------

const MAX_SAVED_STORES = 5;

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

const TABLE_SAVED_STORES = "user_saved_stores";

// ----------------- Small helpers -----------------

function getSupabase() {
  const client = window.supabaseClient || window.supabase;
  if (!client || !client.from) {
    console.error("[flyers] Supabase client not found. Check supabaseClient.js");
    return null;
  }
  return client;
}

async function getCurrentUserOrRedirect() {
  const supabase = getSupabase();
  if (!supabase) throw new Error("Supabase not available");

  const { data, error } = await supabase.auth.getUser();
  if (error) throw error;

  if (!data.user) {
    window.location.href = "login.html";
    throw new Error("Not logged in");
  }

  return data.user;
}

function setText(el, text) {
  if (!el) return;
  el.textContent = text;
}

// ----------------- Saved STORES dual-list panel -----------------

function renderStoreDualList(availableEl, savedEl, selectedStoreIds) {
  availableEl.innerHTML = "";
  savedEl.innerHTML = "";

  const selected = selectedStoreIds || new Set();

  AVAILABLE_STORES.forEach((store) => {
    const optionHtml = `<option value="${store.id}">${store.name}</option>`;
    if (selected.has(store.id)) {
      savedEl.insertAdjacentHTML("beforeend", optionHtml);
    } else {
      availableEl.insertAdjacentHTML("beforeend", optionHtml);
    }
  });
}

async function loadSavedStores(user) {
  const supabase = getSupabase();
  if (!supabase) return new Set();

  try {
    const { data, error } = await supabase
      .from(TABLE_SAVED_STORES)
      .select("store_id")
      .eq("user_id", user.id);

    if (error) throw error;

    const validIds = new Set(AVAILABLE_STORES.map((s) => s.id));
    return new Set(
      (data || [])
        .map((row) => row.store_id)
        .filter((id) => validIds.has(id))
    );
  } catch (err) {
    console.error("[flyers] Error loading saved stores", err);
    return new Set();
  }
}

async function persistSelectedStores(user, selectedStoreIds) {
  const supabase = getSupabase();
  if (!supabase) return;

  const idsArray = Array.from(selectedStoreIds);

  // clear + insert (simple + predictable)
  const { error: delError } = await supabase
    .from(TABLE_SAVED_STORES)
    .delete()
    .eq("user_id", user.id);

  if (delError) throw delError;

  if (idsArray.length > 0) {
    const rows = idsArray.map((id) => ({ user_id: user.id, store_id: id }));
    const { error: insError } = await supabase.from(TABLE_SAVED_STORES).insert(rows);
    if (insError) throw insError;
  }
}

async function initStoresPanel(user) {
  const availableEl = document.getElementById("availableStores");
  const savedEl = document.getElementById("savedStores");
  const addBtn = document.getElementById("addStoreBtn");
  const removeBtn = document.getElementById("removeStoreBtn");
  const statusP = document.getElementById("saved-stores-message");
  const saveBtn = document.getElementById("saveStoresBtn");

  if (!availableEl || !savedEl || !addBtn || !removeBtn || !statusP) {
    console.warn("[flyers] Store chooser elements not found.");
    return;
  }

  let selectedStoreIds = await loadSavedStores(user);
  renderStoreDualList(availableEl, savedEl, selectedStoreIds);

  const refreshStatus = () => {
    const n = selectedStoreIds.size;
    if (n === 0) setText(statusP, "No stores selected yet.");
    else if (n === 1) setText(statusP, "1 store selected.");
    else setText(statusP, `${n} stores selected.`);
  };

  refreshStatus();

  addBtn.addEventListener("click", () => {
    const selectedOptions = Array.from(availableEl.selectedOptions);
    if (selectedOptions.length === 0) return;

    if (selectedStoreIds.size + selectedOptions.length > MAX_SAVED_STORES) {
      alert(`You can only save up to ${MAX_SAVED_STORES} stores.`);
      return;
    }

    selectedOptions.forEach((opt) => selectedStoreIds.add(opt.value));
    renderStoreDualList(availableEl, savedEl, selectedStoreIds);
    refreshStatus();
  });

  removeBtn.addEventListener("click", () => {
    const selectedOptions = Array.from(savedEl.selectedOptions);
    if (selectedOptions.length === 0) return;

    selectedOptions.forEach((opt) => selectedStoreIds.delete(opt.value));
    renderStoreDualList(availableEl, savedEl, selectedStoreIds);
    refreshStatus();
  });

  // Save button persists the selection (so we don’t write on every click)
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        await persistSelectedStores(user, selectedStoreIds);
        setText(statusP, "Saved. Dashboard will use these stores to find deals.");
      } catch (err) {
        console.error("[flyers] Error saving stores", err);
        setText(statusP, "Error saving your stores.");
      } finally {
        saveBtn.disabled = false;
      }
    });
  }
}

// ----------------- Page bootstrap -----------------

async function initFlyers() {
  // Toolbar (only once, after DOM is ready)
  if (window.renderToolbar) window.renderToolbar("flyers");

  // Auth gate + user
  const user = await getCurrentUserOrRedirect();

  // Stores only
  await initStoresPanel(user);
}

document.addEventListener("DOMContentLoaded", () => {
  initFlyers().catch((err) => {
    console.error("[flyers] init error", err);

    const msgEl = document.getElementById("saved-stores-message");
    if (msgEl) msgEl.textContent = "Error loading your saved stores.";
  });
});
