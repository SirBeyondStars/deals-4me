// Suggest Game -> Firestore
import { getFirestore, collection, addDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-firestore.js";
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-app.js";
// TODO: insert your firebaseConfig
const firebaseConfig = { /* your config */ };
const app = initializeApp(firebaseConfig); const db = getFirestore(app);
document.getElementById("suggestionForm").addEventListener("submit", async (e)=>{
  e.preventDefault();
  const parentName = document.getElementById("parentName")?.value || "Anonymous";
  const gameTitle = document.getElementById("gameTitle").value;
  const gameIdea = document.getElementById("gameIdea").value;
  await addDoc(collection(db, "suggestedGames"), { parentName, gameTitle, gameIdea, timestamp: serverTimestamp(), status: "pending" });
  alert("Thanks! Your idea was submitted.");
  e.target.reset();
});
