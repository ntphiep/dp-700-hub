"""Validate study hub content files against src/site.json. Usage: python -I validate.py <file.json>... | --icons"""
import json
import os
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = json.load(open(os.path.join(HERE, "src", "site.json"), encoding="utf-8"))
ICONS = sorted(f[:-4] for f in os.listdir(os.path.join(HERE, "src", "icons")) if f.endswith(".svg"))
BLOCKS = {"text", "callout", "diagram", "table", "decision", "code", "chart", "compare", "steps", "figure"}
FIG_KINDS = {"diagram", "screenshot", "docs"}
# Licenses that allow copying an image into src/figs/. Images under other terms are embedded from the vendor host instead.
FIG_LICENSES = {"CC BY 4.0", "CC BY-SA 4.0", "MIT", "Apache-2.0"}
TONES = {"tip", "trap", "new", "exam"}
GROUP_KINDS = {"cloud", "region", "vpc", "subnet", "account", "org", "onprem", "ou", "workspace", "catalog", "zone", "external", "service"}
CHARTS = {"bar", "hbar", "line", "scatter", "bubble"}
BANNED = ["—", "->", "→"]
# Vietnamese translations of IT terms: the reader wants the English term (security, account, network, ...).
VI_TERMS = ["bảo mật", "tài khoản", "vận hành", "chi phí", "di chuyển", "di trú", "thảm hoạ", "thảm họa", "khôi phục",
    "sao lưu", "mã hoá", "mã hóa", "nhật ký", "kiểm toán", "tuân thủ", "phân quyền", "quyền truy cập", "chính sách",
    "định tuyến", "độ trễ", "băng thông", "thông lượng", "dự phòng", "vùng", "khu vực", "trung tâm dữ liệu",
    "khối lượng công việc", "giám sát", "định danh", "xác thực", "uỷ quyền", "ủy quyền", "máy chủ", "cơ sở dữ liệu",
    "bộ nhớ đệm", "cân bằng tải", "tường lửa", "mạng", "đường hầm", "phát hiện", "hạ tầng", "lưu trữ", "cảnh báo",
    "sự cố", "chứng chỉ", "dịch vụ", "người dùng", "quy tắc", "hàng đợi", "bản sao", "ổ đĩa", "mã nguồn", "triển khai",
    "quản trị", "rủi ro", "các bên liên quan", "tinh chỉnh", "ảo giác", "trường hợp sử dụng", "lực lượng lao động",
    "quản lý thay đổi", "thí điểm", "trí tuệ nhân tạo", "học máy", "lợi tức đầu tư", "chỉ số hiệu suất"]
VI_RE = re.compile(r"(?<![\w])(" + "|".join(map(re.escape, VI_TERMS)) + r")(?![\w])", re.I)

errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def check_text(where, s):
    if not isinstance(s, str):
        return
    for b in BANNED:
        if b in s and not where.endswith(".code"):
            err(where, f"banned sequence {b!r}")
    if not where.endswith(".code"):
        for m in sorted(set(x.lower() for x in VI_RE.findall(s))):
            err(where, f"Vietnamese term '{m}': write the English IT term")
    for url in re.findall(r"\]\((.*?)\)", s):
        if not url.startswith("https://"):
            err(where, f"link must be https: {url}")


def walk_strings(where, obj):
    if isinstance(obj, str):
        check_text(where, obj)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_strings(f"{where}[{i}]", v)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            walk_strings(f"{where}.{k}", v)


FILLER_RE = re.compile(r"(?<![\w])(bấm|click|nhấn)(?![\w])", re.I)
STYLES, ETONES = {"solid", "dashed", "double"}, {"primary", "backup", "deny", "data"}


def check_md(where, s, max_line=30):
    """Prose must be scannable: every non-bullet line short, no UI instructions like 'Bấm Next'."""
    if not isinstance(s, str):
        return
    for line in s.split("\n"):
        if line.strip().startswith("- "):
            continue
        n = len(re.sub(r"\]\(https://[^)]*\)", "]", line).split())
        if n > max_line:
            err(where, f"line has {n} words (max {max_line}): split into '- ' bullets")
    if FILLER_RE.search(s):
        err(where, "UI instruction ('Bấm ...'): delete it")


def check_src(where, src):
    if src is None:
        return
    items = src if isinstance(src, list) else [src]
    for s in items:
        if not isinstance(s, dict) or not str(s.get("url", "")).startswith("https://") or not s.get("label"):
            err(where, "src needs label + https url")


