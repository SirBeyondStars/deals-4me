// flyers.js
// Deals-4Me – Flyers page logic
// - Saved ITEMS (things you track: peanut butter, eggs 12ct, etc.)
// - Saved STORES (New England stores you shop at)
// - Store deals preview for the current week

// ----------------- Constants & metadata -----------------

// Max number of stores a user can follow
const MAX_SAVED_STORES = 5;

// Store metadata – ids should match your folders / dashboard cards
const AVAILABLE_STORES = [
  { id: "aldi",                name: "Aldi" },
  { id: "big_y",               name: "Big Y" },
  { id: "hannaford",           name: "Hannaford" },
  { id: "market_basket",       name: "Market Basket" },
  { id: "price_chopper_market_32", name: "Price Chopper / Market 32" },
  { id: "pricerite",           name: "Price Rite" },
  { id: "roche_bros",          name: "Roche Bros." },
  { id: "shaws",               name: "Shaw's" },
  { id: "stop_and_shop_ct",    name: "Stop & Shop (CT)" },
  { id: "stop_and_shop_mari",  name: "Stop & Shop (MA/RI)" },
  { id: "trucchis",            name: "Trucchi's" },
  { id: "wegmans",             name: "Wegmans" },
  { id: "whole_foods",         name: "Whole Foods" },
];

// Supabase tables – adjust names if yours differ
const TABLE_SAVED_STORES = "user_saved_stores";
const TABLE_SAVED_ITEMS  = "user_saved_items";
const TABLE_FLYER_ITEMS  = "flyer_items";

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

  console.log("[flyers] Fetching current user…");
  const { data, error } = await supabase.auth.getUser();

  if (error) {
    console.error("[flyers] getUser error", error);
    throw error;
  }

  if (!data.user) {
    console.warn("[flyers] No user, redirecting to login…");
    window.location.href = "login.html";
    throw new Error("Not logged in");
  }

  return data.user;
}

function setText(el, text) {
  if (!el) return;
  el.textContent = text;
}

