"""Paths and YAML config loading. Every other module asks here for locations."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("FA_ROOT", Path(__file__).resolve().parents[2]))
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
ARTIFACTS = DATA / "artifacts"

for _p in (RAW, PROCESSED, ARTIFACTS):
    _p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict:
    path = CONFIG / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def variables() -> dict:
    return load_yaml("variables.yaml").get("variables", {})


def datasets() -> dict:
    return load_yaml("datasets.yaml").get("datasets", {})


def validation_rules() -> list:
    return load_yaml("datasets.yaml").get("validation", [])


def models_cfg() -> dict:
    return load_yaml("models.yaml")


def presets() -> dict:
    return load_yaml("presets.yaml")


def media_cfg() -> dict:
    return load_yaml("media.yaml")


def reload() -> None:
    load_yaml.cache_clear()
