// site/saved.js

const SAVED_ITEM_LIMITS = {
  basic: 12,
  gold: 40,
  platinum: null, // unlimited
};

// ----------------------
// Saved-item category rules (locked v1)
// ----------------------
const SAVED_RULES = {
  tier1: [
    "Beef","Chicken","Pork","Turkey","Fish","Seafood","Bacon","Milk","Eggs","Butter",
    "Yogurt","Cottage cheese","Apples","Grapes","Bananas","Oranges","Potatoes","Onions",
    "Flour","Sugar","Rice","Pasta","Cooking oil","Olive oil","Vinegar","Pickles","Olives",
    "Hummus","Spices"
  ],
  tier2: [
    "Cereal","Chips","Crackers","Candy","Ice cream","Coffee","Soda","Cheese","Soup","Deli",
    "Frozen foods","Bakery","Snacks","Pasta sauce","Salad kits"
  ],
  notAllowed: ["Produce", "Grocery", "Groceries", "Food", "Frozen", "Drinks", "Beverages"],
  refineHints: {
    cheese: ["shredded","sliced","block","crumbles","string","deli sliced"],
    cereal: ["cheerios","granola","raisin bran","frosted flakes"],
    chips: ["tortilla","potato","kettle","doritos","lays"],
    soup: ["tomato","chicken noodle","clam chowder"],
    deli: ["ham","turkey","salami","roast beef"],
    "frozen foods": ["pizza","meals","vegetables","ice cream"],
    bakery: ["bread","bagels","muffins","cookies"],
    snacks: ["nuts","trail mix","protein bars","popcorn"],
    "pasta sauce": ["marinara","alfredo","vodka","pesto"],
    "salad kits": ["caesar","greek","southwest"],
  },
};

// ---------- Safe defaults + Supabase client ----------
const sb = window.sb || window.supabaseClient || window.supabase;
if (!sb) console.warn("[saved] Supabase client not found on window (sb/supabaseClient/supabase).");

function setError(msg) {
  console.warn("[saved] " + msg);
  const el = document.getElementById("saved-status") || document.getElementById("saved-add-error");
  if (el) {
    el.style.display = "block";
    el.textContent = msg;
  }
}
function clearError() {
  const el = document.getElementById("saved-status") || document.getElementById("saved-add-error");
  if (el) {
    el.style.display = "none";
    el.textContent = "";
  }
}

function norm(s) {
  return String(s || "").trim().replace(/\s+/g, " ");
}
function normKey(s) {
  return norm(s).toLowerCase();
}
function isTier2(category) {
  const c = normKey(category);
  return SAVED_RULES.tier2.map(normKey).includes(c);
}
function isNotAllowed(category) {
  const c = normKey(category);
  return SAVED_RULES.notAllowed.map(normKey).includes(c);
}