def check_diagram(where, b):
    ids, eids = set(), set()
    if b.get("dir", "RIGHT") not in ("RIGHT", "DOWN"):
        err(where, "dir must be RIGHT or DOWN")
    for k in ("x", "y", "h"):
        if k in b:
            err(where, f"remove coordinate field {k}; layout is automatic")
    gids = {g["id"] for g in b.get("groups", [])}
    for g in b.get("groups", []):
        if g.get("kind") not in GROUP_KINDS:
            err(where, f"group {g.get('id')} bad kind")
        if g.get("parent") and g["parent"] not in gids:
            err(where, f"group {g['id']} unknown parent")
        if len(g.get("label", "")) > 34:
            err(where, f"group {g['id']} label > 34 chars")
        if any(k in g for k in ("x", "y", "w", "h")):
            err(where, f"group {g['id']} has coordinates")
        ids.add(g["id"])
    nodes = b.get("nodes", [])
    if len(nodes) > 9:
        err(where, f"{len(nodes)} nodes, max 9: split the diagram or cut detail")
    for n in nodes:
        if n.get("icon") not in ICONS:
            err(where, f"node {n.get('id')} unknown icon {n.get('icon')}")
        if n.get("group") and n["group"] not in gids:
            err(where, f"node {n['id']} unknown group")
        if len(n.get("label", "")) > 18:
            err(where, f"node {n['id']} label > 18 chars")
        if len(n.get("sub", "")) > 22:
            err(where, f"node {n['id']} sub > 22 chars")
        if "x" in n or "y" in n:
            err(where, f"node {n['id']} has coordinates")
        ids.add(n["id"])
    edges = b.get("edges", [])
    if len(edges) > 10:
        err(where, f"{len(edges)} edges, max 10")
    for e in edges:
        for k in ("from", "to"):
            if e.get(k) not in ids:
                err(where, f"edge {e.get('id')} {k} unknown {e.get(k)}")
        if len(e.get("label", "")) > 22:
            err(where, f"edge {e.get('id')} label > 22 chars")
        eids.add(e.get("id"))
    check_md(where + ".caption", b.get("caption", ""), 20)
    used = {(e.get("style", "solid"), e.get("tone", "primary")) for e in edges}
    legend = b.get("legend", [])
    for it in legend:
        if it.get("style", "solid") not in STYLES or it.get("tone", "primary") not in ETONES or not it.get("label"):
            err(where, "legend item needs style, tone, label")
        if len(it.get("label", "")) > 40:
            err(where, "legend label > 40 chars")
    if len(used) > 1:
        have = {(it.get("style", "solid"), it.get("tone", "primary")) for it in legend}
        for u in sorted(used - have):
            err(where, f"edge style {u} used but missing from legend")
    for n in nodes:
        check_md(where + f".node {n.get('id')}.info", n.get("info", ""))
    for s in b.get("steps", []):
        check_md(where + ".step", s.get("md", ""))
        for x in s.get("hl", []):
            if x not in ids and x not in eids:
                err(where, f"step highlights unknown id {x}")


VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)


def check_figure(where, b):
    img, c = str(b.get("img", "")), b.get("credit") or {}
    for k in ("img", "alt", "caption", "kind"):
        if not b.get(k):
            err(where, f"figure needs {k}")
    if b.get("kind") and b["kind"] not in FIG_KINDS:
        err(where, f"figure kind must be one of {sorted(FIG_KINDS)}")
    if not c.get("label") or not str(c.get("url", "")).startswith("https://"):
        err(where, "figure needs credit {label, url} pointing to the page that shows the image")
    if img.startswith("https://"):
        pass
    elif img.startswith("figs/"):
        if not os.path.isfile(os.path.join(HERE, "src", img)):
            err(where, f"figure file missing: src/{img}")
        if c.get("license") not in FIG_LICENSES:
            err(where, f"a copied figure needs credit.license in {sorted(FIG_LICENSES)}; otherwise embed it by https url")
    else:
        err(where, "figure img is figs/<file> or an https url")
    if len(str(b.get("caption", "")).split()) > 40:
        err(where, "figure caption > 40 words")


def check_title(where, t):
    """Titles are Vietnamese; a title of 4+ words with no Vietnamese letter is English prose."""
    if t and len(t.split()) >= 4 and not VI_CHARS.search(t):
        err(where, f"title in English: '{t}'. Write it in Vietnamese, keep product and IT terms in English")


