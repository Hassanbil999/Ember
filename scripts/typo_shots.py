"""Screenshots of every screen on the demo path at 1440 and 1024 px, for the typography audit (docs/AUDIT.md).
    python scripts/typo_shots.py docs/audit/typography/before      (the app must be running on :8000)"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
SCREENS = [
    ("landing", "/"),
    ("simulation", "/engine?g=0.166&o2=34&p=8.2&u=10&mat=fabric&preset=moon"),
    ("fire-check-estimated", "/engine/check?problem=droplet&fuel=n-heptane&o2=19&psi=14.7&d0=3&g=0"),
    ("fire-check-untested", "/engine/check?problem=gas&fuel=propane&o2=34&psi=8.2&flow=1&g=0"),
    ("find-data", "/engine/data"),
    ("statistics", "/engine/stats"),
    ("research", "/research"),
    ("presentation", "/presentation"),
]

def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (1440, 1024):
            pg = b.new_page(viewport={"width": w, "height": 900})
            for name, url in SCREENS:
                pg.goto(BASE + url)
                pg.wait_for_timeout(2200)
                pg.screenshot(path=str(out / f"{name}-{w}.png"), full_page=True)
            pg.close()
        b.close()
    print("saved", len(SCREENS) * 2, "screenshots to", out)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
