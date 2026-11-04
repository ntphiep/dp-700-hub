// Auto-layout (ELK layered) and SVG rendering for content diagrams. Authors give structure only, never coordinates.
import ELK from "elkjs/lib/elk.bundled.js";

const elk = new ELK();
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// Text width estimates for the page fonts (Be Vietnam Pro 600 15px, JetBrains Mono 12px, Be Vietnam Pro 13px).
const wLabel = s => [...String(s)].length * 8.8;
const wSub = s => [...String(s)].length * 7.4;
const wEdge = s => [...String(s)].length * 7.6 + 16;
const wGroup = s => [...String(s)].length * 8.4 + 24;
const ICON = 44;

function nodeSize(n) {
  const w = Math.max(116, Math.ceil(Math.max(wLabel(n.label || ""), wSub(n.sub || ""))) + 20);
  return { w, h: n.sub ? 104 : 86 };
}

export async function layout(b) {
  const groups = b.groups || [], nodes = b.nodes || [], edges = b.edges || [];
  const elkNodes = new Map();
  for (const g of groups) {
    elkNodes.set(g.id, {
      id: g.id, children: [], labels: [{ text: g.label, width: wGroup(g.label), height: 20 }],
      layoutOptions: { "elk.padding": "[top=46,left=18,bottom=18,right=18]", "elk.nodeSize.minimum": `(${wGroup(g.label) + 20},60)`, "elk.nodeSize.constraints": "MINIMUM_SIZE" },
    });
  }
  for (const n of nodes) {
    const s = nodeSize(n);
    elkNodes.set(n.id, { id: n.id, width: s.w, height: s.h });
  }
  const root = {
    id: "__root", children: [],
    layoutOptions: {
      "elk.algorithm": "layered", "elk.direction": b.dir === "DOWN" ? "DOWN" : "RIGHT",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN", "elk.edgeRouting": "ORTHOGONAL",
      "elk.json.edgeCoords": "ROOT", "elk.json.shapeCoords": "ROOT",
      "elk.edgeLabels.placement": "CENTER", "elk.padding": "[top=16,left=16,bottom=16,right=16]",
      "elk.spacing.nodeNode": "44", "elk.layered.spacing.nodeNodeBetweenLayers": "64",
      "elk.spacing.edgeNode": "22", "elk.spacing.edgeEdge": "14", "elk.spacing.edgeLabel": "6",
      "elk.layered.spacing.edgeNodeBetweenLayers": "26", "elk.spacing.componentComponent": "40",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.crossingMinimization.thoroughness": "40",
    },
    edges: edges.map(e => ({
      id: e.id, sources: [e.from], targets: [e.to],
      labels: e.label ? [{ text: e.label, width: wEdge(e.label), height: 24 }] : [],
    })),
  };
  const parentOf = x => (x.group && elkNodes.has(x.group) ? elkNodes.get(x.group) : root);
  for (const g of groups) parentOf({ group: g.parent }).children.push(elkNodes.get(g.id));
  for (const n of nodes) parentOf(n).children.push(elkNodes.get(n.id));

  const r = await elk.layout(root);
  const out = { W: Math.ceil(r.width), H: Math.ceil(r.height), groups: [], nodes: [], edges: [] };
  const walk = k => {
    for (const c of k.children || []) {
      const src = groups.find(g => g.id === c.id);
      if (src) out.groups.push({ ...src, x: c.x, y: c.y, w: c.width, h: c.height });
      else out.nodes.push({ ...nodes.find(n => n.id === c.id), x: c.x, y: c.y, w: c.width, h: c.height });
      walk(c);
    }
  };
  walk(r);
  const allEdges = [];
  const collect = k => { for (const e of k.edges || []) allEdges.push(e); for (const c of k.children || []) collect(c); };
  collect(r);
  for (const e of edges) {
    const le = allEdges.find(x => x.id === e.id);
    const sec = le?.sections?.[0];
    const pts = sec ? [sec.startPoint, ...(sec.bendPoints || []), sec.endPoint].map(p => [p.x, p.y]) : [];
    const lab = le?.labels?.[0];
    out.edges.push({ ...e, pts, lab: lab && { x: lab.x, y: lab.y, w: lab.width, h: lab.height } });
  }
  out.warnings = overlaps(out);
  return out;
}

function overlaps(L) {
  const boxes = [
    ...L.nodes.map(n => ({ k: "node " + n.id, x: n.x, y: n.y, w: n.w, h: n.h })),
    ...L.edges.filter(e => e.lab).map(e => ({ k: "edge label " + e.id, ...e.lab })),
    ...L.groups.map(g => ({ k: "group label " + g.id, x: g.x + 10, y: g.y + 10, w: wGroup(g.label), h: 24 })),
  ];
  const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  const w = [];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) if (hit(boxes[i], boxes[j])) w.push(`${boxes[i].k} overlaps ${boxes[j].k}`);
  return w;
}

export function svg(L) {
  const r = v => Math.round(v * 10) / 10;
  let s = `<svg viewBox="0 0 ${L.W} ${L.H}" width="${L.W}" height="${L.H}" xmlns="http://www.w3.org/2000/svg"><defs>${["primary", "backup", "deny", "data"].map(t => `<marker id="ah-${t}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ahf-${t}"/></marker>`).join("")}</defs>`;
  for (const g of L.groups) {
    s += `<g class="grp" data-id="${esc(g.id)}"><rect class="gbox g-${esc(g.kind)}" x="${r(g.x)}" y="${r(g.y)}" width="${r(g.w)}" height="${r(g.h)}" rx="10"/><text class="glab" x="${r(g.x + 14)}" y="${r(g.y + 27)}">${esc(g.label)}</text></g>`;
  }
  for (const e of L.edges) {
    if (!e.pts.length) continue;
    const d = "M" + e.pts.map(p => p.map(r).join(",")).join(" L");
    const tone = e.tone || "primary", st = e.style || "solid";
    s += `<g class="edgeg" data-id="${esc(e.id)}">`;
    if (st === "double") s += `<path class="edge ${tone} double" d="${d}"/>`;
    s += `<path class="edge ${tone}${st === "dashed" ? " dashed" : ""}" d="${d}"${e.noarrow ? "" : ` marker-end="url(#ah-${tone})"`}${e.both ? ` marker-start="url(#ah-${tone})"` : ""}/></g>`;
  }
  for (const e of L.edges) {
    if (!e.lab) continue;
    const { x, y, w, h } = e.lab;
    s += `<g class="elab" data-id="${esc(e.id)}"><rect x="${r(x)}" y="${r(y)}" width="${r(w)}" height="${h}" rx="5"/><text x="${r(x + w / 2)}" y="${r(y + h / 2 + 4.5)}">${esc(e.label)}</text></g>`;
  }
  for (const n of L.nodes) {
    const cx = n.x + n.w / 2;
    s += `<g class="node" data-id="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label)}"><rect class="hit" x="${r(n.x)}" y="${r(n.y)}" width="${r(n.w)}" height="${r(n.h)}" rx="10"/>` +
      `<image href="icons/${esc(n.icon)}.svg" x="${r(cx - ICON / 2)}" y="${r(n.y + 6)}" width="${ICON}" height="${ICON}"/>` +
      `<text class="nlab" x="${r(cx)}" y="${r(n.y + ICON + 28)}">${esc(n.label)}</text>` +
      (n.sub ? `<text class="nsub" x="${r(cx)}" y="${r(n.y + ICON + 48)}">${esc(n.sub)}</text>` : "") + `</g>`;
  }
  return s + "</svg>";
}
