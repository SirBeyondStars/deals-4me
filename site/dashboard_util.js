// dashboard_util.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});

  Dash.util = {
    getSupabase() {
      const candidate = window.supabaseClient || window.supabase;
      if (!candidate || typeof candidate.from !== "function") {
        console.error("[dashboard] Supabase client not found. Make sure supabaseClient.js loads before dashboard.js");
        return null;
      }
      return candidate;
    },

    setStatus(elements, message, isError = false) {
      if (!elements || !elements.statusBar) return;
      elements.statusBar.textContent = message;
      elements.statusBar.classList.toggle("error", !!isError);
    },

    escapeHTML(str) {
      return String(str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    },

    prettyStoreName(slug) {
      if (!slug) return "Unknown store";
      const map = Dash.STORE_NAME_BY_SLUG || {};
      if (map[slug]) return map[slug];
      return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    },

    formatDateRange(isoStart, isoEnd) {
      if (!isoStart && !isoEnd) return null;

      const opts = { month: "short", day: "numeric" };
      let startStr = null;
      let endStr = null;

      if (isoStart) {
        const d = new Date(isoStart);
        if (!Number.isNaN(d.getTime())) startStr = d.toLocaleDateString(undefined, opts);
      }
      if (isoEnd) {
        const d = new Date(isoEnd);
        if (!Number.isNaN(d.getTime())) endStr = d.toLocaleDateString(undefined, opts);
      }

      if (startStr && endStr) return `${startStr} – ${endStr}`;
      return startStr || endStr;
    },

    isItemOnSale(item) {
      if (typeof item.is_on_sale === "boolean") return item.is_on_sale;

      const sale = item.sale_price;
      const regular = item.regular_price;

      if (sale != null && regular != null) {
        const s = Number(sale);
        const r = Number(regular);
        if (!Number.isNaN(s) && !Number.isNaN(r)) return s < r;
      }
      return false;
    },

    normalizeItemName(name) {
      return (name || "").trim().toLowerCase();
    },

    listKey(storeId, itemName) {
      return `${storeId}::${Dash.util.normalizeItemName(itemName)}`;
    },
  };
})();
