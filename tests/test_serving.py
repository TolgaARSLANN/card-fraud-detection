import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from card_fraud_detection.features.build import FEATURES, build_features, fit_stats
from card_fraud_detection.models.threshold import Calibrator
from card_fraud_detection.serving.app import app
from card_fraud_detection.serving.history import CardHistoryStore
from card_fraud_detection.serving.service import Decision, ScoringService, risk_level

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]
TIME = "trans_date_trans_time"


def _transactions(n=1500, cards=12, seed=0):
    rng = np.random.default_rng(seed)
    secs = np.sort(rng.integers(0, 30 * 86400, n))
    dup = np.flatnonzero(rng.random(n) < 0.05)
    secs[dup[dup > 0]] = secs[dup[dup > 0] - 1]          # aynı saniyede işlemler
    y = (rng.random(n) < 0.05).astype(int)
    df = pd.DataFrame({
        TIME: pd.Timestamp("2020-01-01") + pd.to_timedelta(secs, unit="s"),
        "cc_num": rng.integers(0, cards, n) + 1000,
        "amt": np.where(y == 1, rng.gamma(5, 150, n), rng.gamma(2, 30, n)).round(2),
        "category": rng.choice(CATEGORIES, n),
        "merchant": rng.choice(["a", "b", "c", "d", "e"], n),
        "is_fraud": y, "split": "train",
    })
    df.insert(0, "tx_id", range(n))
    return df


@pytest.fixture(scope="module")
def setup():
    tx = _transactions()
    stats = fit_stats(tx)
    feats = build_features(tx, stats)
    model = lgb.LGBMClassifier(n_estimators=30, num_leaves=15, verbose=-1).fit(
        feats[FEATURES], tx["is_fraud"])
    cal = Calibrator("önsel düzeltme", beta=1.0)
    return tx, stats, feats, model, cal


def _service(setup, history: pd.DataFrame, review_cost=10.0):
    _, stats, _, model, cal = setup
    return ScoringService(model, cal, Decision("beklenen maliyet", None, review_cost), stats,
                          CardHistoryStore(history), metadata={"model": "test"})


def test_serving_features_equal_training_features(setup):
    """Eğitim/servis tutarlılığı: işlemler tek tek servisten geçirildiğinde özellikler,
    tüm veri üzerinde toplu hesaplananlarla birebir aynı olmalı."""
    tx, _, feats, _, _ = setup
    cut = len(tx) // 2
    service = _service(setup, tx.iloc[:cut])
    # Geçmişi hiç olmayan kart da var: ilk yarıda görülmeyen kartlar
    rows = []
    for _, r in tx.iloc[cut:].iterrows():
        t = r[[TIME, "cc_num", "amt", "category", "merchant"]].to_dict()
        rows.append(service.features_for(t)[FEATURES].iloc[0])
        service.store.add(t)
    online = pd.DataFrame(rows).reset_index(drop=True)
    batch = feats.iloc[cut:][FEATURES].reset_index(drop=True)
    for col in FEATURES:
        if col == "category":
            assert online[col].astype(str).tolist() == batch[col].astype(str).tolist()
        else:
            np.testing.assert_allclose(online[col].astype(float), batch[col].astype(float),
                                       rtol=1e-12, atol=1e-12, equal_nan=True, err_msg=col)


def test_new_card_without_history(setup):
    service = _service(setup, setup[0])
    t = {TIME: pd.Timestamp("2020-03-01 23:00"), "cc_num": 999_999, "amt": 50.0,
         "category": "grocery_pos", "merchant": "z"}
    row = service.features_for(t).iloc[0]
    assert row["card_n_prev"] == 0 and row["n_24h"] == 0
    assert np.isnan(row["hrs_since_prev"]) and np.isnan(row["amt_to_card_mean"])


def test_score_decision_reasons_and_saving(setup):
    tx = setup[0]
    service = _service(setup, tx, review_cost=0.0)        # ücret 0 → her işlem alarm
    before = service.store.n_transactions
    t = {TIME: pd.Timestamp("2020-02-01 23:30"), "cc_num": 1001, "amt": 900.0,
         "category": "shopping_net", "merchant": "a"}
    r = service.score(t, save=False)
    assert r["karar"] == "alarm" and 1 <= len(r["nedenler"]) <= 3
    assert r["islem_no"] is None and service.store.n_transactions == before
    assert r["beklenen_kayip"] == pytest.approx(r["olasilik"] * 900.0)

    strict = _service(setup, tx, review_cost=1e9)         # ücret çok yüksek → onay
    r2 = strict.score(t)
    assert r2["karar"] == "onay" and r2["nedenler"] == []
    assert r2["islem_no"] is not None and strict.store.n_transactions == before + 1


@pytest.mark.parametrize("p, level", [(0.0, "düşük"), (0.0099, "düşük"), (0.01, "orta"),
                                      (0.19, "orta"), (0.2, "yüksek"), (1.0, "yüksek")])
def test_risk_level(p, level):
    assert risk_level(p) == level


def test_api_endpoints(setup):
    app.state.service = _service(setup, setup[0], review_cost=0.0)
    with TestClient(app) as client:
        h = client.get("/health").json()
        assert h["durum"] == "hazır" and h["kart"] == 12
        assert "ozellikler" in client.get("/model").json()

        body = {"cc_num": 1001, "trans_date_trans_time": "2020-02-01T23:30:00", "amt": 900,
                "category": "shopping_net", "merchant": "a"}
        r = client.post("/score", json=body, params={"kaydet": False})
        assert r.status_code == 200
        data = r.json()
        assert data["karar"] == "alarm" and data["islem_no"] is None
        assert all({"grup", "katki", "aciklama"} <= set(n) for n in data["nedenler"])
        assert client.get("/health").json()["islem"] == h["islem"]   # kaydedilmedi

        assert client.post("/score", json=body).json()["islem_no"] is not None
        assert client.get("/health").json()["islem"] == h["islem"] + 1

        bad = client.post("/score", json={**body, "category": "uzay_turizmi"})
        assert bad.status_code == 422 and "Bilinmeyen kategori" in bad.text
        assert client.post("/score", json={**body, "amt": -5}).status_code == 422
    app.state.service = None
