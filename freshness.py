#!/usr/bin/env python3
"""Weekly freshness check for a study hub. Python standard library only.

Usage: python3 -I freshness.py --state <dir> [--hub <dir>]

Reads the hub config `src/watch.json` and every source url in `src/data/**/*.json`.
It finds four kinds of change since the last run (or since `verified` on the first run):
  - exam:     the exam guide pages changed (update date, text hash or linked PDFs);
  - releases: new release-note or what's-new items in the configured feeds;
  - changed:  a docs page used as a source shows a newer update date or new text;
  - broken / moved: a source url or embedded image returns 404 or 410, or redirects;
  - unreachable: a source failed 2 runs in a row with another error (bot blocks are common).
It writes <state>/state.json. When something changed it also writes
<state>/reports/<date>.json and .md and prints `report=<md path>` to $GITHUB_OUTPUT.
"""
import argparse, concurrent.futures as cf, datetime as dt, email.utils, hashlib, html, json, os, re, sys, urllib.error, urllib.parse, urllib.request

UA = "Mozilla/5.0 (compatible; hub-freshness-check; +https://github.com/ntphiep)"
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()
SHORTENERS = {"aka.ms", "bit.ly", "youtu.be", "go.microsoft.com"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def fetch(url, want_body=True, tries=2):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en"})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read(4_000_000) if want_body else b""
                return {"status": r.status, "final": r.geturl(), "body": body.decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "final": e.geturl() or url, "body": ""}
        except Exception as e:  # DNS, TLS, timeout
            last = f"{type(e).__name__}: {e}"
    return {"status": 0, "final": url, "body": "", "error": last}


def text_of(fragment):
    fragment = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", fragment))).strip()


def signal(url, body):
    """Return (date, hash, pdfs) for a page. date is YYYY-MM-DD or None."""
    host = urllib.parse.urlparse(url).netloc
    date = digest = None
    if host == "learn.microsoft.com":
        m = re.search(r'<meta name="updated_at" content="(\d{4}-\d{2}-\d{2})', body) or re.search(r'<meta name="ms.date" content="(\d{4}-\d{2}-\d{2})', body)
        date = m and m.group(1)
    elif host == "docs.databricks.com":
        m = re.search(r"Last updated(?:\s|<[^>]+>)*on(?:\s|<[^>]+>)*([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4})", body)
        if m:
            date = f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    elif host == "docs.aws.amazon.com":
        m = re.search(r'(?s)<div id="main-col-body">(.*?)<div id="js_error_message"', body) or re.search(r'(?s)<div id="main-col-body">(.*)', body)
        if m:
            digest = hashlib.sha256(text_of(m.group(1)).encode()).hexdigest()[:16]
    pdfs = sorted(set(urllib.parse.urljoin(url, h) for h in re.findall(r'href="([^"]+\.pdf)"', body)))
    return date, digest, pdfs


def norm(u):
    p = urllib.parse.urlparse(u)
    return (p.netloc.lower(), p.path.rstrip("/").lower())


def collect_sources(hub):
    """Map every http url in src/data to the places that cite it."""
    found = {}
    root = os.path.join(hub, "src", "data")
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), hub)

            def walk(o, where):
                if isinstance(o, dict):
                    where = f"{where}#{o['id']}" if isinstance(o.get("id"), str) and o.get("type") is None else where
                    for k, v in o.items():
                        if k in ("url", "img") and isinstance(v, str) and v.startswith("http"):
                            u = v.split("#")[0]
                            found.setdefault(u, {"kind": "image" if k == "img" else "page", "where": []})
                            if where not in found[u]["where"]:
                                found[u]["where"].append(where)
                        else:
                            walk(v, where)
                elif isinstance(o, list):
                    for x in o:
                        walk(x, where)

            walk(json.load(open(os.path.join(dirpath, f), encoding="utf-8")), rel)
    return found


def parse_date(s):
    s = (s or "").strip()
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except Exception:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        return m and m.group(1)