function prettyStoreName(slug) {
  const meta = AVAILABLE_STORES.find((s) => s.id === slug);
  if (meta) return meta.name;
  if (!slug) return "Unknown store";
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Determine the active week for this page.
// For now: look at ?week= in the URL, otherwise default to week51
function getActiveWeekCode() {
  const params = new URLSearchParams(window.location.search);
  const weekParam = params.get("week");

  if (weekParam) {
    if (/^week\d+$/i.test(weekParam)) {
      return weekParam.toLowerCase();
    }
    if (/^\d+$/.test(weekParam)) {
      return `week${weekParam}`;
    }
  }

  // TODO later: wire to a “current week” value from DB or config
  return "week51";
}

// Very simple “is item on sale?” helper using sale_price vs regular_price
function isItemOnSale(item) {
  if (typeof item.is_on_sale === "boolean") return item.is_on_sale;

  const sale = item.sale_price;
  const regular = item.regular_price;

  if (sale != null && regular != null) {
    const s = Number(sale);
    const r = Number(regular);
    if (!Number.isNaN(s) && !Number.isNaN(r)) {
      return s < r;
    }
  }
  return false;
}

// ----------------- Saved ITEMS panel -----------------

function renderSavedItemLi(item) {
  const li = document.createElement("li");
  li.dataset.itemId = item.id;

  const mainSpan = document.createElement("span");
  mainSpan.className = "saved-item-main";
  mainSpan.textContent = item.notes
    ? `${item.item_name} – ${item.notes}`
    : item.item_name;

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "link-button";
  removeBtn.textContent = "Remove";

  li.appendChild(mainSpan);
  li.appendChild(removeBtn);

  return { li, removeBtn };
}

async function loadSavedItems(user) {
  const supabase = getSupabase();
  if (!supabase) return;

  const listEl = document.getElementById("saved-items-ul");
  const statusSpan = document.getElementById("saved-item-message");

  if (!listEl) return;

  setText(statusSpan, "Loading your saved items…");
  listEl.innerHTML = '<li class="muted">Loading…</li>';

  try {
    const { data, error } = await supabase
      .from(TABLE_SAVED_ITEMS)
      .select("id, item_name, notes")
      .eq("user_id", user.id)
      .order("id", { ascending: true });

    if (error) throw error;

    listEl.innerHTML = "";

    if (!data || data.length === 0) {
      listEl.innerHTML = "<li>You haven’t added any items yet.</li>";
      setText(statusSpan, "No saved items yet.");
      return;
    }

    data.forEach((row) => {
      const { li, removeBtn } = renderSavedItemLi(row);
      listEl.appendChild(li);

      removeBtn.addEventListener("click", async () => {
        removeBtn.disabled = true;
        try {
          const { error: delError } = await supabase
            .from(TABLE_SAVED_ITEMS)
            .delete()
            .eq("id", row.id)
            .eq("user_id", user.id);

          if (delError) throw delError;
          li.remove();

          if (!listEl.querySelector("li")) {
            listEl.innerHTML = "<li>You haven’t added any items yet.</li>";
          }
        } catch (err) {
          console.error("[flyers] Error deleting saved item", err);
          removeBtn.disabled = false;
          alert("Sorry, there was a problem removing that item.");
        }
      });
    });

    setText(statusSpan, `${data.length} item(s) on your tracking list.`);
  } catch (err) {
    console.error("[flyers] Error loading saved items", err);
    listEl.innerHTML = "<li>Error loading your saved items.</li>";
    setText(statusSpan, "Error loading saved items.");
  }
}

function initSavedItemForm(user) {
  const supabase = getSupabase();
  if (!supabase) return;

  const form = document.getElementById("saved-item-form");
  if (!form) return;

  const nameInput = document.getElementById("saved-item-name");
  const notesInput = document.getElementById("saved-item-notes");
  const listEl = document.getElementById("saved-items-ul");
  const statusSpan = document.getElementById("saved-item-message");

  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    if (!nameInput.value.trim()) return;

    const itemName = nameInput.value.trim();
    const notes = notesInput.value.trim() || null;

    try {
      const { data, error } = await supabase
        .from(TABLE_SAVED_ITEMS)
        .insert({
          user_id: user.id,
          item_name: itemName,
          notes,
        })
        .select("id, item_name, notes")
        .single();

      if (error) throw error;

      // Clear placeholder if it was there
      if (listEl && listEl.querySelector(".muted")) {
        listEl.innerHTML = "";
      }

      const { li, removeBtn } = renderSavedItemLi(data);
      listEl.appendChild(li);

      removeBtn.addEventListener("click", async () => {
        removeBtn.disabled = true;
        try {
          const { error: delError } = await supabase
            .from(TABLE_SAVED_ITEMS)
            .delete()
            .eq("id", data.id)
            .eq("user_id", user.id);

          if (delError) throw delError;
          li.remove();

          if (!listEl.querySelector("li")) {
            listEl.innerHTML = "<li>You haven’t added any items yet.</li>";
          }
        } catch (err) {
          console.error("[flyers] Error deleting saved item", err);
          removeBtn.disabled = false;
          alert("Sorry, there was a problem removing that item.");
        }
      });

      nameInput.value = "";
      notesInput.value = "";
      setText(statusSpan, "Item added to your tracking list.");
    } catch (err) {
      console.error("[flyers] Error adding saved item", err);
      alert("Sorry, there was a problem saving that item.");
    }
  });
}

// ----------------- Saved STORES dual-list panel -----------------

