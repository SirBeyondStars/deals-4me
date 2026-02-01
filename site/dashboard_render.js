// site/dashboard_render.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});
  const U = () => Dash.util;

  Dash.render = {
    dealLine({ item, slug, weekCode, listActiveSet, listBoughtSet }) {
      const name = item.item_name || "(Unnamed item)";
      const sale = item.sale_price != null ? `$${item.sale_price}` : "";
      const reg = item.regular_price != null ? `$${item.regular_price}` : "";
      const key = U().listKey(slug, name);

      const isBought = !!(listBoughtSet && listBoughtSet.has(key));
      const isActive = !!((listActiveSet && listActiveSet.has(key)) || isBought);

      const addLabel = isActive ? "Added" : "Add";
      const boughtLabel = isBought ? "Bought ✓" : "Bought";

      const addClass = isActive ? "mini-btn mini-btn-on" : "mini-btn";
      const boughtClass = isBought ? "mini-btn mini-btn-on" : "mini-btn";

      return `
        <li class="mini-deal-row">
          <div class="mini-deal-text">
            <span class="mini-deal-name">${U().escapeHTML(name)}</span>
            <span class="mini-deal-prices">
              ${sale ? `${U().escapeHTML(sale)}` : ""}${sale && reg ? " • " : ""}${reg ? `Reg ${U().escapeHTML(reg)}` : ""}
            </span>
          </div>
          <div class="mini-deal-actions">
            <button class="${addClass}" data-action="add" data-slug="${U().escapeHTML(slug)}" data-week="${U().escapeHTML(weekCode)}" data-item="${U().escapeHTML(name)}" ${isActive ? "disabled" : ""}>${addLabel}</button>
            <button class="${boughtClass}" data-action="bought" data-slug="${U().escapeHTML(slug)}" data-week="${U().escapeHTML(weekCode)}" data-item="${U().escapeHTML(name)}" ${isBought ? "disabled" : ""}>${boughtLabel}</button>
          </div>
        </li>
      `;
    },

    storeCards({
      elements,
      savedStoreIds,
      allFlyerItems,
      dealsByStore,
      weekCode,
      weekLabel, // passed from dashboard.js
      weekMetaByStore,
      listActiveSet,
      listBoughtSet,
    }) {
      const container = elements.storeContainer;
      if (!container) return;

      container.innerHTML = "";

      if (!savedStoreIds || savedStoreIds.size === 0) {
        container.innerHTML =
          '<p class="muted">You haven’t chosen any stores yet. Go to the Flyers page to pick up to 5 stores you shop at regularly.</p>';
        return;
      }

      // ✅ FIX: group by STORE (not product brand)
      // dashboard_data.js now normalizes each row to include `store_slug`
      const itemsByStore = new Map();
      for (const item of allFlyerItems || []) {
        const storeSlug = (item.store_slug || "").toString().trim() || "unknown";
        if (!itemsByStore.has(storeSlug)) itemsByStore.set(storeSlug, []);
        itemsByStore.get(storeSlug).push(item);
      }

      // Best-effort global label if caller forgot to pass weekLabel
      const fallbackGlobalLabel =
        weekLabel ||
        (U()?.weekCodeToDateRangeLabel ? U().weekCodeToDateRangeLabel(weekCode) : "") ||
        weekCode;

      for (const slug of savedStoreIds) {
        const storeName = U().prettyStoreName(slug);

        // ✅ FIX: pull items directly by store slug
        const storeItems = itemsByStore.get(slug) || [];
        const onSaleItems = storeItems.filter(U().isItemOnSale);

        const totalOnSale = onSaleItems.length;
        const matchedCount = dealsByStore.get(slug) || 0;

        const topStoreDeals = onSaleItems
          .filter((it) => {
            const sale = Number(it.sale_price);
            const reg = Number(it.regular_price);
            return Number.isFinite(sale) && Number.isFinite(reg) && reg > sale;
          })
          .sort(
            (a, b) =>
              Number(b.regular_price) - Number(b.sale_price) -
              (Number(a.regular_price) - Number(a.sale_price))
          )
          .slice(0, 6);

        // ✅ Per-store override if present
        const meta = weekMetaByStore ? weekMetaByStore.get(slug) : null;
        const perStoreRange =
          meta && (meta.weekStart || meta.weekEnd)
            ? U().formatDateRange(meta.weekStart, meta.weekEnd)
            : null;

        const dateDisplay = perStoreRange || fallbackGlobalLabel || weekCode;

        const card = document.createElement("div");
        card.className = "store-card dash-store-card";
        card.setAttribute("data-store-slug", slug);

        card.innerHTML = `
          <div class="store-card-flip">
            <div class="store-card-inner">

              <div class="store-card-face store-card-front">
                <div class="store-card-header">
                  <h3 class="store-name">${U().escapeHTML(storeName)}</h3>
                  <span class="store-week">${U().escapeHTML(dateDisplay)}</span>
                </div>

                <div class="store-card-body">
                  <p><strong>Items on sale this week:</strong> ${totalOnSale}</p>
                  <p><strong>Your items on sale here:</strong> ${matchedCount}</p>
                </div>
              </div>

              <div class="store-card-face store-card-back">
                <div class="store-card-body">
                  <div class="back-row">
                    <div class="back-row-title">Top deals at this store</div>
                    ${
                      topStoreDeals.length
                        ? `<ul class="mini-deal-list">${topStoreDeals
                            .map((it) =>
                              Dash.render.dealLine({
                                item: it,
                                slug,
                                weekCode,
                                listActiveSet,
                                listBoughtSet,
                              })
                            )
                            .join("")}</ul>`
                        : `<div class="muted">No sale items detected for this store this week.</div>`
                    }
                  </div>

                  <div class="back-row">
                    <div class="back-row-title">Your saved deals on sale here</div>
                    <div class="muted">See “My Saved Deals This Week” below for the full list.</div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        `;

        container.appendChild(card);
      }
    },

    savedDealsList({ elements, savedDeals, savedItems }) {
      const listEl = elements.savedDealsList;
      const errorEl = elements.savedDealsError;
      if (!listEl || !errorEl) return;

      listEl.innerHTML = "";
      errorEl.style.display = "none";
      errorEl.textContent = "";

      if (!savedItems || savedItems.length === 0) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent =
          "You haven’t added any items to track yet. Use the Flyers page to add items to your saved list.";
        listEl.appendChild(li);
        return;
      }

      if (!savedDeals || savedDeals.length === 0) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent =
          "None of your saved items are on sale this week at your saved stores (yet). Check back when new flyers are ingested.";
        listEl.appendChild(li);
        return;
      }

      savedDeals.sort((a, b) => {
        if (a.storeName < b.storeName) return -1;
        if (a.storeName > b.storeName) return 1;
        const aName = (a.item.item_name || "").toLowerCase();
        const bName = (b.item.item_name || "").toLowerCase();
        return aName.localeCompare(bName);
      });

      for (const deal of savedDeals) {
        const { storeName, item, matchedNames } = deal;
        const li = document.createElement("li");
        li.className = "saved-deal-row";

        const priceBits = [];
        if (item.sale_price != null) priceBits.push(`Sale: $${item.sale_price}`);
        if (item.regular_price != null) priceBits.push(`Reg: $${item.regular_price}`);

        const matchesSummary =
          matchedNames && matchedNames.length > 0 ? `Matches: ${matchedNames.join(", ")}` : "";

        li.innerHTML = `
          <div class="saved-deal-main">
            <div class="saved-deal-title">
              <strong>${U().escapeHTML(storeName)}</strong> – ${U().escapeHTML(item.item_name || "(Unnamed item)")}
            </div>
            <div class="saved-deal-meta">
              ${
                item.size
                  ? `<span class="deal-size">${U().escapeHTML(item.size)}${item.unit ? " " + U().escapeHTML(item.unit) : ""}</span>`
                  : ""
              }
              ${matchesSummary ? `<span class="deal-matches">${U().escapeHTML(matchesSummary)}</span>` : ""}
            </div>
          </div>
          <div class="saved-deal-prices">
            ${U().escapeHTML(priceBits.join(" • "))}
            ${U().isItemOnSale(item) ? '<span class="badge badge-sale">On Sale</span>' : ""}
          </div>
        `;

        listEl.appendChild(li);
      }
    },
  };
})();
