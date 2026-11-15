# References

Everything Ember uses: data, documents, outside sources, methods, software and AI. NASA data is listed first.
Checksums for every downloaded NASA table are in `data/raw/psi_manifest.json`.

## 1. NASA data: Physical Sciences Informatics (PSI) experimental tables

NASA Physical Sciences Informatics (PSI) system, https://psi.nasa.gov. Each table was downloaded on 2026-11-13 or
2026-11-14 through PSI's download service and pinned by SHA-256. Each DOI was checked to resolve to the study's PSI page.

| PSI id | Investigation | Table | Rows | DOI |
|---|---|---|---|---|
| PSI-10 | Advanced Combustion via Microgravity Experiments (ACME): Flame Design | Normal Flame | 207 | [10.60555/w4zy-bt45](https://doi.org/10.60555/w4zy-bt45) |
| PSI-20 | ACME: Burning Rate Emulator (BRE) | ACME BRE | 18 | [10.60555/vb93-3y72](https://doi.org/10.60555/vb93-3y72) |
| PSI-21 | ACME: Coflow Laminar Diffusion Flame (CLD Flame) | CLD Flame | 32 | [10.60555/23e1-9950](https://doi.org/10.60555/23e1-9950) |
| PSI-22 | ACME: Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames) | E-FIELD Flames | 32 | [10.60555/se5a-8c73](https://doi.org/10.60555/se5a-8c73) |
| PSI-23 | ACME: Structure and Response of Spherical Diffusion Flames (s-Flame) | s-Flame | 18 | [10.60555/k57n-p030](https://doi.org/10.60555/k57n-p030) |
| PSI-25 | Burning and Suppression of Solids II (BASS-II) | BASS-II | 129 | [10.60555/4qc4-de67](https://doi.org/10.60555/4qc4-de67) |
| PSI-26 | Burning and Suppression of Solids (BASS) | BASS | 122 | [10.60555/58h4-dy80](https://doi.org/10.60555/58h4-dy80) |
| PSI-39 | Cool Flames Investigation (CFI) | CFI | 87 | [10.60555/m6pj-a914](https://doi.org/10.60555/m6pj-a914) |
| PSI-68 | Flame Extinguishment Experiment 2 (FLEX-2) | FLEX-2 (test plan) | 8 | [10.60555/byp8-h018](https://doi.org/10.60555/byp8-h018) |
| PSI-69 | Flame Extinguishment Experiment (FLEX) | FLEX | 274 | [10.60555/mbq8-0451](https://doi.org/10.60555/mbq8-0451) |
| PSI-98 | Spacecraft Fire Safety Experiment I (SAFFIRE-I) | SAFFIRE-1 | 4 | [10.60555/0t15-1z43](https://doi.org/10.60555/0t15-1z43) |
| PSI-99 | Spacecraft Fire Safety Experiment II (SAFFIRE-II) | SAFFIRE-2 | 15 | [10.60555/2chp-m469](https://doi.org/10.60555/2chp-m469) |
| PSI-100 | Spacecraft Fire Safety Experiment III (SAFFIRE-III) | SAFFIRE-3 | 2 | [10.60555/040q-4h36](https://doi.org/10.60555/040q-4h36) |
| PSI-101 | Smoke Aerosol Measurement Experiment – Reflight (SAME-R) | SAME-R | 109 | [10.60555/2np7-jv14](https://doi.org/10.60555/2np7-jv14) |
| PSI-102 | Smoke Aerosol Measurement Experiment (SAME) | SAME | 8 | [10.60555/gd4k-8h62](https://doi.org/10.60555/gd4k-8h62) |
| PSI-106 | Structure and Liftoff In Combustion Experiment (SLICE) | SLICE | 12 | [10.60555/pm12-rg61](https://doi.org/10.60555/pm12-rg61) |
| PSI-107 | Smoke Point In Co-flow Experiment (SPICE) | SPICE | 469 | [10.60555/9kbh-e962](https://doi.org/10.60555/9kbh-e962) |
| PSI-159 | Cool Flames Investigation with Gases (CFI-G) | CFI-G Normal Flames | 179 | [10.60555/cyt1-kh64](https://doi.org/10.60555/cyt1-kh64) |
| PSI-159 | Cool Flames Investigation with Gases (CFI-G) | CFI-G Inverse Flames | 154 | [10.60555/cyt1-kh64](https://doi.org/10.60555/cyt1-kh64) |

19 tables from 18 PSI studies: 1,903 rows read, 55 excluded with a logged reason, 1,848 tests used.

## 2. NASA documents

- NASA (2015). *A Researcher's Guide to: Combustion Science*. NP-2015-10-034-JSC. Quoted with page numbers.
  https://www.nasa.gov/sites/default/files/atoms/files/np-2015-10-034-jsc_combustion_in_reduced_gravity-iss-mini-book-011116-508.pdf
- NASA Technical Reports Server (NTRS), records retrieved 2026-11-14 through https://ntrs.nasa.gov/api/citations/search
  (snapshot in `data/raw/ntrs/`). Each is at `https://ntrs.nasa.gov/citations/<id>`:

| NTRS id | Title | Date |
|---|---|---|
| 20040142357 | Space Experiment Concepts: Cup-Burner Flame Extinguishment | 2004 |
| 20050215648 | Fundamental Research Applied To Enable Hardware Performance in Microgravity | 2005 |
| 20070031686 | Particle and Smoke Detection on ISS for Next Generation Smoke Detectors | 2007 |
| 20090014812 | Multi-User Droplet Combustion Apparatus - Flame Extinguishment Experiment | 2009 |
| 20090014827 | Smoke Point in Co-flow Experiment | 2009 |
| 20120015928 | FLEX: A Decisive Step Forward in NASA's Combustion Research Program | 2012 |
| 20130000422 | Particle Morphology and Size Results from the Smoke Aerosol Measurement Experiment-2 | 2012 |
| 20130010979 | Dynamics of Water Absorption and Evaporation During Methanol Droplet Combustion in Microgravity | 2012 |
| 20130014061 | Methanol Droplet Combustion in Oxygen-Inert Environments in Microgravity | 2013 |
| 20140009169 | Gaseous Non-Premixed Flame Research Planned for the International Space Station | 2014 |
| 20140011099 | Thickness and Fuel Preheating Effects on Material Flammability in Microgravity from the BASS Experiment | 2013 |
| 20140017780 | An Experimental and Computational Study on Soot Formation in a Coflow Jet Flame Under Microgravity and Normal Gravity | 2014 |
| 20150002322 | A Computational and Experimental Study of Coflow Laminar Methane/Air Diffusion Flames: Effects of Fuel Dilution, Inlet Velocity, and Gravity | 2014 |
| 20150008961 | Microgravity Flammability of PMMA Rods in Concurrent Flow | 2015 |
| 20150008962 | Concurrent Flame Growth, Spread and Extinction over Composite Fabric Samples in Low Speed Purely Forced Flow in Microgravity | 2015 |
| 20150010172 | Particle Morphology Results from the Smoke Aerosol Measurement Experiment-Reflight | 2012 |
| 20150011070 | A Numerical and Experimental Study of Coflow Laminar Diffusion Flames: Effects of Gravity and Inlet Velocity | 2015 |
| 20150019858 | Results from On-Board CSA-CP and CDM Sensor Readings During the Burning and Suppression of Solids II (BASS-II) Experiment in the Microgravity Science Glovebox (MSG) | 2015 |
| 20150023456 | Detailed Results from the Flame Extinguishment Experiment (FLEX) March 2009 to December 2011 | 2015 |
| 20160000593 | Combustion of Solids in Microgravity: Results from the BASS-II Experiment | 2014 |
| 20160010264 | Quantitative Measurements of Electronically Excited CH Concentration in Normal Gravity and Microgravity Coflow Laminar Diffusion Flames | 2015 |
| 20160012298 | Quantitative Measurements of CH* Concentration in Normal Gravity and Microgravity Coflow Laminar Diffusion Flames | 2015 |
| 20160012691 | Correlation of Normal Gravity Mixed Convection Blowoff Limits with Microgravity Forced Flow Blowoff Limits | 2016 |
| 20170001636 | The Spacecraft Fire Experiment (Saffire) - Objectives, Development and Status | 2016 |
| 20170006615 | Mixed Convection Blowoff Limits as a Function of Oxygen Concentration and Upward Forced Stretch Rate for Burning Pmma Rods of Various Sizes | 2017 |
| 20170007283 | Spacecraft Fire Safety Research at NASA Glenn Research Center | 2016 |
| 20205004657 | Effects of Confinement on Flame Spread in Microgravity | 2021 |
| 20210011385 | Burning and Suppression of Solids-II (BASS-II) Summary Report | 2021 |
| 20210015913 | Advanced Combustion via Microgravity Experiments (ACME) on the International Space Station (ISS) | 2021 |
| 20210021781 | Recent Research on Flames of Gaseous Fuel Aboard the International Space Station | 2021 |
| 20210022542 | Recent Research on Flames of Gaseous Fuel Aboard the International Space Station | 2021 |
| 20210022617 | Isolated Single Droplet Combustion: FLEX Experiments onboard the International Space Station | 2021 |
| 20220015583 | ACME: Advanced Combustion via Microgravity Experiments | 2023 |

- Harper et al. (2016), NASA White Sands Test Facility, on oxygen concentration versus partial pressure (cited in
  `docs/methods`): NTRS 20160004937, https://ntrs.nasa.gov/api/citations/20160004937/downloads/20160004937.pdf

## 3. Starter references (`data/seed.json`, from the team's prototype)

Listed in the catalog; never used to train a model. Placeholders are labelled *unverified* in the app.

- Scientific Reports (2018), BASS-II opposed-flow flame spread over acrylic rods: https://doi.org/10.1038/s41598-017-18398-4
- Ferkul et al. (2017), *The Saffire Experiment*, US National Combustion Meeting: https://discovery-pp.ucl.ac.uk/id/eprint/10069823/8/Ferkul_The_Saffire_Experiment_2017_US_National_Meeting_Final.pdf
- *Flammability Limits from BASS-II Testing in Microgravity Compared to Normal Gravity Limits*, ICES 2019: https://ttu-ir.tdl.org/items/1922ad9f-ef4c-4f52-96a4-980c23debe5e
- *Opposed flame spreading along a structured PMMA sample in exploration atmosphere under microgravity* (Saffire-V), NASA NTRS 2021: https://ntrs.nasa.gov/citations/20210017838
- *Results of Large-Scale Spacecraft Flammability Tests*, NASA NTRS 2017: https://ntrs.nasa.gov/citations/20170008805
- *Preliminary Results from the Saffire VI Experiment*, NASA NTRS 2024: https://ntrs.nasa.gov/citations/20240007488
- *Moon to Mars (M2M): Exploration Atmosphere*, NASA NTRS 2024: https://ntrs.nasa.gov/citations/20240003211
- Saffire I–III results, NASA presentation 2018: https://ntrs.nasa.gov/api/citations/20180005168/downloads/20180005168.pdf
- Soft goods in a 34 % O₂, 8.2 psia atmosphere, NASA JSC 2019: https://ntrs.nasa.gov/api/citations/20200002311/downloads/20200002311.pdf
- NASA image, acrylic rod burning in SoFIE-MIST (2024): https://www.nasa.gov/image-detail/amf-jsc2024e053516
- UC Berkeley Engineering (2024), NASA-funded project offers new insights into fire behavior in space: https://engineering.berkeley.edu/news/2024/12/nasa-funded-project-offers-new-insights-into-fire-behavior-in-space/
- NASA Science, *Collaborating Through Data: Inside the PSI Users Group*: https://science.nasa.gov/uncategorized/collaborating-through-data-inside-the-psi-users-group/
- Phys.org (2023, provided by NASA), *Studying combustion and fire safety*: https://phys.org/news/2023-12-combustion-safety.pdf

## 4. Outside data (kept apart from NASA data, never used to train a model)

- ZARM drop tower, Bremen: Ries, Krieger, Meyer, Eigenbrod (2026). *Flame Spread and Heat Transfer over Discrete
  Fuels separated by Metal Barriers under Microgravity*. Zenodo, https://doi.org/10.5281/zenodo.18479713
  (paper: https://doi.org/10.1016/j.proci.2026.106483). CC BY-NC 4.0. Funded by the German Space Agency at DLR.
- Earth limiting-oxygen values: Green & Perry, *Perry's Chemical Engineers' Handbook*, 8th ed. (McGraw-Hill, 2007),
  §23, as tabulated at https://en.wikipedia.org/wiki/Limiting_oxygen_concentration (`config/outside_reference.yaml`).

## 5. Challenge and context sources

- NASA Space Apps Challenge 2026, *Flame in Freefall* (challenge text and resources; source of the Artemis II smoke
  alarm account and the planned Moon-base atmosphere): https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/
- NASA Safety and Mission Assurance, Apollo 1: https://sma.nasa.gov/sma-disciplines/accllp/apollo-1
- U.S. Food and Drug Administration, safety communication on preventing surgical fires (most surgical fires occur in
  oxygen-enriched environments): archived at https://webarchive.library.unt.edu/web/20121018034751/http://www.fda.gov/MedicalDevices/Safety/AlertsandNotices/ucm275189.htm

## 6. Methods

- Rasmussen, C. E. and Williams, C. K. I. (2006). *Gaussian Processes for Machine Learning*. MIT Press.
- Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research* 12, 2825–2830.
- Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review* 78, 1–3.
- Seung, H. S., Opper, M. and Sompolinsky, H. (1992). Query by committee. *Proceedings of COLT 1992*. (next-test suggestions)
- Riley, R. D. et al. (2019). Minimum sample size for developing a multivariable prediction model: Part II, binary and
  time-to-event outcomes. *Statistics in Medicine*. (number of inputs for small data)
- van den Goorbergh, R., van Smeden, M., Timmerman, D. and Van Calster, B. (2022). The harm of class imbalance
  corrections for risk prediction models. *JAMIA*. https://pmc.ncbi.nlm.nih.gov/articles/PMC9382395 (no rebalancing)
- OECD (2007). *Guidance Document on the Validation of (Q)SAR Models* (principle 3: applicability domain), used for
  the tested / estimated / untested zones.
- Schwarz, G. (1978). Estimating the dimension of a model. *Annals of Statistics* 6, 461–464. (BIC, Statistics page)
- Hubert, L. and Arabie, P. (1985). Comparing partitions. *Journal of Classification* 2, 193–218. (adjusted Rand index)
- Robertson, S. and Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and
  Trends in Information Retrieval* 3, 333–389. (search)
- Cormack, G. V., Clarke, C. L. A. and Büttcher, S. (2009). Reciprocal rank fusion outperforms Condorcet and
  individual rank learning methods. *SIGIR 2009*. (search)

## 7. Software, fonts and hosting

- Python: FastAPI, Uvicorn, Pydantic, pandas, PyArrow, NumPy, SciPy, scikit-learn, DuckDB, PyYAML, rank-bm25,
  PyMuPDF, openpyxl, httpx, Anthropic Python SDK, pytest, ruff.
- Web: React 18, Vite, TypeScript, Vitest, Playwright.
- Fonts (Google Fonts): Barlow Condensed, IBM Plex Sans, IBM Plex Mono.
- Hosting: Docker; Modal (https://modal.com).

## 8. AI (SI) used

- **In the app:** Ask and the AI summary use a large language model through Groq's free tier
  (`openai/gpt-oss-120b`), or Claude (Anthropic) when that key is set. Every AI sentence must cite a NASA source
  and use only numbers found in it, or it is removed. The fire-check estimates are statistical models, not AI text.
- **Building the project:** code, tests and documentation were written with the help of Claude (Anthropic) through
  Claude Code; commits made with it carry a `Co-Authored-By: Claude` line. The team chose the idea, the data and
  the decisions, and reviewed the results.
