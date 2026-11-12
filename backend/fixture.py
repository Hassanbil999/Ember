"""Deterministic demo fixture. SYNTHETIC DATA — never NASA results.

Writes:
  data/raw/flex_demo/flex_droplet_tests.csv     (deliberately messy: mixed units, dupes, gaps)
  data/raw/bass2_demo/bass2_flammability.xlsx   (same)
  data/raw/reports/*.pdf + reports.yaml         (demo reports + compiled context notes)
  data/raw/flex_demo/media/tp_*/                (test-pattern frames; one MP4)
  config/media.yaml                             (links test-pattern media to demo tests)
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .core.config import CONFIG, RAW

SEED = 20260
ATM = 101.325
PSI = 6.894757


def _sig(x):
    return 1 / (1 + np.exp(-x))


# ---------------------------------------------------------------- droplets
FUELS = {  # base K (mm²/s), limiting O2 in N2
    "n-heptane": (0.62, 0.150),
    "methanol": (0.48, 0.170),
    "n-decane": (0.55, 0.155),
    "ethanol": (0.50, 0.165),
}
DIL = {"N2": (1.00, 0.000), "CO2": (0.85, 0.040), "He": (1.15, 0.020)}
FLEX_CAMPAIGNS = [("FLEX-C1", "FLEX", 2009), ("FLEX-C2", "FLEX", 2010), ("FLEX-C3", "FLEX", 2011),
                  ("FLEX2-C1", "FLEX-2", 2013), ("FLEX2-C2", "FLEX-2", 2015)]


def make_droplets(rng: np.random.Generator, n: int = 160) -> pd.DataFrame:
    rows = []
    for i in range(n):
        camp, inv, year = FLEX_CAMPAIGNS[i % len(FLEX_CAMPAIGNS)]
        fuel = rng.choice(list(FUELS), p=[0.4, 0.25, 0.2, 0.15])
        dil = rng.choice(list(DIL), p=[0.6, 0.2, 0.2])
        x = float(np.clip(rng.choice([0.21, rng.uniform(0.12, 0.40)], p=[0.2, 0.8]), 0.1, 0.45))
        p_atm = float(rng.choice([0.5, 0.7, 1.0, 1.0, 1.5, 2.0, 3.0]))
        P = p_atm * ATM
        d0 = float(rng.uniform(1.8, 5.0))
        k0, loi = FUELS[fuel]
        kd, dloi = DIL[dil]
        logit = 22 * (x - loi - dloi) + 0.9 * math.log(P / ATM) - 0.35 * (d0 - 3.2)
        burned = int(rng.random() < _sig(logit))
        K = k0 * (1 + 1.6 * (x - 0.21)) * (P / ATM) ** 0.08 * kd * (1 + 0.03 * (d0 - 3)) * rng.normal(1, 0.04)
        ext_d = np.nan
        if not burned:
            depth = np.clip((loi + dloi + 0.05 - x) / 0.12, 0, 1)
            ext_d = d0 * (0.25 + 0.6 * depth) * rng.normal(1, 0.05)
            if rng.random() > 0.25:      # most extinguished tests report no K
                K = np.nan
        elif d0 > 4.3 and rng.random() < 0.5:   # radiative extinction of large droplets
            ext_d = d0 * rng.uniform(0.15, 0.3)
        rows.append(dict(test_id=f"FX-{i + 1:03d}", campaign=camp, investigation=inv, fuel=fuel, x=x, dil=dil,
                         P=P, p_atm=p_atm, d0=d0, burned=burned, K=K, ext_d=ext_d,
                         date=f"{year}-{1 + (i * 7) % 12:02d}-{1 + (i * 11) % 27:02d}"))
    return pd.DataFrame(rows)


def droplets_to_messy_csv(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    for j, r in df.iterrows():
        style = j % 4
        o2 = [f"{r.x * 100:.1f}%", f"{r.x:.3f}", f"{r.x * 100:.1f}", f"{r.x * 100:.1f} %"][style]
        pr = [f"{r.p_atm:.2f} atm", f"{r.P / PSI:.2f} psi", f"{r.P:.1f} kPa", f"{r.P / 100:.3f} bar"][(j // 3) % 4]
        outcome = ("Burned to completion" if r.burned else
                   ("Flame extinction" if not math.isnan(r.ext_d) else "No ignition"))
        if r.burned and not math.isnan(r.ext_d):
            outcome = "Burned"
        out.append({"Test ID": r.test_id, "Campaign": r.campaign, "Investigation": r.investigation, "Fuel": r.fuel,
                    "O2": o2, "Diluent": r.dil, "Pressure": pr, "D0 (mm)": round(r.d0, 3), "Outcome": outcome,
                    "K (mm^2/s)": "" if math.isnan(r.K) else round(r.K, 4),
                    "Ext. D (mm)": "" if math.isnan(r.ext_d) else round(r.ext_d, 3), "Date": r.date})
    m = pd.DataFrame(out)
    # deliberate dirt for the Refinery
    m.loc[17, "Pressure"] = "0 atm"                        # impossible
    m.loc[[41, 88, 120], "Outcome"] = ""                   # missing outcome
    m.loc[63, "D0 (mm)"] = 12.0                            # implausible size
    m = pd.concat([m, m.loc[[5, 33]]], ignore_index=True)  # duplicates
    return m


# ---------------------------------------------------------------- solids
MATERIALS = {  # base LOC (µg, optimal flow), spread scale (mm/s), thickness options
    "PMMA": (0.165, 3.0, [0.2, 0.5, 1.0]),
    "Cotton-fiberglass fabric": (0.150, 6.0, [0.25]),
    "Nomex-like fabric": (0.205, 2.0, [0.3]),
    "Acetal": (0.170, 2.5, [0.5, 1.0]),
}
BASS_CAMPAIGNS = [("BASS2-C1", 2012, 0.0), ("BASS2-C2", 2012, 0.0), ("BASS2-C3", 2013, 0.0),
                  ("BASS2-C4", 2013, 0.0), ("GND-1", 2012, 1.0)]


def loc_of(mat, U, P, g):
    base = MATERIALS[mat][0]
    if g >= 0.5:  # buoyant 1g reference
        return base + 0.025 - 0.02 * math.log(P / 101.3)
    Ustar = 8.0
    return base + 0.045 * math.log(max(U, 0.3) / Ustar) ** 2 - 0.02 * math.log(P / 101.3)


def make_solids(rng: np.random.Generator, n: int = 140) -> pd.DataFrame:
    rows = []
    for i in range(n):
        camp, year, g = BASS_CAMPAIGNS[i % len(BASS_CAMPAIGNS)]
        mat = rng.choice(list(MATERIALS))
        th = float(rng.choice(MATERIALS[mat][2]))
        x = float(rng.uniform(0.14, 0.40))
        P = float(rng.choice([55.0, 70.3, 101.3, 101.3, 140.0]))
        U = 0.0 if g >= 0.5 else float(np.exp(rng.uniform(math.log(0.6), math.log(40))))
        loc = loc_of(mat, U, P, g)
        burned = int(rng.random() < _sig(32 * (x - loc)))
        spread = np.nan
        if burned:
            spread = MATERIALS[mat][1] * (x - loc + 0.02) * 10 * (max(U, 2) / 8) ** 0.25 / (th / 0.25) ** 0.5
            spread = max(spread, 0.05) * rng.normal(1, 0.06)
        rows.append(dict(test_id=f"BS-{i + 1:03d}", campaign=camp, mat=mat, th=th, x=x, P=P, U=U, g=g,
                         burned=burned, spread=spread, date=f"{year}-{1 + (i * 5) % 12:02d}-{1 + (i * 3) % 27:02d}"))
    return pd.DataFrame(rows)


def solids_to_messy(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for j, r in df.iterrows():
        res = "Burned" if r.burned else ("Self-extinguished" if j % 3 else "No ignition")
        out.append({"Sample": r.test_id, "Campaign": r.campaign, "Material": r.mat, "Thickness [mm]": r.th,
                    "O2 mole frac": round(r.x, 4), "Total P [kPa]": round(r.P, 1), "Flow [mm/s]": round(r.U * 10, 1),
                    "Gravity": "1g" if r.g >= 0.5 else "µg", "Result": res,
                    "Spread rate [mm/s]": None if math.isnan(r.spread) else round(r.spread, 3), "Run date": r.date})
    m = pd.DataFrame(out)
    m.loc[22, "Total P [kPa]"] = 0.0
    m.loc[[50, 97], "Result"] = None
    m.loc[71, "O2 mole frac"] = 1.7          # out of range (typo)
    m = pd.concat([m, m.loc[[12]]], ignore_index=True)
    return m


# ---------------------------------------------------------------- test patterns
def draw_backlit(d_px: float, size: int = 128, bg: int = 225, fg: int = 30, noise: float = 4.0,
                 rng: np.random.Generator | None = None, center=None) -> np.ndarray:
    """Dark disc of diameter d_px on a bright background, supersampled for exact area."""
    ss = 4
    yy, xx = np.mgrid[0:size * ss, 0:size * ss]
    cx, cy = center or (size / 2, size / 2)
    r = d_px / 2 * ss
    inside = ((xx - cx * ss + 0.5) ** 2 + (yy - cy * ss + 0.5) ** 2) <= r * r
    cover = inside.reshape(size, ss, size, ss).mean(axis=(1, 3))
    img = bg - (bg - fg) * cover
    if rng is not None and noise:
        img = img + rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def draw_flame_view(flame_d_px: float, intensity: float, size: int = 128,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """Bright ring (outer diameter flame_d_px) on dark background, RGB."""
    yy, xx = np.mgrid[0:size, 0:size]
    rr = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5)
    R = flame_d_px / 2
    ring = np.exp(-((rr - R * 0.88) / max(R * 0.08, 1.0)) ** 2) * (rr <= R)
    core = 0.25 * np.exp(-(rr / max(R * 0.6, 1)) ** 2)
    v = intensity * (ring + core)
    img = np.stack([v * 255, v * 200, v * 120], axis=-1)
    if rng is not None:
        img += rng.normal(0, 3, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def pattern_series(d0_mm, K, ext_d_mm, px_per_mm, fps, extra_s=2.0):
    """Known ground truth: diameters (mm) per frame and flame on/off."""
    t_end = (d0_mm ** 2 - (ext_d_mm or 0) ** 2) / K
    n = int((t_end + extra_s) * fps)
    ts = np.arange(n) / fps
    d = np.sqrt(np.clip(d0_mm ** 2 - K * ts, (ext_d_mm or 0.05) ** 2, None))
    flame_on = ts < t_end
    return ts, d, flame_on


def write_test_patterns(flex: pd.DataFrame, rng: np.random.Generator) -> list[dict]:
    import imageio.v2 as imageio
    media = []
    burned = flex[(flex.burned == 1) & flex.K.notna() & flex.ext_d.isna()].sort_values("K")
    picks = [burned.iloc[int(q * (len(burned) - 1))] for q in (0.1, 0.5, 0.9)]
    ext = flex[(flex.burned == 0) & flex.K.notna()]
    if len(ext):
        picks.append(ext.iloc[0])
    px_per_mm, fps = 20.0, 5.0
    for k, r in enumerate(picks):
        ext_d = None if math.isnan(r.ext_d) else float(r.ext_d)
        ts, d, on = pattern_series(float(r.d0), float(r.K), ext_d, px_per_mm, fps)
        folder = RAW / "flex_demo" / "media" / f"tp_{r.test_id}"
        (folder / "backlit").mkdir(parents=True, exist_ok=True)
        (folder / "flame").mkdir(parents=True, exist_ok=True)
        frames_b, frames_f = [], []
        for i, (t, di, fo) in enumerate(zip(ts, d, on)):
            b = draw_backlit(di * px_per_mm, rng=rng)
            f = draw_flame_view(di * px_per_mm * (3.2 + 0.4 * t / ts[-1]),
                                (0.95 - 0.35 * t / ts[-1]) if fo else 0.0, rng=rng)
            frames_b.append(b)
            frames_f.append(f)
            if k != 0:
                imageio.imwrite(folder / "backlit" / f"f{i:04d}.png", b)
            imageio.imwrite(folder / "flame" / f"f{i:04d}.png", f)
        common = dict(test_id=r.test_id, dataset="flex_demo", fps=fps, px_per_mm=px_per_mm, t0_s=0.0,
                      kind="test_pattern")
        if k == 0:   # exercise the video path: H.264 MP4
            path = folder / "backlit.mp4"
            w = imageio.get_writer(path, fps=fps, codec="libx264", quality=9, macro_block_size=16,
                                   ffmpeg_params=["-preset", "veryfast"])
            for b in frames_b:
                w.append_data(np.stack([b] * 3, axis=-1))
            w.close()
            media.append(dict(id=f"{r.test_id}-backlit", view="backlit",
                              path=str(path.relative_to(RAW)).replace("\\", "/"), format="mp4", **common))
        else:
            media.append(dict(id=f"{r.test_id}-backlit", view="backlit",
                              path=str((folder / "backlit").relative_to(RAW)).replace("\\", "/"), format="png-seq",
                              **common))
        media.append(dict(id=f"{r.test_id}-flame", view="flame",
                          path=str((folder / "flame").relative_to(RAW)).replace("\\", "/"), format="png-seq", **common))
    return media


# ---------------------------------------------------------------- reports
def _pdf(path: Path, title: str, sections: list[tuple[str, list[str]]], banner: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    ss = getSampleStyleSheet()

    def on_page(c, doc):
        c.saveState()
        c.setFont("Helvetica", 7.5)
        c.drawString(18 * mm, 287 * mm, banner)
        c.drawRightString(192 * mm, 10 * mm, f"page {doc.page}")
        c.restoreState()

    story = [Paragraph(title, ss["Title"]), Spacer(1, 6)]
    for i, (head, paras) in enumerate(sections, 1):
        if i in (3, 5):
            story.append(PageBreak())
        story.append(Paragraph(f"{i}. {head}", ss["Heading2"]))
        for p in paras:
            story.append(Paragraph(p, ss["BodyText"]))
            story.append(Spacer(1, 4))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title=title)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def write_reports(flex: pd.DataFrame, solids: pd.DataFrame) -> None:
    out = RAW / "reports"
    out.mkdir(parents=True, exist_ok=True)
    banner = "DEMO FIXTURE - synthetic text for pipeline testing - NOT a NASA report"

    _pdf(out / "fire_safety_context.pdf", "Microgravity combustion and spacecraft fire safety: context notes", [
        ("The three pillars of fire safety", [
            "NASA spacecraft fire safety rests on three pillars: prevention, detection and suppression.",
            "Prevention covers material selection and flammability limits. Detection covers smoke and aerosol "
            "sensing. Suppression covers extinguishing a fire once it has started.",
        ]),
        ("Investigations by pillar", [
            "Solid material flammability was studied by BASS, BASS-II and the Saffire I to III experiments.",
            "Smoke detection was studied by SAME and SAME-R; DAFT and DAFT-2 measured dust with the same instrument as SAME.",
            "Liquid droplet combustion was studied by FLEX, FLEX-2 and CFI using the MDCA in the Combustion Integrated Rack (CIR).",
            "The ACME project ran six gas-flame experiments, including CFI-G at up to 85% oxygen and E-FIELD Flames. "
            "SPICE and SLICE used the flow duct in the Microgravity Science Glovebox (MSG).",
        ]),
        ("Exploration atmospheres", [
            "The planned Moon base atmosphere is at least 30% oxygen at no more than 10.2 psi, compared with 21% oxygen at 14.7 psi on Earth.",
            "Spacesuits operate with 100% oxygen at 4.3 psi. Higher oxygen fraction widens the range of conditions in which materials burn.",
        ]),
        ("Flow replaces buoyancy", [
            "In microgravity there is no buoyant convection, so the airflow from ventilation replaces buoyancy as the controlling flow.",
            "Some materials burn at lower oxygen concentration in gentle flow in microgravity than they do on Earth.",
        ]),
        ("The partial-gravity gap", [
            "There is no partial-gravity combustion data in the PSI database yet.",
            "Microgravity and normal-gravity results can only bound behavior at lunar or Martian gravity.",
        ]),
        ("Scope", ["Rockets and propellants are out of scope for this platform."]),
    ], "Compiled context notes (platform authors, from the challenge brief) - not a NASA document")

    f = flex
    fb = f[f.burned == 1]
    k_by_fuel = fb.groupby("fuel").K.agg(["min", "max", "mean", "count"])
    k_by_dil = fb.groupby("dil").K.mean()
    low = f[f.x < 0.17]
    high = f[f.x >= 0.21]
    paras = [f"Burning-rate constants for {fuel} droplets that burned to completion ranged from "
             f"{row['min']:.2f} to {row['max']:.2f} mm2/s across {int(row['count'])} tests (mean {row['mean']:.2f} mm2/s)."
             for fuel, row in k_by_fuel.iterrows()]
    _pdf(out / "flex_demo_report.pdf", "Droplet combustion demo report (FLEX-shaped fixture)", [
        ("Purpose", ["This demo report accompanies a synthetic droplet table shaped like FLEX data. "
                     "It exists to test ingestion, search and citation; its numbers are not NASA results."]),
        ("Hardware", ["FLEX-type droplet tests use the Multi-user Droplet Combustion Apparatus (MDCA) inside the "
                      "Combustion Integrated Rack (CIR). A backlit camera view records the droplet and a separate "
                      "view records the flame."]),
        ("Test matrix", [f"The fixture holds {len(f)} droplet tests across {f.campaign.nunique()} campaigns, "
                         f"with oxygen mole fractions from {f.x.min():.2f} to {f.x.max():.2f} and pressures from "
                         f"{f.p_atm.min():.1f} to {f.p_atm.max():.1f} atm. Diluents were nitrogen, carbon dioxide and helium."]),
        ("Burning-rate results", paras + ["Diameter squared decreased linearly with time during quasi-steady burning, "
                                          "consistent with the d2 law."]),
        ("Extinction behavior", [f"Below 17% oxygen, {int((low.burned == 0).sum())} of {len(low)} tests extinguished "
                                 f"before the droplet was consumed. At or above 21% oxygen, {int((high.burned == 0).sum())} "
                                 f"of {len(high)} tests extinguished.",
                                 "Large droplets in microgravity can undergo radiative extinction, where the flame "
                                 "goes out while liquid fuel remains."]),
        ("Diluent effects", [f"Mean burning-rate constant was {k_by_dil.get('N2', float('nan')):.2f} mm2/s in nitrogen, "
                             f"{k_by_dil.get('CO2', float('nan')):.2f} mm2/s in carbon dioxide and "
                             f"{k_by_dil.get('He', float('nan')):.2f} mm2/s in helium.",
                             "Carbon dioxide dilution raised the oxygen needed for sustained burning, consistent with its role as a suppressant."]),
        ("Limits", ["All tests in this fixture are microgravity tests. No partial-gravity tests exist."]),
    ], banner)

    s = solids
    ug = s[s.g < 0.5]
    gentle = ug[(ug.U > 3) & (ug.U < 20) & (ug.burned == 1)]
    oneg = s[(s.g >= 0.5) & (s.burned == 1)]
    rate = s[s.burned == 1].groupby("mat").spread.mean()
    _pdf(out / "bass2_demo_report.pdf", "Solid material flammability demo report (BASS-II-shaped fixture)", [
        ("Purpose", ["This demo report accompanies a synthetic solid-flammability table shaped like BASS-II data. "
                     "Its numbers are not NASA results."]),
        ("Hardware", ["BASS-type tests burn thin solid samples in a flow duct inside the Microgravity Science "
                      "Glovebox (MSG), with controlled oxygen, pressure and flow speed."]),
        ("Test matrix", [f"The fixture holds {len(s)} tests on {s.mat.nunique()} materials, with flow speeds from "
                         f"{ug.U.min():.1f} to {ug.U.max():.1f} cm/s in microgravity and {int((s.g >= 0.5).sum())} "
                         f"normal-gravity reference tests."]),
        ("Flammability boundary", [f"In gentle flow between 3 and 20 cm/s, the lowest oxygen mole fraction with sustained "
                                   f"spread was {gentle.x.min():.3f}. In normal-gravity reference tests the lowest was "
                                   f"{oneg.x.min():.3f}.",
                                   "The extinction boundary is U-shaped in flow speed: very low flow starves the flame of "
                                   "oxygen and high flow blows it off."]),
        ("Flame spread rates", [f"Mean spread rate over {m} was {v:.2f} mm/s." for m, v in rate.items()]),
        ("Limits", ["No partial-gravity data exist in this fixture; microgravity and 1g tests only bound lunar behavior."]),
    ], banner)

    _pdf(out / "detection_suppression_notes.pdf", "Detection and suppression: context notes", [
        ("Smoke detection", ["SAME measured smoke particles produced by overheated spacecraft materials so that detectors "
                             "can be designed for the particle sizes found in spacecraft fires.",
                             "SAME-R repeated and extended these smoke-particle measurements."]),
        ("Background dust", ["DAFT and DAFT-2 measured ambient dust with the same instrument as SAME. Background dust "
                             "matters because detectors must separate smoke from normal cabin aerosol."]),
        ("Suppression", ["FLEX and FLEX-2 studied droplet flame extinguishment in oxygen and diluent atmospheres to "
                         "evaluate fire suppressants such as carbon dioxide.",
                         "BASS and BASS-II included extinguishment by reducing flow or oxygen around burning solids."]),
    ], "Compiled context notes (platform authors) - not a NASA document")

    meta = {"documents": {
        "fire_safety_context.pdf": {"title": "Context notes: microgravity combustion and spacecraft fire safety",
                                    "investigations": ["BASS", "BASS-II", "Saffire-I", "Saffire-II", "Saffire-III", "SAME",
                                                       "SAME-R", "FLEX", "FLEX-2", "CFI", "ACME", "CFI-G",
                                                       "E-FIELD Flames", "SPICE", "SLICE", "DAFT", "DAFT-2"],
                                    "demo": True, "authors": "Freefall Atlas authors", "year": 2026},
        "flex_demo_report.pdf": {"title": "Droplet combustion demo report (FLEX-shaped fixture)",
                                 "investigations": ["FLEX", "FLEX-2"], "demo": True, "authors": "Demo fixture", "year": 2026},
        "bass2_demo_report.pdf": {"title": "Solid material flammability demo report (BASS-II-shaped fixture)",
                                  "investigations": ["BASS-II", "BASS"], "demo": True, "authors": "Demo fixture", "year": 2026},
        "detection_suppression_notes.pdf": {"title": "Context notes: detection and suppression",
                                            "investigations": ["SAME", "SAME-R", "DAFT", "DAFT-2", "FLEX", "BASS"],
                                            "demo": True, "authors": "Freefall Atlas authors", "year": 2026},
    }}
    (out / "reports.yaml").write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")


def build() -> None:
    rng = np.random.default_rng(SEED)
    flex = make_droplets(rng)
    solids = make_solids(rng)
    (RAW / "flex_demo").mkdir(parents=True, exist_ok=True)
    (RAW / "bass2_demo").mkdir(parents=True, exist_ok=True)
    droplets_to_messy_csv(flex, rng).to_csv(RAW / "flex_demo" / "flex_droplet_tests.csv", index=False)
    messy = solids_to_messy(solids)
    with pd.ExcelWriter(RAW / "bass2_demo" / "bass2_flammability.xlsx") as xw:
        pd.DataFrame({"Note": ["DEMO FIXTURE - synthetic, not NASA data"]}).to_excel(xw, sheet_name="README", index=False)
        messy.to_excel(xw, sheet_name="Tests", index=False)
    write_reports(flex, solids)
    media = write_test_patterns(flex, rng)
    header = ("# Media registry. One entry per camera view per test.\n"
              "# kind: footage | test_pattern. Test patterns are synthetic shapes for pipeline tests;\n"
              "# they are never shown as flames or NASA footage. Real footage: drop files in\n"
              "# data/raw/<dataset>/media/ and add an entry with kind: footage.\n")
    (CONFIG / "media.yaml").write_text(header + yaml.safe_dump({"media": media}, sort_keys=False), encoding="utf-8")
    print(f"fixture: {len(flex)} droplet tests, {len(solids)} solid tests, {len(media)} media entries")


if __name__ == "__main__":
    build()
