You're restructuring the frontend of **The Oxygen Edge** (repo: freefall-atlas), our NASA Space Apps 2026 entry, into a small site: a landing page that leads to three places, the **Engine**, the **Presentation** and the **Research**. Work on the `rebuild/new-frontend` branch.

## The baseline we're borrowing from
A past Space Apps winner, Resonant Worlds Explorer (https://resonant-planet.vercel.app/). Their challenge is close to ours (NASA data, a model, an interactive tool), so we borrow its **structure**. Do not copy its name, wording, logo, colours or images. What it has (looked at on 2026-11-14):
- **Landing page:** a row of small badges, a big two-line headline with a gradient accent, a one-paragraph pitch, and four buttons (explorer, presentation, research paper, method). Below that: three feature cards; a "method" section in two numbered columns (pipeline steps and validation tests); one worked-example card with real values and a score; three "why it matters" cards; a closing call to action; and a footer naming the data source.
- **Engine:** its own app shell with a top nav (Dashboard, Train Model, Predict, Upload Data, Explore, Dataset). The dashboard has four stat cards and two charts. Pages use a two-panel layout, settings on the left and results on the right. Explore is an interactive 3D view with a details panel and a card grid. Dataset has stat cards, a bar chart and a scatter plot.
- **Presentation and research paper:** plain PDF links.

Where it falls short, and where we must do better:
- **The URL never changes.** There are no deep links, Back leaves the site, and the logo doesn't go home.
- **Dead ends.** Predict says "Model Not Trained", and the dashboard shows N/A and an empty chart until someone trains a model.
- **Unsupported claims.** Some claims aren't backed by the app, and some details disagree between pages (one page says 2024, the other 2025).

## Read first
`CLAUDE.md`; `README.md` (Decisions); `docs/LIMITS.md`; `SPEC.md` §10–13; `web/src/` (`App.tsx`, `views/`, `components/FireCheck.tsx`); `backend/api/main.py` (it already serves `index.html` for unknown paths, so client-side routes work).

This request changes one rule. `CLAUDE.md` says to match `prototype/index.html` and not redesign. That still holds for the simulator's stage and panels. The new pages (landing, engine shell, research, presentation) are new design work in the same visual language: the colours, fonts and panel style in `web/src/styles.css`. Update that line in `CLAUDE.md` and in SPEC §10 to say so.

## Sitemap
Use real paths with `history.pushState`. Back works, every page can be linked, and the logo goes to `/`.
- `/` landing
- `/engine`: overview (the default)
  - `/engine/check`: the fire check, our main tool
  - `/engine/simulator`: the existing flame simulator (the current Simulate view, unchanged inside)
  - `/engine/data`: the existing Find data view
  - `/engine/models`: model validation
- `/research`
- `/presentation` (`/presentation/3` opens slide 3)
- `/admin/verify` (unchanged)

Old links keep working. `/#simulate` goes to `/engine/simulator` and `/#data` to `/engine/data`, and both keep the query string, because simulator settings and filters live there. Use a small pathname router with no new dependency unless a library is clearly simpler, and log the choice.

## Pages
**Landing:** the baseline's layout, with our content.
- **Hero:**
  - Badges, for example "NASA PSI data", "microgravity tests" and "tested / estimated / untested".
  - A headline and a one-paragraph pitch for spacecraft and habitat engineers.
  - Buttons: Open the engine, View presentation, Read the research, How it works (scrolls to the method section).
  - Background: the simulator's airflow particles, paused under `prefers-reduced-motion`.
- **Three feature cards:** real NASA tests, a fire check with a confidence grade, limits stated openly.
- **Method:** two numbered columns.
  - "How a check works": inputs → distance to NASA tests of the same fuel → tested / estimated / untested → estimate with its range → nearest NASA tests → report.
  - "How we check the models": validation with whole campaigns held out, comparison with a baseline, uncertainty ranges, no number outside the tested range.
- **Worked example:** one real fire check fetched live from `POST /api/fire-check`, at fixed inputs that land in the *tested* zone at 0 g. Today a 30 % ethane gas jet at 34 % O₂, 8.2 psi and 0.5 mg/s does; confirm this through the API. Show the zone, the estimate with its range, and the NASA tests behind it with their IDs. No hard-coded result.
- **Why it matters:** three cards.
- **Closing call to action.**
- **Footer:** data sources (NASA PSI, with PSI IDs), Space Apps 2026, and a link to the README.
- **Numbers:** every number on this page comes from the API at load time (test counts, model scores, number of tables) and is labelled with its source. If the API is down, show the page without numbers, never stale ones.

**Engine shell:** top nav (Overview, Fire check, Simulator, Data, Models), an API status dot, and a footer. Use the baseline's two-panel pattern: inputs on the left, results on the right.
- **Overview:**
  - Four stat cards: NASA tests loaded; tests with a measured outcome that the models use; best model vs. the baseline on unseen campaigns; number of PSI tables.
  - A coverage chart: oxygen vs. pressure for the outcome-labelled NASA tests, with markers for ISS, Moon base and Mars base, so the untested gap is visible.
  - An outcome-split chart (stayed lit / went out).
  - Nothing is ever empty. `ingest` pre-trains the models, so everything shows on first load. If data is missing from the API, add a read-only endpoint. `/api/fire-check/meta` already returns the ranges and model cards.
- **Fire check:** a full page instead of a dialog. Keep the dialog's behaviour, and its element IDs where possible.
  - Inputs on the left. On the right: zone pill, verdict, estimate with range, measured quantities, what moves the estimate, nearest NASA tests, reasons, model summary, and Download report.
  - The simulator keeps a button that opens this page with its current oxygen and pressure.
  - Fix these while moving it:
    - Gravity is chosen on the page (default: microgravity), not inherited from the simulator, so a preset can't silently force "untested".
    - The "tested X–Y" hints use the selected fuel's ranges, not all fuels pooled.
    - Errors are readable sentences. FastAPI's 422 `detail` is a list, and today it shows as "[object Object]". An empty field says "enter a value" instead of becoming 0. Hide the previous result while inputs are invalid.
    - The shown estimate never falls outside its own shown range. Fix this in the display, not the model, and log how.
- **Simulator:** the current Simulate view, moved under the shell. Don't change its model or stage. Load it lazily so the landing page stays light.
- **Data:** the current Find data view.
- **Models:** a read-only take on the baseline's Train page. For each model (gas jets from CFI-G, droplets from FLEX), show:
  - the data used;
  - the validation method (grouped by campaign);
  - the comparison table against the always-the-average baseline;
  - the chosen model and the uncertainty method;
  - the one command that reproduces it (`python run.py ingest predict`).

  No "train now" button.

**Research (`/research`):** a readable web page, not a PDF link.
- Sections: the question; the data (each PSI table with its ID, DOI, what it records, and test counts from the API); the method; validation, with live numbers from the model cards; results; limits (from `docs/LIMITS.md`, in plain words); how to reproduce; references.
- Add a print stylesheet so Print → PDF gives a clean paper.
- Show a Download PDF button only if `web/public/research-paper.pdf` exists.

**Presentation (`/presentation`):** an in-app slide deck of 8–10 slides.
- Slides: the problem, who it's for, the data, how a check works, a screenshot of the engine with a link to it, validation, limits, what's next, the team.
- Arrow keys and on-screen buttons, the slide number in the URL, fullscreen, and one slide per printed page.
- If `web/public/presentation.pdf` exists, offer it for download too.
- Tag text the team must write or check with a visible "draft" label.

## Rules for every page
- Every number traces to the API, a NASA test or a cited source, and is labelled: NASA test, published value, or model estimate.
- No estimate outside the tested range. Show "untested" and the nearest tests instead.
- Every estimate shows its range.
- Limits are visible on the landing page, the fire check, the simulator and the research page.
- Show the name "The Oxygen Edge" in all visible UI and in the report. Keep the repo, package and API names as they are.
- No login and no keys. One command still runs everything: `python run.py start`.
- Accessibility as in `CLAUDE.md`: real buttons and links, full keyboard use, visible focus, never colour alone, and respect `prefers-reduced-motion`.
- Works at 1366×768 and at phone width with no horizontal scroll. Keep the first load light (today about 71 KB of gzipped JS): no 3D library and no large images.
- Don't change the models, the data, the ingest steps or the simulator's maths.

## Steps
After each step, check that the app runs from a clean checkout and that these pass: `python -m pytest backend/tests -q`, `cd web && npm test`, `npm run typecheck` and `python run.py e2e`. Then commit and tell me in three lines what works and what's next.
1. Router and engine shell. Move the Simulator and Data views under it. Redirect the old hash URLs. Update the e2e tests' URLs and selectors.
2. Fire check page with the fixes above, then the Overview page.
3. Landing page.
4. Models, Research and Presentation pages.
5. Final pass: screenshots of every page at 1366×768 and at phone width, and no console errors. Add e2e tests for landing → engine → fire check → report, for `/research` and `/presentation` loading, and for a deep link followed by Back.

If something is unclear, pick the simplest option that keeps the demo working, log it in the README's Decisions table, and continue.

Done means a judge opens `/`, understands the project in 10 seconds, reaches a fire-check result in two clicks, and opens the presentation and research without leaving the site.
