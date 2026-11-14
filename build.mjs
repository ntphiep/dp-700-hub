// Build src/ into dist/: lay out diagrams, merge glossary parts, link terms to sections, build the search index.
// Usage: node build.mjs              full build into dist/
//        node build.mjs --check <id> lay out one topic, print warnings, screenshot preview/<id>.png (no dist write)
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { layout, svg } from "./diagram.mjs";

const SRC = "src", DIST = "dist", MAX_W = 1000, MAX_H = 760;
const readJSON = p => JSON.parse(fs.readFileSync(p, "utf8"));
const list = d => fs.existsSync(d) ? fs.readdirSync(d).filter(f => f.endsWith(".json")).map(f => f.slice(0, -5)).sort() : [];
const plain = s => String(s ?? "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*`]/g, "");
const blockText = b => [b.title, b.md, b.caption, b.alt, b.note, ...(b.rows || []).map(r => Array.isArray(r) ? r.join(" ") : `${r.says} ${r.pick} ${r.why}`),
  ...(b.items || []).map(i => `${i.name || ""} ${i.title || ""} ${(i.points || []).join(" ")} ${i.md || ""}`), ...(b.nodes || []).map(n => `${n.label} ${n.info || ""}`)].map(plain).join(" ");

async function layTopic(id, t) {
  const warns = [];
  for (const s of t.sections) {
    for (const b of s.blocks) {
      if (b.type !== "diagram") continue;
      const L = await layout(b);
      b.svg = svg(L);
      b.W = L.W;
      const at = `${id} / ${s.id} / "${b.title}"`;
      for (const w of L.warnings) warns.push(`${at}: ${w}`);
      if (L.W > MAX_W) warns.push(`${at}: width ${L.W} > ${MAX_W}, text will shrink. Use dir DOWN, fewer nodes per row, or split.`);
      if (L.H > MAX_H) warns.push(`${at}: height ${L.H} > ${MAX_H}. Use dir RIGHT, fewer nodes, or split.`);
    }
  }
  return warns;
}

function screenshot(id, t) {
  const css = fs.readFileSync(`${SRC}/index.html`, "utf8").replace("/*ACCENT*/", "").match(/<style>([\s\S]*?)<\/style>/)[1];
  const edge = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/microsoft-edge"].find(fs.existsSync);
  const ds = t.sections.flatMap(s => s.blocks.filter(b => b.type === "diagram").map(b => ({ s: s.title, b })));
  const html = `<!doctype html><meta charset="utf-8"><base href="${pathToURL(path.resolve(SRC))}/"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600&family=JetBrains+Mono&display=swap"><style>${css} body{padding:20px;width:1040px;background-image:none}</style>` +
    ds.map((d, i) => `<div class="card" style="margin-bottom:20px"><h3>${i + 1}. ${d.s} / ${d.b.title || ""} (${d.b.W}px)</h3><div class="dg">${d.b.svg}</div></div>`).join("");
  const file = path.join(os.tmpdir(), `hub-preview-${id}-${process.pid}.html`);
  fs.writeFileSync(file, html);
  const height = ds.reduce((a, d) => a + Number(d.b.svg.match(/height="(\d+)"/)[1]) * Math.min(1, 1000 / d.b.W) + 100, 60);
  fs.mkdirSync("preview", { recursive: true });
  const png = path.resolve(`preview/${id}.png`);
  execFileSync(edge, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${path.join(os.tmpdir(), "hub-chrome-" + process.pid)}`, `--window-size=1080,${Math.ceil(height)}`, `--screenshot=${png}`, pathToURL(file)], { stdio: "ignore" });
  fs.rmSync(file);
  return png;
}
const pathToURL = p => "file://" + p;

const ci = process.argv.indexOf("--check");
if (ci > 0) {
  const id = process.argv[ci + 1];
  const t = readJSON(`${SRC}/data/topics/${id}.json`);
  const warns = await layTopic(id, t);
  warns.forEach(w => console.log("WARN " + w));
  console.log(`${warns.length} layout warnings. Preview: ${screenshot(id, t)}`);
  process.exit(0);
}

const SITE = readJSON(`${SRC}/site.json`);
// favicons of resource hosts, downloaded by favicons.mjs into src/fav/<host>.png
SITE.fav = fs.existsSync(`${SRC}/fav`) ? fs.readdirSync(`${SRC}/fav`).filter(f => f.endsWith(".png")).map(f => f.slice(0, -4)) : [];
const escH = x => String(x).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function shell() {
  const a = SITE.accent, v = o => `--accent:${o.accent};--accent-ink:${o.ink};--accent-soft:${o.soft}`;
  const accent = a ? `:root{${v(a.light)}}\n@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){${v(a.dark)}}}\n:root[data-theme="dark"]{${v(a.dark)}}` : "";
  const html = fs.readFileSync(`${SRC}/index.html`, "utf8");
  const out = html.replace("/*ACCENT*/", accent).replace("/*SITE*/null", JSON.stringify(SITE).replace(/</g, "\\u003c"))
    .replaceAll("%TITLE%", escH(SITE.title)).replaceAll("%DESC%", escH(SITE.desc)).replaceAll("%ICON%", escH(SITE.icon))
    .replaceAll("%BRAND%", escH(SITE.brand)).replaceAll("%BRANDSUB%", escH(SITE.brandSub)).replaceAll("%HINT%", escH(SITE.hint));
  if (/%[A-Z]+%|\/\*SITE\*\//.test(out)) throw new Error("unfilled placeholder in index.html");
  return out;
}

fs.mkdirSync(DIST, { recursive: true });
for (const f of fs.readdirSync(DIST)) fs.rmSync(`${DIST}/${f}`, { recursive: true, force: true });
fs.cpSync(SRC, DIST, { recursive: true });
fs.rmSync(`${DIST}/data/glossary-parts`, { recursive: true, force: true });
fs.rmSync(`${DIST}/site.json`, { force: true });
fs.writeFileSync(`${DIST}/index.html`, shell());

const topics = list(`${SRC}/data/topics`);
const quiz = list(`${SRC}/data/quiz`).flatMap(f => readJSON(`${SRC}/data/quiz/${f}.json`));
const cards = list(`${SRC}/data/cards`).flatMap(f => readJSON(`${SRC}/data/cards/${f}.json`).map(c => ({ ...c, topic: f })));
const index = [], sections = [];
let warnCount = 0;

for (const id of topics) {
  const t = readJSON(`${SRC}/data/topics/${id}.json`);
  const warns = await layTopic(id, t);
  warns.forEach(w => console.warn("WARN " + w));
  warnCount += warns.length;
  for (const s of t.sections) {
    const text = s.blocks.map(blockText).join(" ");
    sections.push({ href: `#${id}.${s.id}`, title: s.title, topic: t.title, task: s.task, text });
    index.push({ type: "section", title: s.title, sub: t.title, href: `#${id}.${s.id}`, icon: s.icon || t.icon, text });
  }
  fs.writeFileSync(`${DIST}/data/topics/${id}.json`, JSON.stringify(t));
}

