// site/helpers.js

function formatCurrency(amount) {
  if (amount == null || isNaN(amount)) return "-";
  return `$${amount.toFixed(2)}`;
}

window.formatCurrency = formatCurrency;
