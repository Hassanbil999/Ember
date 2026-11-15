# Research summary: will a small fire keep burning in spacecraft and Moon-base air?

*Brief for whoever writes up the research. Every number here comes from the current version of the app (Ember,
repo `freefall-atlas`, branch `main`) and can be regenerated; commands are at the end. Status: 15 November 2026.*

## 1. The question

NASA plans future Moon and Mars habitats with thinner air and more oxygen than the ISS: the candidate exploration
atmosphere is about 34 % oxygen at 8.2 psi, against 21 % at 14.7 psi on the station. Thinner, oxygen-rich air makes
spacewalk preparation shorter, but oxygen feeds fire, and a crew cannot leave a burning habitat. So the engineering
question is concrete: **if a small fire starts in that air, will it keep burning, and how much of the answer has
NASA actually tested?**

We did not run experiments. We asked what NASA's own microgravity combustion tests can and cannot say about it.

## 2. Data

**NASA Physical Sciences Informatics (PSI), 19 experimental tables.** 1,903 rows read, 55 excluded by written
cleaning rules (44 duplicates, 11 physically impossible values such as 3,400 % oxygen), **1,848 usable tests**.
Experiments: FLEX (PSI-69) and FLEX-2 test plan (PSI-68), CFI (PSI-39), CFI-G normal and inverse (PSI-159), ACME
Flame Design (PSI-10), ACME Burning Rate Emulator (PSI-20), ACME CLD Flame (PSI-21), ACME s-Flame (PSI-23), E-FIELD
(PSI-22), SPICE (PSI-107), SLICE (PSI-106), BASS-II (PSI-25), BASS (PSI-26), SAFFIRE-1/2/3 (PSI-98–100), SAME
(PSI-102), SAME-R (PSI-101). DOIs are listed in the README.

**Only two tables record whether the fire kept going**, so only they can train a model:

| Question | NASA table | Tests with an outcome | Outcome |
|---|---|---|---|
| Gas leak flame | CFI-G normal flames (PSI-159) | 133 (31 stayed lit), 11 campaigns | flame stayed lit / went out on its own |
| Liquid fuel drop | FLEX (PSI-69) | 206 (27 burned to the end), 12 campaigns | burned the drop to the end / died with fuel left |

The other tables (solids, smoke, gas jets without an outcome) are used for coverage, search and citation, not for
prediction. Solid materials (fabric, plastic, wire insulation), the most common cabin fire, have **no burned/went-out
column** in the loaded tables.

**Text sources:** NASA's *A Researcher's Guide to Combustion Science* (2015) and 33 NASA Technical Reports Server
documents, quoted by page in the app's question answering.

**Outside NASA, kept apart (never used to train):** five ZARM drop-tower flame-spread rates over thin acrylic at
21–36 % oxygen (Zenodo doi:10.5281/zenodo.18479713, CC BY-NC 4.0), and Earth limiting-oxygen values for ethane
(11 %), propane (11.5 %) and butane (12 %) with nitrogen (*Perry's Chemical Engineers' Handbook*, 8th ed.).

**Cleaning principles:** every value keeps a link to its file, row and column; impossible values are flagged and
withheld, never corrected; values worked out from free-text notes are marked "derived"; missing values are left out
of a model, never filled in.

## 3. Method

**Prediction.** For each question we compared logistic regression, a random forest and a Gaussian process (one
smoothness setting per input) against a baseline that ignores the conditions and always predicts the average.
Inputs: oxygen, pressure, leak size (fuel flow), and the fuel described by what it is (carbon atoms and its share
of the jet) for gas flames; oxygen, pressure, drop size, fuel, and CO₂ and helium shares of the air for drops.

**Validation on experiments the model never saw.** NASA ran tests in campaigns of near-repeats. We hold out whole
campaigns (grouped cross-validation) and score the predictions on them. Random splits overstate skill because a
test's near-twin sits in training: on FLEX, a nearest-neighbour model scores AUC 0.89 with random splits and 0.71
with campaigns held out.

**Scores.** AUC (does the model rank fires that kept going above those that died; 0.5 = chance), Brier score and
log loss (are the probabilities themselves right). Accuracy is reported but not used: 87 % of drops died early, so
always guessing "dies" is already 87 % "accurate". A model is used only if it beats the baseline on **both** Brier
and log loss.

