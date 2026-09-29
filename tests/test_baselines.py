import numpy as np
import pandas as pd

from card_fraud_detection.config import TARGET
from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.models.baselines import (
    MODELS,
    isolation_forest,
    logistic_regression,
    preprocessor,
    rule_based,
)

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]


def _synthetic(n=3000, seed=0):
    """Dolandırıcılığın büyük tutar, gece ve kart ortalamasından sapmayla geldiği küçük veri."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.05).astype(int)
    amt = np.where(y == 1, rng.gamma(5, 120, n), rng.gamma(2, 30, n)).round(2)
    hour = np.where(y == 1, rng.choice([22, 23, 0, 1], n), rng.integers(4, 22, n))
    df = pd.DataFrame({
        TARGET: y, "amt": amt, "log_amt": np.log1p(amt),
        "category": pd.Categorical(rng.choice(CATEGORIES, n), categories=CATEGORIES),
        "hour": hour, "dow": rng.integers(0, 7, n), "is_night": np.isin(hour, [22, 23, 0, 1]),
        "amt_to_cat_median": amt / 50, "amt_to_card_mean": amt / rng.uniform(30, 60, n),
        "amt_card_z": rng.normal(0, 1, n) + 3 * y,
        "hrs_since_prev": rng.exponential(5, n), "card_n_prev": rng.integers(0, 500, n),
        "first_in_category": rng.integers(0, 2, n), "first_at_merchant": rng.integers(0, 2, n),
    })
    for w in ("1h", "24h", "7d"):
        df[f"n_{w}"] = rng.integers(0, 10, n)
        df[f"amt_sum_{w}"] = rng.gamma(2, 50, n)
    df.loc[:10, ["amt_to_card_mean", "amt_card_z", "hrs_since_prev"]] = np.nan  # ilk işlemler
    df["is_night"] = df["is_night"].astype(int)
    return df


def test_preprocessor_covers_all_features():
    df = _synthetic()
    x = preprocessor().fit_transform(df[FEATURES].assign(category=df["category"].astype(str)))
    assert x.shape[0] == len(df)
    assert not np.isnan(np.asarray(x.todense() if hasattr(x, "todense") else x)).any()


def test_rule_based_counts_flags():
    df = pd.DataFrame({"is_night": [0, 1, 1, 1], "amt": [10.0, 10.0, 250.0, 250.0],
                       "amt_to_card_mean": [1.0, np.nan, 1.0, 5.0]})
    assert rule_based(df, df).tolist() == [0, 1, 2, 3]


def test_supervised_and_unsupervised_rank_fraud_higher():
    train, valid = _synthetic(seed=0), _synthetic(seed=1)
    for fn in (logistic_regression, isolation_forest):
        s = fn(train, valid)
        y = valid[TARGET].to_numpy()
        assert s.shape == (len(valid),)
        assert s[y == 1].mean() > s[y == 0].mean(), fn.__name__


def test_scores_do_not_depend_on_other_validation_rows():
    """Doğrulama skoru satır satır aynı olmalı: ön işleme yalnızca eğitimden öğrenir."""
    train, valid = _synthetic(seed=0), _synthetic(seed=1)
    full = logistic_regression(train, valid)
    half = logistic_regression(train, valid.iloc[: len(valid) // 2])
    np.testing.assert_allclose(full[: len(valid) // 2], half)


def test_all_models_registered():
    assert set(MODELS) == {"Yalnızca tutar", "Kural tabanlı", "Lojistik regresyon",
                           "Isolation Forest"}
