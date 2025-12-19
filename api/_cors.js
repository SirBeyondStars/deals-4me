// /api/_cors.js
module.exports = function applyCors(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:5500');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,x-deals4me-token');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return true; // handled
  }
  return false;
};
