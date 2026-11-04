// Download the favicon of every host in src/data/resources.json into src/fav/<host>.png (64 px, via Google's favicon service).
// Usage: node favicons.mjs   (rerun after adding resources; existing files are kept)
import fs from "node:fs";
const hosts = [...new Set(JSON.parse(fs.readFileSync("src/data/resources.json", "utf8")).flatMap(g => g.items.map(i => new URL(i.url).hostname)))];
fs.mkdirSync("src/fav", { recursive: true });
for (const h of hosts) {
  const out = `src/fav/${h}.png`;
  if (fs.existsSync(out)) continue;
  const r = await fetch(`https://www.google.com/s2/favicons?domain=${h}&sz=64`);
  if (!r.ok) { console.warn(`skip ${h}: HTTP ${r.status}`); continue; }
  fs.writeFileSync(out, Buffer.from(await r.arrayBuffer()));
  console.log(`saved ${out}`);
}
