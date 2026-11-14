# How Freefall Atlas works: data, cleaning, models, evaluation

Plain-language answers for students, mentors and judges. Every number in these pages comes from the
NASA tables in this repo and can be regenerated with one command:

```
python run.py ingest all                 # load and clean the NASA tables, train the Fire check models
python scripts/evaluate_methods.py       # rewrites results.md (about 2 minutes)
```

| Page | Answers |
|---|---|
| [1. The data and the science](1-data.md) | Which NASA data? What is a droplet test and a gas-flame test? Why only two models? |
| [2. Cleaning and outliers](2-cleaning.md) | What did we remove, what did we flag, and why we never delete a value just because it looks odd |
| [3. Preprocessing](3-preprocessing.md) | How raw columns become model inputs, and the choices we tested and rejected |
| [4. Models](4-models.md) | Which models, what each one does, which one the app uses and why |
| [5. Evaluation](5-evaluation.md) | Baseline, unseen campaigns, AUC, Brier score, log loss, calibration, "significant", "stable" |
| [6. Questions people ask](6-questions.md) | Short answers to the questions a mentor or judge is likely to ask |
| [results.md](results.md) | The generated numbers (do not edit by hand) |

## The whole method in six sentences

1. We use **real NASA tables only** (19 tables from NASA's PSI repository, 1,848 usable tests), downloaded with checksums so nobody can change them by accident.
2. Cleaning **removes only what is provably wrong** (impossible values, duplicate rows) and **flags** anything suspicious instead of changing it.
3. Only two tables record **whether the fire kept burning**: gas-jet flames (CFI-G) and fuel droplets (FLEX). Only those two get a prediction model.
4. The app tries three model families on each, scores them on **NASA test campaigns the model never saw**, and keeps a model only if it beats a **baseline** that ignores the conditions. The Gaussian process wins on both.
5. Every estimate is labelled **tested / estimated / untested** by its distance to real same-fuel tests, and the app shows **no number** when the request is far from the data.
6. The main conclusion (gas flames need high oxygen to stay lit) is also checked **without any model**: it is statistically significant, it survives removing any one test campaign, and the oxygen range of a Moon base has **no tests at all**.
