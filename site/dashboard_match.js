// site/dashboard_match.js
(() => {
  "use strict";

  const Dash = (window.D4M_DASH = window.D4M_DASH || {});
  const U = () => Dash.util;

  // -----------------------------
  // Text helpers
  // -----------------------------
  function norm(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function hasAny(haystackNorm, needles) {
    for (const n of needles) {
      if (!n) continue;
      if (haystackNorm.includes(n)) return true;
    }
    return false;
  }

  function uniq(arr) {
    return Array.from(new Set((arr || []).filter(Boolean)));
  }

  // -----------------------------
  // Store mapping (brand -> slug)
  // -----------------------------
  function buildSlugLookup() {
    // STORE_NAME_BY_SLUG = { wegmans: "Wegmans", ... }
    const lookup = {};
    const bySlug = Dash.STORE_NAME_BY_SLUG || {};
    for (const slug of Object.keys(bySlug)) {
      const name = bySlug[slug];
      if (name) lookup[norm(name)] = slug;
    }
    return lookup;
  }

  function inferStoreSlugFromItem(item, slugLookup) {
    // Your flyer items use "brand" (store name)
    const b = norm(item && item.brand);
    return slugLookup[b] || null;
  }

  // -----------------------------
  // Saved item parsing
  // Supports:
  //  - "Meat / Seafood: Beef"
  //  - "Meat/Seafood: Salmon"
  //  - "Beef" (fallback)
  // -----------------------------
  function parseSavedItem(savedItem) {
    const raw = String(savedItem?.item_name || "").trim();
    const rawNorm = norm(raw);

    // Try "Category: Refinement"
    const m = raw.match(/^(.+?)\s*:\s*(.+)$/);
    if (m) {
      const category = norm(m[1]);
      const refinement = norm(m[2]);
      return { raw, rawNorm, category, refinement };
    }

    return { raw, rawNorm, category: "", refinement: rawNorm };
  }

  // -----------------------------
  // Protein rules
  // -----------------------------
  const MEAT_CATEGORY_KEYS = [
    "meat seafood",
    "meat / seafood",
    "meat  seafood",
    "meat and seafood",
  ];

  // Broad meats: match ALL cuts
  const BROAD_MEATS = {
    beef: [
      "beef",
      "steak",
      "ribeye",
      "sirloin",
      "tenderloin",
      "filet",
      "flank",
      "skirt",
      "brisket",
      "chuck",
      "round",
      "roast",
      "short rib",
      "ribs",
      "ground beef",
      "burger",
      "hamburger",
      "meatballs",
      "stew beef",
      "corned beef",
    ],
    chicken: [
      "chicken",
      "breast",
      "thigh",
      "wing",
      "wings",
      "drum",
      "drums",
      "drumstick",
      "tender",
      "tenders",
      "rotisserie",
      "whole chicken",
    ],
    pork: [
      "pork",
      "bacon",
      "ham",
      "sausage",
      "chop",
      "chops",
      "loin",
      "tenderloin",
      "shoulder",
      "butt",
      "ribs",
      "spare ribs",
      "st louis",
      "ground pork",
    ],
    lamb: [
      "lamb",
      "rack of lamb",
      "lamb chop",
      "lamb chops",
      "leg of lamb",
      "lamb shank",
      "ground lamb",
    ],
    veal: [
      "veal",
      "veal chop",
      "veal chops",
      "veal cutlet",
      "veal cutlets",
      "ground veal",
    ],
    goat: [
      "goat",
      "cabrito",
      "chevon",
    ],
  };

  // Seafood MUST be specific:
  // If user saves "Salmon", match salmon words (and common variants).
  // If user saves generic "Seafood" or "Fish", we do NOT match (your request).
  const SEAFOOD_SYNONYMS = {
    salmon: ["salmon", "atlantic salmon", "sockeye", "coho", "king salmon", "chinook"],
    cod: ["cod", "scrod"],
    haddock: ["haddock"],
    tilapia: ["tilapia"],
    tuna: ["tuna", "ahi"],
    shrimp: ["shrimp", "prawn", "prawns"],
    lobster: ["lobster", "lobster tail", "lobster tails"],
    crab: ["crab", "crab legs", "snow crab", "king crab"],
    scallops: ["scallop", "scallops"],
    mussels: ["mussel", "mussels"],
    clams: ["clam", "clams"],
    oysters: ["oyster", "oysters"],
    swordfish: ["swordfish"],
    halibut: ["halibut"],
    trout: ["trout"],
    mahi: ["mahi", "mahi mahi"],
  };

  function isMeatSeafoodCategory(categoryNorm) {
    if (!categoryNorm) return false;
    const c = categoryNorm;
    return MEAT_CATEGORY_KEYS.some((k) => c.includes(norm(k)));
  }

  function matchMeatSeafood(savedParsed, flyerTextNorm) {
    // savedParsed.refinement is required
    const r = savedParsed.refinement;

    // Broad meats
    if (BROAD_MEATS[r]) {
      return hasAny(flyerTextNorm, BROAD_MEATS[r]);
    }

    // Seafood rules (specific)
    if (r === "seafood" || r === "fish" || r === "sea food") {
      // You said: keep seafood specific
      return false;
    }

    // If refinement matches a known seafood group, use synonyms
    if (SEAFOOD_SYNONYMS[r]) {
      return hasAny(flyerTextNorm, SEAFOOD_SYNONYMS[r]);
    }

    // Otherwise: allow direct keyword match for user-entered seafood terms
    // Example: "lobster rolls", "stuffed clams", "calamari", etc.
    // (Still specific because user typed it.)
    return r && flyerTextNorm.includes(r);
  }

  // -----------------------------
  // Public API expected by dashboard.js
  // -----------------------------
  Dash.match = Dash.match || {};

  /**
   * buildMatcher(savedItems)
   * returns: (flyerItem) => { matched: boolean, matchedNames: string[] }
   */
  Dash.match.buildMatcher = function buildMatcher(savedItems) {
    const parsed = (savedItems || []).map(parseSavedItem);

    // Build quick lists:
    // - protein items
    // - general items
    const proteinSaved = [];
    const generalSaved = [];

    for (const p of parsed) {
      if (isMeatSeafoodCategory(p.category)) proteinSaved.push(p);
      else generalSaved.push(p);
    }

    // General matcher fallback:
    // - very simple contains() check on normalized text
    // - if you have a richer matcher elsewhere, we keep it compatible
    function matchGeneral(savedParsed, flyerTextNorm) {
      // minimal guard
      const q = savedParsed.refinement || savedParsed.rawNorm;
      if (!q) return false;

      // Favor whole-word-ish behavior for short tokens
      if (q.length <= 3) {
        const re = new RegExp(`\\b${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
        return re.test(flyerTextNorm);
      }
      return flyerTextNorm.includes(q);
    }

    return function matchFlyerItem(flyerItem) {
      const text = norm(
        [
          flyerItem?.item_name,
          flyerItem?.size,
          flyerItem?.unit,
          flyerItem?.notes,
        ].filter(Boolean).join(" ")
      );

      const matchedNames = [];

      // 1) Meat/Seafood protein rules
      for (const s of proteinSaved) {
        if (matchMeatSeafood(s, text)) matchedNames.push(s.raw);
      }

      // 2) General saved items
      for (const s of generalSaved) {
        if (matchGeneral(s, text)) matchedNames.push(s.raw);
      }

      return {
        matched: matchedNames.length > 0,
        matchedNames: uniq(matchedNames),
      };
    };
  };

  /**
   * findSavedDeals({ allFlyerItems, savedItems, matchFn })
   * returns: { savedDeals: Array, dealsByStore: Map(storeSlug => count) }
   */
  Dash.match.findSavedDeals = function findSavedDeals({ allFlyerItems, savedItems, matchFn }) {
    const slugLookup = buildSlugLookup();
    const dealsByStore = new Map();
    const savedDeals = [];

    for (const item of allFlyerItems || []) {
      if (!item) continue;

      const { matched, matchedNames } = matchFn(item);
      if (!matched) continue;

      const storeSlug = inferStoreSlugFromItem(item, slugLookup) || "unknown";
      const storeName = (Dash.STORE_NAME_BY_SLUG || {})[storeSlug] || item.brand || "Unknown";

      dealsByStore.set(storeSlug, (dealsByStore.get(storeSlug) || 0) + 1);

      savedDeals.push({
        storeSlug,
        storeName,
        item,
        matchedNames,
      });
    }

    return { savedDeals, dealsByStore };
  };
})();
