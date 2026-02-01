// site/dashboard_data.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});
  const CFG = () => Dash.CFG;

  // -------------------------
  // Helpers
  // -------------------------
  function uniq(arr) {
    return Array.from(new Set((arr || []).filter(Boolean)));
  }

  async function getFlyerStoreMapping(supabase, storeSlugs) {
    // We don't know your exact column names in flyer_stores,
    // so we try common combos until one works.
    const slugs = uniq(storeSlugs.map((s) => String(s).trim()));
    if (slugs.length === 0) return { slugToId: new Map(), idToSlug: new Map() };

    const attempts = [
      { slugCol: "store_slug", idCol: "id" },
      { slugCol: "slug", idCol: "id" },
      { slugCol: "store_slug", idCol: "store_id" },
      { slugCol: "slug", idCol: "store_id" },
    ];

    for (const a of attempts) {
      const sel = `${a.idCol},${a.slugCol}`;
      const { data, error } = await supabase
        .from("flyer_stores")
        .select(sel)
        .in(a.slugCol, slugs);

      if (error) continue;

      const slugToId = new Map();
      const idToSlug = new Map();

      for (const row of data || []) {
        const slug = row[a.slugCol];
        const id = row[a.idCol];
        if (!slug || id == null) continue;

        const idNum = Number(id);
        if (!Number.isFinite(idNum)) continue;

        slugToId.set(String(slug), idNum);
        idToSlug.set(idNum, String(slug));
      }

      if (slugToId.size > 0) return { slugToId, idToSlug };
    }

    // If we couldn't map, return empty maps (dashboard will show 0)
    // but we also log a clear message.
    console.warn(
      "[dashboard_data] Could not map store slugs -> flyer_store_id. " +
        "Check flyer_stores column names (expected slug/store_slug + id/store_id)."
    );
    return { slugToId: new Map(), idToSlug: new Map() };
  }

  Dash.data = {
    async getActiveWeekCode(supabase) {
      // Allow override: ?week=wk_YYYYMMDD
      const params = new URLSearchParams(window.location.search);
      const weekParam = (params.get("week") || "").trim().toLowerCase();
      if (/^wk_\d{8}$/.test(weekParam)) return weekParam;

      // Compute "this week" (Sunday start) in LOCAL time
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // local midnight
      const day = start.getDay(); // 0=Sun ... 6=Sat
      start.setDate(start.getDate() - day);

      const yyyy = String(start.getFullYear());
      const mm = String(start.getMonth() + 1).padStart(2, "0");
      const dd = String(start.getDate()).padStart(2, "0");
      return `wk_${yyyy}${mm}${dd}`;
    },

    async getCurrentUserOrRedirect(supabase) {
      const { data, error } = await supabase.auth.getUser();
      if (error) throw error;
      if (!data.user) {
        window.location.href = "login.html";
        throw new Error("Not logged in");
      }
      return data.user;
    },

    async loadSavedStores(supabase, userId) {
      const validIds = new Set(CFG().AVAILABLE_STORES.map((s) => s.id));

      const { data, error } = await supabase
        .from(CFG().TABLE_SAVED_STORES)
        .select("store_id")
        .eq("user_id", userId);

      if (error) throw error;

      const result = new Set();
      (data || []).forEach((row) => {
        // store_id is your app slug like "wegmans"
        if (row.store_id && validIds.has(row.store_id)) result.add(row.store_id);
      });

      return result;
    },

    async loadWeekMetaForStores(supabase, weekCode, savedStoreIds) {
      // optional; keep empty for now
      return new Map();
    },

    async loadSavedItems(supabase, userId) {
      const { data, error } = await supabase
        .from(CFG().TABLE_SAVED_ITEMS)
        .select("id, item_name")
        .eq("user_id", userId)
        .order("id", { ascending: true });

      if (error) throw error;
      return data || [];
    },

    // ✅ THE REAL FIX:
    // savedStoreIds are slugs ("wegmans") but flyer_items uses flyer_store_id (int).
    // So we:
    //   1) query flyer_stores to map slug -> id
    //   2) query flyer_items by flyer_store_id
    //   3) attach store_slug to each row for rendering
    async loadFlyerItemsForStores(supabase, weekCode, savedStoreIds) {
      if (!savedStoreIds || savedStoreIds.size === 0) return [];

      const storeSlugs = uniq(Array.from(savedStoreIds).map(String));
      if (storeSlugs.length === 0) return [];

      const { slugToId, idToSlug } = await getFlyerStoreMapping(supabase, storeSlugs);
      const flyerStoreIds = uniq(storeSlugs.map((s) => slugToId.get(s))).filter((n) => Number.isFinite(n));

      if (flyerStoreIds.length === 0) {
        console.warn("[dashboard_data] No flyer_store_id values found for saved stores:", storeSlugs);
        return [];
      }

      const { data, error } = await supabase
        .from(CFG().ITEMS_TABLE) // should be "flyer_items"
        .select("*")
        .eq("week_code", weekCode)
        .in("flyer_store_id", flyerStoreIds);

      if (error) throw error;

      return (data || []).map((row) => ({
        ...row,
        store_slug: idToSlug.get(Number(row.flyer_store_id)) || null,
      }));
    },

    async loadShoppingListForWeek(supabase, userId, weekCode) {
      try {
        const { data, error } = await supabase
          .from(CFG().TABLE_SHOPPING_LIST)
          .select("store_id, week_code, item_name, status")
          .eq("user_id", userId)
          .eq("week_code", weekCode);

        if (error) {
          console.warn("[dashboard] Shopping list table not available (safe):", error);
          return [];
        }
        return data || [];
      } catch (err) {
        console.warn("[dashboard] Shopping list load failed (safe):", err);
        return [];
      }
    },

    async upsertShoppingListStatus(supabase, { userId, weekCode, storeId, itemName, status }) {
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
          .from(CFG().TABLE_SHOPPING_LIST)
          .upsert(payload, { onConflict: "user_id,week_code,store_id,item_name" });

        if (error) console.warn("[dashboard] shopping list upsert error:", error);
      } catch (err) {
        console.warn("[dashboard] shopping list upsert failed:", err);
      }
    },
  };

  // Fallback helper: find latest week_code with data for your saved stores
  Dash.data.getLatestWeekWithFlyersForStores = async function (supabase, savedStoreIds) {
    const storeSlugs = uniq(Array.from(savedStoreIds || []).map(String));
    if (storeSlugs.length === 0) return null;

    const { slugToId } = await getFlyerStoreMapping(supabase, storeSlugs);
    const flyerStoreIds = uniq(storeSlugs.map((s) => slugToId.get(s))).filter((n) => Number.isFinite(n));
    if (flyerStoreIds.length === 0) return null;

    const { data, error } = await supabase
      .from("flyer_items")
      .select("week_code")
      .in("flyer_store_id", flyerStoreIds)
      .not("week_code", "is", null)
      .order("week_code", { ascending: false })
      .limit(1);

    if (error) {
      console.error("[dashboard_data] getLatestWeekWithFlyersForStores error:", error);
      return null;
    }

    return data && data.length ? data[0].week_code : null;
  };
})();
