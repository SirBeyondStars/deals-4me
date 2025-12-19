// Admin review for suggested games
import { getFirestore, collection, getDocs, query, where, updateDoc, doc } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-firestore.js";
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-app.js";
const firebaseConfig = { /* your config */ };
const app = initializeApp(firebaseConfig); const db = getFirestore(app);
async function loadPending(){
  const q = query(collection(db, "suggestedGames"), where("status","==","pending"));
  const snap = await getDocs(q);
  const list = document.getElementById("adminGameList"); list.innerHTML = "";
  snap.forEach(docSnap=>{
    const d = docSnap.data(); const id = docSnap.id;
    const div = document.createElement("div");
    div.innerHTML = `<h4>${d.gameTitle}</h4><p>${d.gameIdea}</p>
      <button data-id="${id}" data-s="approved">Approve</button>
      <button data-id="${id}" data-s="rejected">Reject</button>`;
    list.appendChild(div);
  });
}
async function updateStatus(id, status){
  await updateDoc(doc(db, "suggestedGames", id), { status });
  loadPending();
}
document.addEventListener("click", (e)=>{
  if(e.target.dataset && e.target.dataset.id){
    updateStatus(e.target.dataset.id, e.target.dataset.s);
  }
});
document.addEventListener("DOMContentLoaded", loadPending);