**Three zones, decided by distance to real tests of the same fuel** (inputs scaled by their spread; thresholds
taken from the data's own nearest-neighbour distances, following the "applicability domain" principle used for
regulatory prediction models):
- *Tested:* NASA ran nearly these conditions. The measured outcomes are the answer; the model only cross-checks.
- *Estimated:* between tests of that fuel and inside every tested range. The model gives a chance with a range.
- *Untested:* outside a tested range, too far from the tests, or any gravity other than microgravity. No number.

**Uncertainty.** The chance range comes from 15 models refitted on campaign-bootstrap samples (10th–90th
percentile). Measured quantities (burning rate, drop size at extinction, burn time) carry a 90 % range whose
coverage was checked on unseen campaigns. Each model card stores a calibration table.

**Exploration.** A Gaussian mixture groups the test conditions without looking at outcomes; an oxygen sweep finds
where the chance passes 50 %; a committee of the bootstrap models suggests the tests that would teach the model most.

## 4. Findings

**F1. In NASA's gas-flame tests, no flame stayed lit below 30 % oxygen.** 0 of 41 tests below 30 %, against 29 of 89
at 35–40 % (Fisher exact p = 5.4 × 10⁻⁶). The lowest oxygen at which a gas flame stayed lit was 33.2 % (30 % ethane);
leaving out any one campaign moves it only to 33.2–35.4 %. By fuel, the lowest was 33.2 % (30 % ethane), 35.4 % (50 %
butane), 36.5 % (ethane), 37.1 % (30 % propane), 37.7 % (propane) and 38.4 % (30 % butane). For comparison, the Earth
limits for these fuels are 11–12 %: a different measurement (premixed gas), so a reference, not a ratio.

**F2. The planned Moon-base air sits at that edge, and the data has a hole exactly there.** There are **no**
gas-flame tests with an outcome between 25 % and 33 % oxygen. So the data supports "no flame stayed lit below 30 %
in these tests", not "flames need 33 %". At the habitat condition itself the picture depends on the fuel: one NASA
test of a small diluted ethane leak (30 % ethane, about 0.5 mg/s) at nearly 34 % oxygen and 8.2 psi **stayed lit**
(the app answers *tested*, model 83 %, range 50–91 %), while **pure propane was only ever tested at 13.7–14.7 psi**,
so at 8.2 psi the honest answer is *untested*.

**F3. Oxygen alone does not decide a gas flame.** Even at 35–40 % oxygen, two thirds of the flames went out. The
models need pressure and leak size as well. In the unsupervised grouping, two groups at almost the same high oxygen
differ sharply: about 37 % oxygen with smaller leaks (0.9 mg/s) kept burning in 56 % of tests, about 39 % oxygen
with larger leaks (1.8 mg/s) in 6 %. Larger leaks being *less* likely to stay lit is counterintuitive; it may
reflect the experiment's protocol or flame regime and needs a combustion explanation before it is stated as physics.

**F4. For fuel drops, the directions the model learned match combustion science.** More oxygen helps a drop burn to
the end; a bigger drop makes it less likely (large flames lose heat by radiation and go out); heptane burns to the
end more readily than methanol. Lowest oxygen at which a drop burned to the end: 14 % (heptane), 18 % (methanol).
Example: a 3 mm heptane drop at 19 % oxygen and 14.7 psi, *estimated*, 21 % chance (range 5–26 %), burning-rate
constant 0.47 mm²/s, burn time about 9 s; the chance passes 50 % at about 21 % oxygen.

**F5. The models predict experiments they never saw, but modestly.**

| Model (chosen: Gaussian process) | AUC on unseen campaigns | Brier (baseline) | Improvement over baseline |
|---|---|---|---|
| Gas flame stays lit | 0.86 | 0.109 (0.182) | 40 % |
| Drop burns to the end | 0.82 | 0.094 (0.115) | 18 % |

Over 10 different campaign splits the Gaussian process averages AUC 0.83 ± 0.03 (gas) and 0.84 ± 0.01 (drops).
Measured quantities, all beating the baseline with checked 90 % ranges: burning-rate constant (error 0.059 mm²/s vs
0.112), drop size at extinction (0.27 mm vs 0.80), drop burn time (3.0 s vs 6.0 s), gas time until self-extinction
(20 s vs 44 s, random forest). Calibration: drop probabilities are close to observed rates in every band; gas
probabilities are good at the extremes and overconfident in the middle (predicted 38 %, observed 19 %).

