# The Oxygen Edge: idea validation

NASA Space Apps 2026 · 14 November 2026

## Verdict
**Promising, useful and impactful.** The Oxygen Edge turns NASA's space-station fire experiments into answers that engineers can use, and into a flame that anyone can explore. The hardest part, cleaning NASA's messy data so a model can learn from it, is already done. The models trained on it beat a simple baseline on NASA tests they had never seen.

## The problem
Future Moon and Mars habitats plan to use air with more oxygen at lower pressure than the ISS. The planned Moon-base air is 34 % oxygen at 8.2 psi. In low gravity, hot air doesn't rise, so flames get their oxygen differently and behave in ways that Earth tests don't predict. Fire is one of the most serious dangers in a sealed habitat.

NASA has run hundreds of fire tests in space, but the results are spread across many separate tables. Each table has its own format, free-text notes and errors, so the results are hard to use.

## Our solution
One website with three ways in:
- **Fire check, for engineers:** enter oxygen, pressure, fuel and gravity. The answer comes from NASA's own tests, labelled tested, estimated (with a range) or untested (with the nearest NASA tests). The result can be downloaded as a report.
- **Flame simulator, for anyone:** change gravity, oxygen, pressure and airflow, and watch how a flame behaves differently from one on Earth.
- **Data explorer:** search and filter every NASA test we loaded, each with its source.

## Who it helps
- **Habitat and spacecraft engineers:** they can check air choices early, before building hardware or running expensive tests.
- **Researchers and test planners:** they can see which conditions NASA hasn't tested yet.
- **Students and the public:** they can play with a flame and see why fire in space is different.

## Cleaning NASA's messy data to train models
NASA publishes its fire experiments in its Physical Sciences Informatics (PSI) system as separate tables, each in its own format. We built a pipeline that downloads the tables, cleans them, checks them and turns them into training data.

| What the pipeline does | Result |
|---|---|
| NASA PSI tables downloaded and checksum-verified | 19 |
| NASA experiments covered | 16 |
| Test records read | 1,903 |
| Data problems found and handled | 200 (145 flagged, 55 excluded) |
| Values traced back to the original NASA table | 20,604 |

How the data is cleaned:
- **Fixed sources:** every table is downloaded with a pinned checksum and its source is recorded, so the data can't change without anyone noticing.
- **Notes become data:** lab-notebook notes for solid-material tests (BASS, BASS-II, SAFFIRE) are read into material, shape, thickness and result. The original text is kept beside each value.
- **Errors are caught, not hidden:** examples include an oxygen level of "3400 %", negative airflow, a date in the year 2103, and columns filled by dragging a spreadsheet cell ("CH4, CH5, CH6 …"). Each one is flagged or excluded with a reason, never quietly "fixed".
- **Duplicates removed:** 43 repeated rows across the CFI and SPICE tables.
- **One outcome, one set of units:** each experiment's own codes become a shared outcome. For example, CFI-G's "FT" and "SE" become "stayed lit" and "went out on its own". All tests use the same units, so experiments can be compared and combined.

The result is two clean training sets, each test with a measured outcome: **133 gas-jet flames** from CFI-G (PSI-159) and **206 fuel droplets** from FLEX (PSI-69).

## Models that are properly tested
- We trained three kinds of model (logistic regression, random forest and Gaussian process) and kept the best one, a Gaussian process.
- Each model was tested on whole campaigns it never saw during training, so it can't just memorise one day's runs.
- Each model is compared with a simple baseline that always guesses the average.

| Model | NASA tests | Campaigns | Error vs. baseline | AUC |
|---|---|---|---|---|
| Gas-jet flame (CFI-G) | 133 | 11 | 40 % lower | 0.86 |
| Fuel droplet (FLEX) | 206 | 12 | 18 % lower | 0.82 |

"Error" is the Brier score: the average gap between the predicted chance and what actually happened. AUC measures how well the model tells flames that stayed lit from flames that went out (0.5 is a coin toss, 1 is perfect).

**Trustworthy by design:** every estimate comes with a range. Outside the conditions NASA tested, the tool gives no number and shows the nearest real tests instead.

## Example: Moon-base air
A 30 % ethane gas jet in the planned Moon-base air (34 % oxygen, 8.2 psi), in microgravity, has an **83 % chance of staying lit (range 75–87 %)**. The answer is backed by the NASA tests closest to those conditions. Switch the gravity to the Moon's and the tool shows that NASA hasn't tested this yet, which is a clear lead for the next experiment.

## Why it matters
- **Safer habitats, earlier:** engineers can check air choices instantly, before building hardware.
- **NASA's data, reused:** years of space-station experiments become searchable and ready for machine learning.
- **Clear next experiments:** the tool shows exactly which conditions NASA hasn't tested.
- **Fire science for everyone:** anyone can play with a flame in space conditions.
- **Open and repeatable:** one command runs the app (`python run.py start`), and one more rebuilds the models from NASA's tables (`python run.py ingest predict`).

## Pitch
"Know what NASA has actually tested before you design a habitat's air."

## What's next
- Add solid materials such as fabrics and plastics to the fire check.
- Add Moon and Mars gravity tests as soon as they are run.
- Get feedback from habitat engineers and grow the tool around their decisions.
