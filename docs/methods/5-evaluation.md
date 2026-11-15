# 5. Evaluation: how we know a result can be trusted

## What is the "baseline"?

The simplest possible guess that **ignores the conditions**: always predict the average. For gas flames, 23 % of
tests stayed lit, so the baseline says "23 %" every time. If a model cannot beat that, its inputs are not helping.
"Beats the baseline" always means: **the model's probabilities are better than this constant guess on tests it
never saw**.

## Isn't "always the average" too easy to beat?

Yes, on its own. It is the minimum bar, like a sugar pill in a drug trial: it shows the model learned *something*.
To show it learned something *useful*, we also compare it with smarter ways of guessing, on the same unseen
campaigns ([results.md](results.md), section B2):

| Way of guessing | Gas flames AUC | Droplets AUC |
|---|---|---|
| Always the average | 0.5 | 0.5 |
| Average for this fuel | 0.48 | 0.62 |
| Oxygen only | 0.60 | 0.63 |
| Rule "keeps burning above X % oxygen" | no better than guessing | no better than guessing |
| **Look up the 3 closest NASA tests of this fuel** (what an engineer would do by hand) | 0.71 | 0.74 |
| **Our model (Gaussian process)** | **0.83** | **0.84** |

The model beats the closest-tests lookup on both AUC and Brier score in **10 of 10** splits, by 0.07–0.18 AUC.
Two lessons: oxygen alone does not decide (some flames at high oxygen still went out), and the model learned how
oxygen, pressure, leak or drop size and fuel work **together**, which a lookup of similar tests cannot do.

## What does "tests it never saw" mean here?

NASA ran the tests in **campaigns** (a day or a series). Tests in one campaign are near-repeats. If some of them
are used for training and others for scoring, the model looks better than it is. So we hide **whole campaigns**:

1. Split the 11 (gas) or 12 (droplet) campaigns into 5 groups.
2. Train on 4 groups, predict the hidden group.
3. Repeat so every test is predicted once by a model that never saw its campaign.
4. Score all those predictions against NASA's recorded result.

This is called **grouped cross-validation** (GroupKFold). It answers "would this work on a new experiment?".
Random splits overstate skill (a teammate measured k-nearest neighbours on FLEX: AUC 0.89 with random splits,
0.71 with campaigns hidden).

## Which scores, and why several?

| Score | What it measures | Good value | Why we use it |
|---|---|---|---|
| **AUC** (area under the ROC curve) | **ranking**: pick one test that burned and one that went out; AUC is the chance the model gave the burned one the higher probability | 0.5 = coin flip, 1.0 = perfect | not fooled by rare outcomes (13 % burned) |
| **Brier score** | average of (probability − what happened)²: are the **probabilities** right? | lower is better | an engineer reads "70 %", so it must mean 70 % |
| **Log loss** | like Brier, but punishes confident mistakes hard | lower is better | the app's selection rule uses it |
| **Calibration slope** | do 70 % predictions come true about 70 % of the time? | 1.0 = right; below 1 = over-confident; above 1 = under-confident | catches models that rank well but exaggerate |
| Accuracy | % right if you say "burn" above 50 % | — | **misleading here**: "always went out" already scores 87 % on droplets |

No single score is enough. AUC alone could pass a model with bad probabilities; accuracy alone rewards ignoring
the rare "burned" cases. The app requires **Brier and log loss** to beat the baseline, and we report AUC and
calibration too.

## What do "significant" and "stable" mean?

They are checks on a **conclusion**, done directly on the data, with no model.

**Significant: could it be luck?** The conclusion: "gas flames rarely stay lit at low oxygen". The data: 0 of 41
stayed lit below 30 % oxygen, and 29 of 89 did at 35–40 %. The **Fisher exact test** asks: if oxygen made no
difference, how often would a split this lopsided happen by chance? Answer: p = 0.0000054, about 5 times in a
million. So it is not luck.

**Stable: does it depend on one experiment?** We remove one campaign at a time and recompute. The lowest oxygen at
which a gas flame stayed lit is 33.2 %, and stays between 33.2 % and 35.4 % whichever campaign is removed. So no
single day of testing drives it. For the models, stability is the **±** in [results.md](results.md): the spread of
the score over 10 different ways of splitting the campaigns (for example 0.838 ± 0.013).

**Covered: was it tested at all?** There are **0** gas tests with an outcome between 25 % and 33 % oxygen,
exactly the Moon-base range. So the honest statement is "no flame stayed lit below 30 % *in these tests*", not
"flames need 33 % oxygen". Keeping "not observed" apart from "impossible" is the most important rule.

## Do other sources agree? (independent agreement)

Yes, on the **direction**, which is what an independent source can confirm:

- **NASA materials testing** (Harper et al., 2016): oxygen **percentage** matters more than partial pressure. Our
  data agrees: oxygen % predicts far better than partial pressure ([preprocessing](3-preprocessing.md)).
- **ZARM drop tower** (Germany, outside NASA): thin acrylic spread flame **2.6× faster** at 35.8 % oxygen than in
  Earth air. Same direction as the NASA tests: more oxygen, more fire. It is a different fuel and a different
  measurement (spread speed, not "stays lit"), so it supports the direction, not our exact numbers.
- **NASA** lists 32 % oxygen at 58 kPa as future work: the same gap our data shows.

What no source can do yet is confirm a number **inside** the untested range, because nobody has tested there.

## Is there a physics sanity check?

Yes. In our first comparison, every model's chance of burning **rose with oxygen** in 92–100 % of steps along the
oxygen axis, as combustion science expects.
