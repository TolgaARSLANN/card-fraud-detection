"""Servis ve panel testlerinin ortak kurulumu: sentetik işlemler, küçük model, servis üreteci."""

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.features.build import FEATURES, build_features, fit_stats
from card_fraud_detection.models.calibration import Calibrator
from card_fraud_detection.serving.history import CardHistoryStore
from card_fraud_detection.serving.service import Decision, ScoringService

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]
TIME = "trans_date_trans_time"


def synthetic_transactions(n=1500, cards=12, seed=0) -> pd.DataFrame:
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


@pytest.fixture(scope="session")
def serving_setup():
    tx = synthetic_transactions()
    stats = fit_stats(tx)
    feats = build_features(tx, stats)
    model = lgb.LGBMClassifier(n_estimators=30, num_leaves=15, verbose=-1).fit(
        feats[FEATURES], tx["is_fraud"])
    return tx, stats, feats, model, Calibrator("önsel düzeltme", beta=1.0)


@pytest.fixture
def make_service(serving_setup):
    """Verilen geçmiş ve inceleme ücretiyle sentetik bir skorlama servisi üretir."""
    _, stats, _, model, cal = serving_setup

    def build(history: pd.DataFrame, review_cost: float = 10.0) -> ScoringService:
        return ScoringService(model, cal, Decision("beklenen maliyet", None, review_cost),
                              stats, CardHistoryStore(history), metadata={"model": "test"})
    return build
