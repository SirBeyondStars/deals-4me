// frontend_fix_paths_only.js
// Run with: node frontend_fix_paths_only.js
// Purpose: In /site/*.html, clean up href/src that start with "site/" or "/site/"

const fs = require("fs");
const path = require("path");

// Your front-end pond:
const SITE_DIR = path.join(__dirname, "..", "..", "site");

async function fixFile(fullPath, name) {
  let html = await fs.promises.readFile(fullPath, "utf8");

  // Replace href="/site/..." or href='site/...'
  html = html.replace(/href=["']\/?site\//gi, 'href="');

  // Replace src="/site/..." or src='site/...'
  html = html.replace(/src=["']\/?site\//gi, 'src="');

  await fs.promises.writeFile(fullPath, html, "utf8");
  console.log(`Cleaned paths in: ${name}`);
}

async function run() {
  const entries = await fs.promises.readdir(SITE_DIR, { withFileTypes: true });

  for (const entry of entries) {
    if (!entry.isFile()) continue;

    const name = entry.name;
    if (!name.endsWith(".html")) continue;
    if (name.endsWith(".bak.html") || name.endsWith(".bak")) continue;

    const fullPath = path.join(SITE_DIR, name);
    await fixFile(fullPath, name);
  }

  console.log("✅ Finished cleaning href/src path prefixes in /site");
}

run().catch((err) => {
  console.error("Error while fixing paths:", err);
  process.exit(1);
});