def feed_items(body):
    items = []
    for block in re.findall(r"(?s)<(?:item|entry)\b.*?</(?:item|entry)>", body):
        def tag(name):
            m = re.search(rf"(?s)<{name}\b[^>]*>(.*?)</{name}>", block)
            return m and text_of(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.S))
        link = tag("link") or (re.search(r'<link[^>]+href="([^"]+)"', block) or [None, None])[1]
        items.append({"title": tag("title") or "", "link": link or "", "date": parse_date(tag("pubDate") or tag("updated") or tag("published"))})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default=".")
    ap.add_argument("--state", required=True)
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.hub, "src", "watch.json"), encoding="utf-8"))
    state_path = os.path.join(a.state, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"urls": {}, "exam": {}, "feeds": {}}
    verified = cfg["verified"]
    rep = {"date": TODAY, "hub": cfg["hub"], "verified": verified, "exam": [], "releases": [], "changed": [], "broken": [], "moved": [], "unreachable": []}

    # Exam guide pages: any change in date, text or linked PDFs.
    for e in cfg["exam"]:
        r = fetch(e["url"])
        date, digest, pdfs = signal(r["final"], r["body"])
        if "pdf_pattern" in e:
            pdfs = [p for p in pdfs if re.search(e["pdf_pattern"], p)]
        cur = {"status": r["status"], "date": date, "hash": digest, "pdfs": pdfs}
        old = state["exam"].get(e["url"])
        why = []
        if r["status"] != 200:
            why.append(f"HTTP {r['status']}")
        elif old is None:
            if date and date > verified:
                why.append(f"updated {date}, after verified {verified}")
        else:
            if date and date != old.get("date"):
                why.append(f"updated {old.get('date')} -> {date}")
            if digest and old.get("hash") and digest != old["hash"]:
                why.append("page text changed")
            if pdfs != old.get("pdfs"):
                why.append(f"PDF links {old.get('pdfs')} -> {pdfs}")
        if why:
            rep["exam"].append({"label": e["label"], "url": e["url"], "why": "; ".join(why)})
        if r["status"] == 200:
            state["exam"][e["url"]] = cur

    # Release-note feeds: items newer than the last seen date.
    for f in cfg["feeds"]:
        r = fetch(f["url"])
        if r["status"] != 200:
            rep["unreachable"].append({"url": f["url"], "status": r["status"], "where": ["src/watch.json (feed)"]})
            continue
        since = state["feeds"].get(f["url"], verified)
        kws = [k.lower() for k in f.get("keywords", [])]
        new = [i for i in feed_items(r["body"]) if i["date"] and i["date"] > since and (not kws or any(k in i["title"].lower() for k in kws))]
        for i in sorted(new, key=lambda i: i["date"], reverse=True)[:80]:
            rep["releases"].append({"feed": f["label"], **i})
        dates = [i["date"] for i in feed_items(r["body"]) if i["date"]]
        state["feeds"][f["url"]] = max(dates + [since])

    # Every cited url and embedded image.
    sources = collect_sources(a.hub)

    def check(u):
        meta = sources[u]
        r = fetch(u, want_body=meta["kind"] == "page")
        return u, r, signal(r["final"], r["body"]) if r["body"] else (None, None, [])

    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(check, sorted(sources)))
    new_urls = {}
    for u, r, (date, digest, _) in results:
        where = sources[u]["where"]
        old = state["urls"].get(u, {})
        cur = {"status": r["status"], "final": r["final"], "date": date, "hash": digest}
        if r["status"] in (404, 410):
            rep["broken"].append({"url": u, "status": r["status"], "where": where})
        elif r["status"] != 200:
            # Some hosts block scripts now and then; report only the second failed run in a row.
            cur["fails"] = old.get("fails", 0) + 1
            if cur["fails"] == 2:
                rep["unreachable"].append({"url": u, "status": r["status"], "error": r.get("error"), "where": where})
        else:
            short = urllib.parse.urlparse(u).netloc in SHORTENERS
            if not short and norm(r["final"]) != norm(u) and old.get("final") != r["final"]:
                rep["moved"].append({"url": u, "to": r["final"], "where": where})
            base = old.get("date") or verified
            if date and date > base:
                rep["changed"].append({"url": u, "why": f"page updated {date}, content verified {base}", "where": where})
            elif digest and old.get("hash") and digest != old["hash"]:
                rep["changed"].append({"url": u, "why": "page text changed since last check", "where": where})
        new_urls[u] = cur if r["status"] == 200 or not old else {**old, "status": r["status"], "fails": cur["fails"]}
    state["urls"] = new_urls
    state["checked"] = TODAY

    os.makedirs(a.state, exist_ok=True)
    json.dump(state, open(state_path, "w"), indent=1, sort_keys=True)
    total = sum(len(rep[k]) for k in ("exam", "releases", "changed", "broken", "moved", "unreachable"))
    print(f"{cfg['hub']}: {len(sources)} urls, exam {len(rep['exam'])}, releases {len(rep['releases'])}, changed {len(rep['changed'])}, broken {len(rep['broken'])}, moved {len(rep['moved'])}, unreachable {len(rep['unreachable'])}")
    if not total:
        return
    rdir = os.path.join(a.state, "reports")
    os.makedirs(rdir, exist_ok=True)
    json.dump(rep, open(os.path.join(rdir, f"{TODAY}.json"), "w"), indent=1, ensure_ascii=False)
    md = [f"Freshness report {TODAY} for {cfg['hub']}. Content was last verified on {verified}.", ""]
    titles = {"exam": "Exam guide changed (highest priority)", "releases": "New release notes", "changed": "Source pages updated", "broken": "Broken sources", "moved": "Moved sources", "unreachable": "Unreachable sources (may be bot blocking)"}
    for k, t in titles.items():
        if not rep[k]:
            continue
        md += [f"## {t} ({len(rep[k])})", ""]
        for i in rep[k][:150]:
            if k == "releases":
                md.append(f"- {i['date']} [{i['title']}]({i['link']}) ({i['feed']})")
            else:
                extra = i.get("why") or i.get("to") or f"HTTP {i.get('status')}"
                md.append(f"- {i.get('label', '')} {i['url']}: {extra}" + (f" (cited in {', '.join(i['where'][:4])})" if i.get("where") else ""))
        md.append("")
    mdp = os.path.join(rdir, f"{TODAY}.md")
    open(mdp, "w").write("\n".join(md)[:60000])
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"report={mdp}\n")


if __name__ == "__main__":
    sys.exit(main())
