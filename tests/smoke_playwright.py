"""Browser acceptance test. Run with the API on :8000 and the web app on :3000 (python run.py start).

Checks the things a reviewer would check by eye, on every run:
  - every screen renders with no page errors and shows the demo-data notice
  - navigation has at most four items, in plain words
  - no text under 13 px, no clipped (truncated) text, no overlapping labels
  - Explore never shows more than 15 nodes, in any grouping, with any cluster opened
  - no flagged value is rendered as a normal value; gravity is never "0 g"; no internal 0/1 codes
  - the provenance panel hides the technical trail until asked
  - "Is this material risky in a Moon base?" is answered within 3 clicks, with measured / inferred / untested shown
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
SCREENS = [
    ("/", "[data-ready=home]"),
    ("/answer?topic=moon-base", "[data-ready=answer]"),
    ("/answer?topic=iss-cabin", "[data-ready=answer]"),
    ("/answer?topic=microgravity", "[data-ready=answer]"),
    ("/answer?topic=untested", "[data-ready=answer]"),
    ("/answer?q=burning%20rate%20of%20heptane%20droplets%20in%20helium", "[data-ready=answer]"),
    ("/explore", "[data-ready=explore]"),
    ("/trade", "[data-ready=trade]"),
    ("/lab", "[data-ready=lab]"),
    ("/lab?mode=droplet", "[data-ready=lab]"),
    ("/insights", "[data-ready=insights]"),
    ("/studio", "[data-ready=studio]"),
    ("/studio?chart=gap", "text=Moon base"),
    ("/data", "[data-ready=data]"),
    ("/data?dataset=bass2_demo", "[data-ready=data]"),
    ("/image", "text=TEST PATTERN"),
]

# smallest font size among elements that directly hold visible text
MIN_FONT = """() => {
  let min = 99, who = '';
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement; const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (cs.visibility === 'hidden' || cs.display === 'none' || r.width === 0 || r.height === 0) continue;
    if (el.closest('.sr-only')) continue;
    const fs = parseFloat(cs.fontSize);
    if (fs < min) { min = fs; who = n.textContent.trim().slice(0, 40); }
  }
  return {min, who};
}"""
# labels whose text is clipped by their own box (truncation), anywhere on the screen
CLIPPED = """() => [...document.querySelectorAll('[data-label], h1, h2, h3, th, .chip, .btn, .status')]
  .filter(el => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
  .map(el => el.textContent.trim().slice(0, 50))"""
# pairs of labels whose boxes intersect
OVERLAPS = """(sel) => {
  const els = [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0);
  const out = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
    const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect();
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1)
      out.push(els[i].textContent.trim().slice(0, 30) + ' × ' + els[j].textContent.trim().slice(0, 30));
  }
  return out;
}"""
FORBIDDEN = ["g₀", "NaN", "undefined", "[object"]
CODES = re.compile(r"(?<!of )\b[01] (burned|extinguished)\b")      # internal 0/1 outcome codes

failed, notes = [], []


def check(cond, msg):
    if not cond:
        failed.append(msg)
    return cond


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # ---- every screen
    for path, sel in SCREENS:
        errors.clear()
        page.goto(BASE + path)
        try:
            page.wait_for_selector(sel, timeout=20000)
        except Exception:
            failed.append(f"{path}: {sel} never appeared")
            continue
        page.wait_for_timeout(500)
        check(not errors, f"{path}: page errors {errors[:2]}")
        check(page.locator("header [role=status]").is_visible(), f"{path}: demo-data notice missing")
        mf = page.evaluate(MIN_FONT)
        check(mf["min"] >= 13, f"{path}: text at {mf['min']}px (“{mf['who']}”)")
        clipped = page.evaluate(CLIPPED)
        check(not clipped, f"{path}: truncated text {clipped[:3]}")
        body = page.inner_text("body")
        for bad in FORBIDDEN:
            check(bad not in body, f"{path}: shows “{bad}”")
        check(not CODES.search(body), f"{path}: shows an internal outcome code")
        ov = page.evaluate(OVERLAPS, "svg text")
        check(not ov, f"{path}: overlapping chart labels {ov[:3]}")
        print(("ok  " if not errors else "ERR ") + path)

    # ---- navigation: at most four plain items
    page.goto(BASE + "/")
    nav = page.locator("nav[aria-label=Primary] a").all_inner_texts()
    check(nav == ["Explore", "Simulate", "Insights", "Data"], f"navigation is {nav}")

    # ---- Explore: node budget, no overlaps, in every grouping and with each cluster opened
    page.goto(BASE + "/explore")
    page.wait_for_selector("[data-ready=explore]")
    states = 0
    for view in ("burns", "goal", "era"):
        page.locator(f"[data-view={view}]").click()
        page.wait_for_timeout(450)
        n_clusters = page.locator("[data-kind=cluster]").count()
        for k in range(-1, n_clusters):
            if k >= 0:
                page.locator(f"[data-view={view}]").click()          # fold back to the overview
                page.wait_for_timeout(350)
                page.locator("[data-kind=cluster]").nth(k).click()
                page.wait_for_timeout(450)
            page.mouse.move(700, 80)                                  # off the nodes: nothing hovered, nothing selected
            page.wait_for_timeout(150)
            n = page.locator("[data-node]").count()
            check(n <= 15, f"explore/{view}/{k}: {n} nodes on screen")
            ov = page.evaluate(OVERLAPS, "[data-label], [data-node] > span:first-child")
            check(not ov, f"explore/{view}/{k}: overlaps {ov[:3]}")
            check(page.locator("main svg line").count() == 0, f"explore/{view}/{k}: edges drawn with nothing selected")
            states += 1
    page.locator("[data-view=burns]").click()
    page.wait_for_timeout(350)
    page.locator("[data-node='inv:BASS-II']").hover()
    page.wait_for_timeout(200)
    lines = page.locator("main svg line").count()
    check(1 <= lines <= 4, f"explore: {lines} relationship lines on hover (expected 1–4)")
    print(f"ok  explore: {states} layouts, no overlap, ≤ 15 nodes, links only on hover ({lines})")

    # ---- provenance: flagged values, plain labels, trail hidden by default
    rows = json.loads(page.request.get(BASE + "/api/tests?include_excluded=true").text())
    flagged = [r for r in rows if r["invalid"]]
    check(len(flagged) >= 1, "no flagged rows in the data to test against")
    for r in flagged:
        page.goto(BASE + f"/data?dataset={r['dataset']}&test={r['test_id']}")
        page.wait_for_selector("[data-ready=provenance]")
        check(page.locator("[data-trail]").count() == 0, f"{r['test_id']}: technical trail visible by default")
        for var in r["invalid"]:
            row = page.locator(f"[data-prov-row={var}]")
            check("Flagged" in row.inner_text(), f"{r['test_id']}.{var}: no Flagged chip")
            check(row.locator("[data-value]").count() == 0, f"{r['test_id']}.{var}: a flagged row renders a value")
        check("Not computed: input flagged" in page.locator("[data-prov-row=o2_pp_kpa]").inner_text(), f"{r['test_id']}: derived value not marked as not computed")
        first = page.locator("[data-prov-row]").first.get_attribute("data-status")
        check(first == "flagged", f"{r['test_id']}: flagged values are not listed first")
        panel = page.locator("aside[role=dialog]").inner_text()
        check("→ 0 kPa" not in panel and "= 0 kPa" not in panel and "g₀" not in panel, f"{r['test_id']}: panel shows a converted impossible value")
        check("Microgravity" in panel or "Earth 1g" in panel, f"{r['test_id']}: gravity is not a regime name")
        check("Assumed (dataset setting)" in panel or r["dataset"] != "flex", f"{r['test_id']}: dataset settings not labelled as assumed")
        check("data/raw" not in panel, f"{r['test_id']}: file paths shown in the normal view")
        page.locator(f"[data-prov-row=pressure_kpa] > button").click()
        check(page.locator("[data-open-source]").is_visible(), f"{r['test_id']}: no link to the source row")
        page.locator("[data-trail-toggle]").check()
        check(page.locator("[data-trail]").count() > 5, f"{r['test_id']}: technical trail did not open")
        # the table itself
        cell = page.locator(f"[data-row='{r['test_id']}']")
        if cell.count():
            check("Flagged" in cell.inner_text(), f"{r['test_id']}: table row does not say Flagged")
    print(f"ok  provenance: {len(flagged)} flagged tests checked ({', '.join(r['test_id'] for r in flagged)})")

    # ---- the judge's question: is this material risky in a Moon base? (≤ 3 clicks, ≤ 60 s)
    page.goto(BASE + "/")
    page.wait_for_selector("[data-ready=home]")
    t0 = time.perf_counter()
    page.locator("[data-start=moon-base]").click()                       # click 1
    page.wait_for_selector("[data-ready=answer]")
    page.locator("[data-material=PMMA]").click()                         # click 2
    page.wait_for_selector("[data-material-shown=PMMA]")
    took = time.perf_counter() - t0
    finding = page.locator("[data-finding]").inner_text()
    check("PMMA" in finding and "Moon" in finding, f"moon-base path: finding is {finding!r}")
    for col, title in (("measured", "What NASA measured"), ("inferred", "What the model infers"), ("untested", "What was never tested")):
        box = page.locator(f"[data-column={col}]")
        check(box.is_visible() and title in box.inner_text() and box.locator("li").count() >= 1, f"moon-base path: column “{title}” missing or empty")
    check(page.locator("[data-grade]").is_visible(), "moon-base path: no evidence grade")
    check(took < 60, f"moon-base path took {took:.1f}s")
    print(f"ok  moon-base question: 2 clicks, {took:.2f} s")

    # ---- keyboard: "/" focuses the ask box, Enter answers
    page.goto(BASE + "/explore")
    page.wait_for_selector("[data-ready=explore]")
    page.keyboard.press("/")
    page.keyboard.type("zebra migration")
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Not covered by available NASA data", timeout=10000)
    print("ok  ask box by keyboard; unanswerable question is refused")
    b.close()

if failed:
    print("\nFAILED:\n  " + "\n  ".join(failed))
    sys.exit(1)
print("\nbrowser acceptance: all checks passed")
