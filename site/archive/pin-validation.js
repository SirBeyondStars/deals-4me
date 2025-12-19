// /site/js/pin-validator.js
// Contains only the PIN validation logic used by profile-pin and any other PIN pages.

console.log("pin-validator.js loaded");

function validatePin(pin) {
  // Must be exactly 6 digits
  if (!/^\d{6}$/.test(pin)) {
    return "PIN must be 6 digits.";
  }

  // Too common / banned list
  const bannedPins = [
    "000000","111111","222222","333333","444444","555555",
    "666666","777777","888888","999999",
    "123456","654321","121212","696969","420420","012345"
  ];
  if (bannedPins.includes(pin)) {
    return "That PIN cannot be used. Please choose another.";
  }

  // Repeating pattern (111111, 222222...)
  if (/^(\d)\1{5}$/.test(pin)) {
    return "PIN cannot be repeating digits.";
  }

  // Simple ascending sequence (012345, 123456, 234567, ...)
  if ("0123456789".includes(pin)) {
    return "PIN cannot be an ascending sequence.";
  }

  // Simple descending sequence (987654, 876543, …)
  if ("9876543210".includes(pin)) {
    return "PIN cannot be a descending sequence.";
  }

  // Alternating digits (121212, 343434, etc.)
  if (/^(\d)(\d)\1\2\1\2$/.test(pin)) {
    return "PIN cannot use repeating alternating patterns.";
  }

  // Advanced "almost sequential" patterns like 024686, 135797, 567765
  const digits = pin.split("").map(d => parseInt(d, 10));
  const diffs = [];
  for (let i = 1; i < digits.length; i++) {
    diffs.push(digits[i] - digits[i - 1]);
  }

  const nonZeroDiffs = diffs.filter(d => d !== 0);
  const uniqueDiffs = [...new Set(nonZeroDiffs)];

  // Pure +2 / -2 pattern (e.g., 024680 or 135791)
  if (uniqueDiffs.length === 1 && Math.abs(uniqueDiffs[0]) === 2) {
    return "PIN is too easy to guess. Please choose something less patterned.";
  }

  // “Go up then one step back” sequences (024686, 135797, 567765)
  if (uniqueDiffs.length === 2) {
    const a = uniqueDiffs[0];
    const b = uniqueDiffs[1];
    if (Math.abs(a) === Math.abs(b) && Math.abs(a) <= 2) {
      const mainSign = Math.sign(nonZeroDiffs[0]);
      const offSteps = nonZeroDiffs.filter(
        d => Math.sign(d) !== mainSign
      );
      if (offSteps.length === 1) {
        return "PIN pattern is too simple. Please choose something less predictable.";
      }
    }
  }

  // (Future: date pattern check can go here when you go live)

  return null; // PIN is valid
}
