// site/pinLogin.js

const demoProfiles = [
  { id: "1", name: "John", pin: "1111", role: "adult" },
  { id: "2", name: "Patty", pin: "2222", role: "adult" },
  { id: "3", name: "Emily", pin: "3333", role: "kid" }
];

(async function initPinPage() {
  if (window.requireAuth) {
    await window.requireAuth();
  }

  const selectEl = document.getElementById("profile-select");
  const pinInput = document.getElementById("pin-input");
  const form = document.getElementById("pin-form");
  const alertBox = document.getElementById("pin-alert");
  const submitBtn = document.getElementById("pin-submit");

  if (!selectEl || !form) return;

  function showAlert(msg) {
    alertBox.textContent = msg;
    alertBox.style.display = "block";
  }

  // TODO: replace with Supabase query for real profiles
  demoProfiles.forEach((p) => {
    const option = document.createElement("option");
    option.value = p.id;
    option.textContent = p.name;
    selectEl.appendChild(option);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    alertBox.style.display = "none";

    const selectedId = selectEl.value;
    const pin = (pinInput.value || "").trim();

    const profile = demoProfiles.find((p) => p.id === selectedId);
    if (!profile) {
      showAlert("Profile not found.");
      return;
    }

    if (pin !== profile.pin) {
      showAlert("Incorrect PIN. Try again.");
      return;
    }

    if (window.setActiveProfile) {
      window.setActiveProfile(profile.name, profile.id);
    }

    window.location.href = "/site/dashboard.html";
  });
})();