function formatDisplayName(itemKey) {
  const s = norm(itemKey);
  if (!s) return "(unnamed item)";
  return s
    .split(" ")
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

// Global count for plan-limit checks (set after loading rows)
let currentCount = null;

// ----------------------
// Helpers
// ----------------------
async function getUserPlanTier(userId) {
  // Quiet + safe: if anything goes wrong, default to "basic" without scary console noise.
  try {
    const { data, error } = await sb
      .from("profiles")
      .select("plan_tier")
      .eq("id", userId)
      .maybeSingle();

    // Any error (RLS, network, missing column) => basic
    if (error) return "basic";

    const tier = String(data?.plan_tier || "").toLowerCase();
    if (tier === "gold" || tier === "platinum" || tier === "basic") return tier;

    return "basic";
  } catch {
    return "basic";
  }
}


function showPlanInfo(planTier, planLimit, count) {
  const infoEl = document.getElementById("saved-plan-info");
  if (!infoEl) return;

  const label =
    planTier === "basic" ? "Basic" :
    planTier === "gold" ? "Gold" :
    planTier === "platinum" ? "Platinum" : planTier;

  let msg = "";
  if (planLimit == null) {
    msg = `You are on the ${label} plan. You can save an unlimited number of favorite items.`;
  } else {
    const remaining = Math.max(planLimit - count, 0);
    msg = `You are on the ${label} plan. You can save up to ${planLimit} items. You currently have ${count} saved item${count === 1 ? "" : "s"}.`;
    msg += remaining > 0
      ? ` You can save ${remaining} more item${remaining === 1 ? "" : "s"}.`
      : ` You’ve reached your saved item limit. Remove an item or upgrade your plan to save more.`;
  }

  infoEl.textContent = msg;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ----------------------
// UI-only initializer for category dropdown + refinement UI
// (NO submit handler here — submit is handled in setupAddForm)
// ----------------------
function initCategoryUI() {
  const form = document.getElementById("saved-add-form");
  if (!form) return;

  const sel = document.getElementById("saved-category");
  const refine = document.getElementById("saved-refine");
  const refineSelect = document.getElementById("saved-refine-select");
  const refineLabel = document.getElementById("saved-refine-label");
  const catHelp = document.getElementById("saved-category-help");
  const refineHelp = document.getElementById("saved-refine-help");

  if (!sel) return;

  // Build dropdown once
  if (sel.options.length <= 1) {
    const allCats = [
      ...SAVED_RULES.tier1.map((c) => ({ name: c, tier: 1 })),
      ...SAVED_RULES.tier2.map((c) => ({ name: c, tier: 2 })),
    ].sort((a, b) => a.name.localeCompare(b.name));

    allCats.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.name;
      opt.textContent = c.name + (c.tier === 2 ? " (specific)" : "");
      sel.appendChild(opt);
    });
  }

  function titleCase(s) {
    return (s || "")
      .split(" ")
      .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
      .join(" ");
  }

  function setRefineMode({ tier2, categoryKey }) {
    if (refineSelect) {
      const options = (SAVED_RULES.refineHints[categoryKey] || []).slice(0, 10);
      const prev = refineSelect.value;

      refineSelect.innerHTML = '<option value="">Choose one…</option>';
      options.forEach((o) => {
        const opt = document.createElement("option");
        opt.value = o;
        opt.textContent = titleCase(o);
        refineSelect.appendChild(opt);
      });

      const otherOpt = document.createElement("option");
      otherOpt.value = "__other__";
      otherOpt.textContent = "Other (type it)";
      refineSelect.appendChild(otherOpt);

      if (prev && [...refineSelect.options].some((o) => o.value === prev)) {
        refineSelect.value = prev;
      }

      refineSelect.style.display = tier2 ? "block" : "none";
      refineSelect.required = !!tier2;
    }

    if (refine) {
      if (!tier2) {
        refine.style.display = "block";
        refine.required = false;
        refine.placeholder = "Optional (e.g., ground, shredded, cheddar)";
        return;
      }

      const otherSelected = refineSelect && refineSelect.value === "__other__";
      refine.style.display = otherSelected ? "block" : "none";
      refine.required = !!otherSelected;
      refine.placeholder = otherSelected ? "Type what you mean (brand/type)" : "";
      if (!otherSelected) refine.value = "";
    }
  }

  function refreshUI() {
    clearError();

    const category = norm(sel.value);
    const cKey = normKey(category);

    if (!category) {
      if (catHelp) catHelp.textContent = "Pick a category to save.";
      if (refineLabel) refineLabel.textContent = "Refinement (optional)";
      if (refineHelp) refineHelp.textContent = "";
      setRefineMode({ tier2: false, categoryKey: "" });
      return;
    }

    if (isNotAllowed(category)) {
      if (catHelp) catHelp.textContent = "That category is too broad. Please pick something more specific.";
      if (refineLabel) refineLabel.textContent = "Refinement (required)";
      if (refineSelect) refineSelect.style.display = "none";
      if (refine) {
        refine.style.display = "block";
        refine.required = true;
      }
      return;
    }

    const tier2 = isTier2(category);
    if (catHelp) {
      catHelp.textContent = tier2
        ? "Pick a refinement so matches aren’t noisy."
        : "This category can be saved as-is (refinement optional).";
    }

    if (refineLabel) refineLabel.textContent = tier2 ? "Refinement (required)" : "Refinement (optional)";
    setRefineMode({ tier2, categoryKey: cKey });

    const hints = SAVED_RULES.refineHints[cKey] || [];
    if (refineHelp) refineHelp.textContent = hints.length ? `Examples: ${hints.slice(0, 6).join(", ")}` : "";
  }

  sel.addEventListener("change", refreshUI);
  if (refineSelect) refineSelect.addEventListener("change", refreshUI);
  refreshUI();
}