**F6. What did not work (worth reporting).**
- Logistic regression does not beat the baseline for drops: it cannot capture interactions such as "this only
  matters when oxygen is high".
- Oxygen partial pressure (oxygen % × pressure) as an input is much worse than oxygen % and pressure separately
  (gas AUC 0.82 → 0.65).
- Describing gas fuel by six labels instead of carbon number and share is worse (0.82 → 0.77).
- "Balanced" class weights, a common imbalance fix, keep the ranking but ruin the probabilities (gas Brier
  0.132 → 0.168).
- Training on the inverse-flame tests (oxygen into fuel) destroys the normal-flame model (AUC 0.53).
- CO₂ versus nitrogen as the inert gas for drops: 0 of 18 CO₂ tests vs 16 of 133 nitrogen tests burned to the end
  at 15–21 % oxygen, p = 0.22, and the CO₂ tests ran at different pressures. Not a finding. (On Earth, CO₂ is the
  better smothering gas: limiting oxygen 2.5–3 points higher than with nitrogen.)

**F7. The most useful next tests are computable.** A committee of 15 models suggests where one new experiment would
narrow the answer most. For a diluted ethane leak at Moon-base air, the top suggestion is about 38 % oxygen at
7.3 psi and 0.4 mg/s, where the models disagree between 18 % and 93 %. For pure propane, a test near 33 % oxygen at
14.7 psi; at Moon-base pressure there is nothing in reach yet, which is itself the finding.

## 5. Limits

- **Microgravity only.** Nothing has been tested at Moon or Mars gravity; any partial-gravity case is untested.
- **Gas and liquid fuels only.** The NASA test fuels stand in for cabin fluids (heptane ≈ kerosene-type liquids,
  methanol ≈ alcohols, ethane/propane/butane ≈ gas leaks). Solids are not covered.
- **Small data.** 133 and 206 outcome-labelled tests; ranges are rough and may still understate the uncertainty.
- **Airflow is not an input:** the drops burned in still air and CFI-G records no surrounding flow.
- **The flame simulator for solids is illustrative.** No verified solid test has oxygen, pressure, airflow and an
  outcome together, so it uses published starting values; outside tested conditions it shows a trend and no numbers.
- **The oxygen sweep can fall as oxygen rises** for some gas settings; the app flags it as likely reflecting other
  differences between tests rather than oxygen itself.

## 6. How the project got here

1. A first version (Freefall Atlas) organised NASA's combustion data with provenance and ranked experiments by
   relevance to each habitat. A teammate downloaded and checksum-verified all 19 PSI tables.
2. The question narrowed to one decision: oxygen level versus fire in habitat air ("the oxygen edge"), and the
   counts behind F1–F2 were checked with significance and stability tests.
3. The fire check was built: models validated on unseen campaigns, the three-zone rule, nearest NASA tests with
   their source rows, a downloadable report. A mistake was caught and corrected along the way: an early simplified
   Gaussian process looked useless for drops; the proper one is the best model.
4. The interface was rebuilt as Ember (simulation, fire check, find data, statistics), with "where is the line?",
   "which test next?", and plain-language method notes.
5. Consistency passes: bug fixes from user testing (gas mixes, per-fuel ranges, stale results), the simulator made
   to follow the untested rule, and a typography pass.

## 7. Next steps

- **Physics-informed extension for solids and gravity (proposed, not built):** fit the simulator's flame physics to
  the real solid measurements (13 Saffire outcomes, 7 at Earth gravity; 4 Saffire spread rates; 5 ZARM spread
  rates), treat gravity as an equivalent buoyant airflow (about 30·√g cm/s, roughly 12 cm/s on the Moon), check it
  against the Saffire Earth-gravity tests, and report its error; label anything beyond the data "physics
  extrapolation".
- Tests in the 25–33 % oxygen gap at habitat pressure, for gas leaks.
- Partial-gravity combustion data (NASA's planned lunar investigations) to replace the untested zone with tests.
- A person to verify the simulator's starter reference rows against their cited papers.

## 8. Reproduce

```
python run.py start                     # the app at http://localhost:8000
python run.py ingest predict            # retrain; model cards in data/artifacts/predict/*.card.json
python scripts/evaluate_methods.py      # every method number → docs/methods/results.md
python run.py test                      # 211 backend tests, model parity, browser tests
```

Detailed method in plain language: `docs/methods/`. Decisions with reasons: README table and `docs/DECISIONS.md`.
Known limits: `docs/LIMITS.md`.
