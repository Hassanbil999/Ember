# Round 2 plan

Baseline (before any change) is in `docs/audit/before/` — screenshots and `perf.json`.
Order is fixed: integrity first, then speed, then what the user sees.

| # | Change | Where | Why (principle) |
|---|--------|-------|-----------------|
| 0 | Validate raw values **before** unit conversion; an impossible value is stored as "flagged", never as a number; derived values refuse flagged inputs. One per-test "record" payload carries status (Measured / Derived / Assumed / Flagged), plain labels and blank reasons. | `backend/core/units.py`, `adapters/base.py`, `core/validate.py`, new `backend/record.py`, tests | Science integrity: flag, never convert; distinguish measured / derived / assumed |
| 1 | Measure, then remove the bottlenecks: serve a production build (`run.py start`), drop the React-Flow graph and the modal from first load, cache computed API views, prefetch the four start screens, compute simulator feedback in the browser from one precomputed grid. | `run.py`, `backend/api`, frontend | Measure before optimizing; biggest bottleneck first; Core Web Vitals |
| 2 | New home: one sentence, one ask box, four starting points. Each opens an answer screen (finding, one visual, evidence grade, measured / inferred / never tested, sources). | `app/page.tsx`, `app/answer`, `backend/topics.py` | Hick, visual hierarchy, worked examples before open tools |
| 3 | Explore replaces the Atlas: ≤ 15 nodes, the rest as clusters that open; no permanent edges; grid-slot layout so labels cannot collide; size = amount of data, fill = safety goal, solid core = has test data. | `app/explore`, `backend/explore.py` | Gestalt, Tufte data-ink, recognition over recall |
| 4 | Navigation cut to Explore · Simulate · Insights · Data. Depth and theme move into one menu. Workspace, onboarding modal, lens bar, zoom readout and the fit button are deleted. | `components/Shell.tsx` | Hick, minimalism |
| 5 | Identity: space-dark default, cool precise light theme, amber (burning) and blue (extinction) as the only strong colours, larger type scale (nothing under 13 px). | `config/theme.tokens.json`, `globals.css`, `docs/DESIGN.md` | Figure-ground, WCAG 2.2 AA |
| 6 | Simulate: one hero flame that reacts to three sliders in the same frame, preset chips, one live sentence with confidence and nearest real test. Insights: a feed of computed findings, each sentence + visual + citation + "open in Studio". | `app/lab`, `app/insights`, `backend/insights.py` | Immediate feedback, dual coding, show uncertainty |
| 7 | Provenance panel in three levels (values with status chips → plain-words source with link to the row → technical trail). Used everywhere a test is opened. | `components/ProvenancePanel.tsx`, `app/data` | Progressive disclosure, provenance for every value |
| 8 | Verify: pytest (flag rules, record view), Playwright (no overlapping labels, no flagged value rendered as normal, 3-click Moon-base path), before/after screenshots and timings. | `backend/tests`, `tests/`, `docs/AUDIT.md`, `docs/PERF.md` | Review as judge, student, engineer |

Kept untouched on purpose: the verified extractive answer engine, model training, the vision pipeline, the Studio chart builder and the Image Lab (reachable from Insights and Data, restyled only through the shared tokens).
