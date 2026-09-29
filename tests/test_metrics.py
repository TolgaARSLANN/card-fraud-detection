import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.evaluation.metrics import (
    alert_metrics,
    assign_bursts,
    best_threshold_by_cost,
    burst_metrics,
    cost_curve,
    daily_budget_alerts,
    evaluate,
    pr_auc,
    recall_at_precision,
    threshold_metrics,
)


def test_ranking_metrics():
    y = np.array([0, 0, 1, 0, 1, 1])
    perfect = np.array([0.1, 0.2, 0.8, 0.3, 0.9, 0.7])
    assert pr_auc(y, perfect) == 1.0
    assert recall_at_precision(y, perfect, 1.0) == 1.0
    # Sıralama: 1, 0, 1, 1, 0, 0 → precision 1 yalnızca ilk işlemde (recall 1/3)
    mixed = np.array([0.1, 0.2, 0.8, 0.95, 0.9, 0.7])
    order = np.argsort(-mixed)
    assert y[order].tolist() == [0, 1, 1, 1, 0, 0]
    assert recall_at_precision(y, mixed, 1.0) == 0.0
    assert recall_at_precision(y, mixed, 0.75) == 1.0      # ilk 4'te 3 doğru


def test_alert_metrics_and_cost():
    y = np.array([1, 1, 0, 0, 1])
    alert = np.array([1, 0, 1, 0, 0])
    amt = np.array([100.0, 50.0, 5.0, 5.0, 20.0])
    m = alert_metrics(y, alert, amt, review_cost=10)
    assert (m["tp"], m["fp"], m["fn"], m["alarm"]) == (1, 1, 2, 2)
    assert m["precision"] == 0.5 and m["recall"] == pytest.approx(1 / 3)
    assert m["yakalanan_tutar"] == 100 and m["kacan_tutar"] == 70
    assert m["tutar_recall"] == pytest.approx(100 / 170)
    assert m["maliyet"] == 70 + 10 * 2


def test_no_alerts_is_well_defined():
    m = alert_metrics([1, 0], [0, 0], [10.0, 1.0], review_cost=5)
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["maliyet"] == 10.0


def test_cost_curve_matches_brute_force():
    rng = np.random.default_rng(0)
    n = 400
    y = (rng.random(n) < 0.05).astype(int)
    amt = rng.gamma(2, 50, n).round(2)
    score = np.round(rng.random(n) + 0.5 * y, 2)            # yuvarlama: eşit skorlar da var
    curve = cost_curve(y, score, amt, review_cost=7)

    for _, row in curve.iterrows():
        brute = threshold_metrics(y, score, amt, row["esik"], review_cost=7)
        assert row["alarm"] == brute["alarm"] and row["tp"] == brute["tp"]
        assert row["maliyet"] == pytest.approx(brute["maliyet"])

    thr = best_threshold_by_cost(y, score, amt, review_cost=7)
    candidates = np.r_[np.unique(score), np.inf]
    brute_best = min(threshold_metrics(y, score, amt, t, 7)["maliyet"] for t in candidates)
    assert threshold_metrics(y, score, amt, thr, 7)["maliyet"] == pytest.approx(brute_best)


def test_best_threshold_can_be_no_alert():
    # İnceleme ücreti tutarlardan pahalıysa hiç alarm vermemek en ucuzu
    thr = best_threshold_by_cost([1, 0, 0], [0.9, 0.5, 0.1], [5.0, 1.0, 1.0], review_cost=100)
    assert thr == np.inf


def test_daily_budget_alerts():
    score = np.array([0.9, 0.1, 0.5, 0.5, 0.8, 0.2])
    day = np.array(["a", "a", "a", "b", "b", "b"])
    alert = daily_budget_alerts(score, day, k=2)
    assert alert.tolist() == [True, False, True, True, True, False]
    assert daily_budget_alerts(score, day, k=0).sum() == 0


def _bursts_frame():
    rows = [  # (kart, zaman, etiket, tutar)
        (1, "2020-01-01 00:00", 0, 10.0),
        (1, "2020-01-02 22:00", 1, 300.0),   # 1. patlama
        (1, "2020-01-03 01:00", 1, 900.0),
        (1, "2020-01-03 03:00", 1, 50.0),
        (1, "2020-01-20 22:00", 1, 400.0),   # 17 gün sonra: 2. patlama
        (2, "2020-01-03 02:00", 1, 700.0),   # başka kart: 3. patlama
        (2, "2020-01-03 04:00", 0, 20.0),
    ]
    return pd.DataFrame(rows, columns=["cc_num", "trans_date_trans_time", "is_fraud", "amt"])


def test_assign_bursts():
    df = _bursts_frame()
    b = assign_bursts(df["cc_num"], df["trans_date_trans_time"], df["is_fraud"])
    assert b.tolist() == [-1, 0, 0, 0, 1, 2, -1]


def test_burst_metrics():
    df = _bursts_frame()
    alert = np.array([0, 0, 1, 1, 0, 1, 0])  # 1. patlama 2. işlemde, 3. patlama 1. işlemde
    m = burst_metrics(df["cc_num"], df["trans_date_trans_time"], df["is_fraud"], alert, df["amt"])
    assert m["patlama"] == 3
    assert m["patlama_recall"] == pytest.approx(2 / 3)
    assert m["ilk_islemde_yakalanan"] == pytest.approx(1 / 3)
    assert m["ilk_alarm_sira_medyan"] == 1.5
    # Kayıp: 1. patlamada ilk alarmdan önceki 300 + yakalanmayan 2. patlamanın 400
    assert m["kayip_tutar_orani"] == pytest.approx((300 + 400) / (1250 + 400 + 700))


def test_burst_metrics_order_independent():
    df = _bursts_frame()
    alert = np.array([0, 0, 1, 1, 0, 1, 0])
    idx = np.random.default_rng(1).permutation(len(df))
    a = burst_metrics(df["cc_num"], df["trans_date_trans_time"], df["is_fraud"], alert, df["amt"])
    s = df.iloc[idx]
    b = burst_metrics(s["cc_num"], s["trans_date_trans_time"], s["is_fraud"], alert[idx], s["amt"])
    assert a == b


def test_evaluate_combines_everything():
    df = _bursts_frame()
    score = np.array([0.1, 0.2, 0.9, 0.8, 0.3, 0.95, 0.05])
    m = evaluate(df, score, threshold=0.5, review_cost=10)
    assert m["alarm"] == 3 and m["tp"] == 3 and m["patlama"] == 3
    assert {"pr_auc", "roc_auc", "recall@p0.5", "maliyet", "patlama_recall"} <= set(m)
