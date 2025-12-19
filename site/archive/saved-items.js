import { supabase } from "/site/scripts/supabaseClient.js";

function el(html) {
  const d = document.createElement("div");
  d.innerHTML = html.trim();
  return d.firstChild;
}

async function getUserId() {
  const { data: { user } } = await supabase.auth.getUser();
  return user?.id || null;
}

async function loadSaved(userId) {
  const { data, error } = await supabase
    .from("saved_items")
    .select(`
      id,
      flyer_items (
        id, store_key, week, title, size, price, image_path,
        items ( name )
      )
    `)
    .eq("user_id", userId)
    .order("created_at", { ascending: false });

  if (error) throw error;
  return data || [];
}

async function removeSaved(savedId) {
  return supabase.from("saved_items").delete().eq("id", savedId);
}

(async function init() {
  const wrap = document.getElementById("savedList");
  wrap.innerHTML = "Loading...";

  const userId = await getUserId();
  if (!userId) {
    wrap.innerHTML = "Please log in to view saved items.";
    return;
  }

  try {
    const rows = await loadSaved(userId);

    if (!rows.length) {
      wrap.innerHTML = "No saved items yet.";
      return;
    }

    wrap.innerHTML = "";
    rows.forEach(row => {
      const fi = row.flyer_items;
      const displayName = fi?.items?.name || fi?.title || "Unnamed item";

      const card = el(`
        <div class="card" style="padding:10px; margin-bottom:8px; border:1px solid #e5e5e5; border-radius:10px;">
          <div style="font-weight:600;">${displayName}</div>
          <div style="font-size:0.9em; opacity:0.8;">
            ${fi.store_key} • ${fi.size || ""} • $${fi.price ?? "?"}
          </div>
          <div style="margin-top:6px;">
            <button class="rmBtn"
                    style="padding:6px 10px; border-radius:6px; border:1px solid #999; background:#fff;">
              Remove
            </button>
          </div>
        </div>
      `);

      card.querySelector(".rmBtn").addEventListener("click", async () => {
        const { error } = await removeSaved(row.id);
        if (error) return alert(error.message);
        card.remove();
      });

      wrap.appendChild(card);
    });

  } catch (err) {
    console.error(err);
    wrap.innerHTML = "Error loading saved items.";
  }
})();
