// /api/run-ingest.js
const cors = require('./_cors');
const { spawn } = require('child_process');
const path = require('path');

module.exports = async (req, res) => {
  if (cors(req, res)) return;

  try {
    const token = req.headers['x-deals4me-token'] || process.env.DEALS4ME_ADMIN_TOKEN;
    const store = (req.query?.store || '').toString().trim();
    const week  = (req.query?.week  || '').toString().trim();

    const ADMIN_TOKEN = process.env.ADMIN_TOKEN || process.env.DEALS4ME_ADMIN_TOKEN;

    if (!ADMIN_TOKEN) return res.status(500).send('Missing ADMIN_TOKEN env var.');
    if (token !== ADMIN_TOKEN) return res.status(401).send('Unauthorized: bad or missing x-deals4me-token.');
    if (!store || !week) return res.status(400).send('Missing "store" or "week" query param.');

    // ---- paths from your .env ----
    const PYTHON_PATH = process.env.PYTHON_PATH || "C:\\Users\\jwein\\OneDrive\\Desktop\\deals-4me\\.venv\\Scripts\\python.exe";
    const SCRIPT_PATH = process.env.INGEST_PY_SCRIPT || "C:\\Users\\jwein\\OneDrive\\Desktop\\deals-4me\\python\\run_all_stores.py";

    // ---- launch python non-blocking ----
    const args = [SCRIPT_PATH, '--store', store, '--week', week];

    console.log(`🚀 Launching Python ingest: ${PYTHON_PATH} ${args.join(' ')}`);

    const py = spawn(PYTHON_PATH, args, { shell: true, detached: true, stdio: 'ignore' });
    py.unref();   // let Node exit while Python continues

    console.log(`✅ Ingest process started successfully for ${store} (${week})`);

    return res.status(200).json({
      ok: true,
      store,
      week,
      started: true,
      message: `Python ingest started for ${store} ${week}`
    });
  } catch (err) {
    console.error('❌ run-ingest error:', err);
    return res.status(500).send(`Internal error: ${err.message || String(err)}`);
  }
};
