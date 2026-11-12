"""Tokenization, light stemming and synonym expansion shared by BM25 and the verifier."""
from __future__ import annotations

import re

STOP = set("""a an the of in on at to for and or with by from is are was were be been what how why which does do
did can could should would this that these those it its as into about than then there their them they near
show me tell find give list all any between under over vs versus""".split())

SYN = {
    "oxygen": ["o2"], "o2": ["oxygen"], "extinction": ["extinguish"], "extinguish": ["extinction"],
    "smoke": ["aerosol"], "aerosol": ["smoke"], "droplet": ["drop"], "spread": ["propag"],
    "flammabl": ["flammability", "burn"], "flammability": ["flammabl"], "burn": ["combust"], "combust": ["burn"],
    "suppress": ["extinguish"], "detect": ["sensor", "detector"], "detector": ["detect"],
    "microgravity": ["weightless", "mug"], "moon": ["lunar"], "lunar": ["moon"], "mars": ["martian"],
    "pressur": ["psi", "kpa"], "ventil": ["flow"], "flow": ["ventil"], "soot": ["luminos"],
}


def stem(t: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ities", "ity", "ies", "ed", "es", "s"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(text: str, expand: bool = False) -> list[str]:
    text = text.lower().replace("₂", "2").replace("²", "2").replace("μ", "mu").replace("µ", "mu")
    raw = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text)
    out = []
    for t in raw:
        if t in STOP:
            continue
        s = stem(t)
        out.append(s)
        if expand:
            out += SYN.get(s, []) + SYN.get(t, [])
    return out
