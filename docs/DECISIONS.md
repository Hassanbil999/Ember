# Decisions

Choices made where the brief was open or the environment forced a deviation. Newest last.

| # | Decision | Why |
|---|----------|-----|
| 1 | Product name **Freefall Atlas**; repo at `freefall-atlas/`. | Short, describes the Atlas-first idea. |
| 2 | **`run.py` task runner** mirrors every `make` target. | The build machine had no `make` and no Docker. `make <t>` and `python run.py <t>` do the same thing. |
| 3 | Docker Compose + Dockerfiles are shipped but **were not run here** (no Docker on the build machine). | Kept per spec; the local path (`python run.py dev`) is the verified one. |
| 4 | **Dense embeddings default to local LSA** (TF-IDF → TruncatedSVD, 70 dims). `FA_EMBEDDER=st` switches to sentence-transformers MiniLM if installed. | sentence-transformers needs PyTorch (~2 GB). LSA runs offline instantly; on this corpus hybrid search scores MRR > 0.6 on the labeled set. |
| 5 | **No cross-encoder rerank by default.** | Same dependency reason; RRF of BM25 + dense is enough for tens to hundreds of items. Hook point: `search/index.py::search`. |
| 6 | **PDF viewer renders pages server-side with PyMuPDF** (PNG) and overlays highlight rectangles from `page.search_for`, instead of PDF.js. | Exact, theme-independent highlights with no worker setup; "Open PDF" still opens the original at the page. |
| 7 | Storage: **Parquet + a DuckDB file** (`data/processed/atlas.duckdb`); the API keeps an in-process pandas read model. | DuckDB for ad-hoc SQL and growth; in-memory frames keep requests < 150 ms. |
| 8 | **GP classifier / GP regressors** (RBF ARD + white noise), GroupKFold by campaign, baselines = base rate / training mean. | Gives calibrated uncertainty for the applicability display and the advisor. |
| 9 | **Applicability domain** = mean distance to the 5 nearest training points in standardized feature space (categoricals one-hot × 0.7). Inside ≤ 95th percentile of the training set's own leave-one-out distance; edge ≤ 2×; beyond = outside. Partial gravity is always `untested`. | Simple, explainable, configurable in `models.yaml`. |
| 10 | For partial-gravity scenarios on a model that has gravity as a feature, the Lab shows the **µg and 1g predictions as bounds**, never an interpolated "lunar" prediction. | The brief: microgravity and 1g can only bound partial gravity. |
| 11 | **Auto-grouping** = leaves of a shallow decision tree on the outcome (≤ 6 leaves), labeled by the path conditions; plus grouping by campaign. | Groups come out labeled by their defining conditions, as the spec asks. |
| 12 | **Relationships lens** = Spearman ρ + mutual information with pair counts; cells with n < 12 hatched; matrix ordered by hierarchical clustering on |ρ|, which also orders the parallel-coordinates axes. | Association with sample sizes, clearly not causation. |
| 13 | **Answer Engine is template-first**. An LLM (Anthropic, OpenAI-compatible or Ollama via env vars) may only rephrase the key-finding sentence; the rephrase is re-verified and falls back to the template on failure. | Works with no key; the LLM never adds evidence. |
| 14 | Numbers that restate the user's own query (e.g. "near O₂ 30%") are cited as `query` citations, so the verifier doesn't drop them, and the UI labels them as user input. | Without this, the verifier rejected correct sentences. |
| 15 | Evidence grades: *Measured* if a matched test lies within 0.35 σ; *Close conditions* within `close_conditions_distance` (1.0 σ); *Documented* = passages only; *No data* = abstain. | Configurable in `models.yaml`. |
| 16 | Demo fixture is **synthetic with plausible trends** (U-shaped flammability boundary in flow, CO₂ raising the extinction O₂, He raising K) plus **deliberate dirt** (mixed units, a 0-atm row, duplicates, missing outcomes, a 1.7 O₂ typo). | So every Refinery rule and every chart is exercised. All rows carry `demo = true`. |
| 17 | Catalog **years are approximate**; PSI ids and DOIs are left null ("to be filled from PSI") rather than invented. Material names in the fixture are generic. | Never fabricate citations. |
| 18 | Context-notes PDFs restate only facts from the challenge brief and are labeled "platform authors, not a NASA document". | Gives the Answer Engine documented passages without inventing NASA text. |
| 19 | Pressurized-rover preset: 34 % O₂ / 8.2 psi; ISS ventilation ~10 cm/s. | Common exploration-atmosphere planning values; editable in `presets.yaml`. |
| 20 | **Test patterns** link to four demo droplet tests and are generated from those tests' table K and d₀, so validation vs "published" values is meaningful for the pipeline. One sequence is an H.264 MP4 to exercise the ffmpeg path. Every view labels them "TEST PATTERN — synthetic shape, not a flame". | Proves the extractors without pretending to be footage. |
| 21 | ffmpeg comes from the **imageio-ffmpeg bundled binary** when no system ffmpeg exists. | No system ffmpeg on the build machine. |
| 22 | A flame that goes out with no droplet left is classified as **burnout**, not extinction. | Otherwise every burned-to-completion test reported a false extinction. |
| 23 | Background jobs use a **thread + in-memory job table** (FastAPI process) rather than RQ. | No Redis needed for 5–20 configured tests; swap point: `vision/pipeline.py::start_job`. |
| 24 | Workspace is **React Flow**; a wire between two items renders a live diff label (attributes held constant vs varied). Atlas nodes are dragged onto the Workspace tray with a pointer drag; panel items use HTML5 drag-and-drop. | Wokwi-style wiring without a heavyweight canvas. |
| 25 | Atlas canvas is **custom SVG** with a critically-damped spring camera (no d3-zoom), node moves are CSS-transform transitions. | Full control of fly-to + lens animation; ~50 nodes stay at 60 fps. WebGL is the path for >10k points. |
| 26 | Fonts: **Geist Sans + Geist Mono** from the `geist` npm package (bundled, offline). | Spec suggestion; no network font loading. |
| 27 | One-command swap to real data: `python run.py demo off` sets `config/profile.yaml: include_demo: false` (skips `demo: true` datasets and test-pattern media) and rebuilds. | The spec's "one-command operation". |

