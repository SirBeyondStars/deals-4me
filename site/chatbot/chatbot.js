// /site/chatbot/chat.js
console.log("[chatbot] Deals-4Me assistant loaded");

const chatLogEl   = document.getElementById("chat-log");
const chatFormEl  = document.getElementById("chat-form");
const chatInputEl = document.getElementById("chat-input");
const sendBtnEl   = document.getElementById("chat-send-btn");

let faqData = [];
let fallbackAnswer = "I’m still learning this version of Deals-4Me. Try asking about saved items, regions, or what D4Mii does.";

async function loadFaq() {
  try {
    const res = await fetch("chatbot_faq.json");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    faqData = data || [];

    const fb = faqData.find((f) => f.id === "fallback");
    if (fb && fb.answer) {
      fallbackAnswer = fb.answer;
    }

    console.log("[chatbot] FAQ loaded:", faqData.length, "entries");
  } catch (err) {
    console.error("[chatbot] Failed to load FAQ:", err);
  }
}

function appendMessage({ from, text }) {
  const row = document.createElement("div");
  row.classList.add("msg-row", from === "user" ? "user" : "bot");

  const bubble = document.createElement("div");
  bubble.classList.add("msg-bubble", from === "user" ? "user" : "bot");
  bubble.textContent = text;

  row.appendChild(bubble);
  chatLogEl.appendChild(row);

  // scroll to bottom
  chatLogEl.scrollTop = chatLogEl.scrollHeight;
}

function findFaqAnswer(userText) {
  if (!faqData || faqData.length === 0) {
    return fallbackAnswer;
  }

  const normalized = userText.trim().toLowerCase();
  if (!normalized) return null;

  let bestMatch = null;
  let bestScore = 0;

  for (const entry of faqData) {
    if (!entry.patterns || entry.patterns.length === 0) continue;

    for (const pattern of entry.patterns) {
      const normPattern = pattern.toLowerCase().trim();
      if (!normPattern) continue;

      // super simple scoring: how many words from the pattern appear in the user text
      const words = normPattern.split(/\s+/);
      let score = 0;
      for (const w of words) {
        if (w && normalized.includes(w)) {
          score += 1;
        }
      }

      if (score > bestScore) {
        bestScore = score;
        bestMatch = entry;
      }
    }
  }

  // minimum score: at least 1 word match
  if (bestMatch && bestScore > 0) {
    return bestMatch.answer;
  }

  return fallbackAnswer;
}

function handleUserMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  appendMessage({ from: "user", text: trimmed });

  // basic thinking delay
  sendBtnEl.disabled = true;
  setTimeout(() => {
    const answer = findFaqAnswer(trimmed);
    appendMessage({ from: "bot", text: answer });
    sendBtnEl.disabled = false;
    chatInputEl.focus();
  }, 300);
}

chatFormEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = chatInputEl.value;
  chatInputEl.value = "";
  handleUserMessage(value);
});

// greet user on first load
function showWelcome() {
  appendMessage({
    from: "bot",
    text: "Hi! I’m the Deals-4Me assistant. I can answer basic questions about regions, saved items, account types, and D4Mii. What would you like to know?"
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  await loadFaq();
  showWelcome();
});
