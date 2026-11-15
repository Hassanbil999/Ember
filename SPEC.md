# Ember: Build Spec

NASA Space Apps Challenge 2026: an AI-powered dashboard that summarizes, ranks and interprets NASA microgravity combustion research for fire safety in spacecraft, Moon and Mars habitats, and pressurized rovers.

The working prototype lives at `prototype/index.html`. **It is the source of truth for look, layout and interaction.** This spec says what must become real: a backend, a database, ingestion of real NASA data, AI features with citations, and real exports.

---

## 0. Starting point: build on the existing repo

This is an upgrade, not a fresh build. The repo already holds the old site (then called Freefall Atlas) **with real NASA data the team cleaned and integrated**. Do not repeat that work.

- **Keep:** cleaned datasets, cleaning and ingestion scripts, database contents and migrations, and any backend code that serves the data.
- **Delete:** the old frontend UI, plus code that only it uses. Do this only after the audit (M0) is approved, and only on the branch `rebuild/new-frontend`, with the old version tagged `v0-old-site`.
- **The new frontend is the product.** Port `prototype/index.html` and make it the only UI.
- **Stack:** if the repo has a working backend (for example Node/Express or Python), keep it and implement the API shapes in §9 on top of it. §4's FastAPI + Postgres stack is the default only for parts that don't exist yet.
- **Adapter layer:** map the existing data to the §5 model (investigations, resources, test_points) through views, a mapping module or a migration. The UI only talks to the §9 API.
- **Real data wins.** `data/seed.json` only fills gaps the real data doesn't cover (for example, papers and placeholders the old site lacks), and those rows keep their placeholder/unverified labels. Never overwrite a real row with a seed row.
- **Ingestion (§6):** run only the steps the existing pipeline doesn't already cover. Extend the existing scripts rather than replacing them.

---

## 1. Product in one paragraph

Ember has two connected views.

- **Simulate** lets anyone pick an environment (ISS, Moon base, lunar rover with the fan off, Mars base, custom) and a material, then watch a flame and the airflow react to gravity, oxygen, pressure and fan speed over a time window t1 → t2. A flammability map shows where the settings sit against measured NASA tests.
- **Find data** lets users filter NASA research by data type, investigation, purpose, fuel, environment and credibility. Each result shows a credibility score, and the AI summarizes the filtered set with citations and names the gaps.

The two views form one loop. Any measured test opens in the simulator ("▶ Simulate"), and the simulator jumps to the nearest data ("Find data for these settings").

## 2. Users and top tasks

| User | Top task | Success looks like |
|---|---|---|
| Aerospace engineer | "Will this fabric burn at 34% O₂ and 8.2 psi, and how fast?" | Answer plus nearest measured evidence in under 30 s |
| Researcher / grad student | Get comparable test conditions from many investigations as CSV | One filtered export with a source on every row |
| Student / educator | Understand why fire behaves differently without gravity | Sees the flame change shape live when gravity changes |

## 3. Challenge and judging alignment (requirements)

| Requirement | Where it is met |
|---|---|
| Summarize, rank, interpret PSI combustion investigations | Find data: AI summary, ranking by fit/credibility, investigation tags |
| Most relevant to habitable environments (spacecraft, station, Moon/Mars bases, rovers) | Environment presets; "Best fit for <environment>" sort |
| Extract data for predictive modeling | Test-point table, CSV/JSON export, model fit endpoint |
| Inform next-generation fire safety controls | Purpose tags (prevent / detect / suppress); coverage gaps |
| Optional Earth applications | Environment filter "Earth"; tags on SAME, FLEX etc. |
| Judging: Impact, Creativity, Validity, Relevance, Presentation | See the tests in §13: every number traceable, model validated against anchors, demo path works with no login |

## 4. Architecture

```
            ┌───────────────┐       ┌───────────────────────┐
 browser ──▶│  web (React)  │──────▶│  api (FastAPI)        │──▶ Claude API (summaries, Q&A, extraction)
            └───────────────┘  JSON └─────────┬─────────────┘
                                              │ SQL
                                     ┌────────▼─────────┐
                                     │ Postgres+pgvector│
                                     └────────▲─────────┘
                                              │
                         ingest CLI (python) ─┘◀── PSI S3 bucket, NTRS, data/seed.json
```

