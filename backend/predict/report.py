"""The engineering report: a fixed template filled from one fire-check result. No generated prose: every
sentence is a template and every number comes from the result, the model card or a cited source.
Self-contained HTML in the app's typefaces; prints to PDF from any browser (print styles included)."""
from __future__ import annotations

import html
from datetime import datetime
from functools import lru_cache

e = lambda v: html.escape("" if v is None else str(v))  # noqa: E731

ZONE = {"tested": ("Tested", "NASA tests at nearly these conditions"),
        "estimated": ("Estimated", "Model estimate between NASA tests of this fuel"),
        "untested": ("Untested", "Outside what NASA tested: no estimate")}


@lru_cache(maxsize=1)
def _dois() -> dict:
    """investigation -> (PSI id, DOI), from the team's verified list in config/investigations.yaml."""
    import yaml

    from ..core.config import CONFIG
    try:
        y = yaml.safe_load((CONFIG / "investigations.yaml").read_text(encoding="utf-8"))
        items = y.get("investigations", y) if isinstance(y, dict) else y
        out = {}
        for it in (items.values() if isinstance(items, dict) else items):
            if isinstance(it, dict) and it.get("psi_ids"):
                pid = it["psi_ids"][0]
                out[it.get("id") or it.get("name")] = (pid, (it.get("dois") or {}).get(pid))
        return out
    except Exception:
        return {}


def _pct(p: float) -> str:
    return f"{p * 100:.0f} %"


