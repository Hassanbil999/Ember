"""Citation verifier, answer engine abstention, applicability domain, surrogate sanity."""
import pandas as pd
import pytest

from backend.answer.verifier import numbers_in, verify_sentence
from backend.core.store import get_store


@pytest.fixture(scope="module")
def st():
    return get_store()


def test_numbers_skip_identifiers():
    assert numbers_in("FX-012 and BASS-II at 21% O2") == ["21"]


def test_span_must_exist(st):
    cid = st.chunks.index[0]
    text = st.chunks.loc[cid, "text"]
    span = text[:60]
    ok, _ = verify_sentence({"text": "x", "citations": [{"kind": "chunk", "target": cid, "span": span}]}, st.chunks, st.tests)
    assert ok
    ok, probs = verify_sentence({"text": "x", "citations": [{"kind": "chunk", "target": cid, "span": "fabricated words not in chunk"}]}, st.chunks, st.tests)
    assert not ok and "span not found" in probs[0]


def test_numbers_must_be_backed(st):
    t = st.usable_tests("flex_demo").dropna(subset=["burn_rate_k_mm2_s"]).head(5)
    ids = t.test_id.tolist()
    med = float(t.burn_rate_k_mm2_s.median())
    good = {"text": f"Median K over {len(ids)} tests was {med:.2f} mm2/s.",
            "citations": [{"kind": "aggregate", "op": "median", "field": "burn_rate_k_mm2_s", "rows": ids, "display": f"{med:.2f}"},
                          {"kind": "aggregate", "op": "count", "field": "burn_rate_k_mm2_s", "rows": ids, "display": str(len(ids))}]}
    assert verify_sentence(good, st.chunks, st.tests)[0]
    bad = {**good, "text": f"Median K over {len(ids)} tests was {med + 0.4:.2f} mm2/s."}
    assert not verify_sentence(bad, st.chunks, st.tests)[0]
    wrong_agg = {**good, "citations": [{**good["citations"][0], "display": f"{med + 0.4:.2f}"}, good["citations"][1]]}
    assert not verify_sentence(wrong_agg, st.chunks, st.tests)[0]


def test_answer_is_cited_and_graded():
    from backend.answer.engine import answer
    a = answer("burning rate of heptane droplets in helium")
    assert a["grade"] == "Measured"
    assert a["key"] and all(s["verified"] for s in a["key"] + a["sources"])


def test_answer_abstains():
    from backend.answer.engine import answer
    a = answer("zebra migration patterns in the serengeti")
    assert a["abstain"] and a["grade"] == "No data" and a["nearest"]


def test_answer_partial_gravity_caveat():
    from backend.answer.engine import answer
    a = answer("flame spread at 30% oxygen on the moon")
    assert any(c["kind"] == "partial_gravity" for c in a["caveats"])


def test_applicability_domain():
    from backend.models.surrogate import predict
    inside = predict("droplet_k", {"o2_frac": 0.21, "pressure_kpa": 101.3, "d0_mm": 3, "diluent": "N2", "fuel": "n-heptane"}, False)
    assert inside["domain"]["status"] == "inside"
    outside = predict("droplet_k", {"o2_frac": 0.95, "pressure_kpa": 25, "d0_mm": 5.9, "diluent": "He", "fuel": "methanol"}, False)
    assert outside["domain"]["status"] in ("edge", "outside")
    assert outside["domain"]["distance"] > inside["domain"]["distance"]
    partial = predict("solid_burn", {"o2_frac": 0.3, "pressure_kpa": 70.3, "flow_cm_s": 10, "thickness_mm": 0.5, "material": "PMMA", "gravity_g": 0.165}, False)
    assert partial["domain"]["status"] in ("untested", "outside")
    assert set(partial["bracket"]) == {"µg", "1g"}


def test_models_beat_baseline():
    import json
    from backend.models.surrogate import MODEL_DIR
    for p in MODEL_DIR.glob("*.card.json"):
        card = json.loads(p.read_text(encoding="utf-8"))
        assert card["cv"]["better_than_baseline"], card["id"]
        assert "GroupKFold" in card["cv"]["scheme"]


def test_advisor_targets_uncertainty():
    from backend.models.surrogate import advisor
    a = advisor("solid_burn", {"o2_frac": [0.28, 0.34], "pressure_kpa": [62, 72]}, n=3)
    assert len(a["suggestions"]) == 3
    for s in a["suggestions"]:
        assert 0.28 <= s["conditions"]["o2_frac"] <= 0.34
        assert 0.1 < s["prediction"] < 0.9   # chosen where the outcome is uncertain