function renderStoreDualList(availableEl, savedEl, selectedStoreIds) {
  availableEl.innerHTML = "";
  savedEl.innerHTML = "";

  const validIds = new Set(AVAILABLE_STORES.map((s) => s.id));

  AVAILABLE_STORES.forEach((store) => {
    if (!validIds.has(store.id)) return;

    const optionHtml = `<option value="${store.id}">${store.name}</option>`;
    if (selectedStoreIds.has(store.id)) {
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
    const selectedIds = new Set(
      (data || [])
        .map((row) => row.store_id)
        .filter((id) => validIds.has(id))
    );

    return selectedIds;
  } catch (err) {
    console.error("[flyers] Error loading saved stores", err);
    return new Set();
  }
}

async function saveSelectedStores(user, selectedStoreIds, statusP) {
  const supabase = getSupabase();
  if (!supabase) return;

  const idsArray = Array.from(selectedStoreIds);

  try {
    // Clear existing rows
    const { error: delError } = await supabase
      .from(TABLE_SAVED_STORES)
      .delete()
      .eq("user_id", user.id);

    if (delError) throw delError;

    if (idsArray.length > 0) {
      const rows = idsArray.map((id) => ({
        user_id: user.id,
        store_id: id,
      }));

      const { error: insError } = await supabase
        .from(TABLE_SAVED_STORES)
        .insert(rows);

      if (insError) throw insError;
    }

    if (idsArray.length === 0) {
      setText(statusP, "No stores selected.");
    } else if (idsArray.length === 1) {
      setText(statusP, "1 store saved.");
    } else {
      setText(statusP, `${idsArray.length} stores saved.`);
    }
  } catch (err) {
    console.error("[flyers] Error saving stores", err);
    setText(statusP, "Error saving your stores.");
  }
}

// ----------------- Deals preview for selected store -----------------

async function fetchDealsForStore(weekCode, storeSlug) {
  const supabase = getSupabase();
  if (!supabase) return [];

  const meta = AVAILABLE_STORES.find((s) => s.id === storeSlug);
  if (!meta) {
    console.warn("[flyers] No store metadata for slug", storeSlug);
    return [];
  }

  const brandName = meta.name; // matches flyer_items.brand in our test data

  const { data, error } = await supabase
    .from(TABLE_FLYER_ITEMS)
    .select("*")
    .eq("week_code", weekCode)
    .eq("brand", brandName);

  if (error) {
    console.error("[flyers] Error fetching deals", error);
    return [];
  }

  return data || [];
}

function renderDealsList(items, storeSlug, weekCode) {
  const listEl = document.getElementById("store-deals-list");
  const statusEl = document.getElementById("store-deals-status");
  if (!listEl || !statusEl) return;

  const storeName = prettyStoreName(storeSlug);

  if (!items || items.length === 0) {
    listEl.innerHTML =
      '<p class="muted">No items found for this store in this week yet.</p>';
    setText(
      statusEl,
      `No flyer items found for ${storeName} in ${weekCode}.`
    );
    return;
  }

  setText(
    statusEl,
    `Showing ${items.length} item(s) for ${storeName} – ${weekCode}.`
  );

  const ul = document.createElement("ul");
  ul.className = "store-deals-list-inner";

  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "deal-row";

    const priceBits = [];
    if (item.sale_price != null) priceBits.push(`Sale: $${item.sale_price}`);
    if (item.regular_price != null)
      priceBits.push(`Reg: $${item.regular_price}`);

    li.innerHTML = `
      <div class="deal-main">
        <div class="deal-title">${item.item_name || "(Unnamed item)"}</div>
        <div class="deal-meta">
          ${
            item.size
              ? `<span class="deal-size">${item.size}${
                  item.unit ? " " + item.unit : ""
                }</span>`
              : ""
          }
        </div>
      </div>
      <div class="deal-prices">
        ${priceBits.join(" • ")}
        ${
          isItemOnSale(item)
            ? '<span class="badge badge-sale">On Sale</span>'
            : ""
        }
      </div>
    `;

    ul.appendChild(li);
  });

  listEl.innerHTML = "";
  listEl.appendChild(ul);
}

