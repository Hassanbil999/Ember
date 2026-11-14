"""Real NASA PSI tables: files are byte-identical to PSI, and the gas-flame adapter reads them faithfully."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from backend.adapters import REGISTRY
from backend.adapters.psi_gas_flames import _yyddd
from backend.core import config
from backend.core.config import RAW
from backend.core.validate import validate

MANIFEST = json.loads((RAW / "psi_manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("ds_id", sorted(MANIFEST))
def test_raw_file_matches_psi_checksum(ds_id):
    """Catches line-ending conversion or hand edits: the file must be exactly what PSI served."""
    m = MANIFEST[ds_id]
    data = (RAW.parents[1] / m["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == m["sha256"], f"{m['path']} differs from the PSI file"


def _load(ds_id):
    cfg = config.datasets()[ds_id]
    res = REGISTRY[cfg["adapter"]](ds_id, cfg)
    df, _ = validate(res.tests, ds_id)
    return cfg, res, df


def _raw(ds_id):
    cfg = config.datasets()[ds_id]
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    return raw[raw["Test"].str.strip() != ""]


def test_cfig_every_row_loaded_with_unique_ids():
    _, _, df = _load("cfig_normal")
    assert len(df) == len(_raw("cfig_normal")) == 179
    assert df.test_id.is_unique and df.test_id.str.startswith("CFIG-").all()
    assert not df.excluded.any()


def test_cfig_outcome_comes_only_from_se_ft_column():
    _, _, df = _load("cfig_normal")
    raw = _raw("cfig_normal")
    end = raw["Self-ext or flow term"].str.strip().str.upper().values
    b = df["burned"].values
    assert all(x == 1 for x, e in zip(b, end) if e == "FT")
    assert all(x == 0 for x, e in zip(b, end) if e == "SE")
    assert all(pd.isna(x) for x, e in zip(b, end) if e not in ("FT", "SE")), "no hot ignition must not become an outcome"


def test_cfig_values_converted_and_traced():
    _, res, df = _load("cfig_normal")
    r = df.set_index("test_id").loc["CFIG-21088D1"]
    assert r.o2_frac == pytest.approx(0.382905163)
    assert r.pressure_kpa == pytest.approx(94.43956)            # 0.9443956 bar
    assert r.fuel_flow_mg_s == 1.0 and r.burned == 1
    assert r.mission_date == "2021-03-29" and r.campaign == "Day 1"
    p = [x for x in res.provenance if x["test_id"] == "CFIG-21088D1"]
    by = {x["variable"]: x for x in p}
    assert by["pressure_kpa"]["raw_value"] == "0.9443956" and by["pressure_kpa"]["column"] == "approx p (bar)"
    assert by["burned"]["column"] == "Self-ext or flow term"
    for v in ("mission_date", "campaign", "test_end"):
        assert by[v]["steps"][0]["op"] == "derive" and by[v]["raw_value"] is None


def test_flame_design_claims_no_outcome():
    _, _, df = _load("flame_design_normal")
    assert len(df) == 207 and df.test_id.is_unique
    assert "burned" not in df.columns or df["burned"].isna().all()
    ramped = _raw("flame_design_normal")["mfuel (mg/s)"].str.upper().str.startswith("RAMP").values
    assert df["fuel_flow_mg_s"].isna().values[ramped].all(), "a ramped flow is not a single value"


def test_yyddd_dates():
    assert _yyddd("21088A1") == "2021-03-29"
    assert _yyddd("19115 B2") == "2019-04-25"
    assert _yyddd("A1") == "" and _yyddd("21999") == ""


def test_new_tables_are_real_and_in_the_store():
    from backend.core.store import get_store
    t = get_store().tests
    for ds in ("cfig_normal", "flame_design_normal"):
        assert not config.datasets()[ds]["demo"]
        assert (t.dataset == ds).sum() > 100 and not t.loc[t.dataset == ds, "demo"].any()




# ------------------------------------------------------------------ solids (BASS-II, BASS, SAFFIRE)
def test_bass2_rows_and_no_invented_outcome():
    cfg, res, df = _load("bass2")
    assert len(df) == 129 and df.test_id.is_unique and not df.excluded.any()
    assert "burned" not in df.columns or df["burned"].isna().all(), "BASS-II has no burned/went-out column"
    assert df.o2_frac.min() == pytest.approx(0.136) and df.o2_frac.max() == pytest.approx(0.222)
    ends = df.test_end.value_counts().to_dict()
    assert ends["Flame went out when the airflow was lowered"] == 17 and ends["Flame blew off when the airflow was raised"] == 7


def test_bass2_reads_text_and_says_so():
    _, res, df = _load("bass2")
    r = df.set_index("test_id").loc["BASS2-O4"]
    assert r.material == "Not named in the table" and r.sample_shape == "rod" and r.diameter_mm == pytest.approx(9.525)   # 3/8 inch
    assert r.o2_frac == pytest.approx(0.148) and r.mission_date == "2014-07-08"
    by = {p["variable"]: p for p in res.provenance if p["test_id"] == "BASS2-O4"}
    assert "Every rod sample that the BASS-II table does name is PMMA" in r.notes and "rather than assumed" in r.notes   # context, never inference
    assert by["test_end"]["raw_value"].startswith("Fan display: 5 0.7")
    assert df.set_index("test_id").loc["BASS2-B1"].thickness_mm == pytest.approx(0.1)  # "100 micron"


def test_saffire2_flight_and_ground_rows():
    _, _, df = _load("saffire2")
    d = df.set_index("test_id")
    assert len(df) == 18 and (df.gravity_g == 0).sum() == 9 and (df.gravity_g == 1).sum() == 9
    for s in ("2-1", "2-2", "2-3", "2-4"):                       # silicone: no spread in microgravity
        assert d.loc[f"SAF2-{s}-UG", "material"] == "Silicone" and d.loc[f"SAF2-{s}-UG", "burned"] == 0
    assert d.loc["SAF2-2-1-1G", "burned"] == 1                    # ... while the same sample burned at 1g
    assert d.loc["SAF2-2-5-UG", "burned"] == 1 and d.loc["SAF2-2-5-UG", "spread_rate_mm_s"] == pytest.approx(2.1)
    assert pd.isna(d.loc["SAF2-2-7-UG", "burned"]) and "Nomex was not ignited" in d.loc["SAF2-2-7-UG", "test_end"]
    assert pd.isna(d.loc["SAF2-2-9-UG", "burned"]) and "anchored at the base" in d.loc["SAF2-2-9-UG", "test_end"]
    assert pd.isna(d.loc["SAF2-2-1-1G", "o2_frac"]), "no oxygen level is given for the ground tests"
    assert d.loc["SAF2-2-6-UG", "material"] == "Not named in the table"               # blank cell is not assumed
    assert "row above names Cotton-fiberglass fabric (SIBAL)" in d.loc["SAF2-2-6-UG", "notes"]


def test_bass_run_list_flags_impossible_dates():
    _, res, df = _load("bass")
    d = df.set_index("test_id")
    assert len(df) == 122 and df.test_id.is_unique
    assert pd.isna(d.loc["BASS-104-50", "mission_date"])
    why = next(p for p in res.provenance if p["test_id"] == "BASS-104-50" and p["variable"] == "mission_date")
    assert "2103" in why["steps"][0]["detail"] and "not corrected" in why["steps"][0]["detail"]
    soot = df[df.test_end.fillna("").str.startswith("Soot")]
    assert len(soot) == 1 and soot.material.isna().all()


def test_no_real_solid_test_reaches_moon_base_oxygen():
    """The fact the Moon-base answer rests on: real solid tests stop at 22.2 % O2."""
    from backend.core.store import get_store
    t = get_store().tests
    solids = t[t.dataset.isin(["bass2", "bass", "saffire1", "saffire2", "saffire3"])]
    assert solids.o2_frac.max() == pytest.approx(0.222)


# ------------------------------------------------------------------ smoke for detection (SAME, SAME-R)
def test_same_expands_same_conditions_rows_and_says_so():
    _, res, df = _load("same")
    d = df.set_index("test_id")
    assert len(df) == 20 and df.test_id.is_unique
    assert set(df.material) == {"Teflon", "Kapton", "Silicone Rubber", "Lampwick", "Dibutyl Phthalate"}
    assert d.loc["SAME-5.3", "smoke_aging_s"] == 1200 and d.loc["SAME-3", "smoke_aging_s"] == 1200   # 20 min, copied from sample 3
    why = next(p for p in res.provenance if p["test_id"] == "SAME-5.3" and p["variable"] == "flow_cm_s")
    assert why["steps"][0]["op"] == "derive" and "same conditions as 1-4" in why["steps"][0]["detail"]
    assert "burned" not in df.columns or df["burned"].isna().all(), "the table records no smoke results"


def test_same_r_rows_ids_and_second_measurements():
    _, _, df = _load("same_r")
    d = df.set_index("test_id")
    assert len(df) == 109 and df.test_id.is_unique                    # test 57 appears under two materials
    assert {"SAMER-LAM-57", "SAMER-TEF-57"} <= set(df.test_id)
    assert d.loc["SAMER-KAP-61a", "smoke_aging_s"] == 807 and d.loc["SAMER-KAP-61", "heater_ratio"] == 1.38
    assert d.loc["SAMER-KAP-61a", "notes"].startswith("Second measurement of the smoke from test 61")
    assert "mission_date" not in df.columns or df["mission_date"].isna().all(), "the table gives no year, so none is invented"




# ------------------------------------------------------------------ the remaining PSI tables
def test_cfi_duplicates_are_excluded_and_logged_not_dropped():
    _, _, df = _load("cfi")
    assert len(df) == 87 and int(df.excluded.sum()) == 8
    assert (df[df.excluded]["flags"].map(lambda f: "duplicate" in f)).all()
    assert df.loc[df.test_id == "CFI-1206", "pressure_kpa"].iloc[0] == pytest.approx(101.325)       # "1 atm"


def test_spice_negative_airflow_is_flagged_and_duration_derived():
    _, res, df = _load("spice")
    bad = df[df["flags"].map(lambda f: "impossible_value" in f)]
    assert len(bad) == 8 and bad.excluded.all() and bad.flow_cm_s.isna().all()        # "-0.28 cm/s" is never converted
    first = df[~df.excluded].iloc[0]
    assert first.burn_time_s == 655 and first.fuel == "ethylene"                         # 14:37:08 -> 14:48:03


def test_bre_flags_typos_and_never_claims_sustained_burning():
    _, _, df = _load("acme_bre")
    flagged = df[df.excluded]
    assert set(flagged.test_id) == {"BRE-2019-03-07-1", "BRE-2019-04-01-1"}              # "3400%", "2100%"
    assert "burned" not in df.columns or df["burned"].isna().all(), "ignition is not sustained burning"
    lit = df[~df.excluded & df.test_end.str.startswith("At least one flame ignited")]
    assert lit.o2_frac.max() == pytest.approx(0.40)


def test_inverse_flame_oxygen_never_enters_cabin_air():
    _, _, df = _load("cfig_inverse")
    assert len(df) == 154 and df.test_id.is_unique
    assert "o2_frac" not in df.columns or df["o2_frac"].isna().all()
    assert df.oxidizer_o2_frac.max() == pytest.approx(0.85)


def test_every_downloaded_psi_table_is_used():
    loaded = {d for d, c in config.datasets().items() if c.get("enabled", True) and not c.get("demo")}
    for ds_id in MANIFEST:
        assert ds_id in loaded or ds_id == "flex2", f"{ds_id} is downloaded but not loaded"
    import yaml

    from backend.core.config import CONFIG
    flex2 = next(i for i in yaml.safe_load((CONFIG / "investigations.yaml").read_text(encoding="utf-8"))["investigations"] if i["id"] == "FLEX-2")
    assert "test matrix" in flex2["test_matrix"].lower(), "FLEX-2's PSI table is a test plan, shown as such"


# ------------------------------------------------------------------ NASA's Researcher's Guide
def test_researchers_guide_is_nasas_file_and_quoted_as_nasa():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fetch_psi", RAW.parents[1] / "scripts" / "fetch_psi.py")
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    folder, name, pinned, _ = fp.DOCUMENTS[0]
    assert hashlib.sha256((RAW / folder / name).read_bytes()).hexdigest() == pinned
    from backend.core.store import get_store
    st = get_store()
    doc = st.documents.loc["researchers-guide-combustion-science"]
    assert not doc.demo and doc.pages == 56 and "NASA" in doc.citation
    ch = st.chunks[st.chunks.doc_id == "researchers-guide-combustion-science"]
    assert len(ch) > 100 and not ch.page.isin([6, 7]).any(), "the table of contents is never quoted"
    assert "Fire Safety" in set(ch.section) and "Solid-Fuel Combustion/Material Flammability" in set(ch.section)


# ------------------------------------------------------------------ SLICE, ACME CLD Flame, ACME s-Flame
def test_cld_never_uses_the_autofilled_fuel_bottle_column():
    _, _, df = _load("acme_cld")
    d = df.set_index("test_id")
    assert len(df) == 32 and df.test_id.is_unique
    assert d.loc["CLD-17324", "fuel"] == "methane"                     # bottle cell says "40% CH5": not a molecule
    assert "'40% CH5'" in d.loc["CLD-17324", "notes"] and "auto-fill" in d.loc["CLD-17324", "notes"]
    assert not df.fuel.fillna("").str.contains(r"ch\d|c2h\d", case=False).any()
    assert d.loc["CLD-17319", "mission_date"] == "2017-11-15"           # YYDDD


def test_sflame_keeps_oxygen_levels_and_rejects_autofilled_diluents():
    _, _, df = _load("acme_sflame")
    d = df.set_index("test_id")
    assert set(df.o2_frac.round(2)) == {0.21, 0.30}
    assert d.loc["SFLAME-19308-1", "o2_frac"] == pytest.approx(0.30) and d.loc["SFLAME-19308-1", "diluent"] == "N2"
    assert pd.isna(d.loc["SFLAME-19256-1", "diluent"]) and "'N3' is not a gas" in d.loc["SFLAME-19256-1", "notes"]
    assert d.loc["SFLAME-20006-1", "fuel"] == "44.4% H2 with CH4"        # a fuel mixture, kept as written
    assert "pressure" in d.loc["SFLAME-19254-1", "notes"] and ("pressure_kpa" not in df or df.pressure_kpa.isna().all())


def test_slice_test_days():
    _, _, df = _load("slice")
    assert len(df) == 12 and df.mission_date.min() == "2012-02-09" and df.mission_date.max() == "2012-03-23"
