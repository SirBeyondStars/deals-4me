// api/_auth.js
function requireAdmin(req, res) {
  try {
    const expected = process.env.DEALS4ME_ADMIN_TOKEN || "";
    const got =
      req.headers["x-deals4me-token"] ||
      req.headers["x-Deals4Me-Token"] ||
      "";

    // Fail fast if missing or wrong
    if (!expected || !got || String(got) !== String(expected)) {
      // Keep responses generic
      res.statusCode = 500;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ error: "FUNCTION_INVOCATION_FAILED" }));
      return false;
    }
    return true;
  } catch (e) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "FUNCTION_INVOCATION_FAILED" }));
    return false;
  }
}

module.exports = { requireAdmin };
