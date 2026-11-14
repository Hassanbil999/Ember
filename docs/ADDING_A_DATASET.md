# Adding a dataset

New NASA data plugs in without touching the UI or the core. You need a raw file, a YAML entry, and — only if the file has a new shape — an adapter.

## 1. Drop the raw files

```
data/raw/<dataset_id>/your_table.csv      (or .xlsx)
data/raw/<dataset_id>/media/...           (optional: video or image sequences)
data/raw/reports/your_report.pdf          (optional: PDFs go in the reports folder)
```

## 2. Register it in `config/datasets.yaml`

```yaml
datasets:
  flex2_real:
    title: FLEX-2 droplet tests (PSI)
    adapter: flex_droplets          # reuse an existing adapter if the shape matches
    enabled: true
    demo: false                     # real data: no demo badge
    investigations: [FLEX-2]
    files: [flex2_tests.csv]
    license: "NASA PSI terms of use"
    doi: "10.xxxx/…"                # fill from PSI
    source_urls: ["https://psi.nasa.gov/…"]
    columns:                        # raw column → canonical variable (config/variables.yaml)
      "Run": test_id
      "Increment": campaign
      "Fuel": fuel
      "Oxygen (%)": o2_frac         # units come from the header "(…)"/"[…]" or the cell ("14.7 psi")
      "Chamber P (psia)": pressure_kpa
      "Do (mm)": d0_mm
      "Result": burned
      "K (mm2/s)": burn_rate_k_mm2_s
    units: { "Chamber P (psia)": psi }   # optional override when the header has no unit
    constants: { gravity_g: 0.0, flow_cm_s: 0.0 }
    outcome_map: { "burned": 1, "extinguished": 0, "no ignition": 0 }
```

Also add the investigation id to that investigation's `datasets:` list in `config/investigations.yaml`, so the catalog groups them under the right investigation.

New variables (a new measured quantity) go in `config/variables.yaml` with `unit`, `kind`, `role`, `synonyms` and, optionally, `valid_range` / `plausible_range`. Validation rules are generic and live under `validation:` in `datasets.yaml`.

## 3. Run

```
python run.py ingest      # canonical (adapters → validation → chunks → index) → existing (map to the SPEC §5 tables) → seed → fit
```

Every number keeps its raw value, source row and conversion steps: `GET /api/test/<id>` returns them and `GET /api/source/<dataset>/row/<n>` returns the raw row. The new tests appear in Find data under the dataset's data resource.

## 4. Only if the shape is new: write an adapter

An adapter reads the raw file into a DataFrame and lets the shared machinery do the rest (unit parsing, conversion, derived variables, provenance):

```python
# backend/adapters/my_shape.py
import pandas as pd
from ..core.config import RAW
from .base import AdapterResult, register, tabular_to_canonical

@register("my_shape")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False)
    raw = raw[raw["Run"].str.len() > 0]                       # any shape-specific cleanup
    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{cfg['files'][0]}",
                               category_maps={"diluent": lambda v: (str(v).upper(), None)})
    res.tests["investigation_id"] = cfg["investigations"][0]
    res.published = {r.test_id: {"burn_rate_k_mm2_s": r.burn_rate_k_mm2_s} for r in res.tests.itertuples()}
    return res
```

Then import it in `backend/adapters/__init__.py`. The two worked examples:

| adapter | file | shape |
|---|---|---|
| `flex_droplets` | `backend/adapters/flex_droplets.py` | CSV, units inside cells (`"14.7 psi"`, `"21%"`), diluent/fuel aliases, outcome strings, published K/d₀/d_ext for Image Lab validation |
| `bass2_solids` | `backend/adapters/bass2_solids.py` | XLSX sheet, units in headers (`[mm/s]` → converted to cm/s), gravity labels (`µg`/`1g`), spread rate |
| `generic_table` | `backend/adapters/generic_table.py` | any tidy table where `columns:` is enough |
| `pdf_reports` | `backend/adapters/pdf_reports.py` | PDFs → page-anchored chunks; metadata in `data/raw/reports/reports.yaml` |
