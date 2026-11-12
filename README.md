# Freefall Atlas

What NASA knows about fire in space, and what it doesn't: microgravity combustion experiments (NASA PSI) with their evidence and their gaps in one place. Ask a question or pick a starting point, get a finding with its sources, and see what was measured, what a model infers and what was never tested.

> **This build ships with a synthetic demo fixture** shaped like FLEX and BASS-II data. A notice marks it on every screen. It is never presented as NASA results. Swap in real files with `python run.py demo off` (see `docs/ADDING_A_DATASET.md`).

## Run it (local, verified)

1. Install Python 3.11+ and Node 20+.
2. `python run.py setup` installs Python and Node dependencies.
3. `python run.py all` builds the demo fixture, ingests it, runs the image pipeline and trains the models (~2 min).
4. `python run.py start` builds the web app and serves the fast production version. Open http://localhost:3000.
5. `python run.py test` runs 85 backend checks plus the browser acceptance test (needs the app running and Playwright installed).
6. `python run.py audit` re-captures every screen and its timings into `docs/audit/after/`.

`python run.py dev` starts the hot-reload development servers instead. They are several times slower; do not demo with them.

Docker alternative: `docker compose up --build`. The Compose files are provided but were not run on the build machine.

## What's inside

| Screen | Where | What it does |
|---|---|---|
| **Home** | `/` | One sentence, an ask box and four starting points: Moon base fire risk, ISS cabin, how fire behaves in microgravity, what NASA hasn't tested yet. |
| **Answer** | `/answer` | For a starting point: finding, one visual, evidence grade, then measured / inferred / never tested, with sources. For a typed question: an extractive answer in which every sentence is verified against rows or pages, or an explicit refusal. |
| **Explore** | `/explore` | The experiments, at most 15 on screen, grouped by what burns, safety goal or era. Size = amount of test data. Relationships appear for the experiment in focus. |
| **Simulate** | `/lab` | One flame that reacts to oxygen, pressure and airflow, preset places, and one sentence with confidence and the nearest real test. |
| **Insights** | `/insights` | Up to eight findings recomputed from the data, each a sentence, a chart and its source. Links to the Studio (`/studio`) for custom charts and exports. |
| **Data** | `/data` | Data quality, everything set aside and why, every test. Any test opens the provenance panel: values with status → plain source → technical trail. Links to flame image measurements (`/image`). |

## Layout

```
backend/   adapters · core (schema, units, validation, store) · search · answer · llm · models · vision · api · tests
frontend/  Next.js App Router (home, answer, explore, lab, insights, studio, data, image) + components
config/    datasets.yaml · variables.yaml · models.yaml · presets.yaml · media.yaml · investigations.yaml · concepts.yaml · theme.tokens.json
data/      raw/ (inputs) · processed/ (Parquet + DuckDB) · artifacts/ (indexes, layouts, models, frames, vision results)
docs/      PLAN · DECISIONS · DESIGN · PERF · AUDIT (+ audit/ screenshots) · ADDING_A_DATASET · LIMITS
```

Read `docs/LIMITS.md` before drawing any conclusion from this build.
