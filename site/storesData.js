// site/storesData.js
console.log("[stores] storesData.js loaded");

/**
 * Fetch all active stores from Supabase.
 * Adjust table/column names to match your schema.
 */
async function fetchAllActiveStores() {
  if (typeof supabaseClient === "undefined") {
    console.error("[stores] supabaseClient undefined");
    return { data: [], error: new Error("Supabase not available") };
  }

  // 🔧 CHANGE THESE if your table/columns are named differently:
  //  - "stores"       -> your stores table name (e.g. "stores_ne", "store_list")
  //  - "is_active"    -> flag column for active stores
  //  - "display_name" -> human-readable store name
  //  - "slug"         -> optional slug/code for routing
  const query = supabaseClient
    .from("stores")
    .select("id, display_name, slug, is_active")
    .eq("is_active", true)
    .order("display_name", { ascending: true });

  const { data, error } = await query;
  console.log("[stores] fetchAllActiveStores result:", data, error);
  return { data: data || [], error };
}