def check_topic(path, d):
    for k in ("id", "title", "icon", "summary", "sections"):
        if k not in d:
            err(path, f"missing {k}")
    if d.get("icon") not in ICONS:
        err(path, f"unknown icon {d.get('icon')}")
    check_md(f"{path} summary", d.get("summary", ""))
    for si, s in enumerate(d.get("sections", [])):
        prev = None
        check_title(f"{path} sec {s.get('id')}", s.get("title"))
        if str(s.get("task", "")) not in TASKS:
            err(f"{path} sec {s.get('id')}", f"section task {s.get('task')!r} not in site.json tasks")
        n_src = sum(bool(b.get("src")) + sum(bool(r.get("src")) for r in b.get("rows", []) if isinstance(r, dict)) for b in s.get("blocks", []))
        if n_src < 1:
            err(f"{path} sec {s.get('id')}", "section cites no source: add src to at least 1 block")
        if s.get("icon") and s["icon"] not in ICONS:
            err(f"{path} sec {s.get('id')}", f"unknown icon {s['icon']}")
        for bi, b in enumerate(s.get("blocks", [])):
            where = f"{path} sec {s.get('id')} block {bi}"
            check_title(where, b.get("title"))
            t = b.get("type")
            if t not in BLOCKS:
                err(where, f"bad type {t}")
                continue
            check_src(where, b.get("src"))
            if t == "text":
                if len(b.get("md", "").split()) > 110:
                    err(where, "text block too long (>110 words)")
                if prev == "text":
                    err(where, "two text blocks in a row")
            if t == "callout" and b.get("tone") not in TONES:
                err(where, "bad callout tone")
            if t in ("text", "callout"):
                check_md(where, b.get("md", ""))
            if t == "steps":
                for it in b.get("items", []):
                    check_md(where, it.get("md", ""))
            if t == "diagram":
                check_diagram(where, b)
            if t == "figure":
                check_figure(where, b)
            if t == "chart" and b.get("chart") not in CHARTS:
                err(where, "bad chart kind")
            if t == "compare":
                for it in b.get("items", []):
                    if it.get("icon") and it["icon"] not in ICONS:
                        err(where, f"unknown icon {it['icon']}")
            if t == "decision":
                for r in b.get("rows", []):
                    check_src(where, r.get("src"))
                    if len(r.get("why", "").split()) > 30:
                        err(where, "decision why > 30 words")
            if t == "table":
                n = len(b.get("columns", []))
                for r in b.get("rows", []):
                    if len(r) != n:
                        err(where, "table row width mismatch")
            prev = t
    hosts = set(re.findall(r'"url": ?"https://([^/"]+)', json.dumps(d)))
    if d.get("sections") and len(hosts) < 3:
        err(path, f"topic cites only {len(hosts)} distinct hosts {sorted(hosts)}: cross-check with more sources")
    walk_strings(path, {k: v for k, v in d.items()})


def check_resources(path, d):
    for g in d:
        if not g.get("group") or not g.get("items"):
            err(path, "resource group needs group + items")
        for it in g.get("items", []):
            w = f"{path} {g.get('group')} {it.get('label')}"
            if not it.get("label") or not str(it.get("url", "")).startswith("https://"):
                err(w, "item needs label + https url")
            if it.get("kind") not in RES_KINDS:
                err(w, f"kind must be one of {sorted(RES_KINDS)}")
            if it.get("date") and not re.match(r"20\d\d(-\d\d){0,2}$", it["date"]):
                err(w, "date must be YYYY, YYYY-MM or YYYY-MM-DD")
    walk_strings(path, d)


RES_KINDS = {"official", "docs", "course", "practice", "video", "blog", "book", "community", "repo"}


def check_quiz(path, d):
    seen = set()
    for q in d:
        w = f"{path} {q.get('id')}"
        if q.get("id") in seen:
            err(w, "duplicate id")
        seen.add(q.get("id"))
        keys = [o["k"] for o in q.get("options", [])]
        if not set(q.get("answer", [])) <= set(keys):
            err(w, "answer not in options")
        if len(q.get("answer", [])) != q.get("select"):
            err(w, "select count != answers")
        want = {1: 4, 2: 5, 3: 6}.get(q.get("select"))
        if want is None or len(keys) != want:
            err(w, f"select {q.get('select')} needs {want} options, has {len(keys)}")
        if q.get("domain") not in DOMAINS:
            err(w, f"bad domain {q.get('domain')}")
        if str(q.get("task", "")) not in TASKS:
            err(w, f"task {q.get('task')!r} not in site.json tasks")
        if len(keys) != len(set(keys)):
            err(w, "duplicate option keys")
        if not q.get("explain") or not q.get("refs"):
            err(w, "need explain + refs")
        check_src(w, q.get("refs"))
        for k in keys:
            if k not in q.get("answer", []) and k not in q.get("wrong", {}):
                err(w, f"missing wrong-reason for {k}")
    walk_strings(path, d)


