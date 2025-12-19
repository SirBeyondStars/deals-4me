// site/compare.js

(async function initCompare() {
  if (window.requireAuth) {
    await window.requireAuth();
  }
  if (window.renderToolbar) {
    window.renderToolbar("compare");
  }

  const form = document.getElementById("compare-form");
  const queryInput = document.getElementById("compare-query");
  const alertBox = document.getElementById("compare-alert");
  const body = document.getElementById("compare-body");

  function showAlert(msg) {
    alertBox.textContent = msg;
    alertBox.style.display = "block";
  }
  function hideAlert() {
    alertBox.style.display = "none";
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    hideAlert();
    const q = queryInput.value.trim();
    if (!q) return;

    // TODO: Replace with Supabase search over flyer items
    const fakeResults = [
      {
        store: "Stop & Shop",
        item: `${q} (Stop & Shop)`,
        price: 2.49,
        unit: "12 oz"
      },
      {
        store: "Market Basket",
        item: `${q} (Market Basket)`,
        price: 2.19,
        unit: "12 oz"
      },
      {
        store: "Aldi",
        item: `${q} (Aldi)`,
        price: 1.89,
        unit: "12 oz"
      }
    ];

    if (!fakeResults.length) {
      showAlert("No results found for that item this week.");
      body.innerHTML = "";
      return;
    }

    const bestPrice = Math.min(...fakeResults.map((r) => r.price));
    showAlert(`Best price this week: ${window.formatCurrency(bestPrice)}.`);

    body.innerHTML = fakeResults
      .map(
        (r) => `
        <tr>
          <td>${r.store}</td>
          <td>${r.item}</td>
          <td>${window.formatCurrency(r.price)}</td>
          <td>${r.unit}</td>
        </tr>
      `
      )
      .join("");
  });
})();
