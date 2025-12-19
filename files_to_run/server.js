// server.js
const path = require('path');
const express = require('express');
const app = express();

const PORT = process.env.PORT || 3005;
const HOST = '127.0.0.1';

// load your existing route handlers
const statusHandler   = require('./api/ingest-status.js');
const runIngestHandler = require('./api/run-ingest.js');

// small wrapper to catch errors
const wrap = (fn) => async (req, res) => {
  try { await fn(req, res); }
  catch (err) {
    console.error(err);
    if (!res.headersSent) {
      res.statusCode = 500;
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ error: 'FUNCTION_INVOCATION_FAILED', detail: String(err?.message || err) }));
    }
  }
};

// serve your test page
app.use('/site', express.static(path.join(__dirname, 'site')));

// API endpoints (same paths as before)
app.get('/api/ingest-status', wrap(statusHandler));
app.get('/api/run-ingest',     wrap(runIngestHandler));

// health
app.get('/api/ping', (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify({ ok: true, time: Date.now() }));
});

app.listen(PORT, HOST, () => {
  console.log(`Deals-4Me local server on http://${HOST}:${PORT}`);
});
