# M0 audit: the old Freefall Atlas site

> **Update 2026-11-14 (PR #4):** three more PSI tables are loaded: SLICE (PSI-106), ACME CLD Flame (PSI-21), ACME s-Flame (PSI-23). Now 19 tables and 1,848 usable tests; the catalog has 1,848 real test points (1,738 verified, 110 unverified) plus 12 seed rows. The counts below describe the M0 audit and are kept as written.

Audited 2026-11-14 at commit `2dd0b81` (`main`, after `git pull`). Nothing was changed or deleted to write it.
This replaces the old site's "Audit, round 2" (a UI-screens audit for the Next.js frontend). That document is still in git: `git show 2dd0b81:docs/AUDIT.md`, and it will be under the tag `v0-old-site`.

How it was checked: the existing pipeline was run **in a scratch copy** of the repo (`FA_ROOT=<scratch>`), so the local `data/processed/` was not touched. Every number below comes from that run or from `data/raw/psi_manifest.json`.

---

## 0. Summary

> **Update 2026-11-14 (merge of `real-psi-data`):** three more PSI tables were added after this audit: SLICE (PSI-106), ACME CLD Flame (PSI-21) and ACME s-Flame (PSI-23). The pipeline now reads **19 tables, 1,903 rows, of which 1,848 are usable** (the same 55 excluded). In the §5 model that is 1,848 real test points: 1,738 verified, 110 unverified (the 87 below plus the 23 s-Flame tests, whose oxygen levels are derived from "~21" / "~30"). The counts in the tables below are the audit's original snapshot.


- **Stack:** Python 3 + FastAPI + pandas, with storage in Parquet + one DuckDB file (no database server). The frontend is Next.js 15 + React 19 + Tailwind. Tasks run through `run.py` (and a `Makefile` that calls it). Docker Compose files exist but the team never ran them.
- **Real data:** 16 NASA PSI experimental tables (CSV) fetched with checksums, plus NASA's *Researcher's Guide to Combustion Science* (PDF). The pipeline produces **1,836 tests, of which 1,781 are usable** (55 excluded with logged reasons), 17 investigations, 3 documents and 170 text chunks.
- **Does it run today?** The backend and tests do. A clean checkout does not.
  - Run on its own, the ingest step works and all **134 backend tests pass**. The old frontend builds.
  - **`python run.py start`, `python run.py all` and the Docker image all fail on a clean checkout.** They run `backend/fixture.py` first, which rewrites the tracked `data/raw/reports/reports.yaml` and drops the Researcher's Guide entry. Ingest then crashes (`ArrowTypeError … column year`). The same fixture rewrote the demo PNG, PDF and CSV files that showed up as modified in your working tree before the pull. I stashed those as `stash@{0}`; they differed only in timestamps and line endings.
  - Your local `data/processed/` is out of date (933 tests from 8 datasets). It was built before the last 11 upstream commits.
- **The biggest gap for the new product:** only **one** real test point fits the simulator's model, which needs fabric or PMMA, an O₂ value and an outcome. That point is `SAF2-2-5-UG` (SIBAL fabric, 0 g, 22.1 % O₂, 20 cm/s, burned, 2.1 mm/s), and its table gives no pressure. So §8.4 fitting will keep the default parameters (it needs at least 4 verified points per material). The §13 smoke path (BASS-II paper → ▶ Simulate → "The model agrees") will run on the **seed** test points, which stay labelled unverified.

---

## 1. Stack and how to run it

| Part | What it is | Where |
|---|---|---|
| Task runner | `python run.py setup / fetch / fixture / ingest / train / start / dev / api / web / test / audit / all / demo on\|off`. `Makefile` wraps it. | `run.py`, `Makefile` |
| API | FastAPI 0.162 + uvicorn on :8000. In-process pandas read model loaded from Parquet (`backend/core/store.py`). | `backend/api/main.py` |
| Storage | Parquet tables + `data/processed/atlas.duckdb`, both **gitignored** and rebuilt by `backend.ingest`. Artifacts (search index, models, layouts) in `data/artifacts/` (also gitignored). | `backend/ingest.py` |
| Search | BM25 + dense LSA (TF-IDF → SVD, 96 dims) with rank fusion. sentence-transformers is optional (`FA_EMBEDDER=st`). | `backend/search/` |
| LLM | Optional provider-agnostic rephrasing (`FA_LLM_PROVIDER=none\|anthropic\|openai\|ollama`). Off by default. | `backend/llm/` |
| Web | Next.js 15.1 App Router, React 19, Tailwind 3, d3, zustand, on :3000. It proxies `/api/*` to :8000. | `frontend/` |
| Tests | pytest: 6 files, 134 cases. Playwright scripts for the old UI (not installed locally). | `backend/tests/`, `tests/` |
| Docker | `docker-compose.yml` with api + web. `backend/Dockerfile` runs `run.py all` on first start, which hits the fixture bug above. | root |

Local toolchain checked: Python 3.13.12, Node 24.15, npm 11.14, Docker 28.5. `anthropic` and `playwright` are not installed. No Postgres.

**What actually works (verified in the scratch copy):**

```
python -m backend.ingest        # 1,836 tests / 55 excluded / 3 docs / 170 chunks / 17 investigations, ~16 s
python -c "from backend.vision.pipeline import run_all; run_all()"      # train step, part 1 (Image Lab)
python -c "from backend.models.surrogate import train_all; train_all()" # train step, part 2 (GP surrogates)
python -m backend.ingest        # second pass attaches image-derived values
python -m pytest backend/tests  # 134 passed in 10.8 s
uvicorn backend.api.main:app    # /api/health, /api/meta, /api/tests, /api/test/{id}, /api/search, /api/answer … all 200
cd frontend && next build       # 11 routes build
```

**What fails:** `python run.py all`, `python run.py start` (when `data/processed/` is empty) and `docker compose up`. All three run `fixture` first, which rewrites `data/raw/reports/reports.yaml`, and then ingest crashes.

---

## 2. Data assets

### 2.1 Raw sources (tracked in git, stored byte for byte via `.gitattributes`)

All 16 PSI tables were downloaded by `scripts/fetch_psi.py` from `https://psi.nasa.gov/geode-py/ws/studies/<PSI-id>/download?file=…` on 2026-11-13 and checked against the sha256 values in `data/raw/psi_manifest.json`.

| Dataset id | Investigation | PSI | Raw rows × cols | Adapter (cleaning code) | Tests after ingest (excluded) |
|---|---|---|---|---|---|
| `flex` | FLEX | PSI-69 | 274 × 15 | `adapters/flex_psi.py` | 274 (1) |
| `flex2` | FLEX-2 | PSI-68 | 8 × 7 | (none: a test plan) | 0, kept as `investigations.test_matrix` text |
| `cfi` | CFI | PSI-39 | 87 × 10 | `adapters/psi_summaries.py` (`psi_cfi`) | 87 (8) |
| `cfig_normal` | CFI-G | PSI-159 | 179 × 18 | `adapters/psi_gas_flames.py` | 179 (0) |
| `cfig_inverse` | CFI-G | PSI-159 | 154 × 20 | `adapters/psi_gas_flames.py` | 154 (0) |
| `flame_design_normal` | ACME | PSI-10 | 207 × 15 | `adapters/psi_gas_flames.py` | 207 (0) |
| `acme_bre` | ACME | PSI-20 | 18 × 8 | `adapters/psi_summaries.py` (`psi_bre`) | 43 (2) |
| `efield` | E-FIELD Flames | PSI-22 | 32 × 10 | `adapters/psi_summaries.py` (`psi_efield`) | 21 (1) |
| `spice` | SPICE | PSI-107 | 469 × 9 | `adapters/psi_summaries.py` (`psi_spice`) | 469 (43) |
| `bass2` | BASS-II | PSI-25 | 129 × 17 | `adapters/psi_solids.py` (`psi_bass2`) | 129 (0) |
| `bass` | BASS | PSI-26 | 122 × 6 | `adapters/psi_solids.py` (`psi_bass`) | 122 (0) |
| `saffire1` | Saffire-I | PSI-98 | 4 × 13 | `adapters/psi_solids.py` (`psi_saffire`) | 2 (0) |
| `saffire2` | Saffire-II | PSI-99 | 15 × 17 | `adapters/psi_solids.py` (`psi_saffire`) | 18 (0), split into flight and 1g ground rows |
| `saffire3` | Saffire-III | PSI-100 | 2 × 9 | `adapters/psi_solids.py` (`psi_saffire`) | 2 (0) |
| `same` | SAME | PSI-102 | 8 × 5 | `adapters/psi_smoke.py` (`psi_same`) | 20 (0) |
| `same_r` | SAME-R | PSI-101 | 109 × 10 | `adapters/psi_smoke.py` (`psi_same_r`) | 109 (0) |
| **Total** | | | | | **1,836 (55) → 1,781 usable** |

Some datasets yield more tests than raw rows (`acme_bre`, `same`, `saffire2`). Those adapters split rows that describe several tests, as documented in each adapter.

Other raw files:

| File | What | Origin | Used by |
|---|---|---|---|
| `data/raw/reports/researchers_guide_combustion_science.pdf` (56 pp, 1.5 MB) | NASA, *A Researcher's Guide to: Combustion Science* (NP-2015-10-034-JSC) | nasa.gov (URL in `reports.yaml`) | `adapters/pdf_reports.py` → 161 chunks |
| `data/raw/reports/fire_safety_context.pdf`, `detection_suppression_notes.pdf` | Context notes **written by the team, not NASA** (`demo: true`) | `backend/fixture.py` | 9 chunks |
| `data/raw/reports/flex_demo_report.pdf`, `bass2_demo_report.pdf` | Synthetic demo reports | `backend/fixture.py` | **Not loaded** (not in `datasets.yaml`) |
| `data/raw/reports/reports.yaml` | Titles, authors, years and URLs for the PDFs | hand-written, **overwritten by `fixture.py`** | `pdf_reports.py` |
| `data/raw/flex_demo/` (CSV + 473 PNG/MP4 frames, 11 MB) | **Synthetic** droplet table and image-lab test patterns | `backend/fixture.py` | dataset disabled; frames used by `vision/` only |
| `data/raw/bass2_demo/bass2_flammability.xlsx` | **Synthetic** solids table | `backend/fixture.py` | dataset disabled |
| `data/raw/psi_manifest.json` | URL, sha256, rows, columns and retrieval time per PSI table | `scripts/fetch_psi.py` | `fetch_psi.py --verify`, tests |

### 2.2 Config that drives the cleaning (tracked)

| File | Role |
|---|---|
| `config/datasets.yaml` | Registry of every dataset: adapter, files, column → variable map, unit overrides, outcome maps, constants (e.g. `gravity_g: 0`), validation rules, license. **This is the cleaning specification.** |
| `config/variables.yaml` | 34 canonical variables with unit, kind, role and valid range. |
| `config/investigations.yaml` | 17 investigations: name, pillars, hardware, fuel phase, platform, years (with source), objectives, PSI ids, **DOIs checked on 2026-11-14**, FLEX-2 test matrix. |
| `config/concepts.yaml` | 14 glossary concepts used by search and answers. |
| `config/profile.yaml` | `include_demo` switch. |
| `config/presets.yaml`, `places.yaml`, `models.yaml`, `media.yaml`, `theme.tokens.json` | Settings for the old UI only: Lab presets, `/places` ranking, GP surrogate definitions, Image Lab media, old theme. |

### 2.3 Processed tables (gitignored, rebuilt by `python -m backend.ingest`)

Written to `data/processed/*.parquet` and to `data/processed/atlas.duckdb` (same tables).

| Table | Rows | Columns | Notes |
|---|---|---|---|
| `tests` | 1,836 | 43 | One row per test. Conditions and outcomes in canonical units; `flags`, `invalid` (reason per refused value), `excluded`, `demo`, `_row` (source row). |
| `provenance` | 20,168 | 8 | One row per test × variable: source file, `row N` locator, column, raw value, transformation steps. |
| `validation_log` | 200 | 7 | missing_outcome 131, duplicate 44, impossible_value 11, implausible 7, fractions_do_not_sum 6, extinction_larger_than_start 1. |
| `investigations` | 17 | 18 | From `investigations.yaml`. |
| `documents` | 3 | 10 | The Guide + 2 team context notes. |
| `chunks` | 170 | 7 | Page-anchored text: Guide 161, notes 9. |
| `concepts` | 14 | 6 | Glossary. |
| `variables` | 34 | — | Variable metadata. |
| `media` | 8 | 10 | Image Lab test patterns (synthetic). |
| `measurements` | small | — | Image Lab per-frame results (synthetic media). |

Artifacts (`data/artifacts/`, gitignored): `search_index.pkl` (281 items), `atlas.json` (graph for old Explore), `relationships.json`, `refinery.json` (per-dataset cleaning stages for the old Data screen), `published_values.json`, `glossary.json`, `models/*.joblib` (6 GP surrogates), `vision/*.json`, `frames/`.

**Coverage of the 1,781 usable tests** (non-null counts): gravity 1,781 (1,772 at 0 g, 9 at 1 g) · O₂ 919 · pressure 892 · flow 822 · outcome (`burned`) 497 (124 burned, 373 went out) · spread rate **4** · flow direction 25 · diluent 273 · material text 401 · notes 771 · date 1,202.

---

## 3. Existing API routes (`backend/api/main.py`)

| Route | Returns | Used by | Fate |
|---|---|---|---|
| `GET /api/health` | `{ok:true}` | ops | **keep** |
| `GET /api/meta` | loaded datasets, counts, model cards | old UI | delete (folded into new endpoints) |
| `GET /api/tests?dataset&ids&include_excluded` | test rows | old UI | **adapt** → `GET /api/test-points` |
| `GET /api/test/{id}` | one test: every value with its status, label, unit, source and transformation trail (`record.py`) | old provenance panel | **keep** (backs resource detail and test-point provenance) |
| `GET /api/source/{dataset}/row/{row}` | the raw source row exactly as published | old provenance panel | **keep** (the traceability link for every test point) |
| `GET /api/search?q&k&types&investigation` | hybrid search results | old UI | **adapt** (retrieval for `q` and for Ask) |
| `GET /api/chunk/{id}` | one chunk + neighbours | old UI | **keep** (citation target) |
| `GET /api/doc/{id}/file`, `/page/{p}.png`, `/page/{p}/highlights` | PDF file, a rendered page, highlight rectangles for a quoted span | old source viewer | **keep** (opens a citation at its page) |
| `POST /api/export/csv` | CSV with a `source` column (`file:row N`) | old Studio | **adapt** → `POST /api/export` |
| `POST /api/export/citations` | text + BibTeX | old Studio | **adapt** → `POST /api/export` (bibtex) |
| `POST /api/admin/reload` | reloads caches. **No auth today.** | ops | **adapt** (add `ADMIN_TOKEN`) |
| `GET /api/answer`, `/api/navigate`, `/api/node/{id}`, `/api/topic/{id}` | extractive answers, graph navigation, topic screens | old Home/Answer/Explore | delete |
| `GET /api/atlas`, `/api/explore`, `/api/insights`, `/api/groups/{ds}`, `/api/relationships/{ds}` | graph, clusters, findings, statistics | old Explore/Insights | delete |
| `GET /api/atmosphere`, `/api/places`, `/api/places/{id}` | old atmosphere-trade map, place rankings | old Trade/Places | delete |
| `GET /api/lab/items`, `/api/lab/grid`, `POST /api/scenario`, `POST /api/advisor`, `GET /api/envelope`, `GET /api/models`, `GET /api/gapmap` | GP-surrogate simulator for droplets and gas flames | old Lab | delete (replaced by the §8 model) |
| `GET /api/refinery` | cleaning stages per dataset | old Data screen | delete (the information stays in `validation_log`) |
| `GET/POST /api/vision/*` | Image Lab on synthetic frames | old Image screen | delete |

None of the §9 routes (`/api/presets`, `/api/investigations`, `/api/resources`, `/api/simulate`, `/api/flammability-map`, `/api/ai/*`, `/api/export`) exist yet.

---

## 4. Field mapping: existing data → SPEC §5

Legend: ✅ direct · 🔁 transform · 🌱 from `seed.json` (gap filled, stays placeholder/unverified) · ❌ gap (nothing exists)

### 4.1 `investigations` ← `config/investigations.yaml` (17 rows) + seed (10 grouped rows)

| §5 field | Existing source | Status |
|---|---|---|
| `slug` | `id` (`BASS`, `BASS-II`, `Saffire-I` …); the seed and prototype use grouped slugs (`bass` = BASS & BASS-II) | 🔁 **decision A** |
| `name` | seed group name (`BASS & BASS-II`) or `id` | 🔁 |
| `full_name` | `name` ("Burning and Suppression of Solids II") | ✅ |
| `purposes[]` | `pillars` prevention/detection/suppression → prevent/detect/suppress | 🔁; `basics` ❌ → 🌱 |
| `fuels[]` | `fuel_phase`: solid → solid, "liquid droplet" → liquid, gas → gas, smoke/dust → none | 🔁 |
| `envs[]` | only free-text `platform` ("ISS / MSG", "Cygnus") | ❌ → 🌱 (seed envs), else `space` (+`earth` for SAFFIRE-2 1g ground tests) |
| `hardware` | `hardware` | ✅ |
| `summary` | `objectives` | ✅ |
| `psi_url` | `dois` → `https://doi.org/<doi>` (each checked to resolve to the PSI page) | 🔁 |
| extras kept | `psi_ids`, `years` + `years_source`, `platform`, `test_matrix` (FLEX-2) | not in §5; served as extra fields |
| Seed-only investigations | `sofie` (SoFIE-MIST), `ea` (Exploration Atmosphere): no real rows | 🌱 |
| Real-only investigations | DAFT, DAFT-2, SLICE (no tables), E-FIELD Flames | ✅ grouped per decision A |

### 4.2 `resources`: no such table exists yet; it is built from three real sources plus the seed

| Real source | → resources | Fields |
|---|---|---|
| 16 PSI tables (`psi_manifest.json` + `datasets.yaml`) | 16 rows of `type=data` (FLEX-2 is its test plan) | `title` ← dataset title ✅, `publisher` = "NASA PSI" ✅, `format` = CSV ✅, `url` ← manifest download URL ✅, `year` ← last test year (`investigations.years`) 🔁, `description` ← dataset title + license + row counts 🔁 |
| `researchers_guide_combustion_science.pdf` | 1 row of `type=report` | title, authors, year 2015, nasa.gov URL ✅ |
| 2 team context-notes PDFs | none (they are not NASA material) | **decision D** |
| Synthetic media (`media` table) | none | not NASA data |
| **Seed** (22 rows) | papers ×4, reports ×4, slides ×3, image, news ×3 have no real equivalent → 🌱 loaded as given. `v-saffire` and `i-bass` placeholders → 🌱. The data placeholders `d-bass`, `d-saffire`, `d-flex`, `d-cfig`, `d-same` → **skipped**, because a real PSI data resource exists for each. | as in seed |

| §5 field | Status |
|---|---|
| `investigation_id`, `type`, `title`, `publisher`, `year`, `format`, `url`, `description` | ✅/🔁 as above |
| `s3_key` | ❌ (the files come from the PSI web API, not the S3 bucket) → null |
| `cred_publisher`, `cred_review`, `cred_trace` | ❌ for real rows. Assigned by the §7 rules: PSI data P = 1.0, T = 1.0, R = **decision C**. Guide P = 0.85, R = 0.8, T = 0.8. Seed rows carry their own `cred`. |
| `status` | real rows = `published`; seed rows as given |
| `envs_override` | ❌ → null (seed values where given) |

### 4.3 `test_points` ← `tests` (1,781 usable rows; excluded rows are not mapped) + `provenance`

| §5 field | Existing source | Status |
|---|---|---|
| `code` | `test_id` (unique; duplicates already carry `~dupN` and are excluded) | ✅ |
| `investigation_id` | `investigation_id` → investigation slug | 🔁 |
| `source_resource_id` | `dataset` → that PSI table's data resource | 🔁 |
| `material` (fabric/pmma/droplet/gas/other) | rule: droplet sets (flex, cfi) → droplet; gas sets (cfig\*, flame_design, acme_bre, efield, spice) → gas; solids: SIBAL → fabric, PMMA → pmma, anything else (incl. "Not named in the table") → other; smoke sets → other | 🔁 (never inferred beyond the text) |
| `sample_desc`, `geometry` | `material` text + `fuel` + `thickness_mm`/`d0_mm`; `sample_shape` (236) | 🔁 |
| `gravity_g` | `gravity_g` (1,781) | ✅ |
| `o2_pct` | `o2_frac × 100` (919) | 🔁 |
| `pressure_kpa` | `pressure_kpa` (892); **null for every solid-material test** | ✅ |
| `flow_cm_s` | `flow_cm_s` (822) | ✅ |
| `flow_direction` | `flow_direction` (25) | ✅ |
| `diluent` | `diluent` (N2 249, CO2 20, He 4) | ✅ |
| `outcome` | `burned` 1 → `burned`, 0 → `went_out`; CFI cool-flame rows → `cool_flame`; gas flames with no burned flag → `flame`; anything else → `measured` | 🔁 (exact rule per dataset in M1) |
| `spread_mm_s` | `spread_rate_mm_s` (**4** rows) | ✅ (sparse) |
| `notes` | `notes` + `test_end` + `flags` | 🔁 |
| `source_page` | `provenance.locator` "row N" of the CSV (tables have rows, not pages) | 🔁 |
| `source_quote` (≤ 30 words, verbatim) | ❌ → built from the raw source row (`record.source_rows`): the verbatim cells holding the numbers | 🔁 |
| `extraction` | deterministic adapter read of a NASA table → `manual` | 🔁 |
| `verified`, `verified_by`, `verified_at` | ❌ → **decision B** | ❌ |
| extras not in §5 | `d0_mm`, `burn_rate_k_mm2_s`, `extinction_d_mm`, `fuel_flow_mg_s`, `heater_ratio`, `smoke_aging_s`, `mass_loss_rate_mg_min`, `burner_mm`, `campaign`, `mission_date`, `flags`, `invalid` | kept in `tests`; shown in detail and export |
| Seed test points (12) | `BASS2-01/02/G1/G2`, `BASS-03`, `BASS2-04`, `SAF1-C`, `SAF3-C`, `SAME-01`, `FLEX-01/02`, `CFIG-01`: none of these codes exists in the real data → 🌱 all loaded, `verified=false` | 🌱 |

**Simulator coverage:** real points with fabric or PMMA + O₂ + outcome: **1** (`SAF2-2-5-UG`, no pressure). Points with O₂ + pressure + outcome for the solid model: **0**. So `ingest fit` (§8.4) keeps the §8.1 defaults for both materials, and `model_params.n_points` records why. The anchor tests (§8.5) use the defaults, so they are not affected.

### 4.4 Other §5 tables

| §5 table | Existing | Status |
|---|---|---|
| `resource_points` | none | 🔁 built: PSI data resource ↔ its tests; seed `points` lists |
| `chunks` (`resource_id`, `page`, `text`, `embedding vector(384)`) | `chunks` (170: `doc_id`, `page`, `section`, `anchor`, `text`) + LSA vectors in `search_index.pkl` | 🔁 `doc_id` → resource; embeddings stay in the index (**decision E**) |
| `model_params` | none (`config/models.yaml` defines GP surrogates, a different thing) | ❌ → defaults from seed `model_defaults` / §8.1 |
| `ai_cache` | none | ❌ new |

---

## 5. Keep / adapt / delete

### 5.1 Top-level folders and files

| Path | Decision | Reason |
|---|---|---|
| `backend/` | **adapt** | Holds the cleaning adapters, validation, ingest, provenance and search; these stay (see 5.2). Modules that only serve old screens go. The §9 API is added here on the existing FastAPI app. |
| `config/` | **adapt** | Keep `datasets.yaml`, `variables.yaml`, `investigations.yaml`, `concepts.yaml`, `profile.yaml` (the cleaning spec and catalog). Delete `presets.yaml`, `places.yaml`, `models.yaml`, `media.yaml`, `theme.tokens.json` (old UI only; the new presets come from the prototype/seed). |
| `data/raw/` (PSI tables, Guide PDF, `psi_manifest.json`, `reports.yaml`) | **keep** | Real NASA data and its checksums. Never edited. |
| `data/raw/flex_demo/`, `data/raw/bass2_demo/`, `reports/*_demo_report.pdf` | **delete** (proposed) | Synthetic fixtures, not NASA data. Disabled or unloaded today; they only feed the Image Lab. **decision F** |
| `data/raw/reports/fire_safety_context.pdf`, `detection_suppression_notes.pdf` | **keep** (file) | Team-written notes, labelled; kept out of resources by **decision D**. |
| `data/processed/`, `data/artifacts/` | **keep** (gitignored outputs) | Rebuilt by the existing ingest; never committed. |
| `frontend/` | **delete** | The old Next.js UI. Replaced by the ported prototype (`web/`, React 18 + Vite + TS, per SPEC §4). |
| `scripts/fetch_psi.py` | **keep** | Checksum-verified PSI download (ingestion). |
| `tests/` (`smoke_playwright.py`, `audit_capture.py`, `scene_capture.py`) | **delete** | Playwright scripts for old screens. Replaced by the §13 smoke test. |
| `docs/` | **adapt** | Keep `ADDING_A_DATASET.md` and `LIMITS.md` (data limits; update when the UI changes); keep `DECISIONS.md` as the history of data decisions. Delete `DESIGN.md`, `PERF.md`, `PLAN.md` and `docs/audit/` (11 MB of old-UI screenshots and Lighthouse runs). |
| `run.py`, `Makefile` | **adapt** | Keep the one-command runner. Drop `fixture`, `train` and `audit`, make `start` build the new web app, add `ingest existing\|seed\|fit`. |
| `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | **adapt** / **delete** `frontend/Dockerfile` | One image that serves the API + built web app, without the fixture step. |
| `requirements.txt` | **adapt** | Add `anthropic`; drop `opencv`, `scikit-image`, `imageio*` (vision only) and `reportlab` (fixture only). |
| `.env.example` | **adapt** | Merge with the kit's `.env.example`. |
| `.gitattributes`, `.gitignore` | **keep** | Byte-exact raw data. |
| `README.md` | **adapt** | Rewrite for the new app; add the "Decisions" section. |
| `freefall-atlas-kit (1)/` | **adapt (move)** | Move `CLAUDE.md`, `SPEC.md` and `prototype/` to the root, `seed.json` to `data/seed.json`, and `PROMPT.md` to `docs/PROMPT.md`; merge `.env.example`. Then remove the folder. Today it is staged but not committed. |
| `frontend/tsconfig.tsbuildinfo` | **delete** | Committed build artifact. |

### 5.2 Inside `backend/`

| Module | Decision | Reason |
|---|---|---|
| `core/` (config, schema, units, validate, store) | **keep** | Unit parsing, "flag, never fix" validation, read model. |
| `adapters/` psi_*, flex_psi, pdf_reports, base, generic_table | **keep** | These are the cleaning scripts. |
| `adapters/flex_droplets.py`, `bass2_solids.py` | **keep** (disabled) | Adapters for the synthetic fixtures. Small and harmless; kept so no cleaning code is removed. |
| `ingest.py` | **adapt** | Keep the pipeline exactly. Remove the calls to `atlas` and `vision`. Add the `existing → seed → fit` steps that write the §5 tables (the adapter layer). |
| `record.py` | **keep** | Per-value provenance and the raw source row. This is how `source_quote` and the trail are built. |
| `search/` | **adapt** | Index chunks + resources (not old atlas nodes) for `q` and Ask retrieval. |
| `answer/verifier.py` | **keep** | Verifies that every number and quote in a sentence appears in its cited source; reused for "cite or refuse". |
| `answer/engine.py` | **delete** | Old answer screens. Ask follows SPEC §11 instead. |
| `llm/` | **adapt** | Replace the multi-provider shim with the Anthropic SDK, model from `ANTHROPIC_MODEL`, template fallback. |
| `api/main.py` | **adapt** | Keep the app, CORS, gzip, `_clean` and the kept routes in §3; add the §9 routes. |
| `api/views.py`, `atlas.py`, `explore.py`, `insights.py`, `topics.py`, `relevance.py`, `atmosphere.py`, `labgrid.py` | **delete** | Back the old Explore, Insights, Answer, Places, Trade and Lab screens only. |
| `models/surrogate.py` | **delete** | GP surrogates for the old Lab. The new simulator is the §8 model. |
| `vision/` | **delete** | Image Lab over synthetic test patterns. |
| `fixture.py` | **delete** | Generates synthetic data and **overwrites real metadata** (`reports.yaml`). It is the cause of the clean-checkout failure. |
| `tests/test_core.py`, `test_search.py` | **keep** | Units, validation, search. |
| `tests/test_psi_tables.py`, `test_integrity.py` | **adapt** | Keep every data and provenance test. Drop the 3 + 13 test functions that exercise deleted screens (answers, `/places` ranking, topics, explore, insights, lab grid, atmosphere trade). |
| `tests/test_answer_models.py`, `test_vision.py` | **adapt / delete** | Keep the verifier tests; drop the surrogate and vision tests. |

---

## 6. Decisions I need from you before step 2

| # | Question | My proposal (default if you say "OK") |
|---|---|---|
| **A** | Investigation granularity: the real catalog has 17 (BASS, BASS-II, Saffire-I/II/III …); the prototype and seed group them into 10 (`bass` = BASS & BASS-II). | Use the **prototype's grouped slugs** as `investigations` (`bass, saffire, same, flex, cfi, acme, spice, daft, sofie, ea`). Each lists its real PSI members with their PSI ids, DOIs and years. Test points and data resources keep the exact PSI investigation name. CFI-G and E-FIELD go under `acme` (as in the seed); SLICE under `spice`. |
| **B** | `verified` for real PSI rows (read by the team's adapters, not by AI). | `verified=true`, `extraction=manual`, `verified_by="PSI table (team adapter)"`, `verified_at` = manifest retrieval time, **only** when every value used is "as published". Rows where a value was derived from free-text notes (marked *derived*) stay `verified=false`. Seed points stay `false`. |
| **C** | Credibility "review" factor for PSI flight data (§7 has no rule for it). | R = 0.8 (NASA-curated, not peer-reviewed). With P = 1.0 and T = 1.0 that gives S = 94, **High**. |
| **D** | The two context-notes PDFs the team wrote. | Keep the files, but **don't list them** as resources and don't let Ask cite them, because they are not NASA sources. |
| **E** | Storage and embeddings: SPEC defaults to Postgres + pgvector + MiniLM. | **Keep DuckDB/Parquet** (it works, and needs no DB server for the judges' deploy) and the local LSA embeddings (MiniLM needs about 2 GB of PyTorch). The §5 tables are added as new DuckDB/Parquet tables. Deploy as **one container** (FastAPI serving the API and the built web app) on Render, Fly or Railway: one public URL, no database to host. |
| **F** | Synthetic fixtures (`data/raw/flex_demo` 11 MB, `bass2_demo`, 2 demo report PDFs, `fixture.py`, `vision/`). | **Delete** them. Not NASA data, not loaded by the real profile, and the fixture breaks clean checkouts. They stay recoverable from `v0-old-site`. |
| **G** | Presets. The old `config/presets.yaml` has Moon base at 30 % / 10.2 psi; the prototype has 34 % / 8.2 psi (NASA's 2024 exploration-atmosphere recommendation, `r-ea`). | Use the **prototype/seed presets** (the §8.5 anchors and the §13 smoke path depend on them). |

Also: `stash@{0}` holds the fixture-regenerated demo files from your working tree (timestamp and CRLF changes only). I plan to drop it in step 2 unless you want it kept.

---

## 7. As built (M1): how the mapping was implemented

Approved 2026-11-14 with proposals A–G (product decisions). Code: `backend/catalog/build.py` (`ingest existing`) and `backend/catalog/seed.py` (`ingest seed`). Output tables: `data/processed/atlas_*.parquet`, also in `atlas.duckdb`.

| Table | Rows | Notes |
|---|---|---|
| `atlas_investigations` | 8 real groups + 2 seed (`sofie`, `ea`) | `members` holds each real PSI investigation (PSI ids, DOIs, years, platform, test matrix). `origin` = psi \| seed. |
| `atlas_resources` | 17 real (15 PSI test tables + FLEX-2 test plan + NASA Researcher's Guide) + 17 seed | `investigations` (list) allows multi-investigation resources such as the Guide. `doi` and `psi_id` are kept. The PSI rows score 94 (High). |
| `atlas_test_points` | 1,781 real + 12 seed | 1,694 real points verified. 87 real points are unverified: 79 because a used value was derived (e.g. "~ 22.1" approximate O₂, gravity worked out from the platform) and 8 because they are flagged implausible. `unverified_reason` says which. `extra` (JSON) keeps droplet and gas variables that §5 has no column for. |
| `atlas_resource_points` | 1,781 + seed links | PSI table ↔ its rows; seed `points` lists. |
| `atlas_chunks` | 161 | The Guide only (Decision D). |
| `atlas_presets`, `atlas_model_params` | 5, 2 | From seed (Decision G) and the §8.1 defaults. `ingest fit` replaces the parameters once at least 4 verified points exist. |

Gaps still open after M1: `s3_key` (null everywhere until `ingest psi`, M5), embeddings in `chunks` (LSA index, M4), `verified_by`/`verified_at` for seed rows (set by the admin verify page, M5).

## 8. Typography and spacing pass (2026-11-15)

Scope: fonts, text sizes, spacing and text alignment only. No colour, layout, feature or copy-meaning changes.
Measured from the rendered pages, not only the source: `python scripts/typo_audit.py` reads the computed font of
every visible piece of text (HTML and SVG) on every demo screen at 1440 and 1024 px; `--strict` fails on any
rule break. Screenshots: `python scripts/typo_shots.py <folder>`.

**Before** (3,782 text items measured):
- **35 distinct sizes**, from 10 px to 84 px: 10, 10.4, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15, 15.3, 15.5, 16, 17, 18, 18.5, 19, 20, 22, 24, 24.7, 26, 30, 34, 38, 40, 40.5, 41, 44, 46, 54.1, 65.5, 84.
- **1,171 text instances below 13 px.** Mostly 12.5 px table cells, legends and captions in Find data, the simulator panels and the fire check; 10–11 px axis ticks in the flammability map, the timeline and the simulator canvas; 10.4 px formula subscripts; 11.5 px slide numbers; 12 px code lines.
- **Three font families:** Barlow Condensed (77 items: logo, headings, section labels, pills), IBM Plex Sans, IBM Plex Mono (925 items, including word labels such as section headers, badges, the scale under sliders and the canvas labels).
- **Four weights** (400, 500, 600, 700).
- **81 uppercase labels and 97 tracked labels** (0.02–0.14 em).
- **Uneven spacing:** 169 padding, margin and gap values off a 4 px scale (2, 3, 5, 6, 10, 14, 18, 20 px …).

**After:** two families (IBM Plex Sans 3,066 items, IBM Plex Mono 736 items for numbers, units, IDs and code), weights
400 and 500 only, sizes 13/14/16/18/22/28 px, nothing below 13 px, no uppercase, no tracking above 0.01 em, spacing on
4/8/12/16/24/32/48 px. The one exception is the presentation slides: they scale their text with the slide width (cqw),
like a projected image, with a 13 px floor. No clipped text on any screen. Lint, 211 backend tests, 7 model-parity
tests and 8 browser tests pass.

| Screen | Before | After |
|---|---|---|
| landing | [before 1440](audit/typography/before/landing-1440.png) · [1024](audit/typography/before/landing-1024.png) | [after 1440](audit/typography/after/landing-1440.png) · [1024](audit/typography/after/landing-1024.png) |
| simulation | [before 1440](audit/typography/before/simulation-1440.png) · [1024](audit/typography/before/simulation-1024.png) | [after 1440](audit/typography/after/simulation-1440.png) · [1024](audit/typography/after/simulation-1024.png) |
| fire-check-estimated | [before 1440](audit/typography/before/fire-check-estimated-1440.png) · [1024](audit/typography/before/fire-check-estimated-1024.png) | [after 1440](audit/typography/after/fire-check-estimated-1440.png) · [1024](audit/typography/after/fire-check-estimated-1024.png) |
| fire-check-untested | [before 1440](audit/typography/before/fire-check-untested-1440.png) · [1024](audit/typography/before/fire-check-untested-1024.png) | [after 1440](audit/typography/after/fire-check-untested-1440.png) · [1024](audit/typography/after/fire-check-untested-1024.png) |
| find-data | [before 1440](audit/typography/before/find-data-1440.png) · [1024](audit/typography/before/find-data-1024.png) | [after 1440](audit/typography/after/find-data-1440.png) · [1024](audit/typography/after/find-data-1024.png) |
| statistics | [before 1440](audit/typography/before/statistics-1440.png) · [1024](audit/typography/before/statistics-1024.png) | [after 1440](audit/typography/after/statistics-1440.png) · [1024](audit/typography/after/statistics-1024.png) |
| research | [before 1440](audit/typography/before/research-1440.png) · [1024](audit/typography/before/research-1024.png) | [after 1440](audit/typography/after/research-1440.png) · [1024](audit/typography/after/research-1024.png) |
| presentation | [before 1440](audit/typography/before/presentation-1440.png) · [1024](audit/typography/before/presentation-1024.png) | [after 1440](audit/typography/after/presentation-1440.png) · [1024](audit/typography/after/presentation-1024.png) |

**Noticed, left as is (outside this pass):**
- The fire check's three measured quantities wrap to two rows at 1440 px, leaving the third alone on its line.
- The presentation's title slide still shows the placeholder "Team: names and roles".
- Colours in the flammability-map SVG are hard-coded (`#949eb3` and others) instead of using the colour tokens.
- Find data and the simulator panels keep the prototype's dark palette while the other engine pages use the brighter Ember navy.
- The fire check's oxygen line can fall as oxygen rises (it says so in a caution line); that is a model behaviour, not a typography issue.

