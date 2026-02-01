// site/scripts/saved.js
// Deals-4Me – Saved Items page (one-big-pond)
//
// FIXED:
// - Stops calling the RPC (your table doesn't have list_type/tier columns)
// - Inserts directly into user_saved_items using real columns only
// - Enforces Basic tier cap (12) on the client for now
// - profile_id fallback: uses active profile uuid if present, else user.id (valid uuid)

console.log("SAVED.JS LOADED – DIRECT INSERT FIX (no RPC)");

// ---- Config ----
const TABLE_SAVED_ITEMS = "user_saved_items";

const LIMITS = {
  basic: 12,
  gold: 40,
  platinum: Infinity,
};

const CATEGORIES = [
  { key: "produce", label: "Produce", refine: ["Bananas", "Apples", "Berries", "Salad", "Potatoes", "Onions", "Tomatoes", "Other…"] },
  { key: "meat", label: "Meat / Seafood", refine: ["Chicken", "Beef", "Pork", "Seafood", "Deli", "Other…"] },
  { key: "dairy", label: "Dairy", refine: ["Milk", "Eggs", "Cheese", "Butter", "Yogurt", "Other…"] },
  { key: "frozen", label: "Frozen", refine: ["Pizza", "Vegetables", "Meals", "Ice Cream", "Other…"] },
  { key: "pantry", label: "Pantry", refine: ["Pasta", "Rice", "Sauces", "Canned Goods", "Peanut Butter", "Other…"] },
  { key: "snacks", label: "Snacks", refine: ["Chips", "Crackers", "Cookies", "Granola Bars", "Other…"] },
  { key: "cereal", label: "Cereal / Breakfast", refine: ["Cheerios", "Frosted Flakes", "Oatmeal", "Pancake Mix", "Other…"] },
  { key: "beverages", label: "Beverages", refine: ["Soda", "Juice", "Water", "Coffee", "Tea", "Other…"] },
  { key: "household", label: "Household", refine: ["Paper Towels", "Toilet Paper", "Trash Bags", "Laundry", "Other…"] },
  { key: "personal_care", label: "Personal Care", refine: ["Soap", "Shampoo", "Toothpaste", "Deodorant", "Other…"] },
  { key: "baby_kids", label: "Baby / Kids", refine: ["Diapers", "Wipes", "Baby Food", "Other…"] },
  { key: "pet", label: "Pet", refine: ["Dog Food", "Cat Food", "Litter", "Treats", "Other…"] },
  { key: "other", label: "Other", refine: null },
];

// ---- DOM ----
const el = {
  category: document.getElementById("saved-category"),
  categoryHelp: document.getElementById("saved-category-help"),

  refineSelect: document.getElementById("saved-refine-select"),
  refineText: document.getElementById("saved-refine"),
  refineHelp: document.getElementById("saved-refine-help"),

  form: document.getElementById("saved-add-form"),
  addError: document.getElementById("saved-add-error"),

  alert: document.getElementById("saved-alert"),
  tbody: document.getElementById("saved-body"),
  planInfo: document.getElementById("saved-plan-info"),
};

// ---- Helpers ----
function getSupabase() {
  const candidate = window.supabaseClient || window.supabase;
  if (!candidate || !candidate.from) {
    console.error("[saved] Supabase client not found. Is supabaseClient.js loaded?");
    return null;
  }
  return candidate;
}

