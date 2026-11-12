# Known limitations

Stated plainly, because honest limits are part of the product.

## Data
- **Droplet data is real; the rest is not.** The droplet table is the FLEX experimental table from NASA PSI (PSI-69): 274 tests of methanol and n-heptane droplets, 2009–2011, loaded as published. The **solid-material table, the three reports and the image test patterns are a synthetic demo fixture** and are **not NASA results**; the header notice, the Insights tags and the item pickers say which is which, and exports of demo rows carry the warning.
- The FLEX table gives the atmosphere as four mole fractions. The models use the CO₂ and helium fractions directly; the "main inert gas" shown per test is only the largest of the three and is marked as derived.
- FLEX "Disruption" tests (61 of 274: the droplet broke apart) have no burn-or-extinguish outcome. They are kept for their conditions and rates and left out of the outcome model.
- The FLEX file was copied from the PSI export supplied with the project; it was not re-downloaded or checked against PSI for later corrections.
- The trends in the fixture (U-shaped flammability boundary vs flow, CO₂ raising extinction O₂, helium raising K, lower extinction O₂ in gentle microgravity flow than at 1g) were **chosen by the fixture author** to resemble the literature qualitatively. Any agreement with real physics is by construction, not discovery.
- Only two investigations (BASS-II as demo, FLEX as real data) have table data. The other 14 catalog entries are **metadata only**; their nodes are hollow and say "no test data yet".
- Catalog **years are approximate**; **PSI ids and DOIs are empty** until filled from PSI. Nothing was invented.
- The two "context notes" PDFs restate facts from the challenge brief. They are not NASA documents and are labeled as such.

## Partial gravity
- **PSI contains no partial-gravity combustion data.** Lunar (0.165 g) and Martian (0.38 g) scenarios are always flagged `untested`. Where a model has gravity as a feature (solid tests include 1g ground references), the Lab shows µg and 1g predictions as **bounds**, never a lunar prediction. The droplet models have only µg data and mark any non-zero gravity as outside their scope.

## Models
- Surrogates (Gaussian processes) **interpolate the loaded tests**; they are not physics models and cannot extrapolate physics. Extrapolations are greyed out.
- Cross-validation groups by campaign. With 5 campaigns per dataset the CV estimates are noisy. On the real FLEX data the droplet burn/extinction classifier does **not** beat the base rate on accuracy (0.86 vs 0.87, because 87 % of decided tests end in extinction); it does on Brier score and AUC (0.82). The simulator says so in words. The extinction-diameter model is the strongest (R² 0.83), the burning-rate model moderate (R² 0.56). The solid models are trained on demo data (accuracy 0.66 vs 0.55).
- The applicability domain is distance-based. It does not detect a region that is dense in data but where the response changes abruptly.
- Sensitivity is local (±10 % of each tested range at the current scenario), not a global importance measure.
- The next-experiment advisor proposes points of maximum predictive uncertainty. It is a **research aid**, does not model test cost or hardware limits, and holds gravity at µg (the nearest testable proxy).
- The simulator's flame is an **illustration driven by the model's outputs** (chance of burning, predicted rate) and by simple rules for shape and colour. It is not a combustion simulation and is labelled as such on screen.
- The simulator interpolates a precomputed grid (37 × 13 × 11 points per material). Between grid points the value is a linear blend, so it can differ slightly from a direct model call.
- In the demo fixture the solid-material model finds almost no difference between materials, so the four materials receive nearly identical estimates.

## Atmosphere trade
- Breathing limits (inspired oxygen 127 and 149 mmHg, at least 30 % inert gas) and the spacewalk model (tissue ratio 1.65 for a 4.3 psi suit, 360-minute half-life) are taken from NASA OCHMO technical briefs TB-003 and TB-037. They are not derived from the combustion data.
- The pre-breathe time is a **first-order estimate**: one tissue compartment, body in equilibrium with the cabin, pure-oxygen wash-out. It reproduces the 4-hour protocol from ISS air (4 h 16 min) but it is not a validated protocol; NASA validates those in chamber tests.
- The fire layer is the simulator's model for one fuel or material at a fixed third condition (3 mm droplet, or 10 cm/s airflow). A cell counts as supported only inside the pressures and oxygen levels that were really tested; elsewhere it is hatched.
- FLEX tested nothing below about 10.3 psi, so for real data the planned 8.2 psi / 34 % habitat atmosphere falls in the hatched area. That is a statement about this one dataset, not about all NASA testing.
- Droplets are not habitat materials. The real-data layer shows how fuel droplets behave; the solid-material layer is the one relevant to cabin materials and it is demo data.

## Image Lab
- The test patterns were generated from the retired synthetic droplet table and are validated against it (mean error 0.5 %); they are not linked to any real FLEX test.
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
