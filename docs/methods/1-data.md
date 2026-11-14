# 1. The data and the science

## Where does the data come from?

From NASA's **Physical Sciences Informatics (PSI)** repository, the source the challenge names. We downloaded
**19 experimental tables** from 18 PSI studies (each has a DOI), plus NASA's *A Researcher's Guide to Combustion
Science* (2015) and NASA technical reports from NTRS. The script `scripts/fetch_psi.py` pins a SHA-256 checksum for
every file, so a changed or corrupted file is caught.

- **1,903 rows** were read; **55 were excluded** (see [cleaning](2-cleaning.md)); **1,848 tests are used**.
- They cover fuel droplets (FLEX, CFI), gas flames (CFI-G, ACME, E-FIELD, SPICE, SLICE), solid materials
  (BASS, BASS-II, SAFFIRE-1/2/3) and smoke for fire detection (SAME, SAME-R).

## What is a "gas flame" test? (CFI-G, NASA PSI-159)

A small tube on the space station lets out a **jet of gas fuel** (ethane, propane or butane, sometimes diluted
with nitrogen) into air with a chosen amount of oxygen and pressure. It is lit, and NASA records what happened:

- **stayed lit**: the flame was still burning when the crew stopped the fuel ("FT" in the table), or
- **went out on its own**: the flame self-extinguished ("SE").

Think of it as **a small gas leak that catches fire** in a cabin. 133 tests have this outcome; 31 stayed lit.
Tested range: oxygen 18–40 %, pressure 7.4–44 psi, fuel flow 0.12–3.2 mg/s.

There are also "inverse" flames, where the oxygen comes out of the tube into fuel around it. That is different
physics, so they are **not** mixed into this model (section C of [results](results.md) shows why: adding them
makes the model no better than guessing).

## What is a "droplet" test? (FLEX, NASA PSI-69)

**One drop of liquid fuel** (1.1–4.7 mm across), heptane (like a component of petrol) or methanol (an alcohol), is
lit in microgravity. With no gravity there is no rising hot air, so the flame forms a sphere around the drop.
NASA records:

- **burned to the end** (the drop was used up), or **the flame died with fuel left**;
- the **burning-rate constant K**: the drop's diameter squared shrinks by K mm² every second (the "d² law");
- the **drop size when the flame died**, when it died early.

Think of it as **a drop of spilled liquid that catches fire**. 206 tests have the outcome; 27 burned to the end.
Tested range: oxygen 12–34 %, pressure 10–45 psi, CO₂ up to 70 %, helium up to 45 %.

## Why do only these two get a model?

A prediction model needs examples where **the answer is known**. Only CFI-G and FLEX record both the
conditions (oxygen, pressure) **and** whether the fire kept burning. The others cannot train an honest model:

| Tables | What is missing |
|---|---|
| BASS-II, BASS, SAFFIRE (solid materials) | no cabin pressure recorded; BASS-II has no burned / went-out column |
| ACME BRE, s-Flame, CLD, E-FIELD, SLICE | daily summaries, not one row per outcome |
| SAME, SAME-R | smoke measurements: nothing to predict "burn or not" |

These tables are still used as **evidence and coverage** (what was tested, and where nothing was).

## Isn't a gas jet or a drop very different from a cabin fire?

Yes, and the app says so. The main cabin hazard is **solid materials** (fabric, plastic, wiring). The solid-material
tables do not record enough to train a model, so for solids the app shows the real tests and the gaps, and does
not predict. The gas and droplet models answer two narrower questions: a **gas leak** and a **liquid spill**.
