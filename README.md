# Freefall Atlas

NASA Space Apps 2026: an AI-powered dashboard of NASA microgravity combustion research for fire safety in spacecraft, Moon and Mars habitats, and pressurized rovers. Two linked views: **Simulate** (flame and airflow simulator with a timeline) and **Find data** (filtered research with credibility scores and AI summaries).

> **What is real and what is not.** Every measured test comes from the real NASA PSI experimental tables the team downloaded and cleaned: 19 tables, 1,848 usable tests (FLEX, CFI, FLEX-2 test plan, CFI-G, ACME Flame Design, ACME BRE, ACME CLD Flame, ACME s-Flame, E-FIELD, SPICE, SLICE, BASS-II, BASS, SAFFIRE-1/2/3, SAME, SAME-R). They are loaded as published: impossible source values are flagged, never corrected, and values read from free-text notes are marked *derived*. Starter rows from `data/seed.json` fill only what the real data lacks (papers, reports, and the few acrylic and fabric test conditions the simulator demo needs). They stay labelled **placeholder / unverified** until a person checks them. The simulator is an illustrative reduced-order model, not a design tool.

## Run it

```
python run.py start      # one command from a clean checkout → http://localhost:8000
```

`start` installs missing Python and Node dependencies, runs the ingest steps if `data/processed/` is empty, builds the web app if needed, and serves the app and API on one port. You need Python 3.11+ and Node 20+. No API keys and no login are needed.

| Task | Command |
|---|---|
| Dev servers (API with reload + Vite) | `python run.py dev` |
| Load data (offline, no key) | `python run.py ingest [canonical\|existing\|psi\|ntrs\|text\|seed\|curate\|fit\|index\|all]` |
| Refresh a network snapshot (M5) | `python -m backend.ingest ntrs --fetch` (NASA NTRS records) · `text --fetch` (PDF text) · `psi --discover`, confirm `data/psi_map.csv`, then `psi --fetch` (public PSI bucket) |
| Propose test points with AI (M5; needs `ANTHROPIC_API_KEY`, costs credits, not part of `all`) | `python -m backend.ingest extract`, then review on `/admin/verify` (needs `ADMIN_TOKEN`) |
| Re-download the PSI tables and verify checksums | `python run.py fetch` |
| Unit tests / browser smoke test / both | `python -m pytest backend/tests -q` / `python run.py e2e` / `python run.py test` |
| Container | `docker compose up --build` |

Optional settings are in `.env.example`. With `ANTHROPIC_API_KEY` set, the AI summary and Ask use Claude (`ANTHROPIC_MODEL`).

## Layout

```
backend/   adapters (team's cleaning code) · core (schema, units, validation, store) · ingest · record (provenance)
           · search · answer/verifier · api
web/       React + Vite + TypeScript port of prototype/index.html
config/    datasets.yaml (cleaning spec) · variables.yaml · investigations.yaml · concepts.yaml
data/      raw/ (NASA PSI tables + PDFs, byte-exact, checksummed) · seed.json · processed/ (built, gitignored)
prototype/ the reference UI (do not edit)
docs/      AUDIT (M0) · DECISIONS (old site's data decisions) · LIMITS · ADDING_A_DATASET
```

The old Next.js site is tagged `v0-old-site`.

## Decisions

Choices made where the brief was open. Newest last. The old site's data decisions (1–88) are in `docs/DECISIONS.md`.

