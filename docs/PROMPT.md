You're upgrading **Freefall Atlas**, our NASA Space Apps 2026 entry, in this repo.

What we want: the new frontend in `prototype/index.html` becomes the whole app, and the old site's UI goes. But the old site already has real NASA data that we cleaned and integrated. Keep that data and the code that loads and serves it, and connect the new frontend to it. Do not redo any cleaning or ingestion that already exists.

Read these first:
1. `CLAUDE.md`: rules for this repo
2. `SPEC.md`: the target product. §0 explains how it applies to this repo.
3. `prototype/index.html`: the exact look and behavior. Reuse its CSS, WebGL flame shader, particle airflow, timeline and model code.
4. `data/seed.json`: starter data, used only to fill gaps the real data doesn't cover. It keeps its placeholder labels.

**Step 1: Audit, with no changes yet.** Explore the repo and write `docs/AUDIT.md`:
- the stack, how to run it, and whether it runs today;
- every data asset: files, formats, database tables, row counts, where they came from, and which cleaning or ingestion scripts produced them;
- the existing API routes and what they return;
- a table mapping each existing field to the SPEC.md data model (investigations, resources, test_points), with gaps marked;
- keep, adapt or delete for every top-level folder, with a reason.

Then stop, show me a short summary, and wait for my OK before deleting anything.

**Step 2: Safe cleanup.** Create the branch `rebuild/new-frontend` and tag the current commit `v0-old-site`. Delete the old frontend and the dead code the approved audit lists. Keep the data, the cleaning scripts, and every backend part marked keep or adapt.

**Step 3: Build one milestone at a time,** following SPEC.md §14 from M1.
- Use the existing backend stack if it works. The FastAPI + Postgres stack in SPEC.md is only the default for parts that don't exist yet.
- Put an adapter layer between the existing data and the API shapes in SPEC.md §9, so the new UI talks to one clean API.
- Real data wins over `seed.json`. Load seed rows only where the real data has nothing, and keep them marked placeholder/unverified.
- Never invent NASA data. AI-extracted values stay unverified, with their source page and quote, until a person verifies them.
- AI features use the Anthropic SDK with the model from `ANTHROPIC_MODEL`. They must cite their sources or refuse, and fall back to templates when no key is set.
- Fit the simulator to the real verified test points (SPEC.md §8.4) and keep the anchor tests (§8.5) passing.
- After each milestone: the app runs from a clean checkout with one command, the tests pass, and you commit. Then tell me in three lines what works and what's next.

If something is ambiguous, pick the simplest option that keeps the demo working, log it in `README.md` under "Decisions", and continue.

Done means one public deploy where a judge with no login sees the new frontend running on our real data and can complete the smoke path in SPEC.md §13.
