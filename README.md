# Freefall Atlas

NASA Space Apps 2026: an AI-powered dashboard of NASA microgravity combustion research for fire safety in spacecraft, Moon and Mars habitats, and pressurized rovers. Two linked views: **Simulate** (flame and airflow simulator with a timeline) and **Find data** (filtered research with credibility scores and AI summaries).

> **What is real and what is not.** Every measured test comes from the real NASA PSI experimental tables the team downloaded and cleaned: 16 tables, 1,781 usable tests (FLEX, CFI, FLEX-2 test plan, CFI-G, ACME Flame Design, ACME BRE, E-FIELD, SPICE, BASS-II, BASS, SAFFIRE-1/2/3, SAME, SAME-R). They are loaded as published: impossible source values are flagged, never corrected, and values read from free-text notes are marked *derived*. Starter rows from `data/seed.json` fill only what the real data lacks (papers, reports, and the few acrylic and fabric test conditions the simulator demo needs). They stay labelled **placeholder / unverified** until a person checks them. The simulator is an illustrative reduced-order model, not a design tool.

## Run it

```
python run.py start      # one command from a clean checkout → http://localhost:8000
```

`start` installs missing Python and Node dependencies, runs the ingest steps if `data/processed/` is empty, builds the web app if needed, and serves the app and API on one port. You need Python 3.11+ and Node 20+. No API keys and no login are needed.

| Task | Command |
|---|---|
| Dev servers (API with reload + Vite) | `python run.py dev` |
| Load data | `python run.py ingest [canonical\|existing\|seed\|fit\|all]` |
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
