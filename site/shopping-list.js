// Tracked Items (long-term watchlist)
// - persistent across weeks
// - used for matching deals weekly


console.log("[saved-items] saved-items.js loaded");

let gSupabase = null;
let gUser = null;

let statusEl;
let addFormEl;
let newItemInputEl;
let savedItemsListEl;
let savedItemsEmptyEl;

// ---------------------------------------------------------
// Supabase helpers
// ---------------------------------------------------------
function initSupabaseFromGlobal() {
  if (gSupabase) return gSupabase;

  const client = window.supabaseClient || window.supabase;
  if (!client) {
    console.error(
      "[saved-items] Supabase client missing. Make sure supabaseClient.js and the CDN script are loaded."
    );
    return null;
  }
  gSupabase = client;
  return gSupabase;
}

async function fetchCurrentUser() {
  const supabase = initSupabaseFromGlobal();
  if (!supabase) return null;

  try {
    if (supabase.auth && typeof supabase.auth.getUser === "function") {
      const { data, error } = await supabase.auth.getUser();
      if (error) {
        console.error("[saved-items] getUser error:", error);
        return null;
      }
      if (!data || !data.user) {
        console.warn("[saved-items] no user session found");
        return null;
      }
      console.log("[saved-items] current user:", data.user);
      return data.user;
    }

    if (supabase.auth && typeof supabase.auth.user === "function") {
      const user = supabase.auth.user();
      if (!user) {
        console.warn("[saved-items] no user from auth.user()");
        return null;
      }
      console.log("[saved-items] current user (v1):", user);
      return user;
    }

    console.error(
      "[saved-items] no recognizable auth method on supabase client"
    );
    return null;
  } catch (err) {
    console.error("[saved-items] fetchCurrentUser unexpected error:", err);
    return null;
  }
}

// ---------------------------------------------------------
// Main bootstrap
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  console.log("[saved-items] DOMContentLoaded");

  statusEl = document.getElementById("saved-items-status");
  addFormEl = document.getElementById("add-item-form");
  newItemInputEl = document.getElementById("new-item-input");
  savedItemsListEl = document.getElementById("saved-items-list");
  savedItemsEmptyEl = document.getElementById("saved-items-empty");

  if (statusEl) {
    statusEl.textContent = "Checking your session...";
  }

  gUser = await fetchCurrentUser();
  if (!gUser) {
    if (statusEl)
      statusEl.textContent = "Please log in to manage your saved items.";
    if (addFormEl) addFormEl.classList.add("hidden");
    return;
  }

  if (statusEl) {
    statusEl.textContent = "You’re logged in. These are your saved items.";
  }

  if (addFormEl) {
    addFormEl.addEventListener("submit", onAddItemSubmit);
  }

  await loadSavedItems();
});

// ---------------------------------------------------------
// Load & render saved items
// ---------------------------------------------------------
async function loadSavedItems() {
  const supabase = initSupabaseFromGlobal();
  if (!supabase || !gUser) return;

  const { data, error } = await supabase
    .from("user_saved_products")            // 👈 NEW TABLE NAME
    .select("id, label")
    .eq("user_id", gUser.id)
    .order("label");

  if (error) {
    console.error("[saved-items] loadSavedItems error:", error);
    if (statusEl) statusEl.textContent = "Error loading saved items.";
    return;
  }

  renderSavedItems(data || []);
}

function renderSavedItems(items) {
  if (!savedItemsListEl || !savedItemsEmptyEl) return;

  savedItemsListEl.innerHTML = "";

  if (!items.length) {
    savedItemsEmptyEl.classList.remove("hidden");
    return;
  }

  savedItemsEmptyEl.classList.add("hidden");

  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "saved-item-row";

    const labelDiv = document.createElement("div");
    labelDiv.className = "saved-item-label";
    labelDiv.textContent = item.label;

    const actionsDiv = document.createElement("div");
    actionsDiv.className = "saved-item-actions";

    // Placeholder button for future "search deals for this item"
    const searchBtn = document.createElement("button");
    searchBtn.type = "button";
    searchBtn.textContent = "Find deals";
    searchBtn.addEventListener("click", () => {
      alert(`Later this will search flyers for: "${item.label}"`);
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Remove";
    deleteBtn.classList.add("danger");
    deleteBtn.addEventListener("click", () => {
      deleteSavedItem(item.id);
    });

    actionsDiv.appendChild(searchBtn);
    actionsDiv.appendChild(deleteBtn);

    li.appendChild(labelDiv);
    li.appendChild(actionsDiv);
    savedItemsListEl.appendChild(li);
  });
}

// ---------------------------------------------------------
// Add & delete items
// ---------------------------------------------------------
async function onAddItemSubmit(event) {
  event.preventDefault();
  if (!newItemInputEl || !gUser) return;

  const raw = newItemInputEl.value.trim();
  if (!raw) return;

  const label = raw;
  const normalized = raw.toUpperCase();

  const supabase = initSupabaseFromGlobal();
  if (!supabase) return;

  const { error } = await supabase
    .from("user_saved_products")            // 👈 NEW TABLE NAME
    .insert({
      user_id: gUser.id,
      label,
      normalized_key: normalized,
    });

  if (error) {
    console.error("[saved-items] insert error:", error);
    alert("Could not save item. Please try again.");
    return;
  }

  newItemInputEl.value = "";
  await loadSavedItems();
}

async function deleteSavedItem(id) {
  const supabase = initSupabaseFromGlobal();
  if (!supabase || !gUser) return;

  const { error } = await supabase
    .from("user_saved_products")            // 👈 NEW TABLE NAME
    .delete()
    .eq("id", id)
    .eq("user_id", gUser.id);

  if (error) {
    console.error("[saved-items] delete error:", error);
    alert("Could not remove item. Please try again.");
    return;
  }

  await loadSavedItems();
}
