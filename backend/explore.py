"""Explore payload: investigations, three ways to group them, and the strongest links between them.

The browser shows at most ~15 nodes, so grouping and link ranking are decided here once (cached),
not recomputed on every interaction.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .core.store import get_store

BURNS = [("solid", "Solid materials", {"solid"}), ("droplet", "Fuel droplets", {"liquid droplet"}),
         ("gas", "Gas flames", {"gas"}), ("smoke", "Smoke and dust", {"smoke", "dust"})]
GOALS = [("prevention", "Preventing fire"), ("detection", "Detecting fire"), ("suppression", "Putting fire out")]
PHASE_WORD = {"solid": "solid materials", "liquid droplet": "fuel droplets", "gas": "gas flames", "smoke": "smoke", "dust": "dust"}


@lru_cache(maxsize=1)
def explore() -> dict:
    st = get_store()
    usable = st.usable_tests()
    counts = usable.groupby("investigation_id").size().to_dict()
    concepts = [{"id": f"concept:{c.id}", "label": c.name, "plain": c.plain or c.definition,
                 "investigations": json.loads(c.investigations)} for c in st.concepts.itertuples()]
    invs = []
    for r in st.investigations.itertuples():
        years = json.loads(r.years) if r.years else None
        invs.append({"id": f"inv:{r.id}", "label": r.id, "name": r.name, "pillars": json.loads(r.pillars),
                     "fuel_phase": r.fuel_phase, "burns": PHASE_WORD.get(r.fuel_phase, r.fuel_phase),
                     "hardware": r.hardware, "platform": r.platform, "years": years, "parent": r.parent,
                     "n_tests": int(counts.get(r.id, 0)), "objectives": r.objectives})
    by_id = {i["label"]: i for i in invs}

    # link strength between two investigations, with the reasons spelled out
    links: dict[str, list[dict]] = {}
    for a in invs:
        cand = []
        for b in invs:
            if a is b:
                continue
            score, why = 0, []
            if a["parent"] == b["label"] or b["parent"] == a["label"]:
                score += 3
                why.append("one is part of the other")
            if a["fuel_phase"] == b["fuel_phase"]:
                score += 2
                why.append(f"both burn {a['burns']}")
            shared = [c["label"].lower() for c in concepts if a["label"] in c["investigations"] and b["label"] in c["investigations"]]
            if shared:
                score += min(3, len(shared))
                why.append("both study " + ", ".join(shared[:2]))
            if a["hardware"] == b["hardware"]:
                score += 1
                why.append(f"same hardware ({a['hardware']})")
            if score >= 2:
                cand.append({"to": b["id"], "strength": score, "why": "; ".join(why)})
        cand.sort(key=lambda c: (-c["strength"], -by_id[c["to"][4:]]["n_tests"], c["to"]))
        links[a["id"]] = cand[:4]

    def group(gid, label, members):
        members = sorted(members, key=lambda i: (-i["n_tests"], i["label"]))
        return {"id": gid, "label": label, "members": [m["id"] for m in members],
                "n_tests": sum(m["n_tests"] for m in members)}

    years = sorted({i["years"][0] for i in invs if i["years"]})
    eras = []
    if years:
        cuts = [years[0], years[len(years) // 3], years[2 * len(years) // 3], years[-1] + 1]
        for k in range(3):
            lo, hi = cuts[k], cuts[k + 1]
            ms = [i for i in invs if i["years"] and lo <= i["years"][0] < hi]
            if ms:
                eras.append(group(f"era:{lo}", f"Started {lo}–{hi - 1}" if hi - 1 > lo else f"Started {lo}", ms))
        undated = [i for i in invs if not i["years"]]
        if undated:
            eras.append(group("era:none", "Year not recorded", undated))
    groupings = {
        "burns": [group(f"burns:{gid}", label, [i for i in invs if i["fuel_phase"] in phases]) for gid, label, phases in BURNS],
        "goal": [group(f"goal:{gid}", label, [i for i in invs if gid in i["pillars"]]) for gid, label in GOALS],
        "era": eras,
    }
    groupings = {k: [g for g in v if g["members"]] for k, v in groupings.items()}
    docs = [{"id": f"doc:{d.id}", "label": d.title, "pages": int(d.pages), "demo": bool(d.demo)} for d in st.documents.itertuples()]
    return {"investigations": invs, "groupings": groupings, "links": links,
            "ideas": [{"id": c["id"], "label": c["label"], "plain": c["plain"]} for c in concepts],
            "reports": docs, "demo": bool(st.tests["demo"].any())}