**Default stack** (used only for parts the existing repo doesn't already have; see §0. Chosen to match the team: Python, JavaScript, Docker):

- `web/`: React 18 + Vite + TypeScript. No UI kit; port the prototype's CSS tokens. WebGL flame and canvas particles ported as components.
- `api/`: Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, scipy (model fitting), pdfplumber or PyMuPDF (PDF text), sentence-transformers `all-MiniLM-L6-v2` (384-dim embeddings, runs locally), Anthropic Python SDK.
- `db`: Postgres 16 with the `pgvector` extension.
- `docker-compose.yml` runs db + api + web for local work.

**Repo layout**

```
/web            React app (views/Simulate, views/FindData, components/*)
/api            FastAPI app (routers/, models/, services/, sim/, ai/, credibility/)
/api/ingest     CLI: seed, psi, ntrs, text, extract, embed, fit
/data/seed.json Starter data (from the prototype) – loaded by `ingest seed`
/prototype      The reference prototype (do not edit)
docker-compose.yml, .env.example, README.md
```

## 5. Data model

All tables have `id` (uuid or serial) and `created_at`/`updated_at`.

**investigations**: `slug` (unique, e.g. `bass`), `name`, `full_name`, `purposes text[]` (prevent|detect|suppress|basics), `fuels text[]` (solid|liquid|gas|none), `envs text[]` (space|partial|earth), `hardware`, `summary`, `psi_url`.

**resources**: one row per thing a user can open.
- `investigation_id`, `type` enum: `data | paper | report | slides | video | image | news`
- `title`, `publisher`, `year`, `format` (CSV, PDF, MP4…), `url` (nullable), `s3_key` (nullable), `description`
- `cred_publisher`, `cred_review`, `cred_trace` (0–1 floats, nullable)
- `status` enum: `published | placeholder`. A placeholder has no `url`/`s3_key` and is always "Unverified".
- `envs_override text[]` (nullable; overrides the investigation's envs, e.g. Saffire-V tested an exploration atmosphere)

**test_points**: one measured burn or test condition.
- `code` (unique, e.g. `SAF1-C`), `investigation_id`, `source_resource_id` (nullable for placeholders)
- `material` (fabric|pmma|droplet|gas|other), `sample_desc`, `geometry`
- `gravity_g`, `o2_pct`, `pressure_kpa`, `flow_cm_s`, `flow_direction` (opposed|concurrent|none), `diluent` (N2|CO2|He|null)
- `outcome` enum: `burned | went_out | cool_flame | flame | measured`
- `spread_mm_s`, `notes`
- **provenance**: `source_page`, `source_quote` (≤ 30 words, verbatim, the text that contains the numbers), `extraction` (manual|ai), `verified bool`, `verified_by`, `verified_at`

**resource_points**: many-to-many (a dataset and a paper can both hold the same test point).

**chunks**: `resource_id`, `page`, `text`, `embedding vector(384)`. Used by Ask and by summaries.

**model_params**: `material`, `xmin`, `ustar`, `kl`, `kh`, `c`, `pexp`, `n_points`, `rmse`, `fitted_at`. Defaults from §8 until a fit exists.

**ai_cache**: `key` (sha256 of prompt + inputs), `response jsonb`, `created_at`.

## 6. Ingestion (`python -m ingest <step>`, every step idempotent)

**Run only what the existing pipeline doesn't cover** (see `docs/AUDIT.md`). If the old site already loads PSI data, reuse that loader and map its output; don't download or clean the same data again.

0. **existing**: load or map the team's cleaned data into the §5 model. This always runs first.
1. **seed**: load `data/seed.json` (investigations, resources, test points) **only where no real row exists**, matched by investigation slug, resource URL/title and test-point code. Keep `status` and `verified` exactly as given.
2. **psi**: list the public PSI bucket `s3://nasa-psi` (region `us-west-2`, anonymous access with boto3 `Config(signature_version=UNSIGNED)`). Do not hard-code folder names: first run `ingest psi --discover` to write `data/psi_map.csv` (prefix → candidate investigation slug) for a human to confirm. Then register each file as a resource: `.csv .xlsx .txt .dat` → data, `.mp4 .avi .mov` → video, `.jpg .png .tif` → image, `.pdf` → report, `.ppt .pptx` → slides. Publisher "NASA PSI", trace = 1.0 for raw data files.
3. **ntrs**: for each investigation, query the NASA Technical Reports Server API for its name and acronym (verify the current endpoint and response format before coding; the public search API is under `https://ntrs.nasa.gov/api/`). Map document types: journal article → paper, conference paper → paper, technical report → report, presentation → slides. Store the citation URL.
4. **text**: download PDFs (PSI and NTRS), extract text per page, split into ~800-token chunks with page numbers.
5. **embed**: embed chunks with sentence-transformers and store in `chunks.embedding`.
6. **extract**: for data files and PDFs likely to hold test matrices, ask Claude to return test points that match the `test_points` schema through a tool/JSON schema. Rules:
   - every row must include `source_page` and a verbatim `source_quote` that contains its numbers; drop rows whose quote is not found in the chunk text
   - reject values outside physical ranges (O₂ 0–100 %, pressure 0–200 kPa, flow 0–100 cm/s, gravity 0–1.2 g)
   - insert with `extraction='ai'`, `verified=false`
7. **fit**: fit model parameters per material to **verified** test points (§8.4) and write `model_params`.

Add an admin page `/admin/verify` (protected by `ADMIN_TOKEN`) that lists unverified AI-extracted points next to their source quote and page. Buttons: verify, edit, reject.

## 7. Credibility score

$$S = 100\,(0.4\,P + 0.3\,R + 0.3\,T)$$

Here $P$ is the publisher score, $R$ the review score and $T$ the traceability score, each from 0 to 1. Labels: High for $S \ge 85$, Medium for $65 \le S < 85$, Low below 65. A resource with `status = placeholder` (no URL or file) is **Unverified** and has no score.

Default factor values, assigned by ingestion rules and editable by admins:

| Factor | 1.0 | 0.85 | 0.75 | 0.6 | 0.5 | 0.4 |
|---|---|---|---|---|---|---|
| Publisher $P$ | NASA PSI flight data; peer-reviewed journal; NASA image of record | NASA NTRS | Conference | NASA web article | University/press news | Other web |
| Review $R$ | Peer-reviewed | — | NTRS technical review (0.8) | Presentation | — | Editorial / none |
| Traceability $T$ | Raw data files | Numbers + methods (0.8) | — | Abstract only | Summary | Popular article |

The API returns the score, the label, the three factors and a one-line explanation, so the UI can show "Publisher 85 · Review 80 · Traceability 90".

## 8. Simulation model (illustrative reduced-order model; port from the prototype)

### 8.1 Flame limit and spread

Gravity-driven flow, effective flow and the oxygen limit:

$$u_b = 30\sqrt{g}\ \text{cm/s}, \qquad u_\text{eff} = \sqrt{u^2 + u_b^2 + u_d^2}, \quad u_d = 0.3\ \text{cm/s}$$

$$X_\text{lim}(u) = \Big[X_\text{min} + k\,\ln^2\!\Big(\frac{u_\text{eff}}{u^*}\Big)\Big]\Big(\frac{14.7}{P_\text{psi}}\Big)^{n}, \qquad k = \begin{cases}k_l & u_\text{eff} < u^* \\ k_h & \text{otherwise}\end{cases}$$

The flame burns when $X_{O_2} \ge X_\text{lim}$. Below $u^*$ it goes out by quenching; above, by blow-off. Spread rate:

$$V = c\,(X_{O_2} - X_\text{lim})\,\frac{u_\text{eff}}{u_\text{eff} + 5}\ \text{mm/s}$$

Default parameters (until §8.4 fits them):

| material | $X_\text{min}$ | $u^*$ | $k_l$ | $k_h$ | $c$ | $n$ |
|---|---|---|---|---|---|---|
| fabric (cotton-fiberglass) | 15.5 | 8 | 1.5 | 0.78 | 0.46 | 0.15 |
| pmma (acrylic rod) | 16.0 | 5 | 1.5 | 0.78 | 0.30 | 0.15 |

### 8.2 Time series (`POST /api/simulate`)

Step $\Delta t = 0.05$ s over a 100 mm sample; igniter on for 1.5 s. Intensity $I$ relaxes toward 1 when the flame burns, toward 0.55 while the igniter is on, and toward 0 otherwise (rates 2.2 s⁻¹ rising, 1.4 s⁻¹ falling). The front advances $V \min(1, 1.15 I)\,\Delta t$. Record `t_out` when $I < 0.03$ after ignition ends, and `t_end` when the front reaches 100 mm. Duration $D$ rounds $t_\text{burn} + 4$ up to 5 s, clamped to 10–240 s (10 s if it never burns). The prototype's `simulate()` is the reference implementation.

### 8.3 Coverage and nearest evidence

- Partial gravity ($0.02 < g < 0.95$): "No partial-gravity data exists yet; 0 g and 1 g results bound this."
- Above the highest verified solid-fuel O₂, or below the lowest tested pressure: "Extrapolated".
- Nearest test point, by distance:

$$d^2 = \Big(\frac{\Delta g}{0.3}\Big)^2 + \Big(\frac{\Delta X}{8}\Big)^2 + \Big(\frac{\Delta P_\text{kPa}}{30}\Big)^2 + \Big(\frac{\ln\frac{u+0.3}{u'+0.3}}{1.2}\Big)^2 + 2.25\,[\text{material differs}]$$

A match is close for $d < 1$, partial for $d < 2.5$, otherwise distant.

### 8.4 Fitting (`ingest fit`)

Fit $X_\text{min}, u^*, k_l, k_h, c$ per material with `scipy.optimize.least_squares` on verified points. Use a hinge loss on the sign of $X_{O_2} - X_\text{lim}$ (burned vs went out, margin 0.5 points) plus squared error on `spread_mm_s` where present. Store `n_points` and `rmse`. With fewer than 4 verified points, keep the defaults.

### 8.5 Anchor tests (must pass with default parameters)

- PMMA, 0 g, 17 % O₂, 5 cm/s, 14.7 psi → burns.
- PMMA, 0 g, 21 %, 0.5 cm/s → goes out (quench).
- PMMA, 1 g, 18 %, 0 cm/s → goes out; PMMA, 1 g, 21 %, 0 cm/s → burns.
- Fabric, 0 g, 21 %, 20 cm/s → spread 1.8 ± 0.15 mm/s (Saffire-I).
- Fabric, 0.166 g, 34 %, 8.2 psi, fan off → burns (gravity still feeds it).

## 9. API (FastAPI, JSON, OpenAPI docs at `/docs`)

| Method & path | Purpose |
|---|---|
| `GET /api/presets` | Environment presets (label, g, o2, psi, u, env, note) |
| `GET /api/investigations` | All investigations with tags |
| `GET /api/resources` | Filtered, sorted list. Query: `q, types[], inv[], purpose[], fuel[], env[], cred_min (any|verified|medium|high), sort (fit:<preset>|cred|near|new), g, o2, psi, u, material, page, page_size`. Returns items with credibility, plus facet counts per type |
| `GET /api/resources/{id}` | Details, credibility factors, test points |
| `GET /api/test-points` | Filter by investigation, material, verified, ranges |
| `POST /api/simulate` | Body `{g, o2, psi, u, material}` → model result + time series (`t[], I[], x_mm[]`, `t_out`, `t_end`, `D`), coverage message, 3 nearest test points, model params used |
| `GET /api/flammability-map` | Same body as query → limit curve points for the map |
| `POST /api/ai/summary` | Body: the current filters → 2–3 sentence summary that names top sources and gaps, with citations `[resource_id]`. Cached in `ai_cache` |
| `POST /api/ai/ask` | Body `{question, filters?}` → answer grounded in retrieved chunks, with citations (resource id + page). If retrieval finds nothing relevant: "The data here doesn't cover that." |
| `POST /api/export` | Body `{resource_ids[], format: csv|json|bibtex}` → file download with a source column on every row |
| `POST /api/admin/test-points/{id}/verify` | Admin only (`ADMIN_TOKEN` header) |

## 10. Frontend (port the prototype exactly, then wire to the API)

Keep the prototype's tokens, fonts (Barlow Condensed, IBM Plex Sans, IBM Plex Mono), dark single theme and layout.

**Site structure (added 2026-11-14, README Decision AG).** A landing page (`/`) leads to the engine (`/engine`: Simulation, Fire check, Find data, Statistics; the simulation is the front door), the research page (`/research`) and the presentation (`/presentation`). The Simulate and Find data views below keep the prototype's layout; the palette is the brighter Ember one (Decision AL). The other pages are new design.

**Simulate view**
- Full-bleed stage: particle airflow canvas, scene canvas (duct, sample, char glow, igniter), WebGL flame canvas (the prototype's fragment shader; 2D fallback when WebGL is missing).
- Left panel "Experiment": presets, sliders (gravity, oxygen, pressure, airflow on a log scale), material toggle. Collapsible. The flame stays centred (the camera follows the front), the run starts only on Ignite or Play, and a muteable synthesized fire sound follows the flame (README Decision AP).
- Right panel "Result": verdict pill and sentence, two numbers, flammability map (click to set O₂ and airflow), evidence (coverage line and nearest test with "Load it"), compare box when a record is loaded, "How this is calculated". Collapsible.
- Bottom timeline: play/pause, speed (1×, 2×, 5×, 10×), draggable t1/t2 handles and playhead (keyboard-operable sliders), burned-length curve, out/burn-through marker, and the stats line for t1 → t2.
- The model runs on the server (`/api/simulate`), debounced 150 ms while dragging. Keep a client copy of the model for instant feedback and reconcile with the server result.

**Find data view**
- Filters on top: search + sort, type chips with counts, dropdowns (Investigation, Purpose, Fuel, Environment, Credibility), "Clear filters".
- Summary line: count, high-credibility count, unverified count, AI summary from `/api/ai/summary` with clickable citations.
- Result rows: type icon, title (link), subtitle, credibility meter + label + score, "▶ Try" (when a simulatable test exists), "Add", expand (description, credibility factors and formula, test-point table with ▶ Simulate).
- Export bar appears only when items are selected. The dialog previews CSV/JSON/BibTeX and **downloads a real file** from `/api/export`.
- Add an "Ask the NASA sources" box above the results: question → `/api/ai/ask`, with answers that show their citations.

Routing: real paths (`/engine`, `/engine/check`, `/engine/data`, `/engine/stats`) with Back/Forward; the old `/#simulate` and `/#data` links redirect and keep their query. Keep filters, simulator settings and fire-check inputs in the URL query so views can be shared.

## 11. AI rules (Claude via the Anthropic SDK)

- Model from env `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`). Key from `ANTHROPIC_API_KEY`.
- **Cite or refuse.** Every factual sentence in a summary or answer cites a resource id that was passed in the context. The API drops any citation that is not in the context and rejects answers without citations.
- Never invent numbers. Numbers in answers must appear in the retrieved chunks or test points.
- If no API key is set, `/api/ai/summary` falls back to the prototype's template and `/api/ai/ask` returns 503 with a clear message. The demo must still work.
- Cache by input hash. Time out after 20 s.

## 12. Non-functional

- No login for viewers. Admin pages need `ADMIN_TOKEN`.
- Accessibility: real buttons and labels, keyboard sliders, visible focus, color-blind-safe (orange `#d4772a` and blue `#3f8ee8`, never color alone), `prefers-reduced-motion` respected.
- Performance: the stage holds 50+ fps on a mid laptop. The WebGL canvas renders at ≤ 1.5× DPR; particles scale with area (cap 1300). The first API response arrives in < 300 ms with seed data.
- Every number shown in the UI is traceable: test points link to their resource; placeholders say "placeholder".

## 13. Tests and acceptance criteria

- `pytest`: the §8.5 anchor tests; the credibility formula and labels; filters and sorts on seed data; export CSV has a `source` column; AI endpoints with a mocked client (citation filter drops unknown ids).
- Playwright smoke: load `#simulate`, switch preset to "Lunar rover, fan off" → verdict "Burns"; open Find data → filter type "Research paper" → expand the BASS-II paper → "▶ Simulate" opens the simulator with the record's settings and the compare box says "The model agrees."
- The demo works from a clean checkout with one start command and **the team's real data loaded** (no API key, no S3 access needed).
- No test or screen still depends on the deleted old frontend.

## 14. Milestones (hackathon order: always keep a demoable build)

0. **M0: audit and safe cleanup.** Write `docs/AUDIT.md` covering:
   - the stack and how to run it;
   - every data asset (format, row counts, where it came from, which script made it);
   - the existing API routes;
   - a field-by-field mapping to §5, with gaps marked;
   - a keep/adapt/delete decision for every top-level folder.

   **Stop for the team's approval.** Then create the branch `rebuild/new-frontend`, tag `v0-old-site`, and delete the old UI and dead code.
1. **M1: new frontend on real data.** The schema or adapter maps the existing data to §5. `ingest existing` runs, then `ingest seed`, which only fills gaps. Add `GET /api/resources`, `/api/investigations` and `/api/presets`. The React app ports the prototype and reads from the API. *Demoable on real data.*
2. **M2: simulator on the server.** `/api/simulate` + `/api/flammability-map` + nearest evidence; anchor tests pass.
3. **M3: real exports.** `/api/export` (CSV, JSON, BibTeX) with downloads.
4. **M4: AI.** `/api/ai/summary` with citations and fallback; then `/api/ai/ask` over chunks.
5. **M5: fill data gaps.** Only for sources the cleaned data doesn't include:
   - `ingest psi --discover`, then the team reviews the mapping, then `ingest psi`;
   - `ntrs`, `text`, `embed` (needed for Ask), and `extract`;
   - the admin verify page;
   - `ingest fit` on the real, verified test points.
6. **M6: deploy.** Web on Vercel or Netlify, API on Render/Fly/Railway, Postgres on Neon or Supabase (pgvector on). Public URL with no login.

## 15. Out of scope

- A CFD solver or any claim of design-grade accuracy. The UI always calls the model illustrative.
- Droplet and gas-flame simulation (show "n/a" for those test points, as the prototype does).
- User accounts beyond the admin token.