// activeStoreId lets us pick which saved store to preview
async function updateDealsPreview(weekCode, selectedStoreIds, activeStoreId) {
  const statusEl = document.getElementById("store-deals-status");
  const listEl = document.getElementById("store-deals-list");
  if (!statusEl || !listEl) return;

  if (!selectedStoreIds || selectedStoreIds.size === 0) {
    setText(
      statusEl,
      "Pick at least one store in “Your Saved Stores” to see this week’s flyer items."
    );
    listEl.innerHTML = "";
    return;
  }

  const ids = Array.from(selectedStoreIds);
  // If an active store was requested and is still saved, use it;
  // otherwise fall back to the first saved store.
  let storeId =
    activeStoreId && ids.includes(activeStoreId) ? activeStoreId : ids[0];

  const weekCodeSafe = weekCode || getActiveWeekCode();

  setText(
    statusEl,
    `Loading flyer items for ${prettyStoreName(storeId)} – ${weekCodeSafe}…`
  );
  listEl.innerHTML = '<p class="muted">Loading deals…</p>';

  const items = await fetchDealsForStore(weekCodeSafe, storeId);
  renderDealsList(items, storeId, weekCodeSafe);
}

// ----------------- Stores panel init -----------------

async function initStoresPanel(user, weekCode) {
  const availableEl = document.getElementById("availableStores");
  const savedEl = document.getElementById("savedStores");
  const addBtn = document.getElementById("addStoreBtn");
  const removeBtn = document.getElementById("removeStoreBtn");
  const statusP = document.getElementById("saved-stores-message");

  if (!availableEl || !savedEl || !addBtn || !removeBtn) {
    console.warn(
      "[flyers] Dual-list store elements not found, skipping stores panel init."
    );
    return;
  }

  // Load existing saved stores
  let selectedStoreIds = await loadSavedStores(user);

  // Render the two lists
  renderStoreDualList(availableEl, savedEl, selectedStoreIds);

  // Kick off first deals preview
   // Kick off first deals preview (no specific store yet)
  await updateDealsPreview(weekCode, selectedStoreIds, null);


  addBtn.addEventListener("click", async () => {
    const selectedOptions = Array.from(availableEl.selectedOptions);
    if (selectedOptions.length === 0) return;

    if (selectedStoreIds.size + selectedOptions.length > MAX_SAVED_STORES) {
      alert(`You can only save up to ${MAX_SAVED_STORES} stores.`);
      return;
    }

    selectedOptions.forEach((opt) => {
      selectedStoreIds.add(opt.value);
    });

       renderStoreDualList(availableEl, savedEl, selectedStoreIds);
    await saveSelectedStores(user, selectedStoreIds, statusP);
    await updateDealsPreview(weekCode, selectedStoreIds, null);
  });

  removeBtn.addEventListener("click", async () => {
    const selectedOptions = Array.from(savedEl.selectedOptions);
    if (selectedOptions.length === 0) return;

    const idsToRemove = new Set(selectedOptions.map((opt) => opt.value));
    selectedStoreIds = new Set(
      Array.from(selectedStoreIds).filter((id) => !idsToRemove.has(id))
    );

    renderStoreDualList(availableEl, savedEl, selectedStoreIds);
    await saveSelectedStores(user, selectedStoreIds, statusP);
    await updateDealsPreview(weekCode, selectedStoreIds, null);

  });

   // Update preview when user selects a specific saved store
  savedEl.addEventListener("change", async () => {
    const active = savedEl.value || null; // value of the selected <option>
    await updateDealsPreview(weekCode, selectedStoreIds, active);
  });

}

// ----------------- Page bootstrap -----------------

async function initFlyersPage() {
  const weekCode = getActiveWeekCode();

  const user = await getCurrentUserOrRedirect();

  // Saved items
  await loadSavedItems(user);
  initSavedItemForm(user);

  // Saved stores + deals preview
  await initStoresPanel(user, weekCode);
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("[flyers] DOMContentLoaded");
  initFlyersPage().catch((err) => {
    console.error("[flyers] init error", err);

    const msgEl = document.getElementById("saved-stores-message");
    if (msgEl) {
      msgEl.textContent = "Error loading your saved stores.";
    }
    const itemsMsg = document.getElementById("saved-item-message");
    if (itemsMsg) {
      itemsMsg.textContent = "Error loading saved items.";
    }
  });
});
