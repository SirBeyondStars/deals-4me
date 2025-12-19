const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { initializeApp } = require("firebase-admin/app");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");
const bcrypt = require("bcryptjs");

initializeApp();
const db = getFirestore();

/**
 * setProfilePin
 * Create or update a profile PIN (secure, hashed)
 *
 * data:
 *  - userId: Firebase Auth UID
 *  - householdId: string
 *  - profileId: string
 *  - pin: string (raw 6-digit PIN)
 */
exports.setProfilePin = onCall(async (request) => {
  const auth = request.auth;
  const data = request.data || {};

  // Must be signed in
  if (!auth) {
    throw new HttpsError("unauthenticated", "You must be signed in.");
  }

  const { userId, householdId, profileId, pin } = data;

  if (!userId || !householdId || !profileId || !pin) {
    throw new HttpsError("invalid-argument", "Missing required fields.");
  }

  if (auth.uid !== userId) {
    throw new HttpsError("permission-denied", "You can only modify your own data.");
  }

  if (pin.length !== 6 || !/^\d+$/.test(pin)) {
    throw new HttpsError("invalid-argument", "PIN must be exactly 6 digits.");
  }

  // Hash the PIN securely
  const salt = bcrypt.genSaltSync(10);
  const hash = bcrypt.hashSync(pin, salt);

  // Write hash to Firestore
  await db
    .collection("users")
    .doc(userId)
    .collection("households")
    .doc(householdId)
    .collection("profiles")
    .doc(profileId)
    .set(
      {
        pinHash: hash,
        updatedAt: FieldValue.serverTimestamp(),
      },
      { merge: true }
    );

  return { success: true };
});

/**
 * verifyProfilePin
 * Check if a PIN is correct for a given profile.
 *
 * data:
 *  - userId
 *  - householdId
 *  - profileId
 *  - pin
 */
exports.verifyProfilePin = onCall(async (request) => {
  const auth = request.auth;
  const data = request.data || {};

  if (!auth) {
    throw new HttpsError("unauthenticated", "You must be signed in.");
  }

  const { userId, householdId, profileId, pin } = data;

  if (!userId || !householdId || !profileId || !pin) {
    throw new HttpsError("invalid-argument", "Missing required fields.");
  }

  if (auth.uid !== userId) {
    throw new HttpsError("permission-denied", "You can only access your own data.");
  }

  const docRef = db
    .collection("users")
    .doc(userId)
    .collection("households")
    .doc(householdId)
    .collection("profiles")
    .doc(profileId);

  const snap = await docRef.get();

  if (!snap.exists) {
    throw new HttpsError("not-found", "Profile not found.");
  }

  const profileData = snap.data();

  if (!profileData.pinHash) {
    throw new HttpsError("failed-precondition", "No PIN set on this profile.");
  }

  const isValid = bcrypt.compareSync(pin, profileData.pinHash);

  return { valid: isValid };
});
