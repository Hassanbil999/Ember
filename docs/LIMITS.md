# Known limitations

Stated plainly, because honest limits are part of the product.

## Data
- **All tabular data, reports and media in this build are a synthetic demo fixture.** They are shaped like FLEX and BASS-II tables but are **not NASA results**. A persistent badge says so on every screen; every exported CSV, citation and report carries the same warning.
- The trends in the fixture (U-shaped flammability boundary vs flow, CO₂ raising extinction O₂, helium raising K, lower extinction O₂ in gentle microgravity flow than at 1g) were **chosen by the fixture author** to resemble the literature qualitatively. Any agreement with real physics is by construction, not discovery.
- Only two investigations (BASS-II, FLEX/FLEX-2) have table data. The other 14 catalog entries are **metadata only**; their nodes are hollow and say "no test data yet".
- Catalog **years are approximate**; **PSI ids and DOIs are empty** until filled from PSI. Nothing was invented.
- The two "context notes" PDFs restate facts from the challenge brief. They are not NASA documents and are labeled as such.

## Partial gravity
- **PSI contains no partial-gravity combustion data.** Lunar (0.165 g) and Martian (0.38 g) scenarios are always flagged `untested`. Where a model has gravity as a feature (solid tests include 1g ground references), the Lab shows µg and 1g predictions as **bounds**, never a lunar prediction. The droplet models have only µg data and mark any non-zero gravity as outside their scope.

## Models
- Surrogates (Gaussian processes) **interpolate the loaded tests**; they are not physics models and cannot extrapolate physics. Extrapolations are greyed out.
- Cross-validation groups by campaign. With 5 campaigns per dataset the CV estimates are noisy. All five models beat their naive baseline on the fixture; the solid burn/extinction classifier is the weakest (accuracy 0.66, AUC 0.83 vs baseline AUC 0.5).
- The applicability domain is distance-based. It does not detect a region that is dense in data but where the response changes abruptly.
- Sensitivity is local (±10 % of each tested range at the current scenario), not a global importance measure.
- The next-experiment advisor proposes points of maximum predictive uncertainty. It is a **research aid**, does not model test cost or hardware limits, and holds gravity at µg (the nearest testable proxy).
- The simulator's flame is an **illustration driven by the model's outputs** (chance of burning, predicted rate) and by simple rules for shape and colour. It is not a combustion simulation and is labelled as such on screen.
- The simulator interpolates a precomputed grid (37 × 13 × 11 points per material). Between grid points the value is a linear blend, so it can differ slightly from a direct model call.
- In the demo fixture the solid-material model finds almost no difference between materials, so the four materials receive nearly identical estimates.

## Image Lab
- The only loaded media are **programmatic test patterns** (dark disc on a bright background; bright ring on dark). Extractors measure them within 0.8 % of the known diameters (unit tests require < 2 %). **This proves the pipeline, not its accuracy on real flame footage**, which has soot, glare, fibre supports, out-of-focus edges and drifting droplets.
- The backlit extractor assumes one dominant dark object and a uniform backlight estimated from the frame border. The flame extractor uses a luminosity threshold; the red/blue ratio is only a rough proxy for soot radiation.
- Events (ignition, extinction, burnout, disruption) use simple thresholds and may need per-test tuning through the correction loop.
- Background jobs are in-process threads: they don't survive a server restart, and there's no queue for large batches.

## Search and answers
- Dense retrieval uses local LSA. It is weaker than a neural embedder on paraphrases. `FA_EMBEDDER=st` enables MiniLM if sentence-transformers is installed. There is no cross-encoder rerank.
- The query parser understands common units and phrasings ("30 percent oxygen", "0.3 O2", "10 psi", "moon base"), not arbitrary language. Unparsed words fall back to keyword search.
- The template answer composer picks a metric from keywords (burn share, K, extinction diameter, spread rate). Unusual questions may get a passage-only (*Documented*) answer.
- The citation verifier checks that quoted spans exist verbatim and that every number matches a cited row value, a recomputed aggregate, or the user's own query. It does **not** judge whether a sentence's reasoning is correct.

## Engineering
- Docker Compose files are provided but were not run on the build machine (no Docker available). The verified path is `python run.py start`.
- The Studio report lives in the browser's localStorage. It is per-browser and not shared.
- The simulator animation measured 44–55 fps in a headless browser without a GPU; 60 fps on real hardware is expected but not verified (`docs/PERF.md`).
- Desktop-first. Not tuned for phones or for widths below ~1200 px.
