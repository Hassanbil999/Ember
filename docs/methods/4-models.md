# 4. Models

## What kind of machine learning is this?

**Supervised learning, classification.** Each NASA test is an example with its conditions (inputs) and its known
result (the label). The model learns the link, then estimates the result for new conditions. The two results are:

- gas jet: **stayed lit** (1) or **went out on its own** (0)
- drop: **burned to the end** (1) or **flame died with fuel left** (0)

The model outputs a **probability** between 0 and 1 (for example "70 % chance it stays lit"), not just yes/no.
For the droplet burning rate and extinction size it is **regression** (a number in mm²/s or mm).

## Which models did we try?

All three are trained in `backend/predict/train.py` every time the data is loaded.

| Model | How it works, in one line | Strength | Weakness |
|---|---|---|---|
| **Logistic regression** | adds up the inputs with a weight each, and turns the sum into a probability with an S-shaped curve | simple, explainable ("each extra 1 % oxygen raises the odds") | can only draw straight boundaries |
| **Random forest** | many decision trees vote | handles mixed inputs | jumpy, weak outside the data |
| **Gaussian process** | estimates a new point from similar known points, with a smooth curve and learned importance per input | smooth, works with little data, says when it is unsure | slower, needs good settings |
| *Baseline* | always predicts the average (23 % gas, 13 % droplets) | the bar every model must beat | ignores the conditions |

## Which one does the app use, and why?

The app **lets the data decide**, with a rule fixed in advance: a model is usable only if it beats the baseline on
**both** the Brier score and the log loss (it must give better probabilities, not just a better ranking). Among the
usable ones, the lowest log loss wins.

**Result: the Gaussian process wins for both questions.** Averaged over 10 different splits of the campaigns
([results.md](results.md), section B):

| | Gas (CFI-G) AUC | Brier (baseline 0.179) | Droplets (FLEX) AUC | Brier (baseline 0.114) |
|---|---|---|---|---|
| Logistic regression | 0.815 | 0.132 | 0.757 | 0.115 ❌ does not beat baseline |
| Random forest | 0.809 | 0.130 | 0.760 | 0.101 |
| **Gaussian process** | **0.830** | **0.123** | **0.838** | **0.094** |

**Can we say the Gaussian process is the best?**
- **Droplets: yes, clearly.** Its AUC beats the others by about 0.08, while the variation between splits is
  about ±0.01–0.03.
- **Gas flames: it is ahead, but not by a clear margin.** All three are within about 0.02 AUC, which is the
  size of the variation between splits. The honest claim is "the Gaussian process is the best of three close
  candidates, and the conclusion does not depend on which one we use".

Other models we deliberately did not use: deep neural networks (far too little data), and k-nearest neighbours as
a predictor (poor on the gas data, AUC 0.55 in our first comparison). Nearest neighbours are still used to find
the real tests closest to a request.

## How sure is each estimate?

- **The range shown:** the 5 models trained during validation (each without some campaigns) are kept; how much they
  disagree is the range. For the droplet burning rate and extinction size, the 90 % range is taken from the real
  errors on unseen campaigns (it covered 89.9 % of them, as intended).
- **Tested / estimated / untested** (`backend/predict/domain.py`): the app measures how far the request is from
  real tests **of the same fuel**. Close to a real test: the real tests answer. Within the tested range: the model
  estimates. Beyond it, at another gravity, or with an untested fuel: **no number is shown**.

## What about the AI (language model)?

The language model does not predict fires. It only writes summaries and answers from NASA passages, and a checker
removes any sentence whose numbers are not in its cited sources. Without an API key the app falls back to templates;
a free provider (Groq) can be set in `.env`.
