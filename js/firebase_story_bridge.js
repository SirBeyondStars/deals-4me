// Firebase Bridge for Human Side Connect: Fetching Approved Stories
// Replace config with your Firebase project creds
const firebaseConfig = { /* your config */ };
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-app.js";
import { getFirestore, collection, query, where, getDocs } from "https://www.gstatic.com/firebasejs/10.3.1/firebase-firestore.js";
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const storiesRef = collection(db, "humanStories");
async function fetchStories(company = ""){
  try {
    const q = company ? query(storiesRef, where("company","==",company), where("approved","==",true))
                      : query(storiesRef, where("approved","==",true));
    const snap = await getDocs(q);
    return snap.docs.map(d=>d.data());
  } catch(err){ console.error(err); return []; }
}
window.fetchStories = fetchStories;