## Round 2

Format: *decision → principle → expected effect*. Decisions 24 and 25 above are superseded by 43 and 39.

| # | Decision | Principle | Expected effect |
|---|----------|-----------|-----------------|
| 28 | Raw values are checked against physical limits **in their own unit, before conversion**; a failing value is stored as "flagged" with no number. | Science integrity: flag, never convert | "0 atm" can no longer become "0 kPa" |
| 29 | A derived value is not computed when an input is flagged; it reads "Not computed: input flagged". | Never derive from invalid inputs | No fabricated O₂ partial pressure |
| 30 | Rows with an impossible value are excluded from every chart, statistic and model, and listed on the Data screen. | Provenance; honest limits | Bad rows stay visible but cannot influence a result |
| 31 | One backend "record" turns stored values into display text (status, plain label, unit, blank reason). | Single source of truth | The rules cannot drift between screens; testable without a browser |
| 32 | Gravity is stored as a regime code and always shown as a regime name ("Microgravity (ISS)", "Earth 1g"). | Correct physics: microgravity ≠ 0 g | No "0 g" anywhere |
| 33 | Dataset settings (e.g. flow 0 cm/s for droplets) carry the status "Assumed (dataset setting)" and a distinct style. | Distinguish measured / derived / assumed | An assumption is never read as a measurement |
| 34 | Outcomes read "Burned" / "Extinguished"; every blank states why. | Plain language; visibility of system status | No internal codes, no unexplained dash |
| 35 | Provenance panel in three levels: values → plain source with a link to the raw row → technical trail behind a toggle. | Progressive disclosure | A test is understood in seconds; experts still get everything |
| 36 | The home screen is one sentence, one ask box and four starting points. | Hick's law; one focal point | The purpose is clear in a glance |
| 37 | Each starting point opens an answer screen: finding, one visual, evidence grade, then measured / inferred / never tested as three separate columns. | Worked examples before open tools; dual coding | A first-time reader gets a result before meeting a tool |
| 38 | Explore shows experiments with data plus one cluster per group; clusters open on click; a node budget of 15 is enforced. | Cognitive load; Gestalt proximity | Structure is visible instead of buried |
| 39 | Node positions come from a slot grid computed once per grouping; no force simulation. | Measure, then remove the bottleneck; collision-free by construction | Labels cannot overlap; view changes hold 60 fps |
| 40 | Relationship lines appear only for the node under the pointer or selected, at most four, and labels sit on opaque plates. | Data-ink ratio; figure-ground | No spaghetti; a line never crosses text |
| 41 | Node size = number of tests, fill = safety goal, filled with the count inside = has data, hollow = catalogue entry only. | Recognition over recall; position/length before colour | Readable without the legend |
| 42 | Navigation is Explore · Simulate · Insights · Data. Depth and theme sit in one menu. Studio is reached from Insights, the Image Lab from Data. | Hick's law; minimalism | Four choices in plain words |
| 43 | Removed: Workspace canvas, command palette, onboarding modal, lens bar, relationships lens, zoom readout, fit button. Their packages (`@xyflow/react`, `cmdk`, `framer-motion`) were uninstalled. | Minimalism; delete dead code | Less to learn, less JavaScript to load |
| 44 | Simulator predictions come from one precomputed grid per material, interpolated in the browser. | Immediate feedback | A slider move is answered in the same frame, with no request |
| 45 | The simulator's sentence states outcome, confidence and the nearest real test; confidence is capped at "low" outside the tested range and at untested gravity; far from data it says "No data here". | Show uncertainty; never extrapolate silently; applicability domain | No confident answer where there is no evidence |
| 46 | The tested range is drawn under every slider. | Visibility of system status | The reader sees how far from data they are while dragging |
| 47 | The simulator reports model accuracy next to the baseline, on held-out campaigns. | Report models against baselines with cross-validation | The 66 % vs 55 % is stated, not hidden |
| 48 | Insights are computed from the rows on every load; a finding with too few rows is not emitted. | Provenance; no chart junk | The feed cannot go stale or overclaim |
| 49 | Serve a production build (`python run.py start`); `dev` remains for development. | Measure before optimizing: on-demand compilation was the largest delay | Screens usable in 0.2–0.7 s instead of 1.6–3.2 s |
| 50 | Computed API views are serialized once and the bytes reused; first screens are warmed at start-up. | Biggest bottleneck first (150 ms per grid response was JSON cleaning) | First click as fast as the tenth |
| 51 | Screens one click away are loaded in the background; test records are fetched on hover. | Prefetch the next likely view | Clicks answer in under 100 ms |
| 52 | A start card renders its answer immediately in place while the route change completes behind it; the material choice is local state. | Immediate feedback | 31–56 ms instead of ~190 ms |
| 53 | Dark theme by default, cool light theme, amber and blue as the only saturated colours, minimum text size 13 px. | Figure-ground; WCAG 2.2 AA | An identity tied to the subject; readable |
| 54 | The star field is a fixed layer painted once; overlay shadows are small. | Measured paint cost | Lower interaction-to-paint times |

