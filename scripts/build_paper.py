"""Build the research paper: docs/paper/ember_paper.tex -> docs/Ember_Research_Paper.pdf

1. Draws the figures (vector PDF) from the real cleaned NASA data and the trained fire-check models.
2. Writes docs/paper/numbers.tex: the live fire-check examples quoted in the text, as LaTeX macros, so the
   paper never quotes a number the current models do not give.
3. Compiles the LaTeX source with the first engine it finds: $LATEX (a path), tectonic, latexmk or pdflatex.

Run `python run.py ingest all` first. Model-comparison numbers in the .tex are the generated ones in
docs/methods/results.md (`python scripts/evaluate_methods.py`).

    python scripts/build_paper.py            # figures + numbers + PDF
    python scripts/build_paper.py --no-pdf   # figures + numbers only (e.g. to upload docs/paper/ to Overleaf)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PAPER = ROOT / "docs" / "paper"
FIGS = PAPER / "figures"
OUT = ROOT / "docs" / "Ember_Research_Paper.pdf"

COL, WIDE = 3.35, 7.0          # inches: one column and full text width of the 11pt two-column layout
INK, INK2, MUTED, RULE = "#0b0b0b", "#52514e", "#8a8984", "#d9d8d3"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#e4e3de"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.formatter.use_mathtext": True,
    "axes.unicode_minus": False, "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})
O2 = r"O$_2$"


def fig_gas_outcomes(path: Path) -> None:
    """Fig. 1: every CFI-G normal-flame test with an outcome, oxygen vs pressure (one column)."""
    from backend.predict.problems import PROBLEMS
    df = PROBLEMS["gas"].frame()
    fig, ax = plt.subplots(figsize=(COL, 2.35))
    ax.axvspan(25, 33, color=GREY, lw=0, zorder=0)
    ax.text(29, 24, "no tests\nwith an\noutcome", ha="center", va="center", fontsize=6.5, color=INK2)
    out, lit = df[df.burned == 0], df[df.burned == 1]
    ax.scatter(out.o2_pct, out.psi, s=14, marker="s", facecolors="none", edgecolors=BLUE, linewidths=0.8,
               label=f"went out ($n$ = {len(out)})", zorder=2)
    ax.scatter(lit.o2_pct, lit.psi, s=16, marker="o", color=ORANGE, edgecolors="white", linewidths=0.5,
               label=f"stayed lit ($n$ = {len(lit)})", zorder=3)
    ax.scatter([34], [8.2], marker="*", s=70, color=INK, zorder=4)
    ax.annotate("Moon-base air", (34, 8.2), xytext=(25.4, 2.2), fontsize=6.5, color=INK,
                arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.5})
    ax.set_xlabel(f"{O2} in the atmosphere (%)")
    ax.set_ylabel("Pressure (psi)")
    ax.set_xlim(16, 42)
    ax.set_ylim(0, 48)
    ax.grid(axis="y", color=RULE, lw=0.4)
    ax.legend(loc="upper right", frameon=False, handletextpad=0.3, borderaxespad=0.1)
    fig.savefig(path)
    plt.close(fig)


# docs/methods/results.md, section B: AUC mean and spread over 10 campaign splits
COMPARISON = {
    "(a) Gas jets (CFI-G), 133 tests": [("Logistic regression", 0.815, 0.023), ("Random forest", 0.809, 0.031),
                                        ("Gaussian process", 0.830, 0.032)],
    "(b) Droplets (FLEX), 206 tests": [("Logistic regression", 0.757, 0.029), ("Random forest", 0.760, 0.016),
                                       ("Gaussian process", 0.838, 0.013)],
}


def fig_models(path: Path) -> None:
    """Fig. 2: AUC on withheld campaigns (one column, two stacked panels)."""
    fig, axes = plt.subplots(2, 1, figsize=(COL, 2.55), sharex=True)
    for ax, (title, rows) in zip(axes, COMPARISON.items()):
        ys = np.arange(len(rows))[::-1]
        for y, (name, m, s) in zip(ys, rows):
            c = ORANGE if name == "Gaussian process" else BLUE
            ax.errorbar(m, y, xerr=s, fmt="o", color=c, ms=3.8, capsize=2, lw=1.0)
            ax.text(m + s + 0.012, y, f"{m:.3f}", va="center", fontsize=6.5, color=INK)
        ax.axvline(0.5, color=MUTED, lw=0.7, ls="--")
        ax.set_yticks(ys, [r[0] for r in rows])
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_title(title, loc="left", color=INK)
        ax.grid(axis="x", color=RULE, lw=0.4)
    axes[0].text(0.507, 2.0, "baseline", fontsize=6.5, color=INK2, va="center")
    axes[-1].set_xlim(0.48, 0.95)
    axes[-1].set_xlabel("AUC on unseen campaigns")
    fig.tight_layout(h_pad=0.6)
    fig.savefig(path)
    plt.close(fig)


def fig_learned(path: Path) -> dict:
    """Fig. 3 (full width): (a) GP chance map for the most-tested gas fuel; (b) oxygen sweep for a methanol drop."""
    from backend.predict import pipeline, service
    s = pipeline.surface("gas")
    o2, psi = np.array(s["o2"]), np.array(s["psi"])
    Z = np.array([np.nan if v is None else v for v in s["chance"]], float).reshape(len(psi), len(o2))
    line = service.check({"problem": "droplet", "fuel": "methanol", "o2_pct": 21, "psi": 14.7, "d0_mm": 3})["oxygen_line"]

    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDE, 2.35), gridspec_kw={"width_ratios": [1.15, 1]})
    a.set_facecolor(GREY)
    dx, dy = (o2[1] - o2[0]) / 2, (psi[1] - psi[0]) / 2
    im = a.imshow(np.ma.masked_invalid(Z), origin="lower", aspect="auto", cmap="Blues", vmin=0, vmax=1,
                  extent=[o2[0] - dx, o2[-1] + dx, psi[0] - dy, psi[-1] + dy])
    t = s["tests"]
    a.scatter([r["o2_pct"] for r in t if not r["burned"]], [r["psi"] for r in t if not r["burned"]], s=13, marker="s",
              facecolors="white", edgecolors=INK2, linewidths=0.5, label="went out", zorder=3)
    a.scatter([r["o2_pct"] for r in t if r["burned"]], [r["psi"] for r in t if r["burned"]], s=18, color=ORANGE,
              edgecolors=INK, linewidths=0.4, label="stayed lit", zorder=4)
    a.set_xlabel(f"{O2} (%)")
    a.set_ylabel("Pressure (psi)")
    a.set_title(f"(a) Gas jet, {s['fuel'].replace('%', ' %')}: chance it stays lit", loc="left", color=INK)
    a.legend(loc="upper left", frameon=True, framealpha=0.9, edgecolor=RULE)
    cb = fig.colorbar(im, ax=a, fraction=0.05, pad=0.02)
    cb.outline.set_linewidth(0.4)

    pts = [p for p in line["points"] if p["p"] is not None]
    x = np.array([p["o2_pct"] for p in pts])
    b.fill_between(x, [p["low"] for p in pts], [p["high"] for p in pts], color=BLUE, alpha=0.18, lw=0,
                   label="range (10th to 90th percentile, 15 refits)")
    b.plot(x, [p["p"] for p in pts], color=BLUE, lw=1.6, label="Gaussian process")
    rng = np.random.default_rng(0)
    for r in line["tests"]:
        yv = 1.04 if r["burned"] else -0.04
        b.scatter(r["o2_pct"] + rng.uniform(-0.25, 0.25), yv + rng.uniform(-0.015, 0.015), s=6,
                  color=ORANGE if r["burned"] else MUTED, marker="o" if r["burned"] else "s", lw=0, alpha=0.85, zorder=3)
    cross = line["line"]["o2_pct"]
    if cross:
        b.axvline(cross, color=INK, lw=0.7, ls="--")
        b.text(cross + 0.5, 0.18, f"50 % at\n{cross:.1f} % {O2}", fontsize=6.5, color=INK, va="center")
    b.set_ylim(-0.1, 1.1)
    b.set_xlabel(f"{O2} (%)")
    b.set_ylabel("Chance it burns to the end")
    b.set_title("(b) 3 mm methanol drop, 14.7 psi", loc="left", color=INK)
    b.grid(axis="y", color=RULE, lw=0.4)
    b.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False)
    fig.tight_layout(w_pad=1.5)
    fig.savefig(path)
    plt.close(fig)
    vals = [v for v in s["chance"] if v is not None]
    return {"fuel": s["fuel"], "flow": s["held"][0]["value"], "max": max(vals), "cross": cross}


def numbers(learned: dict) -> str:
    """Live fire-check examples, as LaTeX macros."""
    from backend.predict import service
    gas = {"problem": "gas", "fuel": "30% ethane", "o2_pct": 34, "psi": 8.2, "fuel_flow": 1}
    moon, moon_g = service.check(gas), service.check({**gas, "gravity_g": 0.166})
    prop = service.check({**gas, "fuel": "propane"})
    e, nt = moon["estimate"], prop["next_tests"][0]
    falls = ((moon["oxygen_line"] or {}).get("line") or {}).get("falls_with_oxygen") or {}
    pct = lambda v: f"{100 * v:.0f}"  # noqa: E731
    m = {
        "MoonZone": moon["zone"], "MoonP": pct(e["probability"]), "MoonLow": pct(e["low"]), "MoonHigh": pct(e["high"]),
        "MoonPeak": f"{falls.get('from_o2', float('nan')):.0f}", "MoonGZone": moon_g["zone"], "PropZone": prop["zone"],
        "NextOtwo": f"{nt['inputs']['o2_pct']:.1f}", "NextPsi": f"{nt['inputs']['psi']:.1f}",
        "NextFlow": f"{nt['inputs']['fuel_flow']:.2f}", "NextLow": pct(nt["committee_low"]),
        "NextHigh": pct(nt["committee_high"]), "MapFuel": learned["fuel"].replace("%", r"\,\%"),
        "MapFlow": f"{learned['flow']:.2f}", "MapMax": f"{100 * learned['max']:.1f}", "MethCross": f"{learned['cross']:.1f}",
    }
    lines = ["% Generated by scripts/build_paper.py from the live fire check. Do not edit by hand."]
    lines += [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in m.items()]
    return "\n".join(lines) + "\n"


def engine() -> list[str] | None:
    if os.environ.get("LATEX"):
        return [os.environ["LATEX"]]
    for name, args in (("tectonic", ["--keep-logs"]), ("latexmk", ["-pdf", "-interaction=nonstopmode"]),
                       ("pdflatex", ["-interaction=nonstopmode"])):
        if shutil.which(name):
            return [name, *args]
    return None


def compile_pdf() -> Path | None:
    cmd = engine()
    if cmd is None:
        print("No LaTeX engine found (tectonic, latexmk or pdflatex, or set LATEX=<path>). "
              "Figures and numbers are ready in docs/paper/; compile ember_paper.tex there or on Overleaf.")
        return None
    runs = 2 if Path(cmd[0]).stem == "pdflatex" else 1       # pdflatex needs a second pass for references
    for _ in range(runs):
        subprocess.run([*cmd, "ember_paper.tex"], cwd=PAPER, check=True)
    shutil.copyfile(PAPER / "ember_paper.pdf", OUT)
    return OUT


def build(pdf: bool = True) -> Path | None:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig_gas_outcomes(FIGS / "fig1_gas_outcomes.pdf")
    fig_models(FIGS / "fig2_models.pdf")
    learned = fig_learned(FIGS / "fig3_learned.pdf")
    (PAPER / "numbers.tex").write_text(numbers(learned), encoding="utf-8")
    return compile_pdf() if pdf else None


if __name__ == "__main__":
    print(build(pdf="--no-pdf" not in sys.argv) or "figures and numbers written to docs/paper/")
