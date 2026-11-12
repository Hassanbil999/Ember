"""Audit capture: screenshot every screen and record load / interaction timings.

    python tests/audit_capture.py before|after [theme]

Screens → docs/audit/<label>/, numbers → docs/audit/<label>/perf.json.
Needs the API on :8000 and the web app on :3000.

What is measured
  usable_ms   navigation start → the screen's key element exists (Playwright clock)
  fcp / lcp   paint timings reported by the browser
  response    pointerdown → the result of the click is in the DOM (in-page clock, no test overhead)
  inp         longest input-event duration reported by the Event Timing API (Interaction to Next Paint)
  frames      requestAnimationFrame gaps while a view animates or a slider is dragged
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

LABEL = sys.argv[1] if len(sys.argv) > 1 else "after"
THEME = sys.argv[2] if len(sys.argv) > 2 else ("paper" if LABEL == "before" else "void")
BASE = "http://localhost:3000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "audit" / LABEL
OUT.mkdir(parents=True, exist_ok=True)

# (path, selector that proves the screen is usable, screenshot name)
SCREENS = {
    "before": [
        ("/", "text=prevention", "home_atlas"),
        ("/lab", "text=probability it", "simulate"),
        ("/studio", "text=burned", "studio"),
        ("/studio?chart=gap", "text=Moon base", "gapmap"),
        ("/image", "text=TEST PATTERN", "image"),
        ("/refinery", "text=Data quality", "data"),
        ("/workspace", "text=Workspace", "workspace"),
    ],
    "after": [
        ("/", "[data-ready=home]", "home"),
        ("/answer?topic=moon-base", "[data-ready=answer]", "answer_moon_base"),
        ("/answer?topic=iss-cabin", "[data-ready=answer]", "answer_iss"),
        ("/answer?topic=microgravity", "[data-ready=answer]", "answer_microgravity"),
        ("/answer?topic=untested", "[data-ready=answer]", "answer_untested"),
        ("/answer?q=Is%20PMMA%20flammable%20at%2030%25%20oxygen%3F", "[data-ready=answer]", "answer_question"),
        ("/explore", "[data-ready=explore]", "explore"),
        ("/trade", "[data-ready=trade]", "trade"),
        ("/lab", "[data-ready=lab]", "simulate"),
        ("/insights", "[data-ready=insights]", "insights"),
        ("/studio", "[data-ready=studio]", "studio"),
        ("/data", "[data-ready=data]", "data"),
        ("/image", "text=TEST PATTERN", "image"),
    ],
}[LABEL]

VITALS = """() => new Promise(res => {
  const out = {fcp: null, lcp: null};
  const p = performance.getEntriesByType('paint').find(e => e.name === 'first-contentful-paint');
  if (p) out.fcp = Math.round(p.startTime);
  try {
    new PerformanceObserver(l => { const e = l.getEntries(); out.lcp = Math.round(e[e.length-1].startTime); })
      .observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) {}
  setTimeout(() => res(out), 150);
})"""

# in-page instrumentation: click → DOM result, Event Timing durations, frame gaps
PROBE = """
window.__ev = [];
try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__ev.push({name: e.name, dur: e.duration}); })
  .observe({type: 'event', durationThreshold: 16, buffered: true}); } catch (e) {}
