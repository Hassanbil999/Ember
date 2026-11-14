"""Fire check: machine-learned estimates from NASA's own outcome-labelled microgravity tests.

problems.py  what is predicted, from which NASA table, with which inputs
train.py     grouped cross-validation over several model types; a model is used only if it beats the
             "always the average" baseline on unseen campaigns (Brier score and log loss)
domain.py    tested / estimated / untested, from the distance to real tests of the same fuel
service.py   one call: estimate + nearest NASA tests + what moves the estimate
report.py    the downloadable engineering report (template, no AI prose)
"""
