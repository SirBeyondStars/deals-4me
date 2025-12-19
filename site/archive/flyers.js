// site/flyers.js

(async function initFlyers() {
  if (window.requireAuth) {
    await window.requireAuth();
  }
  if (window.renderToolbar) {
    window.renderToolbar("flyers");
  }

  const storeListEl = document.getElementById("flyers-store-list");
  const dealsContainer = document.getElementById("flyers-deals-container");

  const fakeStores = [
    { id: "stop_and_shop_mari", name: "Stop & Shop (MA/RI)", items: 32 },
    { id: "stop_and_shop_ct", name: "Stop & Shop (CT)", items: 25 },
    { id: "aldi_ne", name: "Aldi", items: 19 },
    { id: "market_basket", name: "Market Basket", items: 28 }
  ];

  function renderStoreButtons() {
    storeListEl.innerHTML = fakeStores
      .map(
        (s) => `
      <button
        type="button"
        class="secondary"
        data-store-id="${s.id}"
        style="width:100%;text-align:left;margin-bottom:0.4rem;"
      >
        ${s.name}
        <span class="badge" style="margin-left:0.4rem;">
          ${s.items} items
        </span>
      </button>
    `
      )
      .join("");

    storeListEl.querySelectorAll("button[data-store-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const storeId = btn.getAttribute("data-store-id");
        const store = fakeStores.find((s) => s.id === storeId);
        if (store) loadDealsForStore(store);
      });
    });
  }

  function loadDealsForStore(store) {
    dealsContainer.classList.remove("alert");
    dealsContainer.innerHTML = `
      <h3 style="margin-bottom:0.5rem;">${store.name}</h3>
      <p class="helper-text">
        Sample data. This will be wired to your Supabase flyer tables.
      </p>
      <table class="table" style="margin-top:0.5rem;">
        <thead>
          <tr>
            <th>Item</th>
            <th>Sale price</th>
            <th>Reg.</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="flyers-deals-body"></tbody>
      </table>
    `;

    const body = document.getElementById("flyers-deals-body");
    const fakeDeals = [
      { name: "Cheerios 12 oz", sale: 1.99, reg: 3.99 },
      { name: "Chicken breast, lb", sale: 2.49, reg: 4.99 },
      { name: "Gala apples, 3 lb bag", sale: 3.49, reg: 5.49 }
    ];

    body.innerHTML = fakeDeals
      .map(
        (d) => `
        <tr>
          <td>${d.name}</td>
          <td>${window.formatCurrency(d.sale)}</td>
          <td>${window.formatCurrency(d.reg)}</td>
          <td>
            <button type="button" class="secondary" data-save-item="${d.name}">
              Save
            </button>
          </td>
        </tr>
      `
      )
      .join("");

    body.querySelectorAll("button[data-save-item]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const itemName = btn.getAttribute("data-save-item");
        // TODO: write to Supabase saved_items
        alert(`(Stub) Saved "${itemName}" for later.`);
      });
    });
  }

  renderStoreButtons();
})();
