// /site/scripts/flyers-search.js
// Uses YOUR schema: public.flyer_items + public.saved_items

// Prefer window.supabase (from header-auth.js). Fallback import if needed.
import { supabase as importedSupabase } from "/site/scripts/supabaseClient.js";
const supabase = window.supabase || importedSupabase;

function el(html) {
  const d = document.createElement("div");
  d.innerHTML = html.trim();
  return d.firstChild;
}

async function getUserId() {
  const { data: { user } } = await supabase.auth.getUser();
  return user?.id || null;
}

async function loadSavedSet(userId) {
  const { data, error } = await supabase
    .from("saved_items")
    .select("flyer_item_id")
    .eq("user_id", userId);

  if (error) {
    console.error(error);
    return new Set();
  }
  return new Set((data || []).map(r => r.flyer_item_id));
}

async function searchFlyerItems(q) {
  // Search by item_name and brand (case-insensitive)
  const { data, error } = await supabase
    .from("flyer_items")
    .select("id, flyer_id, item_name, brand, price, promo_start, promo_end, item_id")
    .or(`item_name.ilike.%${q}%,brand.ilike.%${q}%`)
    .limit(50);

  if (error) throw error;
  return data || [];
}

async function saveFlyerItem(userId, flyerItemId) {
  return supabase.from("saved_items").insert({
    user_id: userId,
    flyer_item_id: flyerItemId
  });
}

async function unsaveFlyerItem(userId, flyerItemId) {
  return supabase
    .from("saved_items")
    .delete()
    .eq("user_id", userId)
    .eq("flyer_item_id", flyerItemId);
}

function renderResults(items, savedSet, userId) {
  const wrap = document.getElementById("searchResults");
  wrap.innerHTML = "";

  if (!items.length) {
    wrap.textContent = "No matches.";
    return;
  }

  items.forEach(item => {
    const name = item.item_name || "Unnamed item";
    const brand = item.brand ? ` • ${item.brand}` : "";
    const price = (item.price !== null && item.price !== undefined) ? `$${item.price}` : "$?";
    const dates =
      (item.promo_start || item.promo_end)
        ? ` • ${item.promo_start || "?"} → ${item.promo_end || "?"}`
        : "";

    const isSaved = savedSet.has(item.id);

    const card = el(`
      <div class="result-card">
        <div class="result-title">${name}</div>
        <div class="result-meta">${price}${brand}${dates}</div>
        <button class="saveBtn" data-id="${item.id}">
          ${isSaved ? "Saved ✅ (click to remove)" : "⭐ Save"}
        </button>
      </div>
    `);

    card.querySelector(".saveBtn").addEventListener("click", async (e) => {
      if (!userId) {
        alert("Please log in to save items.");
        return;
      }

      const id = Number(e.currentTarget.dataset.id);

      if (savedSet.has(id)) {
        const { error } = await unsaveFlyerItem(userId, id);
        if (error) return alert(error.message);
        savedSet.delete(id);
      } else {
        const { error } = await saveFlyerItem(userId, id);
        if (error) return alert(error.message);
        savedSet.add(id);
      }

      renderResults(items, savedSet, userId);
    });

    wrap.appendChild(card);
  });
}

(async function init() {
  const input = document.getElementById("itemSearch");
  let userId = await getUserId();
  let savedSet = userId ? await loadSavedSet(userId) : new Set();

  input.addEventListener("input", async () => {
    const q = input.value.trim();
    if (q.length < 2) {
      document.getElementById("searchResults").innerHTML = "";
      return;
    }
    try {
      const items = await searchFlyerItems(q);
      userId = await getUserId();
      savedSet = userId ? await loadSavedSet(userId) : new Set();
      renderResults(items, savedSet, userId);
    } catch (err) {
      console.error(err);
      alert(err.message);
    }
  });
})();
