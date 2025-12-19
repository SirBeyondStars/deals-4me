// site/scripts/profile-pin.js
// Purpose: Pick a household profile, verify 6-digit PIN, set active profile.

import { supabase } from "./supabaseClient.js"; 
// profile-pin.js and supabaseClient.js are both in site/scripts/

document.addEventListener("DOMContentLoaded", async () => {
  // Support both old and new id names (so you don't get stuck again)
  const form =
    document.getElementById("pin-form") ||
    document.getElementById("pinForm");

  const profileSelect =
    document.getElementById("profile-select") ||
    document.getElementById("profileSelect");

  const pinInput =
    document.getElementById("pin-input") ||
    document.getElementById("pinInput");

  const statusEl =
    document.getElementById("status") ||
    document.getElementById("pinStatus") ||
    document.getElementById("loginStatus");

  function setStatus(msg, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.style.color = isError ? "red" : "green";
  }

  // Hard stop if key elements are missing
  if (!form || !profileSelect || !pinInput) {
    console.error("[profile-pin.js] Missing elements:", {
      formFound: !!form,
      profileSelectFound: !!profileSelect,
      pinInputFound: !!pinInput,
    });
    setStatus("PIN page elements missing. Check IDs.", true);
    return;
  }

  // Ensure we start clean
  profileSelect.innerHTML = `<option value="">Loading profiles...</option>`;
  setStatus("");

  // Get logged-in auth user (account owner)
  const { data: { user }, error: userErr } = await supabase.auth.getUser();
  if (userErr || !user) {
    window.location.href = "../auth/login.html";
    return;
  }

  const ownerId = user.id;

  // Load household member profiles
  const { data: profiles, error } = await supabase
    .from("household_profiles")
    .select("id, display_name, pin, role, age_group")
    .eq("owner_user_id", ownerId)
    .eq("is_active", true)
    .order("display_name", { ascending: true });

  if (error) {
    console.error("[profile-pin.js] load profiles error:", error);
    setStatus("Couldn't load profiles. Check console + schema.", true);
    profileSelect.innerHTML = `<option value="">No profiles</option>`;
    return;
  }

  if (!profiles || profiles.length === 0) {
    setStatus("No profiles found for this account.", true);
    profileSelect.innerHTML = `<option value="">No profiles</option>`;
    return;
  }

  // Populate dropdown
  profileSelect.innerHTML = `<option value="">Select a profile...</option>`;
  for (const p of profiles) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.display_name;
    profileSelect.appendChild(opt);
  }

  // Verify PIN + set active profile
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    const chosenId = profileSelect.value;
    const typedPinRaw = (pinInput.value || "").trim();

    if (!chosenId) {
      setStatus("Pick a profile first.", true);
      return;
    }

    if (!/^\d{6}$/.test(typedPinRaw)) {
      setStatus("Enter a valid 6-digit PIN.", true);
      return;
    }

    const selected = profiles.find(p => p.id === chosenId);
    if (!selected) {
      setStatus("Profile not found. Refresh and try again.", true);
      return;
    }

    const storedPin = String(selected.pin ?? "").padStart(6, "0");

    if (typedPinRaw !== storedPin) {
      setStatus("Incorrect PIN.", true);
      pinInput.value = "";
      pinInput.focus();
      return;
    }

    // Save active profile for rest of app
    localStorage.setItem("activeProfile", JSON.stringify({
      id: selected.id,
      name: selected.display_name,
      role: selected.role,
      age_group: selected.age_group,
    }));

    setStatus("Success! Redirecting...");
const hasSitePrefix = window.location.pathname.includes("/site/");
const prefix = hasSitePrefix ? "/site" : "";
window.location.href = window.location.origin + prefix + "/dashboard.html";




  });
});
