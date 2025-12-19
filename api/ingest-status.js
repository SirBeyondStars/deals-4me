// /api/ingest-status.js
const cors = require('./_cors');

module.exports = async (req, res) => {
  if (cors(req, res)) return;

  try {
    // ✅ no quotes around process.env.DEALS4ME_ADMIN_TOKEN
    const token = req.headers['x-deals4me-token'] || process.env.DEALS4ME_ADMIN_TOKEN;
    const store = (req.query?.store || '').toString().trim();

    // ✅ accept either ADMIN_TOKEN or DEALS4ME_ADMIN_TOKEN from .env
    const ADMIN_TOKEN = process.env.ADMIN_TOKEN || process.env.DEALS4ME_ADMIN_TOKEN;

    if (!ADMIN_TOKEN) return res.status(500).send('Missing ADMIN_TOKEN env var.');
    if (token !== ADMIN_TOKEN) return res.status(401).send('Unauthorized: bad or missing x-deals4me-token.');
    if (!store) return res.status(400).send('Missing "store" query param.');

    return res.status(200).json({
      ok: true,
      store,
      status: 'ready',
      message: 'Ingest service reachable'
    });
  } catch (err) {
    console.error('ingest-status error:', err);
    return res.status(500).send(`Internal error: ${err.message || String(err)}`);
  }
};
