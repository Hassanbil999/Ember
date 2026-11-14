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
    t = st.usable_tests("flex").dropna(subset=["burn_rate_k_mm2_s"]).head(5)
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












