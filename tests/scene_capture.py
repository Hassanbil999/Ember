"""Screenshots of the flame scene in its main states → docs/audit/after/scene_*.png.
Needs the app running (python run.py start)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "audit" / "after"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    page = b.new_page(viewport={"width": 1440, "height": 860})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    def shot(name, wait=1800):
        page.wait_for_timeout(wait)
        page.screenshot(path=str(OUT / f"scene_{name}.png"))
        print("shot", name, "gl" if page.locator("[data-scene=gl]").count() else "flat fallback")

    page.goto(BASE + "/lab?gl=1")
    page.wait_for_selector("[data-ready=lab]")
    page.locator("[data-preset=moon_base]").click()
    shot("solid_moon_base")
    page.locator("[data-preset=earth]").click()
    shot("solid_earth")
    page.locator("[data-preset=iss]").click()
    box = page.locator("[data-slider=o2]").bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.03, box["y"] + box["height"] / 2)
    shot("solid_goes_out")

    page.goto(BASE + "/lab?mode=droplet&gl=1")
    page.wait_for_selector("[data-ready=lab]")
    shot("droplet_live")
    page.locator("[data-replay]").click()
    page.wait_for_selector("[data-replay-readout]")
    shot("droplet_replay_mid", 2500)
    page.wait_for_function("document.querySelector('[data-replay-readout]')?.innerText.match(/went out|completion|broke apart/i)", timeout=30000)
    shot("droplet_replay_end", 700)
    print("errors:", errors[:5])
    b.close()