function escapeHTML(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function showAlert(message, isError = false) {
  if (!el.alert) return;
  el.alert.textContent = message;
  el.alert.style.display = "block";
  el.alert.classList.toggle("error", !!isError);
}

function hideAddError() {
  if (!el.addError) return;
  el.addError.style.display = "none";
  el.addError.textContent = "";
}

function showAddError(msg) {
  if (!el.addError) return;
  el.addError.style.display = "block";
  el.addError.textContent = msg;
}

function formatISODate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

// LocalStorage active profile (your current app keys)
// If it's JSON and contains a uuid id/profile_id/profileId, use it.
// Otherwise return null and we'll fallback to user.id.
function getActiveProfileIdSafe() {
  const keys = ["d4m_active_profile", "d4m_activeProfile", "d4m_active_profile_id", "active_profile_id", "profile_id"];

  for (const k of keys) {
    const raw = localStorage.getItem(k);
    if (!raw) continue;

    if (raw.trim().startsWith("{")) {
      try {
        const obj = JSON.parse(raw);
        const id = obj?.id || obj?.profile_id || obj?.profileId;
        if (typeof id === "string" && id.includes("-") && id.length > 20) return id;
      } catch (_) {}
      continue;
    }

    if (raw.includes("-") && raw.length > 20) return raw;
  }

  return null;
}

function buildItemName(categoryKey, refineValue, refineFreeText) {
  const cat = CATEGORIES.find((c) => c.key === categoryKey);
  const catLabel = cat ? cat.label : "Item";
  const refine = (refineValue || "").trim();
  const free = (refineFreeText || "").trim();
  const chosen = refine && refine !== "Other…" ? refine : free;
  if (chosen) return `${catLabel}: ${chosen}`;
  return catLabel;
}

function makeItemKey(itemName) {
  return String(itemName || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

function getRowDisplayName(row) {
  const candidates = [row.item_name, row.name, row.item, row.title, row.product_name];
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c.trim();
  }
  return "(unnamed item)";
}

function getRowBestPrice(row) {
  const v = row.best_price ?? row.lowest_price ?? row.min_price ?? null;
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toFixed(2)}`;
}

function getRowBestStore(row) {
  return row.best_store ?? row.best_store_name ?? row.store ?? "—";
}

function getRowLastSeen(row) {
  return row.last_seen ?? row.last_seen_at ?? row.updated_at ?? row.created_at ?? null;
}

// ---- UI wiring ----
function populateCategories() {
  if (!el.category) return;

  el.category.innerHTML = `<option value="">Choose a category…</option>`;
  for (const c of CATEGORIES) {
    const opt = document.createElement("option");
    opt.value = c.key;
    opt.textContent = c.label;
    el.category.appendChild(opt);
  }
}

function setRefineModeForCategory(categoryKey) {
  const cat = CATEGORIES.find((c) => c.key === categoryKey);

  if (el.refineSelect) el.refineSelect.style.display = "none";
  if (el.refineText) el.refineText.style.display = "none";
  if (el.refineHelp) el.refineHelp.textContent = "";
  if (el.categoryHelp) el.categoryHelp.textContent = "";

  if (!cat) {
    if (el.categoryHelp) el.categoryHelp.textContent = "Pick a category first.";
    return;
  }

  if (el.categoryHelp) el.categoryHelp.textContent = `Optional: refine ${cat.label.toLowerCase()} (brand, size, type).`;

  // Presets dropdown
  if (Array.isArray(cat.refine) && cat.refine.length) {
    if (el.refineSelect) {
      el.refineSelect.style.display = "block";
      el.refineSelect.innerHTML = `<option value="">Choose one…</option>`;
      for (const r of cat.refine) {
        const opt = document.createElement("option");
        opt.value = r;
        opt.textContent = r;
        el.refineSelect.appendChild(opt);
      }
    }
    if (el.refineHelp) el.refineHelp.textContent = "Choose one, or pick “Other…” to type your own.";
    if (el.refineText) {
      el.refineText.value = "";
      el.refineText.style.display = "none";
    }
    return;
  }

  // Free text
  if (el.refineText) {
    el.refineText.style.display = "block";
    el.refineText.value = "";
  }
  if (el.refineHelp) el.refineHelp.textContent = "Type a quick note (brand, size, etc.) or leave blank.";
}

// ---- Data ----
async function getAuthedUser(supabase) {
  if (window.requireAuth) await window.requireAuth();

  const { data, error } = await supabase.auth.getUser();
  if (error) throw error;
  if (!data.user) {
    window.location.href = "login.html";
    throw new Error("Not logged in");
  }
  return data.user;
}

async function fetchSavedItems(supabase, userId) {
  // Your table has BOTH user_id and auth_user_id.
  // We'll prefer auth_user_id if it exists on rows (it does in your schema).
  const { data, error } = await supabase
    .from(TABLE_SAVED_ITEMS)
    .select("*")
    .eq("auth_user_id", userId)
    .order("created_at", { ascending: true });

  if (error) throw error;
  return data || [];
}

async function insertSavedItemDirect(supabase, { userId, profileId, itemName }) {
  const payload = {
    auth_user_id: userId,
    user_id: userId,
    profile_id: profileId,
    item_name: itemName,
    item_key: makeItemKey(itemName),
    notes: null,
  };

  const { error } = await supabase.from(TABLE_SAVED_ITEMS).insert(payload);
  if (error) throw error;
}

async function removeSavedItem(supabase, userId, row) {
  if (row?.id) {
    const { error } = await supabase
      .from(TABLE_SAVED_ITEMS)
      .delete()
      .eq("id", row.id)
      .eq("auth_user_id", userId);
    if (error) throw error;
    return;
  }

  // fallback
  const name = getRowDisplayName(row);
  const { error } = await supabase
    .from(TABLE_SAVED_ITEMS)
    .delete()
    .eq("auth_user_id", userId)
    .eq("item_name", name);
  if (error) throw error;
}

// ---- Rendering ----
function renderRows(rows) {
  if (!el.tbody) return;
  el.tbody.innerHTML = "";

  if (!rows || rows.length === 0) {
    el.tbody.innerHTML = `
      <tr>
        <td colspan="5" class="muted" style="padding: 0.75rem;">
          You don’t have any saved items yet. Add one above.
        </td>
      </tr>
    `;
    return;
  }

  for (const row of rows) {
    const name = getRowDisplayName(row);
    const bestPrice = getRowBestPrice(row);
    const bestStore = escapeHTML(getRowBestStore(row));
    const lastSeen = formatISODate(getRowLastSeen(row));

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHTML(name)}</td>
      <td>${escapeHTML(bestPrice)}</td>
      <td>${bestStore || "—"}</td>
      <td>${escapeHTML(lastSeen)}</td>
      <td style="text-align:right;">
        <button class="mini-btn" data-action="remove">Remove</button>
      </td>
    `;

    const btn = tr.querySelector('button[data-action="remove"]');
    if (btn) {
      btn.addEventListener("click", () => {
        document.dispatchEvent(new CustomEvent("saved:remove", { detail: row }));
      });
    }

    el.tbody.appendChild(tr);
  }
}

