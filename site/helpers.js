// helpers.js
// Deals-4Me shared helper utilities
// Goal: centralize "saved item" interpretation + matching rules
// So dashboard + flyers can reuse the SAME logic.
//
// Usage (later, in dashboard/flyers):
//   const match = D4M.buildSavedItemMatcher(savedItems);
//   const matched = match(flyerItem.item_name);  // returns array of saved item names that match

(() => {
  "use strict";

  // Create a single global namespace so we don't pollute window with many functions.
  const D4M = (window.D4M = window.D4M || {});

  // -----------------------------
  // Text normalization utilities
  // -----------------------------

  function safeStr(v) {
    return String(v == null ? "" : v);
  }

  // Keep it simple and predictable:
  // - lowercases
  // - removes most punctuation
  // - collapses whitespace
  // - trims
  function normalizeText(input) {
    const s = safeStr(input).toLowerCase();
    return s
      .replace(/['"]/g, "")               // remove quotes
      .replace(/[^a-z0-9\s]/g, " ")       // punctuation -> spaces
      .replace(/\s+/g, " ")               // collapse spaces
      .trim();
  }

  // Basic singularization (very light)
  // eggs -> egg, apples -> apple, etc.
  function normalizeToken(token) {
    const t = normalizeText(token);
    if (!t) return "";
    // Only strip trailing 's' when it looks like a simple plural
    if (t.length > 3 && t.endsWith("s") && !t.endsWith("ss")) return t.slice(0, -1);
    return t;
  }

  function tokenize(input) {
    const s = normalizeText(input);
    if (!s) return [];
    return s.split(" ").map(normalizeToken).filter(Boolean);
  }

  function isFlyerPageRow(name) {
    const n = normalizeText(name);
    return n.startsWith("flyer page");
  }

  // -----------------------------
  // Saved-item rule model
  // -----------------------------

  // Block super broad terms that will explode the UI (and feel useless).
  // Users must narrow these down.
  const BLOCKED_BROAD_TERMS = new Set([
    "fruit",
    "fruits",
    "vegetable",
    "vegetables",
    "produce",
    "meat",
    "meats",
    "seafood",
    "fish",       // too broad as a single word
    "snack",
    "snacks",
    "drink",
    "drinks",
    "beverage",
    "beverages",
    "food",
    "foods",
  ].map(normalizeToken));

  // Allowed category keywords.
  // These are intentionally "safe broad" categories where users commonly mean a department.
  //
  // NOTE: Start small. Add as OCR quality improves and you see real-world usage.
  const ALLOWED_CATEGORIES = {
    // Requested: allow "beef" even though it's broad.
    beef: [
      "beef",
      "steak",
      "sirloin",
      "chuck",
      "brisket",
      "roast",
      "ground beef",
      "ribeye",
      "t bone",
      "tbone",
      "strip steak",
      "top loin",
      "tenderloin",
      "filet",
    ],

    chicken: [
      "chicken",
      "breast",
      "thigh",
      "drumstick",
      "wing",
      "rotisserie",
      "ground chicken",
    ],

    pork: [
      "pork",
      "bacon",
      "ham",
      "sausage",
      "pork chop",
      "chop",
      "loin",
      "tenderloin",
    ],

    turkey: [
      "turkey",
      "ground turkey",
      "turkey breast",
    ],

    eggs: [
      "egg",
      "eggs",
      "dozen eggs",
      "12 ct",
      "12ct",
    ],

    // Add a few “common intent” categories that are still reasonably scoped
    dairy: [
      "milk",
      "cheese",
      "yogurt",
      "butter",
      "cream",
      "half and half",
    ],

    bread: [
      "bread",
      "bagel",
      "roll",
      "bun",
      "tortilla",
    ],
  };

  // Some phrases are “category-like” but we may want to keep them as normal phrases.
  // We’ll treat anything that exactly matches a category key as category mode.
  const CATEGORY_KEYS = new Set(Object.keys(ALLOWED_CATEGORIES).map(normalizeToken));

  // -----------------------------
  // Matching implementation
  // -----------------------------

  // Compile categories to token sets for faster matching.
  function compileCategory(categoryKey) {
    const raw = ALLOWED_CATEGORIES[categoryKey] || [];
    const phrases = raw
      .map((p) => normalizeText(p))
      .filter(Boolean);

    // Split into:
    // - multiword phrases (matched by substring)
    // - single tokens (matched by token presence)
    const multiword = [];
    const singles = new Set();

    for (const p of phrases) {
      if (p.includes(" ")) multiword.push(p);
      else singles.add(normalizeToken(p));
    }

    return { multiword, singles };
  }

  const COMPILED_CATEGORIES = {};
  for (const key of Object.keys(ALLOWED_CATEGORIES)) {
    const normKey = normalizeToken(key);
    COMPILED_CATEGORIES[normKey] = compileCategory(key);
  }

  function classifySavedItem(savedItemName) {
    const raw = safeStr(savedItemName);
    const norm = normalizeText(raw);

    if (!norm) return { kind: "empty", raw, norm };

    // Blocked broad terms (fruit, vegetables, etc.)
    if (BLOCKED_BROAD_TERMS.has(normalizeToken(norm))) {
      return { kind: "blocked", raw, norm };
    }

    // Exact category keyword (beef, chicken, pork, eggs...)
    const asKey = normalizeToken(norm);
    if (CATEGORY_KEYS.has(asKey)) {
      return { kind: "category", raw, norm, categoryKey: asKey };
    }

    // Otherwise treat as an "exact-ish phrase"
    return { kind: "phrase", raw, norm };
  }

  // Phrase match:
  // - multiword: substring match on normalized flyer name
  // - single word: token presence match
  function phraseMatchesFlyer(phraseNorm, flyerNorm, flyerTokensSet) {
    if (!phraseNorm || !flyerNorm) return false;

    if (phraseNorm.includes(" ")) {
      // Substring is OK here because phrase is specific (peanut butter, rice pilaf)
      return flyerNorm.includes(phraseNorm);
    }

    // Single token phrase like "hummus" — require token presence
    const token = normalizeToken(phraseNorm);
    return !!token && flyerTokensSet.has(token);
  }

  function categoryMatchesFlyer(categoryKey, flyerNorm, flyerTokensSet) {
    const compiled = COMPILED_CATEGORIES[categoryKey];
    if (!compiled) return false;

    // Multiword phrases first
    for (const p of compiled.multiword) {
      if (flyerNorm.includes(p)) return true;
    }

    // Single token hits
    for (const t of compiled.singles) {
      if (flyerTokensSet.has(t)) return true;
    }

    return false;
  }

  // Public: match a list of saved items against one flyer item name
  // Returns: array of saved item display names that matched (skips blocked/empty)
  function matchSavedItemsToFlyerItem(savedItems, flyerItemName) {
    const flyerNorm = normalizeText(flyerItemName);

    // Never match flyer-page rows
    if (!flyerNorm || isFlyerPageRow(flyerNorm)) return [];

    const flyerTokens = tokenize(flyerNorm);
    const flyerTokensSet = new Set(flyerTokens);

    const matches = [];

    for (const si of savedItems || []) {
      // Accept either { item_name: "..." } rows or raw strings
      const savedName = typeof si === "string" ? si : (si?.item_name || "");
      const classified = classifySavedItem(savedName);

      if (classified.kind === "empty") continue;
      if (classified.kind === "blocked") continue;

      if (classified.kind === "category") {
        if (categoryMatchesFlyer(classified.categoryKey, flyerNorm, flyerTokensSet)) {
          matches.push(savedName);
        }
        continue;
      }

      // phrase
      if (phraseMatchesFlyer(classified.norm, flyerNorm, flyerTokensSet)) {
        matches.push(savedName);
      }
    }

    return matches;
  }

  // Public: build a function that matches quickly (pre-classifies saved items once)
  function buildSavedItemMatcher(savedItems) {
    const classified = (savedItems || []).map((si) => {
      const savedName = typeof si === "string" ? si : (si?.item_name || "");
      const c = classifySavedItem(savedName);
      c.savedName = savedName;
      return c;
    });

    return (flyerItemName) => {
      const flyerNorm = normalizeText(flyerItemName);
      if (!flyerNorm || isFlyerPageRow(flyerNorm)) return [];

      const flyerTokensSet = new Set(tokenize(flyerNorm));
      const matches = [];

      for (const c of classified) {
        if (c.kind === "empty" || c.kind === "blocked") continue;

        if (c.kind === "category") {
          if (categoryMatchesFlyer(c.categoryKey, flyerNorm, flyerTokensSet)) matches.push(c.savedName);
          continue;
        }

        if (phraseMatchesFlyer(c.norm, flyerNorm, flyerTokensSet)) matches.push(c.savedName);
      }

      return matches;
    };
  }

  // Public: expose pieces you may want later
  D4M.normalizeText = normalizeText;
  D4M.tokenize = tokenize;
  D4M.isFlyerPageRow = isFlyerPageRow;

  D4M.classifySavedItem = classifySavedItem;
  D4M.matchSavedItemsToFlyerItem = matchSavedItemsToFlyerItem;
  D4M.buildSavedItemMatcher = buildSavedItemMatcher;

  // Optional: expose config so you can tweak later without hunting code
  D4M.SAVED_ITEM_RULES = {
    BLOCKED_BROAD_TERMS: Array.from(BLOCKED_BROAD_TERMS),
    ALLOWED_CATEGORIES: JSON.parse(JSON.stringify(ALLOWED_CATEGORIES)),
  };

  console.log("[helpers] helpers.js loaded (saved-item rules ready)");
})();
