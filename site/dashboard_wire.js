// dashboard_wire.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});
  const U = () => Dash.util;

  Dash.wire = {
    tapToFlip(elements) {
      const container = elements.storeContainer;
      if (!container) return;

      container.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (btn) return;

        const face = e.target.closest(".store-card-face");
        if (!face) return;

        const inner = e.target.closest(".store-card-inner");
        if (!inner) return;

        inner.classList.toggle("is-flipped");
      });
    },

    miniDealButtons({ elements, supabase, userId, weekCode, listActiveSet, listBoughtSet }) {
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

        const key = U().listKey(slug, itemName);

        if (action === "add") {
          if ((listActiveSet && listActiveSet.has(key)) || (listBoughtSet && listBoughtSet.has(key))) return;

          listActiveSet.add(key);

          btn.textContent = "Added";
          btn.classList.add("mini-btn-on");
          btn.disabled = true;

          await Dash.data.upsertShoppingListStatus(supabase, {
            userId,
            weekCode,
            storeId: slug,
            itemName,
            status: "active",
          });
          return;
        }

        if (action === "bought") {
          if (listBoughtSet.has(key)) return;

          listBoughtSet.add(key);
          listActiveSet.add(key);

          btn.textContent = "Bought ✓";
          btn.classList.add("mini-btn-on");
          btn.disabled = true;

          const row = btn.closest(".mini-deal-row");
          if (row) {
            const addBtn = row.querySelector('button[data-action="add"]');
            if (addBtn) {
              addBtn.textContent = "Added";
              addBtn.classList.add("mini-btn-on");
              addBtn.disabled = true;
            }
          }

          await Dash.data.upsertShoppingListStatus(supabase, {
            userId,
            weekCode,
            storeId: slug,
            itemName,
            status: "bought",
          });
        }
      });
    },
  };
})();
