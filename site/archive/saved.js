// site/saved.js

(async function initSaved() {
  if (window.requireAuth) {
    await window.requireAuth();
  }
  if (window.renderToolbar) {
    window.renderToolbar("saved");
  }

  const alertBox = document.getElementById("saved-alert");
  const body = document.getElementById("saved-body");

  // TODO: Replace with Supabase query for real saved_items
  const fakeSaved = [
    {
      id: 1,
      name: "Cheerios 12 oz",
      bestPrice: 1.89,
      store: "Stop & Shop",
      lastSeen: "2025-11-24"
    },
    {
      id: 2,
      name: "Chicken breast, lb",
      bestPrice: 2.39,
      store: "Market Basket",
      lastSeen: "2025-11-23"
    }
  ];

  if (!fakeSaved.length) {
    alertBox.textContent =
      "You don’t have any saved items yet. Tap “Save” from flyers to track your favorites.";
    return;
  }

  alertBox.style.display = "none";

  body.innerHTML = fakeSaved
    .map(
      (item) => `
      <tr>
        <td>${item.name}</td>
        <td>${window.formatCurrency(item.bestPrice)}</td>
        <td>${item.store}</td>
        <td>${item.lastSeen}</td>
        <td>
          <button type="button" class="secondary" data-remove-id="${item.id}">
            Remove
          </button>
        </td>
      </tr>
    `
    )
    .join("");

  body.querySelectorAll("button[data-remove-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-remove-id");
      // TODO: delete from Supabase saved_items
      alert(`(Stub) Removed saved item #${id}.`);
    });
  });
})();