window.__arm = (sel) => {
  window.__resp = null;
  let t0 = null;
  const down = (e) => { t0 = performance.now(); window.removeEventListener('pointerdown', down, true); };
  window.addEventListener('pointerdown', down, true);
  const seen = document.querySelector(sel);
  if (seen) seen.setAttribute('data-stale', '1');
  const mo = new MutationObserver(() => {
    const el = document.querySelector(sel + ':not([data-stale])');
    if (el && t0 != null) { window.__resp = Math.round(performance.now() - t0); mo.disconnect(); }
  });
  mo.observe(document.documentElement, {childList: true, subtree: true, attributes: true});
};
window.__frames = (ms) => new Promise(res => {
  const gaps = []; let last = performance.now(); const end = last + ms;
  const tick = (t) => { gaps.push(t - last); last = t; if (t < end) requestAnimationFrame(tick); else res(gaps); };
  requestAnimationFrame(tick);
});
"""


def respond(page, click, selector):
    """ms from pointerdown to `selector` appearing, measured inside the page."""
    page.evaluate("sel => window.__arm(sel)", selector)
    click()
    page.wait_for_function("window.__resp != null", timeout=20000)
    return page.evaluate("window.__resp")


def frame_stats(gaps):
    gaps = sorted(gaps[1:])
    if not gaps:
        return {}
    return {"frames": len(gaps), "median_ms": round(gaps[len(gaps) // 2], 1), "p95_ms": round(gaps[int(len(gaps) * 0.95) - 1], 1),
            "worst_ms": round(gaps[-1], 1), "fps": round(1000 / (sum(gaps) / len(gaps)), 1)}


def inp(page):
    ev = page.evaluate("window.__ev")
    return round(max([e["dur"] for e in ev], default=0))


perf = {"label": LABEL, "theme": THEME, "screens": {}, "interactions": {}}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860})
    key = "freefall-atlas" if LABEL == "before" else "freefall-atlas-2"
    ctx.add_init_script(
        "localStorage.setItem('%s', JSON.stringify({state:{onboarded:true,theme:'%s',role:'researcher',"
        "focus:'all',work:[],wires:[],report:[]},version:0}))" % (key, THEME))
    ctx.add_init_script(PROBE)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for rnd in ("cold", "warm"):          # cold = first visit, warm = revisit
        for path, sel, name in SCREENS:
            t0 = time.perf_counter()
            page.goto(BASE + path)
            ok = True
            try:
                page.wait_for_selector(sel, timeout=30000)
            except Exception:
                ok = False
            usable = round((time.perf_counter() - t0) * 1000)
            v = page.evaluate(VITALS)
            perf["screens"].setdefault(name, {})[rnd] = {"usable_ms": usable, "fcp_ms": v["fcp"], "lcp_ms": v["lcp"], "ok": ok}
            if rnd == "warm":
                page.wait_for_timeout(600)
                page.screenshot(path=str(OUT / f"{name}.png"))
            print(f"{rnd:4} {'ok ' if ok else 'ERR'} {usable:6} ms  {path}")

    I = perf["interactions"]
    if LABEL == "before":
        try:
            page.goto(BASE + "/refinery")
            page.wait_for_selector("text=Data quality")
            row = page.locator("tr", has_text="FX-018").first
            I["open_provenance_ms"] = respond(page, lambda: row.click(timeout=5000), "aside[aria-label=Provenance] table")
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "provenance_FLEX-114.png"))
            I["inp_ms"] = inp(page)
        except Exception as e:
            print("prov click failed:", str(e)[:160])
    else:
        # home → answer (start card)
        page.goto(BASE + "/")
        page.wait_for_selector("[data-ready=home]")
        page.wait_for_timeout(1500)      # a reader takes at least this long to choose a card
        I["home_to_answer_ms"] = respond(page, lambda: page.locator("[data-start=moon-base]").click(), "[data-ready=answer]")
        page.wait_for_timeout(700)
        I["answer_pick_material_ms"] = respond(page, lambda: page.locator("[data-material=PMMA]").click(), "[data-topic][data-material-shown=PMMA]")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "answer_moon_base_PMMA.png"))
        I["inp_answer_ms"] = inp(page)

        # top navigation: answer → Explore
        page.wait_for_timeout(1200)
        I["nav_to_explore_ms"] = respond(page, lambda: page.locator("nav[aria-label=Primary] a", has_text="Explore").click(), "[data-ready=explore]")

        # explore: open a node, switch grouping, open a cluster
        page.goto(BASE + "/explore")
        page.wait_for_selector("[data-ready=explore]")
        page.wait_for_timeout(800)
        page.locator("[data-node='inv:BASS-II']").hover()
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "explore_hover_links.png"))
        I["explore_open_node_ms"] = respond(page, lambda: page.locator("[data-node='inv:BASS-II']").click(), "[data-ready=detail]")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "explore_node_open.png"))
        page.evaluate("window.__f = window.__frames(700)")
        page.locator("[data-view=goal]").click()
        I["explore_switch_view_frames"] = frame_stats(page.evaluate("window.__f"))
        page.wait_for_timeout(450)
        page.screenshot(path=str(OUT / "explore_by_goal.png"))
        page.evaluate("window.__f = window.__frames(700)")
        page.locator("[data-kind=cluster]").first.click()
        I["explore_open_cluster_frames"] = frame_stats(page.evaluate("window.__f"))
        page.mouse.move(700, 90)
        page.wait_for_timeout(450)
        page.screenshot(path=str(OUT / "explore_cluster_open.png"))
        I["inp_explore_ms"] = inp(page)

        # simulator: preset chip and a slider drag
        page.goto(BASE + "/lab")
        page.wait_for_selector("[data-ready=lab]")
        page.wait_for_timeout(1200)
        I["lab_idle_frames"] = frame_stats(page.evaluate("window.__frames(1000)"))
        before = page.locator("[data-sentence]").inner_text()
        page.evaluate("window.__f = window.__frames(900)")
        page.locator("[data-preset=moon_base]").click()
        page.wait_for_function("t => document.querySelector('[data-sentence]').innerText !== t", arg=before, timeout=5000)
        I["lab_preset_frames"] = frame_stats(page.evaluate("window.__f"))
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "simulate_moon_base.png"))
        box = page.locator("[data-slider=o2]").bounding_box()
        page.evaluate("window.__f = window.__frames(1200)")
        page.mouse.move(box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2)
        page.mouse.down()
        for i in range(40):
            page.mouse.move(box["x"] + box["width"] * (0.25 - 0.2 * i / 40), box["y"] + box["height"] / 2)
        page.mouse.up()
        I["lab_slider_drag_frames"] = frame_stats(page.evaluate("window.__f"))
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / "simulate_low_oxygen.png"))
        I["inp_lab_ms"] = inp(page)

        # provenance, three levels
        page.goto(BASE + "/data")
        page.wait_for_selector("[data-ready=data]")
        page.wait_for_timeout(500)
        I["open_provenance_ms"] = respond(page, lambda: page.locator("[data-test=FLEX-114]").first.click(), "[data-ready=provenance]")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "provenance_FLEX-114.png"))
        I["provenance_open_row_ms"] = respond(page, lambda: page.locator("[data-prov-row=pressure_kpa] > button").click(), "[data-open-source]")
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "provenance_FLEX-114_level2.png"))
        page.locator("[data-open-source]").click()
        page.wait_for_selector("[data-ready=source-row] table")
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "provenance_FLEX-114_source_row.png"))
        page.keyboard.press("Escape")
        page.locator("[data-trail-toggle]").check()
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUT / "provenance_FLEX-114_level3.png"))
        I["inp_data_ms"] = inp(page)

        # light theme, for the record
        light = b.new_context(viewport={"width": 1440, "height": 860})
        light.add_init_script("localStorage.setItem('freefall-atlas-2', JSON.stringify({state:{theme:'paper',role:'researcher',report:[]},version:0}))")
        page = light.new_page()
        for path, sel, name in [("/", "[data-ready=home]", "light_home"), ("/explore", "[data-ready=explore]", "light_explore"),
                                ("/lab", "[data-ready=lab]", "light_simulate"), ("/answer?topic=moon-base", "[data-ready=answer]", "light_answer"),
                                ("/data?test=FLEX-114", "[data-ready=provenance]", "light_provenance"), ("/trade", "[data-ready=trade]", "light_trade")]:
            page.goto(BASE + path)
            page.wait_for_selector(sel)
            page.wait_for_timeout(700)
            page.screenshot(path=str(OUT / f"{name}.png"))
    perf["page_errors"] = errors[:10]
    b.close()

(OUT / "perf.json").write_text(json.dumps(perf, indent=1), encoding="utf-8")
print(json.dumps(perf["interactions"], indent=1), "\npage errors:", len(errors))