def _table(head: list[str], rows: list[list[str]], num: set[int] = frozenset()) -> str:
    th = "".join(f'<th class="{"n" if i in num else ""}">{h}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _line_svg(ol: dict, entered: float | None, yes: str, no: str) -> str:
    """Static SVG of the oxygen line for print (same encoding as the app's chart, light colours)."""
    W, H, ml, mr, mt, mb = 640, 262, 44, 14, 30, 50
    row_yes, row_no = 14, H - mb + 14       # outcome rows outside the plot
    iw, ih = W - ml - mr, H - mt - mb
    pts = ol["points"]
    x0, x1 = pts[0]["o2_pct"], pts[-1]["o2_pct"]
    X = lambda o: ml + (min(x1, max(x0, o)) - x0) / (x1 - x0) * iw  # noqa: E731
    Y = lambda p: mt + (1 - p) * ih  # noqa: E731
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Chance it keeps going as oxygen changes">',
           '<defs><pattern id="h" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
           '<line x1="0" y1="0" x2="0" y2="6" stroke="#cdd3de" stroke-width="2"/></pattern></defs>']
    run = None
    for i, p in enumerate(pts):
        if p["p"] is None and run is None:
            run = p["o2_pct"]
        if run is not None and (p["p"] is not None or i == len(pts) - 1):
            end = p["o2_pct"] if p["p"] is None else pts[i - 1]["o2_pct"]
            out.append(f'<rect x="{X(run):.1f}" y="{mt}" width="{max(2, X(end) - X(run)):.1f}" height="{ih}" fill="url(#h)"><title>untested</title></rect>')
            run = None
    for p in (0, 0.5, 1):
        dash = ' stroke-dasharray="4 4"' if p == 0.5 else ""
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="#d5dae4"{dash}/>'
                   f'<text x="{ml - 6}" y="{Y(p) + 4:.1f}" text-anchor="end" class="ax">{p * 100:.0f}%</text>')
    t = 5 * -(-x0 // 5)
    while t <= x1:
        out.append(f'<text x="{X(t):.1f}" y="{H - 6}" text-anchor="middle" class="ax">{t:g}</text>')
        t += 5
    out.append(f'<text x="{W - mr}" y="{H - 20}" text-anchor="end" class="ax">oxygen, %</text>')
    est = [p for p in pts if p["p"] is not None]
    if len(est) > 1:
        up = "L".join(f'{X(p["o2_pct"]):.1f},{Y(p["high"]):.1f}' for p in est)
        dn = "L".join(f'{X(p["o2_pct"]):.1f},{Y(p["low"]):.1f}' for p in reversed(est))
        out.append(f'<path d="M{up}L{dn}Z" fill="#0d121e" opacity="0.10"/>')
        out.append('<path d="M' + "L".join(f'{X(p["o2_pct"]):.1f},{Y(p["p"]):.1f}' for p in est) + '" fill="none" stroke="#0d121e" stroke-width="2"/>')
    L = ol["line"]
    if L and L["o2_pct"] is not None:
        out.append(f'<line x1="{X(L["o2_pct"]):.1f}" x2="{X(L["o2_pct"]):.1f}" y1="{Y(0.5) - 8:.1f}" y2="{Y(0.5) + 8:.1f}" stroke="#0d121e" stroke-width="2"/>'
                   f'<text x="{X(L["o2_pct"]) - 6:.1f}" y="{Y(0.5) - 6:.1f}" text-anchor="end" class="lab">50 % at {L["o2_pct"]:g} %</text>')
    if entered is not None:
        ex = X(entered)
        right = ex > W - mr - 90
        out.append(f'<line x1="{ex:.1f}" x2="{ex:.1f}" y1="{mt}" y2="{mt + ih}" stroke="#5b6478" stroke-width="1.5" stroke-dasharray="2 3"/>'
                   f'<text x="{ex - 5 if right else ex + 5:.1f}" y="{mt + 13}" text-anchor="{"end" if right else "start"}" class="lab">yours {entered:g} %</text>')
    for tt in ol["tests"]:
        c = "#b85f17" if tt["burned"] else "#2369bf"
        cy = row_yes if tt["burned"] else row_no
        fill, stroke, sw = (c, "#fff", 2) if tt["near_settings"] else ("none", c, 1.5)
        label = f'{tt["code"]}: {yes if tt["burned"] else no} at {tt["o2_pct"]:g} % oxygen'
        out.append(f'<circle cx="{X(tt["o2_pct"]):.1f}" cy="{cy}" r="4" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"><title>{e(label)}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def verdict(res: dict) -> str:
    """One template sentence; never more than the result supports."""
    z, est, t = res["zone"], res["estimate"], res["tested"]
    if z == "untested":
        return "No estimate: these conditions are outside what NASA tested for this fuel. The nearest real tests are listed for reference."
    s = ""
    if t:
        if t["n"] == 1:
            s += f"The one NASA test at nearly these conditions {t['outcome_yes'] if t['yes'] else t['outcome_no']}. "
        else:
            s += f"{t['yes']} of the {t['n']} NASA tests at nearly these conditions {t['outcome_yes']}. "
    if est:
        s += (f"Model estimate: {_pct(est['probability'])} chance it {est['will']} "
              f"(likely range {_pct(est['low'])}–{_pct(est['high'])}, from models refitted on resampled NASA campaigns).")
        if t is not None and "agrees" in t:
            s += " The model agrees with those tests." if t["agrees"] else " The model disagrees with those tests: trust the tests."
    return s


def render(res: dict, stamp: datetime) -> str:
    m = res["model"]
    psi_id, doi = _dois().get(m["investigation"], (None, None))
    psi_id = psi_id or m["psi_id"]
    zl, zd = ZONE[res["zone"]]
    parts = []

    parts.append(f'<section><h2>Conditions entered</h2>{_table(["Input", "Value"], [[e(r["label"]), e(r["value"])] for r in res["inputs"]])}</section>')

    v = f'<div class="verdict z-{res["zone"]}"><span class="zone">{zl}</span><span class="zd">{zd}</span></div><p class="lead">{e(verdict(res))}</p>'
    if res["reasons"]:
        v += "<ul>" + "".join(f"<li>{e(r)}</li>" for r in res["reasons"]) + "</ul>"
    parts.append(f"<section><h2>Result</h2>{v}</section>")

    rows = []
    if res["estimate"]:
        est = res["estimate"]
        rows.append([e(f"Chance it {est['will']}"), _pct(est["probability"]), f"{_pct(est['low'])}–{_pct(est['high'])}", e(est["model"])])
    for q in res["quantities"]:
        rows.append([e(f"{q['label']} ({q['unit']})"), f"{q['value']:.3g}", f"{q['low']:.3g}–{q['high']:.3g} (90 %)", e(q["model"])])
    if rows:
        parts.append(f'<section><h2>Estimates</h2>{_table(["Quantity", "Estimate", "Range", "Model"], rows, {1, 2})}'
                     '<p class="note">Chance range: 10th–90th percentile of 15 models, each refitted on NASA campaigns drawn with replacement (tests in one campaign are not independent). It shows how much the answer depends on which campaigns were run; it is not a guarantee. '
                     'Measured-quantity range: 90 % of the errors on unseen campaigns were smaller than this (split-conformal).</p></section>')

    near = res["nearest"]
    if near:
        extra = "Fuel flow (mg/s)" if res["problem"] == "gas" else "Drop size (mm)"
        nrows = []
        for r in near:
            oc = "b" if r["burned"] else "o"
            nrows.append([f'<span class="mono">{e(r["code"])}</span>', e(r["fuel"]), f'{r["o2_pct"]:g}', f'{r["psi"]:g}',
                          f'{r.get("fuel_flow", r.get("d0_mm")):g}', f'<span class="oc-{oc}">{e(r["outcome"])}</span>',
                          f'{r["distance"]:.2f}{" · close" if r["close"] else ""}',
                          e(f'{m["investigation"]} table, row {r["source_row"]}' if r["source_row"] else m["investigation"])])
        parts.append(f'<section><h2>Nearest NASA tests (same fuel)</h2>'
                     f'{_table(["Test", "Fuel", "O₂ %", "psi", extra, "Measured outcome", "Distance", "Source"], nrows, {2, 3, 4, 6})}'
                     '<p class="note">Distance: inputs scaled by their spread in the NASA tests; “close” means nearer than half of the tests are to their own nearest neighbour.</p></section>')

    if res["drivers"]:
        drows = [[e(d["label"]), e(f'+{d["step"]:g} {d["unit"]}'.strip()), f'{d["change_pts"]:+.1f} pts'] for d in res["drivers"]]
        parts.append(f'<section><h2>What moves the estimate</h2>{_table(["Input", "Change", "Change in chance"], drows, {2})}'
                     '<p class="note">Each input raised by a tenth of its tested range, the others held. Read as direction and size near these conditions, not as a law.</p></section>')

    ol = res.get("oxygen_line")
    if ol:
        entered = next((float(str(r["value"]).split()[0]) for r in res["inputs"] if r["label"] == "Oxygen"), None)
        yes = res["estimate"]["outcome_yes"] if res["estimate"] else ("stayed lit" if res["problem"] == "gas" else "burned to the end")
        no = res["estimate"]["outcome_no"] if res["estimate"] else ("went out on its own" if res["problem"] == "gas" else "flame died with fuel left")
        L = ol["line"]
        if L and L["o2_pct"] is not None:
            lo, hi = L["range"] or (None, None)
            rng = f'{lo:.3g} %' if lo is not None else "below the estimated range"
            rng += f' to {hi:g} %' if hi is not None else " to beyond the estimated range"
            lead = f'The estimated chance passes 50 % at about <b>{L["o2_pct"]:g} % oxygen</b> (models disagree from {rng}).'
        elif L:
            lead = f'Where an estimate is allowed, the chance stays between {_pct(L["min_p"])} and {_pct(L["max_p"])}: it does not pass 50 %.'
        else:
            lead = "No estimate anywhere on this line: these settings are outside what NASA tested for this fuel. Only the real tests are shown."
        warn = ""
        if L and L.get("falls_with_oxygen"):
            warn = (f'<p class="note warn">Physics check: the estimate falls as oxygen rises above {L["falls_with_oxygen"]["from_o2"]:g} %. '
                    "More oxygen is expected to help a flame, so this probably reflects other differences between those NASA tests "
                    "(their exact flow or pressure), not oxygen itself. Read that part with caution.</p>")
        parts.append(f'<section><h2>Where is the line? Oxygen, everything else as entered</h2><p>{lead}</p>'
                     f'{_line_svg(ol, entered, yes, no)}{warn}'
                     f'<p class="note">Held as entered: {e(", ".join(ol["held"]).lower())}. Line: the model used ({e(m["chosen"])}); band: lowest and highest of the 15 campaign-bootstrap models. '
                     f'Hatched: untested, no estimate. Dots: NASA tests of this fuel, top row {e(yes)}, bottom row {e(no)}; filled = near your other settings, hollow = at other settings.</p></section>')

    nt = res.get("next_tests") or []
    if nt:
        nrows = []
        for n in nt:
            cond = " · ".join(f'{e(n["labels"][k])} {v:.3g}{(" " + e(n["units"][k])) if n["units"][k] else ""}' for k, v in n["inputs"].items())
            nrows.append([cond, f'{_pct(n["committee_low"])}–{_pct(n["committee_high"])}',
                          f'<span class="mono">{e(n["nearest_test"])}</span> ({"kept going" if n["nearest_burned"] else "went out"}), {n["nearest_distance"]:g} away'])
        parts.append(f'<section><h2>Tests that would teach the model most</h2>'
                     f'{_table(["Conditions (same fuel)", "Five models say", "Nearest NASA test of this fuel"], nrows, {1})}'
                     f'<p class="note">Query by committee (Seung, Opper and Sompolinsky, 1992): the five models, each trained without some NASA campaigns, disagree most here, '
                     f'so one test here narrows the answer most. Candidates stay inside what the {e(m["investigation"])} hardware has already done, away from existing tests of this fuel and near your settings.</p></section>')

    ref = res.get("reference")
    if ref:
        if ref["values"]:
            body = _table(["Fuel", "Inert gas: nitrogen", "Inert gas: CO₂"], [[e(ref["fuel"]), f'{ref["values"]["N2"]:g} % O₂', f'{ref["values"]["CO2"]:g} % O₂']], {1, 2})
        else:
            body = f'<p>{e(ref["missing"])}</p>'
        parts.append(f'<section><h2>Reference: Earth limiting oxygen (not NASA test data)</h2>{body}'
                     f'<p class="note">{e(ref["meaning"])} {e(ref["note"])} Source: <a href="{e(ref["source"]["url"])}">{e(ref["source"]["label"])}</a>.</p></section>')

    crows = []
    for r in m["comparison"]:
        chosen = r["model"] == m["chosen"]
        crows.append([e(r["model"]) + (" <b>· used</b>" if chosen else ""), "—" if r.get("auc") is None else f'{r["auc"]:.3f}',
                      f'{r["brier"]:.4f}', f'{r["log_loss"]:.4f}', f'{r["accuracy"]:.3f}',
                      "—" if "beats_baseline" not in r else ("yes" if r["beats_baseline"] else "no")])
    parts.append(f'<section><h2>Model and validation</h2>'
                 f'<p>Trained on {m["n_tests"]} {e(m["investigation"])} tests ({e(psi_id)}) with a measured outcome, from {m["n_campaigns"]} NASA test campaigns. '
                 f'Validation: {e(m["validation"])}: each campaign is hidden during training and then predicted. '
                 'A model is used only if it beats the baseline on both Brier score and log loss.</p>'
                 f'{_table(["Model", "AUC", "Brier", "Log loss", "Accuracy", "Beats baseline"], crows, {1, 2, 3, 4})}'
                 '<p class="note">AUC: how often a test that burned is ranked above one that did not (0.5 = chance). Brier and log loss: error of the probabilities (lower is better). '
                 'Accuracy is shown but not used: when one outcome is common, always guessing it already scores high.</p>'
                 + (f'<p>Improvement over always guessing the average (Brier skill): <b>{m["skill"] * 100:.0f} %</b>. '
                    'Small datasets: read the estimate as a screening value, not a precise probability.</p>' if m.get("skill") is not None else "")
                 + (_table(["Predicted chance (unseen campaigns)", "Observed share", "Tests"],
                           [[_pct(c["predicted"]), _pct(c["observed"]), str(c["n"])] for c in m.get("calibration", [])], {0, 1, 2})
                    + '<p class="note">Calibration: tests sorted by predicted chance into five equal groups. Close numbers in a row mean the chances can be read at face value.</p>'
                    if m.get("calibration") else "")
                 + '</section>')

    parts.append('<section><h2>Limits</h2><ul>'
                 '<li>All NASA tests used here ran in microgravity. Gravity is not something the model has learned.</li>'
                 '<li>NASA test fuels stand in for cabin fluids: heptane is similar to kerosene-type liquids, methanol to alcohols, ethane/propane/butane to gas leaks.</li>'
                 '<li>Solid materials (fabric, plastics, wire insulation) are not covered: their loaded tables record no burned/went-out outcome.</li>'
                 '<li>A screening estimate for early design and test planning. It does not certify a material or a design.</li></ul></section>')

    src = f'NASA Physical Sciences Informatics, {e(m["investigation"])} experimental table ({e(psi_id)})'
    if doi:
        src += f', <a href="https://doi.org/{e(doi)}">doi:{e(doi)}</a>'
    parts.append(f"<section><h2>Sources</h2><p>{src}.</p></section>")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fire check report · {e(res["label"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<header><div><h1>Ember</h1><span class="kicker">Fire check report</span></div>
<div class="meta"><span>{e(res["label"])} · {e(res["question"])}</span><span class="mono">{stamp:%Y-%m-%d %H:%M} UTC</span>
<button onclick="window.print()">Print / save as PDF</button></div></header>
{''.join(parts)}
<footer>Generated by Ember from NASA's own test tables. Every number above traces to a NASA test row, the model's validation, or the cited source.</footer>
</main></body></html>"""


CSS = """
:root{--ink:#0d121e;--muted:#5b6478;--line:#d5dae4;--soft:#eef1f6;--burn:#b85f17;--cool:#2369bf;
--fd:'Barlow Condensed','Arial Narrow',sans-serif;--fb:'IBM Plex Sans',system-ui,sans-serif;--fm:'IBM Plex Mono',ui-monospace,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:#f6f7fa;color:var(--ink);font:14px/1.5 var(--fb)}
main{max-width:920px;margin:24px auto;background:#fff;border:1px solid var(--line);border-radius:10px;padding:28px 32px}
header{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:12px;flex-wrap:wrap}
h1{margin:0;font:600 26px/1 var(--fd);letter-spacing:.06em;text-transform:uppercase}
.kicker{font:500 12px var(--fm);color:var(--muted)}
.meta{display:flex;flex-direction:column;align-items:flex-end;gap:4px;font-size:12.5px;color:var(--muted)}
.meta button{font:500 12.5px var(--fb);border:1px solid var(--line);background:#fff;border-radius:6px;padding:5px 10px;cursor:pointer;color:var(--ink)}
section{margin-top:22px}h2{margin:0 0 8px;font:600 14px var(--fd);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:500;color:var(--muted);font-size:11.5px;background:var(--soft)}td.n,th.n{text-align:right;font-family:var(--fm);font-variant-numeric:tabular-nums}
.mono{font-family:var(--fm)}.oc-b{color:var(--burn)}.oc-o{color:var(--cool)}
.verdict{display:flex;gap:12px;align-items:baseline}.zone{font:600 22px var(--fd);letter-spacing:.06em;text-transform:uppercase;border:1.5px solid currentColor;border-radius:999px;padding:1px 12px}
.z-tested .zone{color:#1d7a46}.z-estimated .zone{color:#8a5a00}.z-untested .zone{color:var(--muted)}.zd{color:var(--muted);font-size:13px}
.lead{font-size:15px;margin:10px 0 0;max-width:75ch}ul{margin:8px 0 0;padding-left:20px}li{margin:3px 0}
.note{font-size:12px;color:var(--muted);margin:6px 0 0;max-width:85ch}a{color:var(--cool)}
svg.chart{width:100%;height:auto;display:block;margin-top:8px}.ax{font:11px var(--fm);fill:var(--muted)}.lab{font:500 11.5px var(--fb);fill:var(--ink)}
.warn{color:#8a5a00}
footer{margin-top:26px;padding-top:10px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}
@media print{body{background:#fff}main{border:0;margin:0;padding:0;max-width:none}.meta button{display:none}section{break-inside:avoid}}
"""