| # | Decision | Why |
|---|---|---|
| A | **Investigations use the prototype's grouped slugs** (`bass` = BASS + BASS-II, `saffire` = Saffire-I/II/III, `same` = SAME + SAME-R, `flex` = FLEX + FLEX-2, `cfi`, `acme` = ACME + CFI-G + E-FIELD Flames, `spice` = SPICE + SLICE, `daft` = DAFT + DAFT-2, plus seed-only `sofie` and `ea`). Each group lists its real PSI members with PSI ids, DOIs and years. Test points and data resources keep the exact PSI investigation name. | Matches the prototype's filter and the seed's references. No real information is lost. |
| B | **Real PSI rows are `verified=true`, `extraction=manual`** (read by the team's deterministic adapters) only when every value used is as published. Rows that use a value derived from free-text notes stay `verified=false`. Seed rows stay as given (`false`). | They are NASA's published tables, not AI extraction. Derived values deserve a human check. |
| C | Credibility review factor for PSI flight data: **R = 0.8** (with P = 1.0 and T = 1.0, S = 94, High). | §7 has no rule for curated NASA data that is not peer-reviewed. |
| D | The two context-notes PDFs the team wrote are **not resources** and are not cited by AI. | They are not NASA sources. |
| E | **No Postgres.** The existing DuckDB + Parquet store is kept, and the §5 tables are added beside it. Embeddings stay local LSA (`FA_EMBEDDER=st` switches to MiniLM). The deploy is **one container** that serves the API and the built web app. | The existing stack works, the demo needs no database server, and MiniLM would add about 2 GB of PyTorch. |
| F | **Deleted:** the old frontend, the synthetic-data generator (`backend/fixture.py`), the Image Lab (`backend/vision/`) and its 11 MB of synthetic frames, the GP surrogates, and the old screens' backend modules. **Kept:** the two small synthetic tables, because the adapter unit tests check the cleaning code against them. | `fixture.py` overwrote `data/raw/reports/reports.yaml` and broke every clean checkout (docs/AUDIT.md §0). Nothing deleted was NASA data. All of it is recoverable from `v0-old-site`. |
| G | **Presets come from the prototype/seed** (Moon base 34 % O₂ at 8.2 psi), not from the old `config/presets.yaml` (30 % at 10.2 psi). | The §8.5 anchor tests and the §13 smoke path depend on them; the value is NASA's 2024 exploration-atmosphere recommendation (`r-ea`). |
| H | The processed tables stay gitignored. A clean checkout runs the team's unchanged pipeline (`ingest canonical`) once, at start or at image build. | Nothing is re-cleaned by hand. Running the existing deterministic code is the only way to rebuild its outputs. |
| I | `POST /api/admin/reload` now requires the `X-Admin-Token` header, and admin routes are disabled while `ADMIN_TOKEN` is empty or `change-me`. | It had no auth on the old site. |
| J | A seed **placeholder data** resource (`d-bass`, `d-saffire`, `d-flex`, `d-cfig`, `d-same`) is skipped when a real PSI data resource exists for its investigation. Its starter test points still load (codes don't collide with real ones), marked unverified, with no source. | Each placeholder stood in for "the PSI test matrix". The real tables now exist, and the simulator's demo points have no real equivalent. |
| K | Investigation **environments** = where the real tests ran (0 g → space, 1 g ground tests → earth) **plus** the seed's relevance tags (e.g. "Moon or Mars"). Purposes add the seed's `basics`. Fuels come from the seed only when the real catalog names none (smoke, dust). | These are classification tags the real catalog lacks. Taking the union never removes a real value. |
| L | A test point is **simulatable** when it is fabric or PMMA, has an O₂ value, and has a burned / went-out outcome. Only those appear on the flammability map and as nearest evidence. | The compare box needs a measured outcome. Real BASS-II rows report O₂ but no outcome, so they would always "disagree". |
| M | Loading a test whose table gives no pressure runs the simulator at 14.7 psi and **says so** in the compare box. Pressure and flow are left out of the §8.3 distance when the test doesn't report them. | It keeps the prototype's behaviour without presenting an assumed pressure as measured. |
| N | Coverage thresholds come from the loaded points: "Extrapolated" above the highest solid-fuel O₂ that has an outcome (22.1 % today, SAF2-2-5-UG), or below the lowest tested pressure. | SPEC §8.3, computed instead of hard-coded. |
| O | The AI summary template names **gaps computed from the data** (no partial-gravity tests; no solid-material test below sea-level pressure) and cites resource ids as `[id]` markers, the same format the Claude version will use. | One citation format for template and AI; the gaps are checked, not asserted. |
| P | Export is implemented in M1 as `POST /api/export` (CSV / JSON / BibTeX downloads). The dialog previews the server's file. | The prototype's client-side preview had nothing to export from once data moved to the API. |
| Q | `ingest fit` runs on the real data and **keeps the §8.1 defaults**: 0 verified fabric/PMMA tests report oxygen, pressure, airflow and an outcome. The fitter itself is tested on model-generated points (in the test suite only). The screen says the parameters are defaults and why. | SPEC §8.4: fit to verified points or keep the defaults. We do not relax "verified" or assume a cabin pressure to get a fit. |
| R | The browser keeps a copy of the model for instant feedback. After 150 ms the server's `/api/simulate` result is compared with it, and replaces it if they differ. A 600-case golden file (`backend/tests/fixtures/model_golden.json`) proves the two copies match. | SPEC §10 reconciliation, without a round-trip on every frame. |
| S | **AI uses `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`, per SPEC §11)**, effort `low`, a 20 s timeout and no retries. Server-side refusal fallbacks (`fallbacks: "default"`) are on for models that support them. The model sees sources as `[S1]…[Sn]`; the server maps them back to resource ids. It then drops unknown labels, sentences with no citation, and sentences with a number that isn't in the sources. An answer left with nothing is rejected. | "Cite or refuse" enforced in code, not just asked for in the prompt. Short labels are more reliable than long ids. |
| T | The AI summary writes only the "start with…" sentences; the **gap sentences are computed from the data** and appended. | The model would have to cite a source to say that no source covers something. Computing absences from the data is both checkable and true. |
| U | **Ask with no API key returns 503 plus the matching NASA passages**, and the UI shows them, so the public demo still answers with evidence. Off-topic questions are refused before any AI call: a passage must share at least two of the question's content words. | SPEC §11 says 503; showing the evidence keeps the demo useful. The word gate stops spurious matches (e.g. "best" in a pizza question). |
| V | `ai_cache` is a SQLite file next to the processed tables, keyed by sha256 of prompt version + model + context. | No database server (Decision E). A cache failure never fails a request. |
| W | Retrieval for Ask uses the team's existing hybrid index (BM25 + local LSA). It is extended with the §5 resources, which are returned only when a caller asks for them. NASA passages only (Decision D). | Reuses the existing search instead of adding pgvector. The old site's search-quality tests still pass. |
| X | The public `nasa-psi` bucket is read **directly over HTTPS** (its S3 listing and file URLs), not through Amazon's Python SDK. | The bucket is public, so no credentials or SDK are needed; one less dependency, and the request code is small enough to test with mocked responses. |
| Y | **Every network step writes a committed snapshot** (`data/raw/ntrs/`, `data/raw/ntrs/text/`, `data/raw/psi_bucket/`), and `ingest all` reads only the snapshots. Each step's `--fetch` refreshes its snapshot. | A clean checkout, the tests and the container build run offline and give the same result every time; a network refresh is a deliberate, reviewable change. |
