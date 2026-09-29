import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.config import TARGET
from card_fraud_detection.models.train import MINORITY_RATIO, STRATEGIES, fit_predict, resample

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]
FEATS = ["amt", "category", "hour", "is_night", "amt_to_card_mean"]


def _data(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.03).astype(int)
    hour = np.where(y == 1, rng.choice([22, 23, 0], n), rng.integers(4, 22, n)).astype("int8")
    df = pd.DataFrame({
        TARGET: y,
        "amt": np.where(y == 1, rng.gamma(5, 100, n), rng.gamma(2, 30, n)),
        "category": pd.Categorical(rng.choice(CATEGORIES, n), categories=CATEGORIES),
        "hour": hour, "is_night": np.isin(hour, [22, 23, 0]).astype("int8"),
        "amt_to_card_mean": rng.gamma(2, 1, n) + 3 * y,
    })
    df.loc[:20, "amt_to_card_mean"] = np.nan                 # kartın ilk işlemleri
    return df


def test_resample_keeps_input_unchanged_and_hits_ratio():
    df = _data()
    x, y = df[FEATS], df[TARGET]
    before = x.copy()
    n_pos = int(y.sum())

    xu, yu, _ = resample(x, y, "alt örnekleme")
    assert yu.sum() == n_pos                                 # tüm dolandırıcılıklar korunur
    assert yu.sum() / (yu == 0).sum() == pytest.approx(MINORITY_RATIO, rel=0.01)
    assert xu.index.isin(x.index).all()                       # yalnızca gerçek satırlar

    xs, ys, _ = resample(x, y, "SMOTE")
    assert ys.sum() / (ys == 0).sum() == pytest.approx(MINORITY_RATIO, rel=0.01)
    assert (ys == 0).sum() == (y == 0).sum()                  # normal işlemlere dokunulmaz
    pd.testing.assert_frame_equal(xs.iloc[: len(x)].set_axis(x.index), x)  # özgün satırlar aynen
    synthetic = xs.iloc[len(x):]
    assert synthetic["category"].isin(CATEGORIES).all()       # kategori ara değer almaz
    assert set(synthetic["is_night"].unique()) <= {0, 1}
    assert not synthetic.isna().any().any()
    assert list(xs.dtypes) == list(x.dtypes)

    xw, yw, params = resample(x, y, "ağırlık")
    assert params["scale_pos_weight"] == pytest.approx((y == 0).sum() / n_pos)
    assert xw is x
    pd.testing.assert_frame_equal(x, before)


@pytest.mark.parametrize("kind", ["LightGBM", "XGBoost"])
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_combination_learns(kind, strategy):
    train, valid = _data(seed=0), _data(seed=1)
    s = fit_predict(kind, strategy, train, valid, FEATS, n_estimators=30)
    y = valid[TARGET].to_numpy()
    assert s.shape == (len(valid),) and np.isfinite(s).all()
    assert s[y == 1].mean() > s[y == 0].mean()


def test_validation_rows_are_scored_independently():
    train, valid = _data(seed=0), _data(seed=1)
    full = fit_predict("LightGBM", "SMOTE", train, valid, FEATS, n_estimators=30)
    part = fit_predict("LightGBM", "SMOTE", train, valid.iloc[:500], FEATS, n_estimators=30)
    np.testing.assert_allclose(full[:500], part, rtol=1e-6)
