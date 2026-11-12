# Design

The product should feel **precise, ignited and honest**. Every screen is checked against those three words.

- **Precise**: one focal point per screen, readable numbers with units, nothing decorative that could be mistaken for data.
- **Ignited**: the subject is fire in space. A space-dark canvas, and amber that appears only where something burns or where the reader should act.
- **Honest**: what was measured, what a model infers and what was never tested are never blended. Uncertainty and gaps are drawn, not footnoted.

## Screen check

| Screen | Precise | Ignited | Honest |
|---|---|---|---|
| Home | One sentence, one input, four starting points | Headline accent, four drawn visuals (Moon, cabin, two flames, the gap) | "Demo data" notice; the fourth card is about what is missing |
| Answer | One finding sentence, one visual, evidence grade | Amber/blue test dots, amber target box | Three separate columns: measured / inferred / never tested; sources quoted with page |
| Explore | ≤ 15 nodes, slot layout, labels never collide | Glow on experiments that hold data | "No test data yet" on catalogue-only entries; links appear only for the node in focus |
| Simulate | Three sliders, one sentence | The hero flame grows, leans, cools to blue and dies with the sliders | Tested range under each slider, confidence in the sentence, "No data here" instead of a confident flame, model vs baseline stated |
| Insights | One sentence + one chart per finding | Amber = burned, blue = went out | Source and "see the tests" on every finding; demo warning at the top |
| Data | Quality bar with three counts, full test table | – | Everything set aside is listed with its reason |
| Provenance panel | One value per row, units, status chip | – | Flagged first with a reason; source one click away; technical trail behind a toggle |

## Tokens (`config/theme.tokens.json` → `frontend/app/tokens.css`)

| role | Dark (default) | Light |
|---|---|---|
| background | `#05070C` + faint star field and amber horizon | `#F6F8FB` |
| surfaces | `#0B0F17` · `#111723` · `#182030` | `#FFFFFF` · `#EEF1F6` · `#E2E7EF` |
| text | `#EEF1F6` · `#B6BECC` · `#8792A6` | `#0A111E` · `#39424F` · `#5C6778` |
| **burning / primary action** | `#FF9A3D` | `#B5490A` |
| **extinction** | `#5AA9FF` | `#1D5FB0` |
| uncertainty (quiet) | `#A9A2D2` | `#5A5290` |
| warning / flagged (quiet) | `#D9C27E` | `#7A5C08` |
| safety goals (quiet) | `#7FB3A2` / `#C4B37C` / `#BE93A6` | `#2E7A60` / `#77651D` / `#8C4562` |

Amber and blue are the only saturated colours. Everything else is desaturated so those two keep their meaning.
Text pairs meet WCAG 2.2 AA (tertiary text ≥ 4.5:1 on its background in both themes). Lighthouse accessibility: 100 on Home, Explore and Simulate.

## Type
Geist Sans for everything; Geist Mono only for numbers and the technical trail. Scale: display 34–56 px, title 28, lead 20, body 15, small 13–14. **Nothing is set below 13 px** (enforced by the browser test on every screen).

## Status language (used wherever a value is shown)
`Measured` solid dot · `Derived` dashed, diamond · `Assumed (dataset setting)` dotted, hollow, italic value · `Flagged` warning triangle, tinted · `No value` with the reason in words. Told apart by word, shape and colour, never by colour alone.

## Motion (only where it means something)
- The flame eases toward each new state, so a slider move reads as growing or dying. It is drawn by one GPU shader inside a window that stays dark in both themes: blue and round when starved or in microgravity, amber and stretched with buoyancy or airflow, never grey in between.
- A real test can be replayed in that same window: the droplet shrinks at its measured rate and the flame ends when and how the record says.
- Sound is part of the same scene and off until asked for: a low cabin hum, airflow, a flame roar that follows the burning rate, and breathing that grows laboured as the air's oxygen falls. Quiet, eased, no effects that do not map to a number.
- Explore nodes slide to their new slot when the grouping changes (300 ms).
- Untested gaps pulse slowly ("never tested", "0 tests").
- `prefers-reduced-motion` turns all of it off; the flame becomes a still image that updates on change.

## Charts
Position and length carry the data (Cleveland & McGill); colour only repeats what a label already says. Labels sit on or beside the marks; legends are one line. No gridline or tick that does not help reading a value. Each chart has an `aria-label`.

## Deliberately absent
Permanent graph edges, lens bars, zoom readouts, onboarding modals, a command palette, a workspace canvas, tooltips needed to understand a mark, and any label that needs a glossary.

## Accessibility
All controls are native buttons, links, inputs or selects and are reachable by keyboard. `/` or Ctrl+K focuses the ask box. Escape closes one overlay layer at a time. The simulator sentence is an `aria-live` region.
