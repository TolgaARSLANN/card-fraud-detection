import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.config import TARGET, TIME_COL
from card_fraud_detection.features.build import (
    DEMOGRAPHIC_FEATURES,
    FEATURES,
    FeatureStats,
    build_features,
    fit_stats,
)

CATEGORIES = ["gas_transport", "grocery_pos", "shopping_net"]
FEATURE_COLS = FEATURES + DEMOGRAPHIC_FEATURES


def _frame(rows):
    """(zaman, kart, tutar, kategori, satıcı) satırlarından temiz tablo biçimi."""
    df = pd.DataFrame(rows, columns=[TIME_COL, "cc_num", "amt", "category", "merchant"])
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    df = df.sort_values(TIME_COL, kind="stable", ignore_index=True)
    df.insert(0, "tx_id", range(len(df)))
    df["category"] = df["category"].astype("category")
    df["merchant"] = df["merchant"].astype("category")
    df["gender"] = pd.Categorical(np.where(df["cc_num"] % 2 == 0, "F", "M"))
    df["dob"] = pd.Timestamp("1980-06-15")
    df["split"] = "train"
    df[TARGET] = 0
    return df


def _random_frame(n=600, cards=8, seed=0):
    rng = np.random.default_rng(seed)
    secs = np.sort(rng.integers(0, 20 * 86400, n))
    # Satırların ~%5'i bir öncekiyle aynı saniyede: eşitlik durumları da sınansın
    dup = np.flatnonzero(rng.random(n) < 0.05)
    secs[dup[dup > 0]] = secs[dup[dup > 0] - 1]
    times = pd.Timestamp("2019-01-01") + pd.to_timedelta(secs, unit="s")
    rows = zip(times, rng.integers(0, cards, n), rng.gamma(2, 40, n).round(2),
               rng.choice(CATEGORIES, n), rng.choice(["a", "b", "c", "d"], n), strict=True)
    return _frame(list(rows))


def _stats():
    return FeatureStats(category_median_amt={"gas_transport": 50.0, "grocery_pos": 100.0,
                                             "shopping_net": 10.0},
                        categories=CATEGORIES, genders=["F", "M"])


def test_card_history_values():
    df = _frame([
        ("2020-01-01 00:00", 1, 10.0, "grocery_pos", "a"),
        ("2020-01-01 00:30", 1, 30.0, "grocery_pos", "b"),
        ("2020-01-01 12:00", 1, 200.0, "shopping_net", "a"),
        ("2020-01-02 12:00", 1, 20.0, "grocery_pos", "a"),   # tam 24 saat sonra
        ("2020-01-01 00:10", 2, 999.0, "grocery_pos", "a"),  # başka kart karışmamalı
    ])
    f = build_features(df, _stats()).set_index("tx_id")
    c1 = f[f["cc_num"] == 1].sort_values(TIME_COL)

    assert c1["card_n_prev"].tolist() == [0, 1, 2, 3]
    assert c1["n_1h"].tolist() == [0, 1, 0, 0]
    assert c1["amt_sum_1h"].tolist() == [0, 10, 0, 0]
    # Pencere [t - 24 sa, t): 4. işlemde tam 24 saat önceki 12:00 işlemi dahil, 00:00 ve 00:30 hariç
    assert c1["n_24h"].tolist() == [0, 1, 2, 1]
    assert c1["amt_sum_24h"].tolist() == [0, 10, 40, 200]
    assert c1["n_7d"].tolist() == [0, 1, 2, 3]
    assert np.isnan(c1["hrs_since_prev"].iloc[0])
    assert c1["hrs_since_prev"].iloc[1:].tolist() == [0.5, 11.5, 24.0]
    # Geçmiş ortalama: 10 → 10; (10+30)/2 = 20; (10+30+200)/3 = 80
    assert np.isnan(c1["amt_to_card_mean"].iloc[0])
    assert c1["amt_to_card_mean"].iloc[1:].tolist() == pytest.approx([3.0, 10.0, 0.25])
    # z-skoru en az iki geçmiş işlem ister: 3. işlemde geçmiş {10, 30}, std = 14.142
    assert np.isnan(c1["amt_card_z"].iloc[:2]).all()
    assert c1["amt_card_z"].iloc[2] == pytest.approx((200 - 20) / np.std([10, 30], ddof=1))
    assert c1["first_in_category"].tolist() == [1, 0, 1, 0]
    assert c1["first_at_merchant"].tolist() == [1, 1, 0, 0]
    # Kategori medyanı eğitimden öğrenilen sabitlerden gelir
    assert c1["amt_to_cat_median"].tolist() == pytest.approx([0.1, 0.3, 20.0, 0.2])
    assert c1["is_night"].tolist() == [1, 1, 0, 0]

    # İkinci kartın ilk işlemi: başka kartın geçmişini görmemeli
    c2 = f[f["cc_num"] == 2].iloc[0]
    assert c2["card_n_prev"] == 0 and c2["n_24h"] == 0 and c2["amt_sum_7d"] == 0
    assert np.isnan(c2["hrs_since_prev"]) and np.isnan(c2["amt_to_card_mean"])
    assert c2["first_in_category"] == 1 and c2["first_at_merchant"] == 1


