#!/usr/bin/env node
/**
 * Guard: fail if legacy Super Bowl strings appear in the repo.
 * Use with: node scripts/guard-superbowl-strings.js
 * Bash version for CI: scripts/guard-superbowl-strings.sh (requires rg)
 */
const fs = require("fs");
const path = require("path");

const BAD_PATTERN = /Kansas City Chiefs|San Francisco 49ers|\bChiefs\b|\b49ers\b|superbowlTeams/;
const ROOT = path.resolve(__dirname, "..");
const IGNORE = new Set([
  "node_modules",
  ".git",
  "__pycache__",
  "kalshi_signals.db",
  "watchlist.json",
  "package-lock.json",
]);

function walk(dir, cb) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (IGNORE.has(e.name)) continue;
    if (e.isDirectory()) walk(full, cb);
    else if (e.isFile()) cb(full);
  }
}

const hits = [];
walk(ROOT, (file) => {
  const rel = path.relative(ROOT, file);
  if (rel.replace(/\\/g, "/").startsWith("scripts/guard-superbowl-strings")) return; // exclude self and .sh guard
  const ext = path.extname(file).toLowerCase();
  const isText = [".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".py", ".sh", ".env.example"].includes(ext) || !ext;
  if (!isText) return;
  const content = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
  const lines = content.split("\n");
  lines.forEach((line, i) => {
    if (BAD_PATTERN.test(line)) {
      hits.push(`${rel}:${i + 1}:${line.trim()}`);
    }
  });
});

if (hits.length > 0) {
  console.error("❌ Found legacy Super Bowl strings. Replace with config + formatters:");
  hits.forEach((h) => console.error(h));
  process.exit(1);
}
console.log("✅ No legacy Super Bowl strings found.");
