// pinLogin.js
console.log("[pin] pinLogin.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  console.log("[pin] DOMContentLoaded");

  const pinForm     = document.getElementById("pin-form");
  const pinInput    = document.getElementById("pin-input");
  const pinDots     = document.getElementById("pin-dots");
  const keypad      = document.getElementById("pin-keypad");
  const errorEl     = document.getElementById("pin-error");
  const profileList = document.getElementById("profile-list");

  console.log("[pin] elements", {
    pinForm,
    pinInput,
    pinDots,
    keypad,
    errorEl,
    profileList,
  });

  if (!pinForm || !pinInput || !pinDots || !keypad) {
    console.warn("[pin] Missing one or more core elements, aborting.");
    return;
  }

  const MAX_LEN   = 6;
  const PIN_TABLE = "profile_pins";   // holds account_email, profile_name, pin_hash
  const ACTIVE_PROFILE_KEY = "d4m_active_profile";

  let currentUserEmail = null;        // set after auth.getUser()

  // ---------- Supabase client helper ----------
  function getSupabaseClient() {
    const client = window.supabaseClient; // created in supabaseClient.js
    if (!client) {
      console.warn(
        "[pin] Supabase client not found on window.supabaseClient. " +
        "PIN validation will fail (dev mode)."
      );
      return null;
    }
    return client;
  }

  // ---------- error helpers ----------
  function showError(msg) {
    if (!errorEl) return;
    errorEl.textContent = msg;
    errorEl.style.display = "block";
  }

  function clearError() {
    if (!errorEl) return;
    errorEl.textContent = "";
    errorEl.style.display = "none";
  }

  // ---------- PIN / dots helpers ----------
  function refreshDots() {
    const len = pinInput.value.length;
    const filled = "•".repeat(len);
    const blanks = "○".repeat(Math.max(0, MAX_LEN - len));
    pinDots.textContent = filled + blanks;
  }

  function setPinValue(newVal) {
    const clean = newVal.replace(/\D/g, "").slice(0, MAX_LEN);
    pinInput.value = clean;
    refreshDots();
  }

  function getPin() {
    return pinInput.value.trim();
  }

  // ---------- profiles: render + click handling ----------
  function renderProfiles(list) {
    if (!profileList) return;

    if (!list || !list.length) {
      // fallback: Jesse + Tara
      list = [{ name: "Jesse" }, { name: "Tara" }];
    }

    profileList.innerHTML = list
      .map(
        (p, idx) => `
        <button type="button"
                class="profile-pill ${idx === 0 ? "active" : ""}"
                data-profile-name="${p.name}">
          ${p.name}
        </button>
      `
      )
      .join("");

    console.log("[pin] rendered profiles:", list.map((p) => p.name));
  }

  function getActiveProfileName() {
    if (!profileList) return null;
    const active = profileList.querySelector(".profile-pill.active");
    return active ? active.dataset.profileName : null;
  }

  if (profileList) {
    profileList.addEventListener("click", (event) => {
      const pill = event.target.closest(".profile-pill");
      if (!pill) return;

      profileList
        .querySelectorAll(".profile-pill")
        .forEach((el) => el.classList.remove("active"));

      pill.classList.add("active");
      clearError();
      pinInput.focus();
    });
  }

  // ---------- NUMPAD ----------
  const keyButtons = keypad.querySelectorAll(".key-btn");
  console.log("[pin] found key buttons:", keyButtons.length);

  keyButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const digit  = btn.getAttribute("data-digit");
      const action = btn.getAttribute("data-action");
      console.log("[pin] key-btn click", { digit, action });

      if (digit !== null) {
        setPinValue(pinInput.value + digit);
        clearError();
        return;
      }

      if (action === "clear") {
        setPinValue("");
        clearError();
        pinInput.focus();
        return;
      }

      if (action === "backspace") {
        setPinValue(pinInput.value.slice(0, -1));
        clearError();
        pinInput.focus();
        return;
      }
    });
  });

  // ---------- keyboard typing ----------
  pinInput.addEventListener("input", () => {
    setPinValue(pinInput.value);
    clearError();
  });

  pinInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSubmit();
    }
  });

  // ---------- SHA-256 helper ----------
  async function sha256Hex(text) {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // ---------- Supabase: load PIN profiles ----------
  (async () => {
    try {
      const supabaseClient = getSupabaseClient();
      if (!supabaseClient) {
        renderProfiles(null);
        return;
      }

      const { data: userData, error: userError } =
        await supabaseClient.auth.getUser();
      if (userError) throw userError;
      if (!userData || !userData.user) throw new Error("No signed-in user");

      const user = userData.user;
      currentUserEmail = user.email;
      console.log("[pin] Supabase user email:", currentUserEmail);

      const { data: rows, error } = await supabaseClient
        .from(PIN_TABLE)
        .select("profile_name")
        .eq("account_email", currentUserEmail)
        .order("profile_name", { ascending: true });

      if (error) throw error;

      if (!rows || !rows.length) {
        console.warn(
          "[pin] profile_pins returned no rows for this email; using defaults."
        );
        renderProfiles(null);
        return;
      }

      const profileNames = rows.map((row) => ({ name: row.profile_name }));
      console.log("[pin] PIN profiles from profile_pins:", profileNames);
      renderProfiles(profileNames);
    } catch (err) {
      console.warn("[pin] Failed to load PIN profiles; using defaults:", err);
      renderProfiles(null);
    }
  })();

  // ---------- Supabase: validate PIN for selected profile ----------
  async function validatePinForProfile(profileName, pin) {
    try {
      const supabaseClient = getSupabaseClient();
      if (!supabaseClient) {
        console.warn("[pin] No Supabase client, cannot validate PIN.");
        return false;
      }

      if (!profileName) {
        console.warn("[pin] No profile name, treating PIN as invalid.");
        return false;
      }

      if (!currentUserEmail) {
        console.warn("[pin] No currentUserEmail, cannot look up PIN.");
        return false;
      }

      const { data, error } = await supabaseClient
        .from(PIN_TABLE)
        .select("pin_hash")
        .eq("account_email", currentUserEmail)
        .eq("profile_name", profileName)
        .single();

      if (error) {
        console.warn("[pin] Error fetching pin_hash for profile:", error);
        return false;
      }

      if (!data || !data.pin_hash) {
        console.warn("[pin] No pin_hash stored for profile:", profileName);
        return false;
      }

      const storedHash = String(data.pin_hash).trim();
      const enteredHash = await sha256Hex(pin.trim());

      console.log(
        "[pin] compare hashes:",
        "\n  profile =", profileName,
        "\n  enteredHash =", enteredHash,
        "\n  storedHash  =", storedHash
      );

      return enteredHash === storedHash;
    } catch (err) {
      console.warn("[pin] validatePinForProfile exception:", err);
      return false;
    }
  }

  // ---------- form submit ----------
  pinForm.addEventListener("submit", (event) => {
    event.preventDefault();
    handleSubmit();
  });

  async function handleSubmit() {
    clearError();

    const pin = getPin();
    const activeProfileName = getActiveProfileName();

    console.log("[pin] submit: pin =", pin, "profile =", activeProfileName);

    if (!activeProfileName) {
      showError("Please pick your profile first.");
      pinInput.focus();
      return;
    }

    if (pin.length !== MAX_LEN) {
      showError(`PIN must be exactly ${MAX_LEN} digits.`);
      pinInput.focus();
      return;
    }

    const ok = await validatePinForProfile(activeProfileName, pin);

    if (!ok) {
      showError("Incorrect PIN. Please try again.");
      setPinValue("");       // clear dots & input
      pinInput.focus();      // keep numpad usable
      return;
    }

    // Store active profile so dashboard (and other pages) know who is using the site
    const activeProfile = {
      profileName: activeProfileName,
      setAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem(ACTIVE_PROFILE_KEY, JSON.stringify(activeProfile));
    } catch (err) {
      console.warn("[pin] Failed to store active profile in localStorage:", err);
    }

    console.log("[pin] Correct PIN for profile", activeProfileName);
    window.location.href = "dashboard.html";
  }

  // ---------- init visuals ----------
  pinInput.focus();
  setPinValue(""); // ○○○○○○
});
