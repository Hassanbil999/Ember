# Performance

Measured with `tests/audit_capture.py` (Playwright, Chromium, 1440×860) on the build laptop.
Raw numbers: `docs/audit/before/perf.json`, `docs/audit/after/perf.json`, Lighthouse JSON in `docs/audit/after/`.

"Before" is the app as first run (`python run.py dev`, the development server). "After" is `python run.py start` (production build).

## Screens: time until the screen is usable

Navigation start to the screen's key element being present; warm = revisit.

| Screen | Before, warm | After, cold | After, warm |
|---|---|---|---|
| Home | 1908 ms (Atlas) | 905 ms | 259 ms |
| Answer (Moon base) | did not exist | 761 ms | 328 ms |
| Explore | 1908 ms (Atlas) | 499 ms | 312 ms |
| Simulate | 2661 ms | 450 ms | 372 ms |
| Insights | did not exist | 357 ms | 331 ms |
| Studio | 1998 ms | 447 ms | 383 ms |
| Data | 2366 ms (Refinery) | 348 ms | 384 ms |
| Image measurements | 1734 ms | 380 ms | 232 ms |

Target "first meaningful screen under 1.5 s": met on every screen, including the very first load of a fresh browser (905 ms).
Largest Contentful Paint after: 164–636 ms. Cumulative Layout Shift: 0.00–0.01.

## Interactions

Time from pointer-down to the result being in the page, measured inside the page.

| Interaction | Before | After |
|---|---|---|
| Home card → answer screen | – | 43 ms |
| Choose a material on the answer | – | 50 ms |
| Top navigation → Explore | – | 68 ms |
| Open an experiment in Explore | not captured (my test selector for the old Atlas did not match) | 10 ms |
| Open a test record | 634 ms (test-runner clock, includes its click overhead) | 20 ms |
| Open a row's source | – | 5 ms |
| Longest interaction-to-next-paint (Event Timing) | – | 80–168 ms per screen |

Targets "respond under 100 ms" and "Interaction to Next Paint under 200 ms": met for every measured interaction.

## Animation

| What | Result |
|---|---|
| Explore: switch grouping | 60.0 fps, worst frame 16.8 ms |
| Explore: open a cluster | 60.0 fps, worst frame 16.7 ms |
| Simulate: idle flame | 55 fps, worst frame 33 ms |
| Simulate: drag the oxygen slider | 52 fps, worst frame 33 ms |
| Simulate: apply a preset | 44 fps, one 83 ms frame |

**Not met:** the simulator's flame does not hold 60 fps in this measurement. The test browser is headless and draws the canvas in software (no GPU). JavaScript accounts for under 10 % of the time in a CPU profile of the drag; the rest is rasterisation. Halving the canvas resolution and the number of fills did not change the figure, which points at the software compositor and not at the page. It has not been measured on a GPU-backed browser.

## Lighthouse

| Screen | Preset | Performance | Accessibility | FCP | LCP | Total blocking | CLS |
|---|---|---|---|---|---|---|---|
| Home | desktop | 85 | 100 | 0.72 s | 1.01 s | 267 ms | 0.01 |
| Explore | desktop | 78 | 100 | 0.47 s | 1.12 s | 446 ms | 0.00 |
| Simulate | desktop | 86 | 100 | 0.51 s | 1.16 s | 280 ms | 0.01 |
| Home | mobile, 4× CPU throttle | 64 | 100 | 1.2 s | 2.5 s | 4.7 s | 0.00 |

The blocking time comes from loading the neighbouring screens in the background after first paint (decision 51). It buys the sub-100 ms clicks above and costs Lighthouse points; on a throttled phone it is too aggressive. The app is desktop-first and this was not tuned for phones.

## What was slow, and what fixed it

| Bottleneck (measured) | Fix |
|---|---|
| Development server compiling and serving unminified code: 1.6–3.2 s per screen | Production build served by `python run.py start` |
| Atlas: React Flow graph of 49 nodes and 73 edges, spring camera, layout work on the main thread | Replaced by ≤ 15 buttons on a precomputed slot grid |
| Simulator: one model request per slider move (~240 ms each) | One grid per material, interpolated in the browser |
| Grid response: 150 ms of JSON cleaning per request, five requests in parallel | Serialized once, bytes reused |
| First request after start: 1.3 s (models loading) | Warm-up thread at API start |
| Home → answer: ~190 ms waiting on the route change | Answer rendered in place immediately; route change completes behind it |
| Test record: fetched on click (114 ms) | Fetched on hover and warmed for listed tests |
| Full-page star-field gradients repainted on every change; large overlay shadows | Fixed layer painted once; smaller shadows |
| `getComputedStyle` every animation frame in the flame | Read once, refreshed on theme change |

## Reproduce

```
python run.py start            # terminal 1
python run.py audit            # terminal 2: screenshots + perf.json into docs/audit/after
python run.py test             # 85 backend tests + browser acceptance test
```
