// site/dashboard.js

(async function initDashboard() {
  if (window.requireAuth) {
    await window.requireAuth();
  }

  if (window.renderToolbar) {
    window.renderToolbar("dashboard");
  }

  const summaryEl = document.getElementById("dashboard-summary");
  const tableBody = document.querySelector("#dashboard-store-table tbody");

  const fakeStoreData = [
    { name: "Stop & Shop", items: 32, savings: 18.5 },
    { name: "Market Basket", items: 27, savings: 15.25 },
    { name: "Aldi", items: 19, savings: 12.4 }
  ];

  const activeName = window.getActiveProfileName
    ? window.getActiveProfileName()
    : "Guest";

  if (!fakeStoreData.length) {
    summaryEl.textContent = `Hi ${activeName}, once flyers are in the system we’ll show your best stores here.`;
  } else {
    summaryEl.textContent = `Hi ${activeName}, this week you’ll find the most total deals at ${fakeStoreData[0].name}, then ${fakeStoreData[1].name}, and ${fakeStoreData[2].name}.`;
  }

  tableBody.innerHTML = fakeStoreData
    .map(
      (s) => `
      <tr>
        <td>${s.name}</td>
        <td>${s.items}</td>
        <td>${window.formatCurrency ? window.formatCurrency(s.savings) : `$${s.savings}`}</td>
      </tr>
    `
    )
    .join("");
})();
