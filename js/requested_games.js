// Load approved suggested games
import { getFirestore, collection, getDocs, query, where, orderBy } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-firestore.js";
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-app.js";
const firebaseConfig = { /* your config */ };
const app = initializeApp(firebaseConfig); const db = getFirestore(app);
async function loadApproved(){
  const q = query(collection(db, "suggestedGames"), where("status","==","approved"));
  const snap = await getDocs(q);
  const el = document.getElementById("requestedGamesList"); el.innerHTML = "";
  snap.forEach(docSnap=>{
    const g = docSnap.data();
    el.innerHTML += `<div class="game"><h3>${g.gameTitle}</h3><p>${g.gameIdea}</p><p><em>Suggested by ${g.parentName}</em></p></div>`;
  });
}
document.addEventListener("DOMContentLoaded", loadApproved);
