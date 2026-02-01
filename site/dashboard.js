// site/dashboard.js
// Orchestrator: load saved stores/items -> load flyer items -> match -> render -> wire

(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});

  function $(id) { return document.getElementById(id); }

  function getElements() {
    return {
      statusBar: $("dashboard-status"),
      weekLabel: $("current-week-label"),
      noStoresMsg: $("dashboard-no-stores-message"),
      storeContainer: $("store-cards-container"),
      savedDealsError: $("saved-deals-error"),
      savedDealsList: $("saved-deals-list"),
    };
  }

  function setWeekLabel(elements, weekCode) {
    if (!elements.weekLabel) return;
    const pretty =
      Dash.util?.weekCodeToDateRangeLabel?.(weekCode) ||
      (weekCode ? String(weekCode) : "—");
    elements.weekLabel.textContent = pretty;
  }

  function buildShoppingSets(rows) {
    const active = new Set();
    const bought = new Set();
    for (const r of rows || []) {
      const storeId = r.store_id;
      const itemName = r.item_name;
      if (!storeId || !itemName) continue;

      const key = Dash.util.listKey(storeId, itemName);
      const st = String(r.status || "").toLowerCase();

      if (st === "bought") { bought.add(key); active.add(key); }
      else if (st === "active") { active.add(key); }
    }
    return { active, bought };
  }

  let _wiredOnce = false;

  async function initDashboard() {
    initShoppingDate();
    const elements = getElements();

    // modules must already be loaded by dashboard.html script tags
    if (!Dash.util || !Dash.data || !Dash.match || !Dash.render || !Dash.wire) {
      console.error("[dashboard] Missing modules. Check script order.");
      elements.statusBar && (elements.statusBar.textContent = "Dashboard scripts missing. Check script order.");
      return;
    }

    const supabase = Dash.util.getSupabase();
    if (!supabase || !supabase.from) {
      Dash.util.setStatus(elements, "Supabase client not found. Check supabaseClient.js + CDN include.", true);
      return;
    }

    try {
      Dash.util.setStatus(elements, "Loading dashboard…");

      const user = await Dash.data.getCurrentUserOrRedirect(supabase);
      const userId = user.id;

      // Week code (Sunday-start)
      let weekCode = await Dash.data.getActiveWeekCode(supabase);
      setWeekLabel(elements, weekCode);

      // Saved stores/items
      const savedStoreIds = await Dash.data.loadSavedStores(supabase, userId);
      const savedItems = await Dash.data.loadSavedItems(supabase, userId);

      // show/hide “no stores” message
      if (elements.noStoresMsg) {
        elements.noStoresMsg.style.display = savedStoreIds.size ? "none" : "block";
      }

          function initShoppingDate() {
      const input = document.getElementById("shopping-date");
      const label = document.getElementById("shopping-date-label");

      if (!input || !label) return;

      const today = new Date();
      const yyyyMmDd = today.toISOString().slice(0, 10);

      input.value = yyyyMmDd;
      updateShoppingDateLabel(today);

      input.addEventListener("change", () => {
        const d = new Date(input.value + "T00:00:00");
        updateShoppingDateLabel(d);

        // later: reload dashboard using selected date
      });
    }

    function updateShoppingDateLabel(d) {
      const label = document.getElementById("shopping-date-label");
      if (!label) return;

      label.textContent = d.toLocaleDateString("en-US", {
        weekday: "long",
        month: "short",
        day: "numeric"
      });
    }


      // Shopping list (optional)
      const listRows = await Dash.data.loadShoppingListForWeek(supabase, userId, weekCode);
      const { active: listActiveSet, bought: listBoughtSet } = buildShoppingSets(listRows);

      // Flyer items for those stores/week
      let allFlyerItems = await Dash.data.loadFlyerItemsForStores(supabase, weekCode, savedStoreIds);

      // fallback to latest week that actually has flyer data for these stores
      if (savedStoreIds.size > 0 && (!allFlyerItems || allFlyerItems.length === 0)) {
        const latest = await Dash.data.getLatestWeekWithFlyersForStores?.(supabase, savedStoreIds);
        if (latest && latest !== weekCode) {
          weekCode = latest;
          setWeekLabel(elements, weekCode);
          allFlyerItems = await Dash.data.loadFlyerItemsForStores(supabase, weekCode, savedStoreIds);
        }
      }

      const weekMetaByStore = await Dash.data.loadWeekMetaForStores(supabase, weekCode, savedStoreIds);

      // Match + render
      const matchFn = Dash.match.buildMatcher(savedItems);
      const { savedDeals, dealsByStore } = Dash.match.findSavedDeals({ allFlyerItems, savedItems, matchFn });

      Dash.render.storeCards({
        elements,
        savedStoreIds,
        allFlyerItems,
        dealsByStore,
        weekCode,
        weekLabel: elements.weekLabel?.textContent || weekCode,
        weekMetaByStore,
        listActiveSet,
        listBoughtSet,
      });

      Dash.render.savedDealsList({ elements, savedDeals, savedItems });

      // Wire events once
      if (!_wiredOnce) {
        Dash.wire.tapToFlip(elements);
        Dash.wire.miniDealButtons({ elements, supabase, userId, weekCode, listActiveSet, listBoughtSet });
        _wiredOnce = true;
      }

      Dash.util.setStatus(elements, "Dashboard loaded.");
    } catch (err) {
      console.error("[dashboard] init error:", err);
      Dash.util.setStatus(elements, `Dashboard error: ${err?.message || err}`, true);
    }
  }

  document.addEventListener("DOMContentLoaded", initDashboard);
})();
