// /auth/scripts/firebase-app.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyDI7ZUwcXNn0HRpmk3dNvCdObAtBFXtzQw",
  authDomain: "deals-4me-24e59.firebaseapp.com",
  projectId: "deals-4me-24e59",
  storageBucket: "deals-4me-24e59.firebasestorage.app",
  messagingSenderId: "371824876408",
  appId: "1:371824876408:web:6835492135efd123a7468d"
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
