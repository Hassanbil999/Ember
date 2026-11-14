# Known limitations

Stated plainly, because honest limits are part of the product.

## Data
- **All loaded test data is real NASA PSI data.** Loaded as published: FLEX droplets (PSI-69, 274 tests of methanol and n-heptane, 2009–2011), CFI-G normal gas flames (PSI-159, 179 tests, 2021), ACME Flame Design normal gas flames (PSI-10, 207 tests, 2019), and the solid-material tables BASS-II, BASS and SAFFIRE-1/2/3 (below). The synthetic BASS-II-shaped fixture that stood in for solids is switched off (`enabled: false`, kept only for adapter tests). What is still not NASA material: the two context-notes PDFs and the Image Lab test patterns (below).
- **CFI-G outcome.** "Kept burning" means the file marks the test FT (the flame was still burning when the fuel flow was stopped); "went out" means SE (self-extinguished). 46 tests with no hot ignition have no outcome. "Kept burning" is therefore *survived until the run ended*: the 31 FT flames burned 13–276 s before the flow was stopped, at a time the researchers chose, and the table cannot say how much longer they would have lasted. Some flames that went out by themselves burned longer (up to 304 s) than some FT flames, so the outcome is about how a run ended, not how long a flame lived. These are gas jets fed by a burner, not materials: they show how oxygen, pressure and fuel supply decide whether a flame survives in microgravity, not whether a cabin material ignites. The share that kept burning in any group reflects the conditions the researchers chose to test, not a real-world probability.
- **Flame Design has no outcome column.** Its tests are shown for their conditions only; nothing is claimed about burning. Cells marked "RAMP"/"RAMPED" (fuel flow changed during the test) carry no value.
- Test dates for CFI-G and Flame Design are read from the YYDDD prefix of the test code (year, day of year) and marked as derived.
- **Real solid-material tests are read from lab-notebook tables.** BASS-II (PSI-25, 129 tests), BASS (PSI-26, 122 runs) and SAFFIRE-1/2/3 (PSI-98/99/100) describe samples and results in free text. Material, shape, thickness, diameter, flow direction and how a test ended are read from that text and shown as *derived*, with the original text in the trail. What the text does not say stays blank with a reason.
  - BASS-II has **no burned/went-out column**: almost every test was lit and then deliberately taken to a limit by lowering or raising the airflow. "How the test ended" comes from the notes for 26 of 129 tests; the rest do not say. BASS-II airflow is a sequence of display readings with no stated unit, so no airflow is assigned.
  - Where a row does not name its material, it is named only if every named sample of the same shape in that file is one material (e.g. all named BASS-II and BASS rods and spheres are PMMA). The trail says so.
  - SAFFIRE-2 gives each sample a flight result and a 1g ground result; both are loaded as separate tests. The ground tests have no oxygen level or airflow in the table. "Burned the whole sample" / "Did not spread" become an outcome; partial burns and the two-part PMMA/Nomex sample have none and are described in words, with the table's footnotes.
  - Two BASS dates in the source cannot be right ("6/29/\`12", "5/15/2103"); they are left blank with the source text quoted, not corrected. SAFFIRE thickness "037 mm" is flagged as unusual and kept as written.
  - **No real solid test ran above 22.2 % O₂**, and none of these tables records pressure.
- **Smoke experiments for detection (SAME, PSI-102; SAME-R, PSI-101) record conditions, not results.** The PSI tables list the material, airflow, heater setting, heating time and smoke aging time of each run; the smoke particle measurements are not in them, so nothing is claimed about the smoke. SAME rows that say "same conditions as 1-4" are expanded into four tests each and marked derived. SAME-R rows numbered with a letter (51a) are a second, longer-aged measurement of the same smoke, and the note says so. SAME-R dates have no year, so none is recorded.
- **Every downloaded PSI table is used.** The last six, as their tables allow:
  - **CFI** (PSI-39) and **SPICE** (PSI-107): per-test conditions only; neither records how a flame ended. SPICE lists several fuel/air settings per flame; its flame duration (flame-off minus ignition) belongs to the whole flame. Exact duplicate rows (8 in CFI, 35 in SPICE) are excluded and logged; 8 SPICE rows with a negative airflow ("-0.28 cm/s") are flagged and excluded.
  - **ACME Burning Rate Emulator** (PSI-20) and **E-FIELD** (PSI-22) are *daily summaries*, not per-test tables. BRE lists the oxygen levels at which flames ignited each day; each level becomes one row saying so. Ignition is not sustained burning, so no outcome is set, and the table gives no pressure. Two oxygen cells ("3400%", "2100%", the second on a day with 0 flames ignited) are flagged and excluded, not corrected.
  - **CFI-G inverse flames** blow oxygen into a fuel atmosphere; their oxygen is the oxidizer stream, stored separately and never mixed into the cabin-air charts, answers or models.
  - **FLEX-2** (PSI-68) is a test plan (ranges), not tests; it is shown as the experiment's test plan in Explore.
