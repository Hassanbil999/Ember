"""Build the README illustrations from the running app and the real results (python scripts/readme_assets.py).
Needs the app on :8000 and docs/methods/results.md (python scripts/evaluate_methods.py).

docs/assets/hero.gif              the demo path: landing → simulation at Moon-base air → ignite → fire check
docs/assets/screen-*.png          simulation with verdict, fire check with nearest NASA tests, statistics
docs/assets/validation.png        (a) every CFI-G gas-flame test with an outcome, the 25–33 % gap and Moon-base air;
                                  (b) AUC on unseen campaigns per model, mean ± spread over 10 partitions
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "assets"
BASE = "http://127.0.0.1:8000"
SIM = "/engine?g=0.166&o2=34&p=8.2&u=10&mat=fabric&preset=moon"
CHECK = "/engine/check?problem=gas&fuel=30%25+ethane&o2=34&psi=8.2&flow=1&g=0"


def screens_and_gif():
    from PIL import Image
    from playwright.sync_api import sync_playwright
    frames: list[Image.Image] = []
    durations: list[int] = []

    def grab(pg, n=1, wait=0, hold=250):
        for _ in range(n):
            if wait:
                pg.wait_for_timeout(wait)
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
            frames.append(im.resize((1200, int(im.height * 1200 / im.width)), Image.LANCZOS))
            durations.append(hold)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        # stills
        pg.goto(BASE + SIM); pg.wait_for_timeout(2500)
        pg.locator("#igniteBtn").click(); pg.wait_for_timeout(2500)
        pg.screenshot(path=str(OUT / "screen-simulation.png"))
        pg.goto(BASE + CHECK); pg.wait_for_timeout(3000)
        pg.screenshot(path=str(OUT / "screen-fire-check.png"))
        pg.goto(BASE + "/engine/stats"); pg.wait_for_timeout(3000)
        pg.screenshot(path=str(OUT / "screen-statistics.png"))
        # the GIF, about 9 s: still pages are one frame held, the burning flame is animated
        pg.goto(BASE + "/"); pg.wait_for_timeout(2500); grab(pg, hold=1800)
        pg.goto(BASE + SIM); pg.wait_for_timeout(2500); grab(pg, hold=1000)
        pg.locator("#igniteBtn").click(); grab(pg, 12, 250)
        pg.goto(BASE + CHECK); pg.wait_for_timeout(2500); grab(pg, hold=3200)
        b.close()
    pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(OUT / "hero.gif", save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)


def validation_chart():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from backend.predict.problems import PROBLEMS
    g = PROBLEMS["gas"].frame()
    res = (ROOT / "docs" / "methods" / "results.md").read_text(encoding="utf-8")

    def auc(section: str):
        block = res.split(section, 1)[1].split("###", 1)[0]
        rows = re.findall(r"\| (Logistic regression|Random forest|Gaussian process)[^|]*\| ([\d.]+) ± ([\d.]+) \|", block)
        return [(m, float(a), float(s)) for m, a, s in rows]

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 11})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    a1.axvspan(25, 33, color="#e9e6e0", zorder=0)
    a1.text(29, 46, "no tests with\nan outcome", ha="center", va="top", fontsize=10, color="#555")
    out, lit = g[g.burned == 0], g[g.burned == 1]
    a1.scatter(out.o2_pct, out.psi, marker="s", facecolors="none", edgecolors="#2a64c9", s=34, label=f"went out (n = {len(out)})")
    a1.scatter(lit.o2_pct, lit.psi, marker="o", color="#d4561e", s=34, label=f"stayed lit (n = {len(lit)})")
    a1.scatter([34], [8.2], marker="*", color="black", s=180, zorder=5, label="Moon-base air (34 %, 8.2 psi)")
    a1.set(xlabel="Oxygen in the atmosphere (%)", ylabel="Pressure (psi)", xlim=(16, 42), ylim=(0, 48),
           title="(a) Every NASA CFI-G gas-flame test with an outcome")
    a1.legend(loc="upper left", fontsize=9, frameon=False)
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
    gas, drop = auc("### Gas leak flame"), auc("### Liquid fuel droplet")
    labels = [m for m, _, _ in gas]
    y = range(len(labels))
    a2.errorbar([a for _, a, _ in gas], [i + 0.15 for i in y], xerr=[s for _, _, s in gas], fmt="o", color="#d4561e", capsize=3, label="gas flames (CFI-G, 133 tests)")
    a2.errorbar([a for _, a, _ in drop], [i - 0.15 for i in y], xerr=[s for _, _, s in drop], fmt="s", color="#2a64c9", capsize=3, label="fuel drops (FLEX, 206 tests)")
    a2.axvline(0.5, ls="--", color="#888"); a2.text(0.505, -0.6, "baseline (0.5)", fontsize=9, color="#666")
    a2.set_yticks(list(y), labels); a2.set_xlim(0.45, 0.95); a2.set_ylim(-0.8, len(labels) - 0.4)
    a2.set(xlabel="AUC on NASA test campaigns the model never saw", title="(b) Models vs baseline (10 partitions)")
    a2.legend(loc="lower right", fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "validation.png", dpi=110)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    validation_chart()
    screens_and_gif()
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size / 1e6:.2f} MB")