def check_cards(path, d):
    for c in d:
        if not c.get("front") or not c.get("back"):
            err(f"{path} {c.get('id')}", "card needs front/back")
        check_src(f"{path} {c.get('id')}", c.get("ref"))
    walk_strings(path, d)


def check_glossary(path, d):
    seen = set()
    for g in d:
        w = f"{path} {g.get('id')}"
        if g.get("id") in seen:
            err(w, "duplicate id")
        seen.add(g.get("id"))
        for k in ("id", "term", "what", "means", "src"):
            if not g.get(k):
                err(w, f"missing {k}")
        if len(g.get("what", "").split()) > 25:
            err(w, "what > 25 words")
        if not isinstance(g.get("means"), list) or len(g["means"]) > 4:
            err(w, "means must be a list of at most 4 bullets")
        for b in g.get("means") or []:
            if len(b.split()) > 20:
                err(w, f"means bullet > 20 words: {b[:40]}")
        if g.get("cat") not in GL_CATS:
            err(w, f"bad cat {g.get('cat')}")
        check_src(w, g.get("src"))
    for g in d:
        for r in g.get("related", []):
            if r not in seen:
                err(f"{path} {g['id']}", f"related unknown id {r}")
    walk_strings(path, d)


GL_CATS = set(SITE["glCats"])
DOMAINS = set(SITE["domains"])
TASKS = set(SITE["tasks"])
VI_TERMS += SITE.get("viTerms", [])
VI_RE = re.compile(r"(?<![\w])(" + "|".join(map(re.escape, VI_TERMS)) + r")(?![\w])", re.I)
CATS = {"networking", "security", "management", "cost", "migration", "compute", "containers", "storage", "database",
    "analytics", "integration", "devtools", "euc", "frontend", "ml", "iot", "media"}


def check_services(path, d):
    seen = set()
    for sv in d:
        w = f"{path} {sv.get('id')}"
        if sv.get("id") in seen:
            err(w, "duplicate id")
        seen.add(sv.get("id"))
        for k in ("id", "name", "category", "icon", "what", "keywords", "src"):
            if not sv.get(k):
                err(w, f"missing {k}")
        if sv.get("category") not in CATS:
            err(w, f"bad category {sv.get('category')}")
        if sv.get("icon") not in ICONS:
            err(w, f"unknown icon {sv.get('icon')}")
        if len(sv.get("what", "").split()) > 25:
            err(w, "what > 25 words")
        parts = sv.get("parts")
        if not isinstance(parts, list) or not 1 <= len(parts) <= 4:
            err(w, "parts must be a list of 1 to 4 bullets")
        for b in parts or []:
            if len(b.split()) > 20:
                err(w, f"parts bullet > 20 words: {b[:40]}")
        if len(sv.get("status", "").split()) > 30:
            err(w, "status > 30 words")
        check_src(w, sv.get("src"))
        for r in sv.get("pick", []):
            check_src(w, r.get("src"))
        for f in sv.get("facts", []):
            check_src(w, f.get("src"))
        for n in sv.get("new", []):
            if not str(n.get("url", "")).startswith("https://") or not re.match(r"20\d\d-\d\d-\d\d$", n.get("date", "")):
                err(w, "new item needs YYYY-MM-DD date + https url")
    walk_strings(path, d)


def main(argv):
    if argv and argv[0] == "--icons":
        print(" ".join(ICONS))
        return 0
    for p in argv:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        norm = p.replace("\\", "/")
        if "/topics/" in norm:
            check_topic(p, d)
        elif "/quiz/" in norm:
            check_quiz(p, d)
        elif "/cards/" in norm:
            check_cards(p, d)
        elif "/services/" in norm:
            check_services(p, d)
        elif norm.endswith("resources.json"):
            check_resources(p, d)
        elif norm.endswith("glossary.json") or "/glossary-parts/" in norm:
            check_glossary(p, d)
        else:
            walk_strings(p, d)
    if errors:
        print("\n".join(errors))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