function renderPlanInfo(count, tierGuess = "basic") {
  if (!el.planInfo) return;
  const limit = LIMITS[tierGuess] ?? LIMITS.basic;
  el.planInfo.textContent =
    limit === Infinity ? `You’re tracking ${count} item(s).` : `You’re tracking ${count}/${limit} item(s).`;
}

// ---- Main ----
async function initSavedPage() {
  console.log("[saved] initSavedPage()");

  if (window.renderToolbar) window.renderToolbar("saved");

  const supabase = getSupabase();
  if (!supabase) {
    showAlert("Supabase is not available. Are you offline?", true);
    return;
  }

  populateCategories();
  setRefineModeForCategory("");

  if (el.category) {
    el.category.addEventListener("change", () => setRefineModeForCategory(el.category.value));
  }

  if (el.refineSelect) {
    el.refineSelect.addEventListener("change", () => {
      const v = el.refineSelect.value;
      if (el.refineText) {
        el.refineText.style.display = v === "Other…" ? "block" : "none";
        if (v !== "Other…") el.refineText.value = "";
      }
    });
  }

  let user;
  try {
    user = await getAuthedUser(supabase);
  } catch (err) {
    console.error("[saved] auth error:", err);
    showAlert("Please log in again.", true);
    return;
  }

  const tier = "basic"; // keep simple for now

  // Load + render
  try {
    showAlert("Loading your saved items...");
    const rows = await fetchSavedItems(supabase, user.id);
    renderRows(rows);
    renderPlanInfo(rows.length, tier);
    showAlert(rows.length ? "Here are your saved items." : "No saved items yet. Add one above.");
  } catch (err) {
    console.error("[saved] load error:", err);
    showAlert("Couldn’t load saved items. Check console for details.", true);
  }

  // Add item
  if (el.form) {
    el.form.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideAddError();

      const categoryKey = el.category ? el.category.value : "";
      if (!categoryKey) return showAddError("Pick a category first.");

      const refineSelectVal =
        el.refineSelect && el.refineSelect.style.display !== "none" ? el.refineSelect.value : "";
      const refineTextVal =
        el.refineText && el.refineText.style.display !== "none" ? el.refineText.value : "";

      const itemName = buildItemName(categoryKey, refineSelectVal, refineTextVal);

      try {
        // reload rows so cap is accurate
        const rowsBefore = await fetchSavedItems(supabase, user.id);
        const limit = LIMITS[tier] ?? LIMITS.basic;
        if (rowsBefore.length >= limit) {
          return showAddError(`Basic tier limit reached (${limit}).`);
        }

        // profile_id: use active profile uuid if present, else user.id
        const profileId = getActiveProfileIdSafe() || user.id;

        await insertSavedItemDirect(supabase, { userId: user.id, profileId, itemName });

        const rows = await fetchSavedItems(supabase, user.id);
        renderRows(rows);
        renderPlanInfo(rows.length, tier);
        showAlert("Saved!", false);

        if (el.category) el.category.value = "";
        if (el.refineSelect) el.refineSelect.value = "";
        if (el.refineText) el.refineText.value = "";
        setRefineModeForCategory("");
      } catch (err) {
        console.error("[saved] add error:", err);
        showAddError(err?.message || "Could not save item. Check console for details.");
      }
    });
  }

  // Remove handler
  document.addEventListener("saved:remove", async (evt) => {
    const row = evt.detail;
    try {
      await removeSavedItem(supabase, user.id, row);
      const rows = await fetchSavedItems(supabase, user.id);
      renderRows(rows);
      renderPlanInfo(rows.length, tier);
      showAlert("Removed.", false);
    } catch (err) {
      console.error("[saved] remove error:", err);
      showAlert("Could not remove item. Check console for details.", true);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSavedPage().catch((err) => console.error("[saved] init crash:", err));
});
