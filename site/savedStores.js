// savedStores.js
console.log("[savedStores] loaded");

const SAVED_STORES_TABLE = "saved_stores";

/**
 * Get Supabase client from global.
 */
function getSupabaseClient() {
  const client = window.supabaseClient;
  if (!client) {
    console.warn("[savedStores] supabaseClient not found on window");
  }
  return client;
}

/**
 * Get the current signed-in user's email.
 */
async function getCurrentAccountEmail() {
  const supabase = getSupabaseClient();
  if (!supabase) return null;

  const { data, error } = await supabase.auth.getUser();
  if (error || !data?.user) {
    console.warn("[savedStores] getUser error or no user:", error);
    return null;
  }
  return data.user.email;
}

/**
 * Save a store for this account (id + name).
 * Enforces uniqueness via DB constraint.
 */
async function saveStoreForAccount(storeId, storeName) {
  const supabase = getSupabaseClient();
  if (!supabase) return { ok: false, message: "No Supabase client" };

  const email = await getCurrentAccountEmail();
  if (!email) return { ok: false, message: "Not signed in" };

  const { error } = await supabase
    .from(SAVED_STORES_TABLE)
    .upsert(
      {
        account_email: email,
        store_id: storeId,
        store_name: storeName,
      },
      {
        onConflict: "account_email,store_id",
      }
    );

  if (error) {
    console.error("[savedStores] upsert error:", error);
    return { ok: false, message: "Could not save store." };
  }

  return { ok: true, message: "Store saved." };
}

/**
 * Load all saved stores for the current account.
 */
async function loadSavedStoresForAccount() {
  const supabase = getSupabaseClient();
  if (!supabase) return [];

  const email = await getCurrentAccountEmail();
  if (!email) return [];

  const { data, error } = await supabase
    .from(SAVED_STORES_TABLE)
    .select("store_id, store_name, created_at")
    .eq("account_email", email)
    .order("store_name", { ascending: true });

  if (error) {
    console.error("[savedStores] load error:", error);
    return [];
  }

  return data || [];
}

/**
 * Attach click handlers for "Save store" buttons on flyers.html.
 * Expects buttons with class .js-save-store and data-store-id/name.
 */
function attachSaveStoreButtons() {
  const buttons = document.querySelectorAll(".js-save-store");
  if (!buttons.length) {
    console.log("[savedStores] no .js-save-store buttons on this page");
    return;
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      const storeId = btn.getAttribute("data-store-id");
      const storeName = btn.getAttribute("data-store-name") || storeId;
      if (!storeId) {
        console.warn("[savedStores] button missing data-store-id");
        return;
      }

      btn.disabled = true;
      const originalText = btn.textContent;
      btn.textContent = "Saving...";

      const result = await saveStoreForAccount(storeId, storeName);

      if (!result.ok) {
        alert(result.message || "Could not save store.");
        btn.disabled = false;
        btn.textContent = originalText;
        return;
      }

      btn.textContent = "Saved";
      btn.classList.add("saved-store-btn");
    });
  });
}

/**
 * Render saved stores list into dashboard, if container exists.
 */
async function renderDashboardSavedStores() {
  const container = document.getElementById("dashboard-saved-stores");
  if (!container) {
    console.log("[savedStores] no #dashboard-saved-stores on this page");
    return;
  }

  container.innerHTML = "<p>Loading your stores...</p>";

  const stores = await loadSavedStoresForAccount();

  if (!stores.length) {
    container.innerHTML =
      "<p>You don't have any saved stores yet. Visit the Flyers page to pick your favorites.</p>";
    return;
  }

  const list = document.createElement("ul");
  list.className = "saved-stores-list";

  stores.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s.store_name;
    list.appendChild(li);
  });

  container.innerHTML = "";
  container.appendChild(list);
}

// Expose helpers if you need them elsewhere
window.savedStores = {
  attachSaveStoreButtons,
  renderDashboardSavedStores,
};
