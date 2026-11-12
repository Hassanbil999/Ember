# Audit, round 2

Screenshots: `docs/audit/before/` (the app as first run) and `docs/audit/after/` (now). Timings: `docs/PERF.md`.
Everything below marked "test" is checked automatically by `python run.py test`.

## 1. The data-validation bug

**What was wrong.** Test FX-018 has "0 atm" in the source. The value was parsed, converted to 0 kPa, used to derive an oxygen partial pressure of 0 kPa, and both were displayed as facts. The row was excluded from models, but the panel showed the numbers as normal values.

**What happens now.** A raw value is checked in its own unit before any conversion. If it is impossible it is stored with no number and a reason; nothing is derived from it; the row is excluded and listed.

| | Before | After |
|---|---|---|
| Panel | `before/provenance_FX-018.png` | `after/provenance_FX-018.png` |
| Total pressure | `0 kPa` | Flagged: "Total pressure must be greater than zero: nothing can burn in a vacuum. The source says 0 atm." |
| O₂ partial pressure | `0 kPa` (computed from the bad value) | Flagged: "Not computed: input flagged (total pressure)." |
| Gravity | `0 g₀` | "Microgravity (ISS)", status Assumed (dataset setting) |
| Flow | `0 cm/s`, shown like a measurement | `0 cm/s`, italic, status Assumed (dataset setting) |
| Outcome | `0 extinguished` | "Extinguished" |
| Burning rate | `–` | "Not applicable: flame extinguished" |
| Source | file paths and parse logs in the main view | "Droplet combustion tests, row 19, column “Pressure”" with a link to the raw row (`after/provenance_FX-018_source_row.png`); paths only under "Technical trail" (`after/provenance_FX-018_level3.png`) |

### Scan of the whole dataset (303 source rows)

Impossible values, checked before conversion (pressure ≤ 0, oxygen outside 0–100 %, non-positive sizes, negative rates or speeds, unknown units):

| Test | Data set | Source value | Result |
|---|---|---|---|
| FX-018 | Droplet tests, row 19 | Pressure "0 atm" | Flagged, excluded, partial pressure not computed |
| BS-023 | Solid-material tests | Total P "0" kPa | Flagged, excluded, partial pressure not computed. Same defect as FX-018, in the second data set. |

Possible but unusual values (kept, marked with a warning, shown with their value):

| Test | Value | Why it is marked |
|---|---|---|
| FX-064 | droplet 12 mm | outside the usual 0.5–6 mm |
| BS-072 | oxygen 1.7 % | outside the usual 5–100 % (probably a typo for 17 %; not corrected) |

Other rows set aside or marked: 3 duplicates excluded (FX-006, FX-034, BS-013 second occurrences); 5 rows with no recorded outcome kept for their conditions (FX-042, FX-089, FX-121, BS-051, BS-098); 10 droplet rows that report a burning rate although the flame extinguished, kept with a warning.

Totals: 298 rows used (of which 17 with a warning), 5 excluded.

### Tests added
- `backend/tests/test_integrity.py` (26 checks): impossible raw values in several units are flagged and never converted; unknown units are flagged; a flagged input blocks the derived value; every record of every test has no value on a flagged field and a reason on every blank; gravity is always a regime name; outcomes are words; the API never returns a number for a flagged variable.
- Browser test: for every flagged test, the panel shows the Flagged chip, renders no value element in that row, lists flagged rows first, hides file paths and the technical trail by default, and the Data table says "Flagged" in that cell.

## 2. Acceptance checks

| Check from the brief | Result | How it was verified |
|---|---|---|
| I understand what it is and what to do in 3 seconds | Home is one sentence, one ask box, four starting points (`after/home.png`) | Review; a 3-second read by a real first-time user was not tested |
| Every click feels instant | 5–68 ms from click to result; longest interaction-to-paint 80–168 ms | `perf.json`, measured in the page |
| No stutter | Explore holds 60 fps. **The simulator flame measured 44–55 fps** in the headless, GPU-less test browser | `perf.json`; see PERF.md. Not verified on a GPU |
| No overlapping text | No overlapping labels in 11 Explore layouts (3 groupings, every cluster opened) and no overlapping chart text on 15 screens | Browser test (bounding boxes) |
| No truncated labels | No clipped headings, labels, chips, buttons or table headers on 15 screens | Browser test |
| No lines going nowhere | No edges drawn unless a node is hovered or selected; then 1–4, ending on visible nodes | Browser test |
| Nothing under 13 px | Smallest text on every screen is 13 px | Browser test |
| "Is this material risky in a Moon base?" in under 60 s and 3 clicks | 2 clicks (Moon base card, material), 0.8 s; shows measured, inferred and never-tested columns with an evidence grade | Browser test (`after/answer_moon_base_PMMA.png`) |
| It does not look like a template | Dark space canvas, amber/blue only, drawn visuals, large type (`after/*.png`, light theme in `after/light_*.png`) | Review; a matter of judgement |
| Click any test and understand it in 10 s; trail one click away | Three-level panel | Browser test + screenshots |
| No impossible value shown as normal | See section 1 | Backend + browser tests |
| Navigation ≤ 4 plain items | Explore · Simulate · Insights · Data | Browser test |
| Explore ≤ 15 nodes | Holds in all 11 layouts | Browser test |
| Accuracy guarantees kept | Verified citations, abstention ("Not covered by available NASA data"), demo notice on every screen | 59 earlier backend tests still pass; browser test |

Totals: 85 backend tests pass; the browser acceptance test passes.

## 3. Three reviewers

**A sceptical judge** would have found: the home was a graph with no instruction (now a question and four answers); a click took seconds (now tens of milliseconds); FX-018 showed 0 kPa (fixed, and a second such row found). Still open for a judge: all data is synthetic demo data, and every model number on screen reflects that fixture.

**A confused student** would have found: jargon in the navigation and the legend (now four plain words and a one-line legend); a wall of file paths in the panel (now behind a toggle); tools before answers (now answers first). Still open: the Studio and the image-measurement screen keep their expert layout and vocabulary; they were only restyled through the shared tokens and font floor.

**An aerospace engineer looking for one error** would have found: 0 kPa, "0 g₀", an assumed flow shown as measured, a derived value from a bad input (all fixed and tested). Still open, and stated on screen: the burn/no-burn model is right 66 % of the time against a 55 % baseline; partial gravity has no data and is only bracketed; the flame is an illustration driven by the model, not a simulation of combustion; in this fixture the model shows almost no difference between materials, so the four materials get nearly the same Moon-base estimate.

## 4. Not done or not verified
- Simulator animation at 60 fps is not demonstrated (above).
- Lighthouse performance is 78–86 on desktop, 64 under phone throttling; the app was not tuned for phones.
- Studio and image-measurement screens were not redesigned.
- The old Atlas artefacts (`backend/atlas.py` layouts for nine lenses) are still built at ingest; only its node and grouping data are used now.
- Docker files remain unrun, as before.
