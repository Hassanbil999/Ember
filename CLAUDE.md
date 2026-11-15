# Ember (repo: freefall-atlas)

NASA Space Apps 2026 entry: will a small fire keep burning in spacecraft and Moon/Mars habitat air? Built on NASA microgravity combustion research. A landing page (`/`) leads to the **engine** (`/engine`: Simulation, Fire check, Fire map, Find data, Statistics), the **research paper** (a PDF, `web/public/research-paper.pdf`, README Decision BA) and the **presentation**. The name is Ember everywhere; only the GitHub repo name and the live link's Modal app id still read freefall-atlas (README Decision AT). UI style: a product, not a paper: short copy, colour, no Limits sections on pages (README Decision AU).

## This repo
- This repo already holds the **old site with real, cleaned NASA data**. We are replacing its UI with the new frontend and connecting that frontend to the existing data. We are not starting over.
- Target product: `SPEC.md`. **§0 explains how it applies to this repo.** Read it before planning.
- Simulator and Find data reference: `prototype/index.html`. Match it; do not redesign those two views. Reuse its shader, model and layout code. The landing, engine shell, fire check, statistics and presentation pages are new design on the same type, with the brighter Ember palette (README Decisions AQ, AU).
- Gap-filling starter data: `data/seed.json`. Use it only where the real data has nothing.
- Audit of the old site: `docs/AUDIT.md` (written in M0). Keep it up to date when the mapping changes.

## Never do
- Delete or rewrite cleaned data, cleaning scripts, migrations or database contents.
- Re-run cleaning or ingestion that already exists (see `docs/AUDIT.md`).
- Delete anything before the M0 audit is approved.
- Work outside the `rebuild/new-frontend` branch. The old site is tagged `v0-old-site`.
- Let a seed or placeholder row overwrite a real row.
- Invent NASA data. Every number in the UI or an export traces to a source, or is labelled placeholder/unverified. AI-extracted values stay `verified=false` until a person checks them.

## Rules that matter for judging
- **AI must cite or refuse.** Summaries and answers cite resource ids from their context; unknown ids are stripped. With no `ANTHROPIC_API_KEY`, fall back to templates so the demo still works.
- **The simulator is illustrative.** Keep the "How this is calculated" note and the coverage messages. The anchor tests in `SPEC.md` §8.5 must pass, and the model is fitted to real verified points (§8.4).
- **The demo needs no login and no API keys.** One start command from a clean checkout runs the new UI on the real data.
- Keep a working build at the end of every milestone (`SPEC.md` §14) and commit after each.
- Accessibility: real buttons and labels, keyboard-operable sliders, visible focus, never color alone, respect `prefers-reduced-motion`.

## Stack and commands
Existing backend kept: Python + FastAPI (`backend/`), data in Parquet + DuckDB (`data/processed/`, gitignored, rebuilt by ingest). New web app: React 18 + Vite + TS in `web/`, built into `web/dist` and served by FastAPI on the same port. No Postgres (README Decision E).

- Start everything (clean checkout, one command): `python run.py start` → http://localhost:8000
- Dev servers: `python run.py dev` (API :8000 with reload, Vite :5173)
- Load data: `python run.py ingest [canonical|existing|seed|fit|all]` (= `python -m backend.ingest <step>`); `canonical` is the team's cleaning pipeline, unchanged
- Unit tests: `python -m pytest backend/tests -q` · browser model parity: `cd web && npm test` · e2e: `python run.py e2e` · all: `python run.py test`
- Container: `docker compose up --build` (root `Dockerfile`: builds the web app, runs `ingest all` at build time)
- Code map: `backend/catalog/` = adapter layer to SPEC §5 (`build.py` existing, `seed.py`, `query.py` read side); `backend/api/routes_*.py` = SPEC §9; `backend/sim/model.py` = SPEC §8; `backend/predict/` = fire check (`firemap.py` = fire map); `web/src/sim/` = stage, model copy, store; `web/src/router.tsx` = pathname router; `web/src/Engine.tsx` = engine shell; `web/src/views/` = engine pages; `web/src/site/` = landing, presentation

## Secrets
Use `.env` (see `.env.example`, merged with any existing env file). Never commit keys.
