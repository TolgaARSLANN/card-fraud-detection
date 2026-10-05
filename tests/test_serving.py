import numpy as np
import pandas as pd
import pytest
from conftest import TIME
from fastapi.testclient import TestClient

from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.serving.app import app
from card_fraud_detection.serving.service import risk_level


def test_serving_features_equal_training_features(serving_setup, make_service):
    """Eğitim/servis tutarlılığı: işlemler tek tek servisten geçirildiğinde özellikler,
    tüm veri üzerinde toplu hesaplananlarla birebir aynı olmalı."""
    tx, _, feats, _, _ = serving_setup
    cut = len(tx) // 2
    service = make_service(tx.iloc[:cut])
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


def test_new_card_without_history(serving_setup, make_service):
    service = make_service(serving_setup[0])
    t = {TIME: pd.Timestamp("2020-03-01 23:00"), "cc_num": 999_999, "amt": 50.0,
         "category": "grocery_pos", "merchant": "z"}
    row = service.features_for(t).iloc[0]
    assert row["card_n_prev"] == 0 and row["n_24h"] == 0
    assert np.isnan(row["hrs_since_prev"]) and np.isnan(row["amt_to_card_mean"])


def test_score_decision_reasons_and_saving(serving_setup, make_service):
    tx = serving_setup[0]
    service = make_service(tx, review_cost=0.0)           # ücret 0 → her işlem alarm
    before = service.store.n_transactions
    t = {TIME: pd.Timestamp("2020-02-01 23:30"), "cc_num": 1001, "amt": 900.0,
         "category": "shopping_net", "merchant": "a"}
    r = service.score(t, save=False)
    assert r["karar"] == "alarm" and 1 <= len(r["nedenler"]) <= 3
    assert r["islem_no"] is None and service.store.n_transactions == before
    assert r["beklenen_kayip"] == pytest.approx(r["olasilik"] * 900.0)

    strict = make_service(tx, review_cost=1e9)            # ücret çok yüksek → onay
    r2 = strict.score(t)
    assert r2["karar"] == "onay" and r2["nedenler"] == []
    assert r2["islem_no"] is not None and strict.store.n_transactions == before + 1


def test_reset_restores_initial_history(serving_setup, make_service):
    service = make_service(serving_setup[0])
    n0 = service.store.n_transactions
    t = {TIME: pd.Timestamp("2020-02-01 23:30"), "cc_num": 1001, "amt": 900.0,
         "category": "shopping_net", "merchant": "a"}
    p0 = service.score(t)["olasilik"]
    service.score(t)                                       # geçmiş değişti
    service.reset()
    assert service.store.n_transactions == n0
    assert service.score(t, save=False)["olasilik"] == pytest.approx(p0)


def test_reset_until_rebuilds_history_from_transactions(serving_setup, make_service):
    """Akışı bir andan başlatmak: geçmiş, o ana kadarki tüm işlemlerle kurulur ve
    sonraki işlemin özellikleri toplu hesaplamayla aynı olur."""
    tx, _, feats, _, _ = serving_setup
    service = make_service(tx.iloc[:100])
    service.transactions = tx
    cut_time = tx[TIME].iloc[900]
    service.reset(until=cut_time)
    assert service.store.n_transactions == int((tx[TIME] < cut_time).sum())
    first = int((tx[TIME] < cut_time).sum())                   # o andan sonraki ilk işlem
    t = tx.iloc[first][[TIME, "cc_num", "amt", "category", "merchant"]].to_dict()
    online = service.features_for(t)[FEATURES].iloc[0]
    np.testing.assert_allclose(online.drop("category").astype(float),
                               feats.iloc[first][FEATURES].drop("category").astype(float),
                               equal_nan=True)
    service.transactions = None
    with pytest.raises(ValueError, match="until"):
        service.reset(until=cut_time)


@pytest.mark.parametrize("p, level", [(0.0, "düşük"), (0.0099, "düşük"), (0.01, "orta"),
                                      (0.19, "orta"), (0.2, "yüksek"), (1.0, "yüksek")])
def test_risk_level(p, level):
    assert risk_level(p) == level


def test_api_endpoints(serving_setup, make_service):
    app.state.service = make_service(serving_setup[0], review_cost=0.0)
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

        after_reset = client.post("/reset").json()
        assert after_reset["islem"] == h["islem"]                     # kayıt geri alındı
        # Sıfırlamadan sonra aynı işlem aynı sonucu vermeli (geçmiş bozulmamış)
        again = client.post("/score", json=body, params={"kaydet": False}).json()
        assert again["olasilik"] == pytest.approx(data["olasilik"])

        bad = client.post("/score", json={**body, "category": "uzay_turizmi"})
        assert bad.status_code == 422 and "Bilinmeyen kategori" in bad.text
        assert client.post("/score", json={**body, "amt": -5}).status_code == 422
    app.state.service = None