- Pressures up to 600 kPa count as plausible because CFI ran droplets at 5 atm.
- **Because the solid tables record no pressure, solids are placed by oxygen only.** The Moon base and ISS answers count solid tests by oxygen level and say so; the oxygen–pressure charts show solids as an oxygen band, not as points. No model is trained on solids, and the simulator and the trade map run on droplets and gas flames only.
- The FLEX table gives the atmosphere as four mole fractions. The models use the CO₂ and helium fractions directly; the "main inert gas" shown per test is only the largest of the three and is marked as derived.
- FLEX "Disruption" tests (61 of 274: the droplet broke apart) have no burn-or-extinguish outcome. They are kept for their conditions and rates and left out of the outcome model.
- The PSI tables are downloaded by `python run.py fetch` and checked against pinned SHA-256 checksums; on 2026-11-13 the FLEX file in the repo was byte-identical to the one PSI serves. Source URL, checksum and retrieval time of every table are in `data/raw/psi_manifest.json`. If PSI corrects a table later, the fetch keeps the old file and saves the new one beside it for review.
- Eight investigations have loaded table data (FLEX, CFI-G, ACME, BASS, BASS-II, Saffire-I, -II, -III). The other catalog entries are **metadata only**; their nodes are hollow and say "no test data yet".
- Catalog **years are approximate**; **PSI ids and DOIs are empty** until filled from PSI. Nothing was invented.
- **Quoted passages come mostly from NASA's *A Researcher's Guide to: Combustion Science* (2015, 56 pages)**, checksum-verified against NASA's file. Its table of contents, acronym list and garbled hardware tables are not quoted. It predates BASS-II, SAFFIRE and CFI-G and does not discuss the Moon or partial gravity, so those answers rest on the test data.
- The two "context notes" PDFs restate facts from the challenge brief (for example the planned Moon-base atmosphere). They are not NASA documents, are labelled as such wherever they are quoted, and stay only until a NASA source for those facts is loaded.

## Partial gravity
- **PSI contains no partial-gravity combustion data.** Lunar (0.165 g) and Martian (0.38 g) scenarios are always flagged `untested`. The droplet and gas-flame models have only microgravity data and do not take gravity as an input, so the gravity setting does not change their prediction; the screen says so. The only real 1g comparison is SAFFIRE-2's ground tests, shown as measurements, not modelled.

## Models
- Surrogates (Gaussian processes) **interpolate the loaded tests**; they are not physics models and cannot extrapolate physics. Extrapolations are greyed out.
- Cross-validation groups by campaign. With 5 campaigns per dataset the CV estimates are noisy. On the real FLEX data the droplet burn/extinction classifier does **not** beat the base rate on accuracy (0.86 vs 0.87, because 87 % of decided tests end in extinction); it does on Brier score and AUC (0.82). The simulator says so in words. The extinction-diameter model is the strongest (R² 0.83), the burning-rate model moderate (R² 0.56). The CFI-G gas-flame model (still burning vs went out by itself, from oxygen, pressure, fuel and fuel flow) is right 81 % of the time on test days it has not seen against 77 % for the base rate (AUC 0.80). It has no burning-rate counterpart: the CFI-G table records no rate, so the simulator shows none for gas flames.
- The applicability domain is distance-based. It does not detect a region that is dense in data but where the response changes abruptly.
- Sensitivity is local (±10 % of each tested range at the current scenario), not a global importance measure.
- The next-experiment advisor proposes points of maximum predictive uncertainty. It is a **research aid**, does not model test cost or hardware limits, and holds gravity at µg (the nearest testable proxy).
- **The flame's look is art; its behaviour is data.** Size, colour family, lean, stretch and whether it is lit follow the model; in a replay the droplet's size over time and the moment and manner of the ending follow the test's measured burning rate, extinction diameter and burn time. The flicker, glow and exact shape are drawn, not simulated. Replays longer than 12 s are sped up and say so.
- The sound is generated in the browser from the same numbers. The breathing sound follows the inspired-oxygen limits of the NASA brief; it is a cue, not a physiological model.
- The GPU scene was measured on one machine only (Intel UHD integrated graphics, Chrome): 120 fps live and during a replay. On machines without a GPU the app uses the flat flame instead. Other graphics cards, browsers and phones are not tested.
- The simulator's flame is an **illustration driven by the model's outputs** (chance of burning, predicted rate) and by simple rules for shape and colour. It is not a combustion simulation and is labelled as such on screen.
- The simulator interpolates a precomputed grid (37 × 13 × 11 points per fuel). Between grid points the value is a linear blend, so it can differ slightly from a direct model call.
- In gas-flame mode the scene draws the CFI-G spherical burner like a droplet of fixed size; the flame's size follows the fuel-flow slider, not a predicted rate.

