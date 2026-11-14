# 2. Cleaning and outliers

## What is the main rule?

**Flag, never silently fix.** A value is only removed when it is provably wrong. Anything that just looks odd is
kept and marked, with the reason written down. Every decision is logged in `data/processed/validation_log.parquet`.

## What exactly did the cleaning do?

| Rule | What it catches | Action | Rows |
|---|---|---|---|
| `impossible_value` | a value that cannot be physically true (e.g. FLEX-114: pressure **0 mmHg**, a vacuum, where nothing burns) | **excluded** | 11 |
| `duplicate` | the same test id twice (SPICE 35, CFI 8, E-FIELD 1); the first one is kept | **excluded** | 44 |
| `implausible` | outside a sensible range for that variable (e.g. FLEX-130 burning rate 0.05 mm²/s; SAFFIRE-2 thickness "37 mm") | flagged, kept | 7 |
| `fractions_do_not_sum` | O₂ + N₂ + CO₂ + He in the table do not add up to 100 % | flagged, kept | 6 |
| `extinction_larger_than_start` | the drop is bigger when the flame dies than when it started | flagged, kept | 1 |
| `missing_outcome` | no burned / went-out value: kept for its conditions, not used to train | flagged, kept | 131 |

Total: 1,903 rows read, **55 excluded**, 1,848 used. The counts are regenerated in [results.md](results.md), section A.

Other rules:
- **Checks happen before unit conversion**, so a bad value is never converted into a believable-looking one.
- Values worked out from free-text notes are marked **derived**, not measured.
- A missing material or fuel is **never guessed** (for example, a blank SAFFIRE material is not copied from the row above).
- Auto-filled spreadsheet errors are rejected (in CLD Flame, the fuel column counts up "CH4, CH5, CH6…", which are not real molecules).

## How did you handle outliers?

We **did not delete statistical outliers**. Only two kinds of rows were removed: physically impossible values
and duplicates. Why:

1. **Small data.** With 27–31 "burned" examples, deleting even a few rows changes the result. Guidance on outliers
   agrees: delete only values shown to be errors, otherwise keep them and report them.
2. **An extreme test is often the most informative one.** A flame that survived at an unusual condition is
   exactly what a fire-safety tool must not throw away.
3. **We checked that it does not matter.** The FLEX model data contains 6 flagged rows. Training without them:
   AUC 0.830 instead of 0.838, Brier 0.095 instead of 0.094 ([results.md](results.md), section C). The flagged
   rows do not drive the result. The CFI-G model data has no flagged rows.

## Did you rebalance the data because "burned" is rare?

No, on purpose. Only 23 % of gas tests and 13 % of droplet tests are "burned". Tricks like SMOTE or class weights
make the model predict "burned" more often, but medical prediction research found they **ruin the probabilities**
without improving the ranking (van den Goorbergh et al., 2022). We tested it on our data: with balanced class
weights the droplet model's Brier score doubled (0.232 vs 0.115) and the AUC did not improve.

## Did you fill in missing values?

No. A row missing an input the model needs (or the outcome) is left out of that model. Nothing is invented.

## Sources

- van den Goorbergh, van Smeden, Timmerman, Van Calster (2022). *The harm of class imbalance corrections for risk prediction models.* JAMIA. https://pmc.ncbi.nlm.nih.gov/articles/PMC9382395
- On deleting outliers in small samples: https://metricgate.com/blogs/winsorizing-vs-trimming-outlier-mistakes/