const re = a => new RegExp(`(^|[^A-Za-z0-9-])${a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}($|[^A-Za-z0-9-])`, "i");
const glossary = [];
for (const f of list(`${SRC}/data/glossary-parts`)) for (const g of readJSON(`${SRC}/data/glossary-parts/${f}.json`)) {
  if (glossary.some(x => x.id === g.id || x.term.toLowerCase() === g.term.toLowerCase())) { console.warn(`WARN glossary duplicate ${g.id} in ${f}, skipped`); continue; }
  glossary.push(g);
}
for (const g of glossary) g.related = (g.related || []).filter(r => glossary.some(x => x.id === r));
for (const g of glossary) {
  const rx = [g.term, ...(g.aliases || [])].map(re);
  g.sections = sections.filter(s => rx.some(r => r.test(s.title + " " + s.text))).map(s => ({ href: s.href, title: s.title, topic: s.topic }));
  index.push({ type: "term", title: g.term, sub: plain(g.full ? `${g.full}. ${g.what}` : g.what), href: `#glossary.${g.id}`, text: (g.aliases || []).join(" ") });
}
fs.writeFileSync(`${DIST}/data/glossary.json`, JSON.stringify(glossary));
for (const q of quiz) index.push({ type: "quiz", title: plain(q.stem).slice(0, 120), sub: q.id, href: `#q.${q.id}`, text: [...(q.options || []).map(o => plain(o.t)), ...(q.slots || []).flatMap(x => [plain(x.label), ...x.options.map(plain)])].join(" ") });
for (const c of cards) index.push({ type: "card", title: plain(c.front), sub: plain(c.back).slice(0, 140), href: `#cards.${c.topic}`, text: "" });
for (const e of index) e.text = (e.text || "").slice(0, 1500);
fs.writeFileSync(`${DIST}/data/search.json`, JSON.stringify(index));
fs.writeFileSync(`${DIST}/data/map.json`, JSON.stringify(sections.map(({ href, title, topic, task }) => ({ href, title, topic, task }))));
console.log(`built ${topics.length} topics, ${glossary.length} terms, ${quiz.length} quiz, ${cards.length} cards, ${index.length} search entries, ${warnCount} layout warnings`);
