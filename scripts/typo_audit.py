"""Measure the typography the browser actually renders on every demo screen (HTML and SVG text).
    python scripts/typo_audit.py            report sizes, fonts, weights and violations
    python scripts/typo_audit.py --strict   exit 1 if any rule of the type system is broken
Rules (docs/DECISIONS.md, typography pass): sizes 13/14/16/18/22/28 px only, two fonts, weights 400/500,
no uppercase, letter-spacing at most 0.01em (large text may go to -0.01em), mono only for numbers/units/IDs."""
import collections
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from typo_shots import BASE, SCREENS

SIZES = {13, 14, 16, 18, 22, 28}
JS = r"""() => {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, t = n.textContent.trim();
    if (!t) continue;
    const el = n.parentElement; if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || el.closest('[hidden],[inert],.sr,dialog:not([open])')) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const fs = parseFloat(cs.fontSize);
    const ls = cs.letterSpacing === 'normal' ? 0 : parseFloat(cs.letterSpacing) / fs;
    out.push({ slide: !!el.closest('.slide'), code: !!el.closest('code,pre,kbd'), t: t.slice(0, 40), tag: el.tagName.toLowerCase(), cls: (el.getAttribute('class') || '').slice(0, 40),
      size: Math.round(fs * 10) / 10, fam: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
      w: cs.fontWeight, tt: cs.textTransform, ls: Math.round(ls * 1000) / 1000 });
  }
  return out;
}"""

def audit():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (1440, 1024):
            pg = b.new_page(viewport={"width": w, "height": 900})
            for name, url in SCREENS:
                pg.goto(BASE + url)
                pg.wait_for_timeout(2000)
                for r in pg.evaluate(JS):
                    rows.append({**r, "screen": f"{name}@{w}"})
            pg.close()
        b.close()
    return rows

def problems(rows):
    out = collections.defaultdict(list)
    for r in rows:
        where = f"{r['screen']}  <{r['tag']} class='{r['cls']}'>  “{r['t']}”"
        if r["size"] < 13:
            out["below 13 px"].append(f"{r['size']} px  {where}")
        if r["size"] not in SIZES and not r.get("slide"):     # slides scale with their own width (documented exception)
            out["off-scale size"].append(f"{r['size']} px  {where}")
        if r["w"] not in ("400", "500"):
            out["weight not 400/500"].append(f"{r['w']}  {where}")
        if r["tt"] == "uppercase":
            out["uppercase"].append(where)
        if r["ls"] > 0.0101 or (r["ls"] < -0.0101 and r["size"] < 22):
            out["letter-spacing"].append(f"{r['ls']}em  {where}")
        mono = "mono" in r["fam"].lower() and not r.get("code")
        unit = r["t"].strip() in {"mg/s", "psi", "mm", "cm/s", "kPa", "g", "%", "s", "mm/s", "mm²/s"}
        if mono and not unit and any(c.isalpha() for c in r["t"].replace("psi", "").replace("mm", "").replace("cm", "").replace("mg", "").replace("kPa", "")) and not any(ch.isdigit() for ch in r["t"]):
            out["mono used for words"].append(f"{r['fam']}  {where}")
    return out

if __name__ == "__main__":
    rows = audit()
    fams = collections.Counter(r["fam"] for r in rows)
    sizes = collections.Counter(r["size"] for r in rows)
    weights = collections.Counter(r["w"] for r in rows)
    print("text items:", len(rows))
    print("font families:", dict(fams))
    print("sizes (px):", dict(sorted(sizes.items())))
    print("weights:", dict(weights))
    probs = problems(rows)
    for k, v in probs.items():
        uniq = sorted(set(v))
        print(f"\n== {k}: {len(uniq)} distinct")
        for line in uniq[:25]:
            print("  ", line)
    json.dump({"families": fams, "sizes": {str(k): v for k, v in sizes.items()}, "weights": weights,
               "problems": {k: sorted(set(v)) for k, v in probs.items()}}, open(Path(__file__).resolve().parents[1] / "docs/audit/typography/audit.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if "--strict" in sys.argv and probs:
        sys.exit(1)
