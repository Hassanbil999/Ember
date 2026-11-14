# 3. Preprocessing: from table columns to model inputs

## What goes into each model?

| Model | Inputs (features) | Output |
|---|---|---|
| Gas leak flame (CFI-G) | oxygen %, pressure (psi), fuel flow (mg/s), **carbon atoms** in the fuel (2, 3 or 4), **fuel share** of the jet (0.3, 0.5 or 1) | stayed lit (1) or went out (0) |
| Fuel droplet (FLEX) | oxygen %, pressure, drop size (mm), fuel (heptane or methanol), CO₂ %, helium % | burned to the end (1) or flame died (0); also burning rate K and extinction size |

Code: `backend/predict/problems.py`.

## Why describe the fuel by "carbon atoms" and "fuel share" instead of its name?

The table has 6 fuel labels ("30% butane", "ethane", …). As 6 separate yes/no columns that is 5 extra numbers for
the model to learn from only 31 "stayed lit" tests. Two physical numbers say the same thing more compactly and let
the model share what it learns between fuels. **It works better:** AUC 0.815 vs 0.766, and better-calibrated
probabilities ([results.md](results.md), section C).

## Why so few inputs?

Research on prediction models with a yes/no outcome (Riley et al., 2019) ties the safe number of inputs to the
number of **events** (here, "burned" tests). We have about 4–5 events per input, which is low, so every extra
input risks **overfitting** (learning noise). We saw it: a droplet model with only 3 inputs (oxygen, drop size,
fuel) scored better than the same model with 6 (AUC 0.796 vs 0.757). The Gaussian process the app uses handles
the 6 inputs well because it learns how much each input matters.

## Why oxygen as a percentage and not as partial pressure?

We tested both. Oxygen **percentage** predicts much better than oxygen **partial pressure** (% × pressure):
gas AUC 0.815 vs 0.649; droplets 0.757 vs 0.692. This agrees with NASA's own materials testing, which found
flammability depends more on oxygen concentration than on equivalent partial pressure (Harper et al., NASA
WSTF, 2016). It matters for a Moon base: lowering the pressure does **not** cancel out the effect of raising the oxygen %.

## Did you scale the numbers?

Yes, for logistic regression and the Gaussian process: each input is **standardized** (minus its average, divided by
its spread) inside the training data only, so oxygen in % and fuel flow in mg/s count equally. Random forests do
not need scaling. We also tried taking the log of pressure and fuel flow: no improvement (AUC 0.800 vs 0.815).

## Did you combine data sets to get more data?

We tested adding the 139 inverse-flame tests to the 133 normal-flame tests. It made the model **useless**
(AUC 0.532, worse than the baseline), because an oxygen jet inside fuel is different physics. More data only helps
when it describes the same thing. Data from outside NASA (the ZARM drop tower) is kept separate and never trains
a model.

## Summary of choices tested

| Choice | Result | Kept? |
|---|---|---|
| Fuel as carbon atoms + share | better than 6 labels | ✅ |
| Oxygen as % | much better than partial pressure | ✅ |
| Standardize inputs | needed for logistic / GP | ✅ |
| Log transform | no gain | ❌ |
| Strong penalty (C = 0.1) | worse ranking, under-confident | ❌ |
| Class rebalancing | ruins probabilities | ❌ |
| Delete flagged rows | no real change | ❌ (kept, flagged) |
| Mix in inverse flames | destroys the model | ❌ |

## Sources

- Riley et al. (2019). *Minimum sample size for developing a multivariable prediction model: Part II, binary and time-to-event outcomes.* Statistics in Medicine.
- Harper et al. (2016), NASA White Sands Test Facility, on oxygen concentration versus partial pressure: NTRS 20160004937, https://ntrs.nasa.gov/api/citations/20160004937/downloads/20160004937.pdf
