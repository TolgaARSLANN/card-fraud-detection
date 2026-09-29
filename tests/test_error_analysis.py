import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.evaluation.error_analysis import (
    after_fraud,
    burst_position,
    card_concentration,
    fraud_breakdown,
    group_error_rates,
    outcome,
    standardized_rate,
)


def _frame():
    rows = [  # (kart, zaman, etiket, alarm, tutar, grup)
        (1, "2020-05-01 10:00", 0, 0, 20.0, "a"),
        (1, "2020-05-02 22:00", 1, 0, 15.0, "a"),   # patlama 1, sıra 1, kaçtı
        (1, "2020-05-02 23:00", 1, 1, 900.0, "a"),  # sıra 2, yakalandı
        (1, "2020-05-03 12:00", 0, 1, 80.0, "a"),   # patlamadan 13 sa sonra: yanlış alarm
        (1, "2020-05-10 12:00", 0, 0, 30.0, "a"),   # 72 saatten sonra
        (2, "2020-05-02 12:00", 0, 1, 500.0, "b"),  # yanlış alarm, patlamayla ilgisiz
        (2, "2020-05-04 12:00", 1, 1, 700.0, "b"),  # patlama 2, sıra 1, yakalandı
    ]
    df = pd.DataFrame(rows, columns=["cc_num", "trans_date_trans_time", "is_fraud", "alert",
                                     "amt", "grup"])
    df["trans_date_trans_time"] = pd.to_datetime(df["trans_date_trans_time"])
    return df


def test_outcome_labels():
    assert outcome(_frame()).tolist() == ["doğru sessizlik", "kaçtı", "yakalandı",
                                          "yanlış alarm", "doğru sessizlik", "yanlış alarm",
                                          "yakalandı"]


def test_burst_position_and_order_independence():
    df = _frame()
    pos = burst_position(df)
    assert pos.tolist()[1:3] == [1, 2] and pos.iloc[6] == 1
    assert pos.isna().tolist() == [True, False, False, True, True, True, False]
    shuffled = df.sample(frac=1, random_state=0)
    pd.testing.assert_series_equal(burst_position(shuffled).sort_index(), pos,
                                   check_names=False)


def test_after_fraud_window():
    flag = after_fraud(_frame())
    # Yalnızca 1. kartın patlamadan 13 saat sonraki normal işlemi işaretli
    assert flag.tolist() == [False, False, False, True, False, False, False]


def test_fraud_breakdown():
    df = _frame()
    t = fraud_breakdown(df, df["grup"])
    assert t.loc["a", "dolandırıcılık"] == 2 and t.loc["a", "kaçan"] == 1
    assert t.loc["a", "kaçan tutar ($)"] == 15.0 and t.loc["b", "kaçan"] == 0
    assert t["kaçan tutar payı"].sum() == pytest.approx(1.0)


def test_group_error_rates():
    df = _frame()
    t = group_error_rates(df, df["grup"])
    assert t.loc["a", "recall"] == 0.5 and t.loc["b", "recall"] == 1.0
    assert t.loc["a", "yanlış alarm oranı (‰)"] == pytest.approx(1000 / 3)
    assert t.loc["b", "yanlış alarm oranı (‰)"] == 1000.0


def test_standardized_rate_removes_mix_effect():
    """İki grup her katmanda aynı orana sahip ama farklı karışımda: ham fark var,
    standartlaştırılmış fark yok."""
    rows = ([("F", "risky", 1)] * 8 + [("F", "risky", 0)] * 72 + [("F", "safe", 0)] * 20
            + [("M", "risky", 1)] * 2 + [("M", "risky", 0)] * 18 + [("M", "safe", 0)] * 80)
    df = pd.DataFrame(rows, columns=["g", "cat", "y"])
    raw = df.groupby("g")["y"].mean()
    assert raw["F"] == pytest.approx(0.08) and raw["M"] == pytest.approx(0.02)
    std = standardized_rate(df, "g", ["cat"], "y")
    assert std["F"] == pytest.approx(std["M"])


def test_card_concentration():
    c = card_concentration(_frame())
    assert c["yanlış alarm"] == 2 and c["yanlış alarm alan kart"] == 2
    assert c["kart başına en fazla yanlış alarm"] == 1
    assert 0 < c["en çok alarm alan %10 kartın payı"] <= 1
    assert np.isfinite(c["en çok alarm alan %10 kartın payı"])
