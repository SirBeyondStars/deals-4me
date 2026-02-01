// dashboard_config.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});

  Dash.CFG = {
    ITEMS_TABLE: "flyer_items",
    TABLE_SAVED_STORES: "user_saved_stores",
    TABLE_SAVED_ITEMS: "user_saved_items",
    TABLE_SHOPPING_LIST: "user_shopping_list", // optional; safe if missing
    FALLBACK_WEEK: "week51",

    AVAILABLE_STORES: [
      { id: "aldi",                     name: "Aldi" },
      { id: "big_y",                    name: "Big Y" },
      { id: "hannaford",                name: "Hannaford" },
      { id: "market_basket",            name: "Market Basket" },
      { id: "price_chopper_market_32",  name: "Price Chopper / Market 32" },
      { id: "pricerite",                name: "Price Rite" },
      { id: "roche_bros",               name: "Roche Bros." },
      { id: "shaws",                    name: "Shaw's" },
      { id: "stop_and_shop_ct",         name: "Stop & Shop (CT)" },
      { id: "stop_and_shop_mari",       name: "Stop & Shop (MA/RI)" },
      { id: "trucchis",                 name: "Trucchi's" },
      { id: "wegmans",                  name: "Wegmans" },
      { id: "whole_foods",              name: "Whole Foods" },
    ],
  };

  // Lookup maps (computed once)
  const STORE_NAME_BY_SLUG = {};
  const STORE_SLUG_BY_NAME = {};
  for (const s of Dash.CFG.AVAILABLE_STORES) {
    STORE_NAME_BY_SLUG[s.id] = s.name;
    STORE_SLUG_BY_NAME[s.name] = s.id;
  }

  Dash.STORE_NAME_BY_SLUG = STORE_NAME_BY_SLUG;
  Dash.STORE_SLUG_BY_NAME = STORE_SLUG_BY_NAME;
})();