// ----------------------
// Load + render saved items
// ----------------------
async function loadAndRenderSavedItems(user) {
  const alertBox = document.getElementById("saved-alert");
  const body = document.getElementById("saved-body");

  const { data: rows, error } = await sb
    .from("user_saved_items")
    .select("id, item_key, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("[saved] error loading user_saved_items:", error);
    if (alertBox) {
      alertBox.style.display = "block";
      alertBox.textContent = "Error loading saved items. Please try again.";
    }
    currentCount = null;
    return { rows: [], ok: false };
  }

  const savedItems = (rows || []).map((r) => ({
    id: r.id,
    name: formatDisplayName(r.item_key),
    rawKey: r.item_key || "",
    bestPrice: null,
    store: "",
    lastSeen: r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : "",
  }));

  currentCount = savedItems.length;

  if (!savedItems.length) {
    if (alertBox) {
      alertBox.style.display = "block";
      alertBox.textContent =
        "You don’t have any saved items yet. Save your favorite products from Flyers to track when they go on sale.";
    }
    if (body) body.innerHTML = "";
    return { rows: [], ok: true };
  }

  if (alertBox) alertBox.style.display = "none";

  body.innerHTML = savedItems
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.name)}</td>
          <td>${item.bestPrice != null && window.formatCurrency ? window.formatCurrency(item.bestPrice) : "&mdash;"}</td>
          <td>${escapeHtml(item.store || "—")}</td>
          <td>${escapeHtml(item.lastSeen || "&mdash;")}</td>
          <td>
            <button type="button" class="secondary" data-remove-id="${item.id}">Remove</button>
          </td>
        </tr>
      `
    )
    .join("");

  // Remove handlers
  body.querySelectorAll("button[data-remove-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-remove-id");
      if (!id) return;

      if (!confirm("Remove this saved item?")) return;

      const { error: delErr } = await sb
        .from("user_saved_items")
        .delete()
        .eq("id", id)
        .eq("user_id", user.id);

      if (delErr) {
        console.error("[saved] delete error:", delErr);
        alert("Could not remove this item. Please try again.");
        return;
      }

      await initSaved(); // refresh list without reload
    });
  });

  return { rows: savedItems, ok: true };
}

// ----------------------
// Submit handler (the ONLY submit handler)
// ----------------------
function setupAddForm(ctx) {
  const form = document.getElementById("saved-add-form");
  if (!form) {
    console.warn("[saved] add form not found");
    return;
  }

  // Avoid double-binding if initSaved runs multiple times
  if (form.dataset.bound === "1") return;
  form.dataset.bound = "1";

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearError();

    const categorySelect = document.getElementById("saved-category");
    const refine = document.getElementById("saved-refine");
    const refineSelect = document.getElementById("saved-refine-select");

    const category = norm(categorySelect?.value || "");
    if (!category) {
      setError("Choose a category first.");
      return;
    }

    if (isNotAllowed(category)) {
      setError("That category is too broad. Please pick something more specific.");
      return;
    }

    // Compute refinement
    let refinement = "";
    const tier2 = isTier2(category);

    if (tier2) {
      const selVal = norm(refineSelect?.value || "");
      if (refineSelect && refineSelect.style.display !== "none") {
        if (!selVal) {
          setError("Please choose a refinement.");
          return;
        }
        if (selVal === "__other__") {
          refinement = norm(refine?.value || "");
          if (!refinement) {
            setError("Please type what you mean (brand/type).");
            return;
          }
        } else {
          refinement = selVal;
        }
      } else {
        refinement = norm(refine?.value || "");
        if (!refinement) {
          setError("Please type what you mean (brand/type).");
          return;
        }
      }
    } else {
      refinement = norm(refine?.value || "");
    }

    // Plan limit check (use global currentCount if available; fallback to DOM rows)
    const countNow = Number.isFinite(currentCount)
      ? currentCount
      : document.querySelectorAll("#saved-body tr").length;

    if (ctx.planLimit != null && countNow >= ctx.planLimit) {
      setError(`You reached your ${ctx.planTier} plan limit (${ctx.planLimit}). Remove an item to add another.`);
      return;
    }

    const itemKey = normKey(refinement ? `${category} ${refinement}` : category);

    const { error } = await sb
      .from("user_saved_items")
      .insert({ user_id: ctx.user.id, item_key: itemKey });

    if (error) {
      console.warn("[saved] insert error:", error);
      setError("Could not save that item (it may already be saved).");
      return;
    }

    // Clear inputs
    if (categorySelect) categorySelect.value = "";
    if (refineSelect) refineSelect.value = "";
    if (refine) refine.value = "";

    // Refresh UI
    await initSaved();
  });
}

// ----------------------
// Main init
// ----------------------
async function initSaved() {
  // Require login
  if (window.requireAuth) {
    await window.requireAuth();
  }
  // Render toolbar tab highlight
  if (window.renderToolbar) {
    window.renderToolbar("saved");
  }

  if (!sb?.auth) {
    setError("Supabase client not ready.");
    return;
  }

  const { data: userData, error: userErr } = await sb.auth.getUser();
  if (userErr || !userData?.user) {
    console.error("[saved] getUser error:", userErr);
    const alertBox = document.getElementById("saved-alert");
    if (alertBox) alertBox.textContent = "Please log in to see your saved items.";
    return;
  }
  const user = userData.user;

  const planTier = await getUserPlanTier(user.id);
  const planLimit = SAVED_ITEM_LIMITS[planTier] ?? null;

  // UI-only setup
  initCategoryUI();

  // Ensure submit handler exists (single source of truth)
  setupAddForm({ user, planTier, planLimit });

  // Load + render
  await loadAndRenderSavedItems(user);

  // Plan info
  showPlanInfo(planTier, planLimit, Number.isFinite(currentCount) ? currentCount : 0);
}

// Kick off
initSaved();
