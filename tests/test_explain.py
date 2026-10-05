import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.formatting import tr_num
from card_fraud_detection.models.explain import (
    GROUPS,
    base_value,
    describe,
    explain_rows,
    explainer,
    group_contributions,
    shap_values,
    top_reasons,
)

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]


def _data(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.1).astype(int)
    amt = np.where(y == 1, rng.gamma(5, 150, n), rng.gamma(2, 30, n))
    hour = np.where(y == 1, rng.choice([22, 23, 0], n), rng.integers(4, 22, n))
    x = pd.DataFrame({
        "amt": amt, "log_amt": np.log1p(amt),
        "category": pd.Categorical(rng.choice(CATEGORIES, n), categories=CATEGORIES),
        "hour": hour, "dow": rng.integers(0, 7, n), "is_night": np.isin(hour, [22, 23, 0]) * 1,
        "amt_to_cat_median": amt / 50, "amt_to_card_mean": amt / 40, "amt_card_z": y * 3.0,
        "hrs_since_prev": rng.exponential(5, n), "card_n_prev": rng.integers(0, 500, n),
        "first_in_category": rng.integers(0, 2, n), "first_at_merchant": rng.integers(0, 2, n),
        **{f"n_{w}": rng.integers(0, 9, n) for w in ("1h", "24h", "7d")},
        **{f"amt_sum_{w}": rng.gamma(2, 50, n) for w in ("1h", "24h", "7d")},
    })[FEATURES]
    x.loc[:5, ["amt_to_card_mean", "hrs_since_prev"]] = np.nan
    model = lgb.LGBMClassifier(n_estimators=40, num_leaves=15, verbose=-1).fit(x, y)
    return x, y, model


def test_every_feature_in_exactly_one_group():
    grouped = [c for cols in GROUPS.values() for c in cols]
    assert sorted(grouped) == sorted(FEATURES)


def test_shap_is_additive_to_raw_score():
    x, _, model = _data()
    expl = explainer(model)
    sv = shap_values(expl, x.iloc[:200])
    raw = model.predict_proba(x.iloc[:200], raw_score=True)
    np.testing.assert_allclose(sv.sum(axis=1) + base_value(expl), raw, atol=1e-4)
    # Gruplamak toplamı değiştirmez
    np.testing.assert_allclose(group_contributions(sv).sum(axis=1), sv.sum(axis=1), atol=1e-9)


def test_top_reasons_are_positive_sorted_and_limited():
    contrib = pd.Series({"tutar": 2.0, "saat": 0.5, "kategori": -1.0, "son 24 saat": 1.0,
                         "haftanın günü": 0.1})
    row = pd.Series({"amt": 812.5, "hour": 23, "is_night": 1, "category": "shopping_net",
                     "n_24h": 4, "amt_sum_24h": 1940.0, "dow": 4})
    r = top_reasons(contrib, row, k=3)
    assert [x["grup"] for x in r] == ["tutar", "son 24 saat", "saat"]
    assert r[0]["aciklama"] == "Tutar: $812,50"
    assert r[1]["aciklama"] == "Son 24 saatte kartta 4 işlem, toplam $1.940"
    assert r[2]["aciklama"] == "İşlem saati 23:00 (gece)"
    assert top_reasons(pd.Series({"tutar": -1.0}), row) == []     # olumlu katkı yoksa neden yok


def test_describe_handles_missing_history():
    row = pd.Series({"amt_to_card_mean": np.nan, "hrs_since_prev": np.nan,
                     "first_at_merchant": 1, "first_in_category": 0})
    assert describe("karta göre tutar", row) == "Kartın bu işlemden önce geçmişi yok"
    assert describe("önceki işlemden süre", row) == "Kartın ilk işlemi"
    assert describe("yeni satıcı / kategori", row) == "Bu satıcıyla ilk işlem"


@pytest.mark.parametrize("x, d, expected", [(1940, 0, "1.940"), (5.23, 1, "5,2"),
                                            (1234567.891, 2, "1.234.567,89")])
def test_tr_num(x, d, expected):
    assert tr_num(x, d) == expected


def test_explain_rows_end_to_end():
    x, y, model = _data()
    fraud_rows = x[y == 1].head(5)
    reasons = explain_rows(model, fraud_rows)
    assert len(reasons) == 5
    for r in reasons:
        assert 1 <= len(r) <= 3
        assert all(item["katki"] > 0 and item["aciklama"] for item in r)