## Atmosphere trade
- Breathing limits (inspired oxygen 127 and 149 mmHg, at least 30 % inert gas) and the spacewalk model (tissue ratio 1.65 for a 4.3 psi suit, 360-minute half-life) are taken from NASA OCHMO technical briefs TB-003 and TB-037. They are not derived from the combustion data.
- The pre-breathe time is a **first-order estimate**: one tissue compartment, body in equilibrium with the cabin, pure-oxygen wash-out. It reproduces the 4-hour protocol from ISS air (4 h 16 min) but it is not a validated protocol; NASA validates those in chamber tests.
- The fire layer is the simulator's model for one fuel at a fixed third condition (3 mm droplet, or 1 mg/s of gas to the burner). A cell counts as supported only inside the pressures and oxygen levels that were really tested; elsewhere it is hatched.
- FLEX tested nothing below about 10.3 psi, so on the droplet layer the planned 8.2 psi / 34 % habitat atmosphere falls in the hatched area. CFI-G includes tests at about 7.4 psi (0.5 bar). These are statements about these datasets, not about all NASA testing.
- Droplets and gas jets are not habitat materials. The map shows how real flames behave across cabin atmospheres; it has no solid-material layer, because no real solid table records pressure.

## Image Lab
- The test patterns were generated from the retired synthetic droplet table and are validated against it (mean error 0.5 %); they are not linked to any real FLEX test.
- The only loaded media are **programmatic test patterns** (dark disc on a bright background; bright ring on dark). Extractors measure them within 0.8 % of the known diameters (unit tests require < 2 %). **This proves the pipeline, not its accuracy on real flame footage**, which has soot, glare, fibre supports, out-of-focus edges and drifting droplets.
- The backlit extractor assumes one dominant dark object and a uniform backlight estimated from the frame border. The flame extractor uses a luminosity threshold; the red/blue ratio is only a rough proxy for soot radiation.
- Events (ignition, extinction, burnout, disruption) use simple thresholds and may need per-test tuning through the correction loop.
- Background jobs are in-process threads: they don't survive a server restart, and there's no queue for large batches.

## Search and answers
- Dense retrieval uses local LSA. It is weaker than a neural embedder on paraphrases. `FA_EMBEDDER=st` enables MiniLM if sentence-transformers is installed. There is no cross-encoder rerank.
- The query parser understands common units and phrasings ("30 percent oxygen", "0.3 O2", "10 psi", "moon base"), not arbitrary language. Unparsed words fall back to keyword search.
- A passage is quoted only through a sentence that shares at least two of the question's key words. This keeps off-topic sentences out, but some broad questions ("why do flames behave differently in microgravity?") get no answer even though the guide discusses them; the home page's microgravity starting point covers that one.
- The template answer composer picks a metric from keywords (burn share, K, extinction diameter, spread rate). Unusual questions may get a passage-only (*Documented*) answer.
- The citation verifier checks that quoted spans exist verbatim and that every number matches a cited row value, a recomputed aggregate, or the user's own query. It does **not** judge whether a sentence's reasoning is correct.

## Engineering
- Docker Compose files are provided but were not run on the build machine (no Docker available). The verified path is `python run.py start`.
- The Studio report lives in the browser's localStorage. It is per-browser and not shared.
- In the headless test browser (no GPU) the simulator falls back to the flat flame and measures 44–60 fps depending on machine load; in real Chrome on this laptop the GPU scene holds 120 fps (`docs/PERF.md`).
- Desktop-first. Not tuned for phones or for widths below ~1200 px.
