# 6. Questions people ask (short answers)

**Is the data real?**
Yes. 19 NASA PSI tables, downloaded with checksums, 1,848 usable tests. Starter rows from `data/seed.json` and
the ZARM drop-tower data are labelled as not NASA and never train a model.

**Is this supervised or unsupervised learning?**
Supervised. Each NASA test has a known result (stayed lit / went out), and the model learns from those.

**Which model do you use?**
A Gaussian process, for both questions. It was chosen by a rule fixed in advance: beat the baseline on Brier score
and log loss on campaigns it never saw; lowest log loss wins. See [4. Models](4-models.md).

**Is the Gaussian process the best possible model?**
We tested three families plus a baseline. For droplets it is clearly best (AUC 0.838 vs about 0.76). For gas flames
it is narrowly ahead (0.830 vs 0.815 and 0.809), within the variation between splits. We do not claim "optimal";
we claim "best of the tested candidates, and the conclusions do not depend on the choice".

**What does logistic regression predict? Isn't it just two options?**
It predicts the **probability** of one of two outcomes (stayed lit or went out). Two outcomes is exactly the
question NASA's tables answer. The probability carries the "how likely", and the app shows a range around it.

**What is the baseline?**
Always predicting the average (23 % for gas, 13 % for droplets), ignoring the conditions. A model is only shown if
it beats this.

**Isn't "always the average" a weak baseline?**
Yes, so it is only the minimum bar. We also beat an oxygen-only model, a fuel average, an oxygen threshold rule and
"look up the 3 closest NASA tests", in 10 of 10 splits. See [5. Evaluation](5-evaluation.md).

**What is AUC?**
Take one test that burned and one that went out. AUC is the chance the model ranked the burned one higher.
0.5 is a coin flip, 1.0 is perfect. Ours: 0.83–0.84.

**Why not just accuracy?**
Because "burned" is rare. Saying "went out" every time is already 87 % accurate on droplets while being useless.

**How did you handle outliers?**
We removed only impossible values (11) and duplicate rows (44). Suspicious values are flagged and kept, and we
checked that leaving them out changes nothing important. See [2. Cleaning](2-cleaning.md).

**Did you balance the classes?**
No. Research and our own test show it ruins the probabilities without improving the ranking.

**How do you know the prediction is right?**
We cannot know a single prediction is right. We know how often the model is right on **experiments it never saw**,
we show a range, and we refuse to give a number far from real tests. Near a real test, the real test answers.

**Can it predict a Moon base fire?**
Only partly. Microgravity tests only, so Moon gravity (1/6 g) is untested. Gas flames have no tests between 25 % and
33 % oxygen, so at Moon-base air the app says "untested" instead of guessing. Solid materials have no model.

**Did you compare with experts or published results?**
With published results, yes, on the direction of the effects (NASA WSTF on oxygen %, the ZARM drop tower). A review of
selected predictions by a combustion expert is the next step we would take.

**Where is the line between "keeps burning" and "goes out"?**
The Fire check sweeps oxygen at your settings and shows where the chance passes 50 %, with a range, only where
NASA's tests allow an estimate. See [4. Models](4-models.md).

**What experiment would help most?**
The app suggests three tests where the models disagree most, inside what NASA's hardware can do. That turns a gap
into a concrete next experiment (active learning, "query by committee").

**Why not deep learning or reinforcement learning?**
133 and 206 examples are far too few for deep learning, and there is no environment for reinforcement learning to act
in. They would add risk, not insight.