## Round 3: real data and the atmosphere trade

| # | Decision | Principle | Expected effect |
|---|----------|-----------|-----------------|
| 55 | The real FLEX table (NASA PSI-69) replaces the synthetic droplet set; the synthetic set is disabled, not mixed in. | Provenance; never blend real and synthetic | Every droplet number on screen is a NASA measurement |
| 56 | "Disruption" maps to no outcome instead of being forced into burned or extinguished. | Do not invent a measurement | 61 tests stay honest; the outcome model uses 212 decided tests |
| 57 | Test id, campaign (calendar quarter) and main inert gas are built by the adapter and recorded as derived. | Distinguish measured from derived | Nothing synthetic is presented as a source column |
| 58 | Droplet models use the CO₂ and helium mole fractions as features, not a single diluent category. | Use the data as measured | Mixtures are represented as they were tested |
| 59 | The rule "rate reported for an extinguished flame" now applies to flame spread only. | Correct physics: a droplet has a burning rate before it extinguishes | 170 real rows are no longer wrongly flagged |
| 60 | Two new checks: gas fractions that do not add to 100 %, and an extinction diameter above the starting diameter. | Flag, never fix | Found 6 and 1 rows in the real table |
| 61 | Screens and findings are labelled per dataset ("Real NASA data" / "Demo data"); findings on real data are listed first. | Honest limits; provenance | A reader always knows which kind of evidence they are looking at |
| 62 | When a model does not beat its baseline the simulator says "no better than always guessing" and reports the AUC. | Report models against baselines | The droplet classifier's 86 % is not passed off as skill |
| 63 | New centrepiece: the atmosphere trade map (pressure × oxygen) with breathing, spacewalk and fire layers. | One focal point; dual coding; show the decision the data serves | The gap becomes a consequence: the planned habitat air sits outside the FLEX tests |
| 64 | Physiology constants and formulas are taken from NASA OCHMO briefs, served with their sources, and unit-tested against the briefs' own numbers. | Provenance for every value; correct physics | Nothing on the map is from memory |
| 65 | On the trade map a prediction counts as supported only inside the tested pressure and oxygen ranges. | Applicability domain; never extrapolate silently | No confident colour where FLEX never tested |
| 66 | The synthetic droplet report is no longer ingested. | Remove what contradicts the evidence | Answers cannot quote synthetic droplet text beside real droplet data |
| 67 | The simulator's flame is drawn by one fragment shader (no 3D library), in a window that stays dark in both themes. | Measure before adding weight: no new dependency; figure-ground | A cinematic flame for a few kilobytes of code |
| 68 | Blue and amber are kept as two colour families that cross-fade in a narrow band. | Correct physics (starved microgravity flames are blue); colour carries meaning | The flame never turns an ambiguous grey |
| 69 | A real FLEX test can be replayed in the same scene, timed by d² = d₀² − K·t and ending at the measured extinction diameter. Reached from the "nearest real test" in the sentence, not from a new screen. | Worked example; provenance; no extra feature surface | Spectacle and data are the same thing |
| 70 | Sound is generated, tied to burning rate, airflow and breathable oxygen, and off by default. | Immediate feedback through a second sense; user control | Adds feeling without surprising anyone |
| 71 | The simulator states whether a crew could breathe the chosen air, using the same NASA limits as the atmosphere trade. | Consistency; connect the screens | Fire and breathing are read together everywhere |
| 72 | Without a GPU (software rendering) the flat flame is used; with one, the scene lowers its own resolution if frames run slow. | Performance budget first | No machine is made to stutter for decoration |