def test_window_excludes_same_second():
    df = _frame([("2020-01-01 10:00:00", 1, 5.0, "grocery_pos", "a"),
                 ("2020-01-01 10:00:00", 1, 7.0, "grocery_pos", "a")])
    f = build_features(df, _stats()).sort_values("tx_id")
    assert f["n_24h"].tolist() == [0, 0]            # aynı saniye "geçmiş" sayılmaz
    assert f["card_n_prev"].tolist() == [0, 1]      # sıra tabanlı özellik tx_id sırasını kullanır


def test_no_leakage_from_future_rows():
    """t anından sonraki satırlar değiştiğinde, t ve öncesindeki özellikler değişmemeli."""
    df = _random_frame()
    cutoff = df[TIME_COL].quantile(0.6)
    before = build_features(df, _stats())

    rng = np.random.default_rng(1)
    future = df[TIME_COL] > cutoff
    changed = df.copy()
    changed["merchant"] = changed["merchant"].astype(str)     # yeni satıcı adı atanabilsin
    changed.loc[future, "amt"] = rng.gamma(1, 500, future.sum()).round(2)
    changed.loc[future, "category"] = rng.choice(CATEGORIES, future.sum())
    changed.loc[future, "merchant"] = rng.choice(["a", "e"], future.sum())
    changed.loc[future, TARGET] = 1
    after = build_features(changed, _stats())

    past = ~future
    assert future.sum() > 100 and past.sum() > 100
    pd.testing.assert_frame_equal(before.loc[past, FEATURE_COLS], after.loc[past, FEATURE_COLS])
    # Kontrol: değişiklik gerçekten bir şey değiştirdi
    assert not before.loc[future, "amt_sum_24h"].equals(after.loc[future, "amt_sum_24h"])


def test_row_order_does_not_matter():
    df = _random_frame(seed=3)
    a = build_features(df, _stats()).set_index("tx_id").sort_index()
    shuffled = df.sample(frac=1, random_state=0)
    b = build_features(shuffled, _stats()).set_index("tx_id").sort_index()
    pd.testing.assert_frame_equal(a[FEATURE_COLS], b[FEATURE_COLS])


def test_labels_are_not_used():
    df = _random_frame(seed=4)
    a = build_features(df, _stats())
    b = build_features(df.assign(**{TARGET: 1}), _stats())
    pd.testing.assert_frame_equal(a[FEATURE_COLS], b[FEATURE_COLS])


def test_fit_stats_uses_train_only():
    df = _random_frame()
    with pytest.raises(ValueError, match="yalnızca eğitim"):
        fit_stats(df.assign(split="valid"))

    stats = fit_stats(df)
    expected = df.groupby("category", observed=True)["amt"].median()
    assert stats.category_median_amt == pytest.approx(expected.to_dict())
    assert FeatureStats.from_json(stats.to_json()) == stats


def test_unknown_category_becomes_missing():
    df = _frame([("2020-01-01", 1, 10.0, "travel", "a")])
    f = build_features(df, _stats())
    assert f["category"].isna().all()
    assert f["amt_to_cat_median"].isna().all()
