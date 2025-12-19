console.log("[profiles] profiles-page.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  console.log("[profiles] DOMContentLoaded");

  // --- DOM refs ---
  const ownerInfoEl      = document.getElementById("owner-info");
  const warningEl        = document.getElementById("access-warning");
  const tbody            = document.getElementById("profiles-tbody");
  const addForm          = document.getElementById("add-member-form");
  const displayInput     = document.getElementById("new-display-name");
  const roleSelect       = document.getElementById("new-role");
  const ageGroupInput    = document.getElementById("new-age-group");
  const pinInput         = document.getElementById("new-pin");
  const isActiveInput    = document.getElementById("new-is-active");
  const pinRow           = document.getElementById("pin-row");
  const submitBtn        = document.getElementById("member-submit-btn");
  const cancelEditBtn    = document.getElementById("cancel-edit-btn");

  // --- PIN visibility helper (0–5 has no PIN) ---
  function updatePinVisibility() {
    const ageGroup = ageGroupInput.value;

    if (ageGroup === "0-5") {
      // Hide PIN for 0–5, clear any existing value
      pinRow.style.display = "none";
      pinInput.value = "";
    } else {
      // Show PIN for 6+ kids/adults
      pinRow.style.display = "block";
    }
  }

  ageGroupInput.addEventListener("change", updatePinVisibility);
  updatePinVisibility(); // run once on load

  // --- Supabase ready? ---
  if (!window.supabaseClient) {
    alert("Supabase client not ready. Check supabaseClient.js.");
    return;
  }

  // --- 1) Ensure we have an active profile + it's the owner ---
  const rawActive = localStorage.getItem("d4m_activeProfile");
  if (!rawActive) {
    warningEl.style.display = "block";
    warningEl.textContent =
      "No active profile found. Please choose a profile first.";
    window.location.href = "pin.html";
    return;
  }

  let activeProfile;
  try {
    activeProfile = JSON.parse(rawActive);
  } catch (e) {
    console.error("[profiles] bad activeProfile JSON", e);
    warningEl.style.display = "block";
    warningEl.textContent =
      "Problem with active profile data. Please log in again.";
    window.location.href = "login.html";
    return;
  }

  ownerInfoEl.textContent =
    "Logged in as: " +
    activeProfile.name +
    " (" +
    (activeProfile.role || "unknown role") +
    ")";

  if (activeProfile.role !== "owner") {
    warningEl.style.display = "block";
    warningEl.textContent =
      "Only the account owner can manage household profiles.";
    addForm.style.display = "none";
    return;
  }

  // --- 2) State ---
  let currentUserId        = null;
  let currentHouseholdId   = null;
  let currentAddressLine   = null;
  let editingProfileId     = null;
  let editingProfileHasPin = false;

  // --- 3) Render profiles into the table ---
  function renderProfiles(rows) {
    if (!rows || rows.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6">No profiles found for this account.</td></tr>';
      return;
    }

    tbody.innerHTML = "";

    rows.forEach(row => {
      // Capture household/address from the OWNER row if we can
      if (row.role === "owner") {
        currentHouseholdId = row.household_id || currentHouseholdId;
        currentAddressLine = row.address_line || currentAddressLine;
      }

      const tr = document.createElement("tr");

      const created = row.created_at ? new Date(row.created_at) : null;
      const createdText = created ? created.toLocaleDateString() : "";

      const canDelete = row.role !== "owner";

      tr.innerHTML = `
        <td>${row.display_name || ""}</td>
        <td>${row.role || ""}</td>
        <td>${row.age_group || ""}</td>
        <td>${row.is_active ? "Yes" : "No"}</td>
        <td>${createdText}</td>
        <td>
          <div class="action-buttons">
            <button
              type="button"
              class="edit-member-btn"
              data-profile-id="${row.id}">
              Edit
            </button>

            ${
              canDelete
                ? `
                  <button
                    type="button"
                    class="delete-member-btn"
                    data-profile-id="${row.id}"
                    data-display-name="${row.display_name || ""}">
                    Remove
                  </button>
                `
                : ``
            }
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    });
  }

  // --- 4) Helper to reload profiles for this owner ---
  async function reloadProfiles() {
    if (!currentUserId) return;

    try {
      const { data: rows, error: profError } = await supabaseClient
        .from("household_profiles")
        .select("*")
        .eq("owner_user_id", currentUserId)
        .order("created_at", { ascending: true });

      console.log("[profiles] reload rows:", rows, profError);

      if (profError) {
        warningEl.style.display = "block";
        warningEl.textContent =
          "Error loading profiles: " + profError.message;
        return;
      }

      renderProfiles(rows || []);
    } catch (err) {
      console.error("[profiles] reload exception", err);
      warningEl.style.display = "block";
      warningEl.textContent =
        "Unexpected error refreshing profiles. See console for details.";
    }
  }

  // --- 5) Load Supabase user + initial profiles ---
  (async () => {
    try {
      const { data: userData, error: userError } =
        await supabaseClient.auth.getUser();

      console.log("[profiles] getUser:", userData, userError);

      if (userError || !userData || !userData.user) {
        warningEl.style.display = "block";
        warningEl.textContent =
          "Not logged in. Please log in again.";
        window.location.href = "login.html";
        return;
      }

      currentUserId = userData.user.id;
      const email = userData.user.email;
      ownerInfoEl.textContent += " – account email: " + email;

      console.log("[profiles] initial load for user:", currentUserId);
      await reloadProfiles();
    } catch (err) {
      console.error("[profiles] FATAL error", err);
      warningEl.style.display = "block";
      warningEl.textContent =
        "Unexpected error loading profiles. See console for details.";
    }
  })();

  // --- 6) Helpers for edit mode ---
  function enterEditModeFromButton(btn) {
    editingProfileId     = btn.dataset.profileId;
    editingProfileHasPin = btn.dataset.hasPin === "true";

    displayInput.value        = btn.dataset.displayName || "";
    roleSelect.value          = btn.dataset.role || "adult";
    ageGroupInput.value       = btn.dataset.ageGroup || "";
    isActiveInput.checked     = btn.dataset.isActive === "true";
    pinInput.value            = ""; // never prefill actual PIN
    updatePinVisibility();

    submitBtn.textContent     = "Save Changes";
    cancelEditBtn.style.display = "inline-block";
  }

  function resetFormAndEditState() {
    editingProfileId     = null;
    editingProfileHasPin = false;

    displayInput.value        = "";
    roleSelect.value          = "adult";
    ageGroupInput.value       = "";
    pinInput.value            = "";
    isActiveInput.checked     = true;
    submitBtn.textContent     = "Add Member";
    cancelEditBtn.style.display = "none";
    updatePinVisibility();
  }

  cancelEditBtn.addEventListener("click", () => {
    resetFormAndEditState();
  });

  // --- 7) Add / Edit member handler ---
  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!currentUserId) {
      alert(
        "User context not ready yet. Please wait a moment and try again."
      );
      return;
    }

    const displayName = displayInput.value.trim();
    const role        = roleSelect.value;
    const ageGroup    = ageGroupInput.value; // from <select>
    const pin         = pinInput.value.trim();
    const isActive    = isActiveInput.checked;

    // Extra safety: no second owner allowed
    if (role === "owner") {
      alert("Only one household owner is allowed.");
      return;
    }

    // Required fields: name + age group
    if (!displayName || !ageGroup) {
      alert("Display name and age group are required.");
      return;
    }

    const isUnder5 = ageGroup === "0-5";

    // --- CREATE (no editingProfileId) ---
    if (!editingProfileId) {
      // PIN rules for create:
      //  - Age group 0–5: PIN optional
      //  - 6+ : PIN required
      if (!isUnder5 && !pin) {
        alert("PIN is required for ages 6 and up.");
        return;
      }

      // If a PIN is provided, it must be exactly 6 digits
      if (pin && !/^[0-9]{6}$/.test(pin)) {
        alert("PIN must be exactly 6 digits.");
        return;
      }

      console.log("[profiles] adding member:", {
        displayName,
        role,
        ageGroup,
        isActive,
        householdId: currentHouseholdId,
        addressLine: currentAddressLine,
      });

      const { error: insertError } = await supabaseClient
        .from("household_profiles")
        .insert([
          {
            owner_user_id: currentUserId,
            household_id: currentHouseholdId,
            display_name: displayName,
            role: role,
            age_group: ageGroup,
            pin: pin || null, // under-5 can have null PIN
            is_active: isActive,
            address_line: currentAddressLine || null,
          },
        ]);

      if (insertError) {
        console.error("[profiles] insert error", insertError);
        alert("Could not add member: " + insertError.message);
        return;
      }

      // Reset + reload
      resetFormAndEditState();
      await reloadProfiles();
      return;
    }

    // --- UPDATE (editingProfileId != null) ---
    const updateFields = {
      display_name: displayName,
      role: role,
      age_group: ageGroup,
      is_active: isActive,
    };

    // PIN rules for update:
    //  - If age group is 0–5:
    //      - If new PIN provided, validate and set it
    //      - If left blank, clear PIN (set null)
    //  - If age group is 6+:
    //      - If there was no PIN before and none now: require PIN
    //      - If new PIN provided, validate and set it
    //      - If left blank and they had a PIN: keep existing PIN (no change)

    if (isUnder5) {
      if (pin) {
        if (!/^[0-9]{6}$/.test(pin)) {
          alert("PIN must be exactly 6 digits.");
          return;
        }
        updateFields.pin = pin;
      } else {
        // Under 5 and no PIN: clear any existing PIN
        updateFields.pin = null;
      }
    } else {
      // Age 6+
      if (!editingProfileHasPin && !pin) {
        alert("PIN is required for ages 6 and up.");
        return;
      }

      if (pin) {
        if (!/^[0-9]{6}$/.test(pin)) {
          alert("PIN must be exactly 6 digits.");
          return;
        }
        updateFields.pin = pin;
      }
      // else: had a PIN, left blank → leave existing PIN unchanged
    }

    console.log("[profiles] updating member:", editingProfileId, updateFields);

    const { error: updateError } = await supabaseClient
      .from("household_profiles")
      .update(updateFields)
      .eq("id", editingProfileId);

    if (updateError) {
      console.error("[profiles] update error", updateError);
      alert("Could not update member: " + updateError.message);
      return;
    }

    resetFormAndEditState();
    await reloadProfiles();
  });

  // --- 8) Delete + Edit button handling (event delegation) ---
  tbody.addEventListener("click", async (event) => {
    const editBtn = event.target.closest(".edit-member-btn");
    if (editBtn) {
      enterEditModeFromButton(editBtn);
      return;
    }

    const deleteBtn = event.target.closest(".delete-member-btn");
    if (!deleteBtn) return;

    const profileId   = deleteBtn.dataset.profileId;
    const displayName = deleteBtn.dataset.displayName || "this profile";

    if (!profileId) return;

    const confirmed = window.confirm(
      `Remove "${displayName}" from this household?\n\n` +
      `They will no longer be able to sign in with their PIN.`
    );

    if (!confirmed) return;

    console.log("[profiles] deleting member:", profileId, displayName);

    const { error: deleteError } = await supabaseClient
      .from("household_profiles")
      .delete()
      .eq("id", profileId);

    if (deleteError) {
      console.error("[profiles] delete error", deleteError);
      alert("Could not delete member: " + deleteError.message);
      return;
    }

    await reloadProfiles();
  });

  // --- 9) Helper: enter edit mode from button (defined after usage above) ---
  function enterEditModeFromButton(btn) {
    editingProfileId     = btn.dataset.profileId;
    editingProfileHasPin = btn.dataset.hasPin === "true";

    displayInput.value    = btn.dataset.displayName || "";
    roleSelect.value      = btn.dataset.role || "adult";
    ageGroupInput.value   = btn.dataset.ageGroup || "";
    isActiveInput.checked = btn.dataset.isActive === "true";
    pinInput.value        = ""; // never prefill actual PIN
    updatePinVisibility();

    submitBtn.textContent     = "Save Changes";
    cancelEditBtn.style.display = "inline-block";
  }
});
