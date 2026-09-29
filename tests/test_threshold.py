import numpy as np
import pandas as pd
import pytest

from card_fraud_detection.models.threshold import (
    ORACLE,
    Calibrator,
    choose,
    expected_calibration_error,
    expected_cost_alerts,
    forward_folds,
    prior_correction,
)


def test_prior_correction():
    p = np.array([0.0, 0.2, 0.5, 1.0])
    np.testing.assert_allclose(prior_correction(p, 1.0), p)          # tutulan oran 1: değişmez
    # Normallerin %10'u tutulduysa 0,5 skor → gerçek olasılık 0,1/1,1
    assert prior_correction(0.5, 0.1) == pytest.approx(0.05 / 0.55)
    assert np.all(np.diff(prior_correction(np.linspace(0, 1, 11), 0.1)) >= 0)  # monoton


def test_prior_correction_recovers_true_rate():
    """Normalleri alt örneklenmiş veride öğrenilen oran, düzeltmeyle gerçek orana döner."""
    true_p, beta = 0.01, 0.05
    sampled_p = true_p / (true_p + (1 - true_p) * beta)   # alt örneklemede görülen oran
    assert prior_correction(sampled_p, beta) == pytest.approx(true_p)


@pytest.mark.parametrize("method", Calibrator.METHODS)
def test_calibrators_are_monotone_probabilities(method):
    rng = np.random.default_rng(0)
    score = rng.random(5000)
    y = (rng.random(5000) < score**3).astype(int)
    p = Calibrator(method, beta=0.2).fit(score, y).transform(np.linspace(0, 1, 101))
    assert np.all((p >= 0) & (p <= 1))
    assert np.all(np.diff(p) >= -1e-12)


@pytest.mark.parametrize("method", Calibrator.METHODS)
def test_saved_state_needs_no_project_classes(method):
    """Kaydedilen durum proje sınıflarına atıf yapmamalı; aksi hâlde betik olarak çalıştırılıp
    kaydedilen dosya başka bir yerden yüklenemez (`__main__.Calibrator` hatası)."""
    import pickle

    rng = np.random.default_rng(0)
    score, y = rng.random(500), (rng.random(500) < 0.2).astype(int)
    cal = Calibrator(method, beta=0.3).fit(score, y)
    blob = pickle.dumps(cal.state())
    assert b"card_fraud_detection" not in blob and b"__main__" not in blob
    restored = Calibrator.from_state(pickle.loads(blob))
    np.testing.assert_allclose(restored.transform(score), cal.transform(score))


def test_isotonic_fixes_miscalibrated_scores():
    rng = np.random.default_rng(1)
    true_p = rng.random(20000) * 0.1
    y = (rng.random(20000) < true_p).astype(int)
    inflated = np.sqrt(true_p)                                 # sıralaması doğru, ölçeği yanlış
    cal = Calibrator("izotonik").fit(inflated, y)
    assert expected_calibration_error(y, cal.transform(inflated)) < 0.2 * \
        expected_calibration_error(y, inflated)


def test_ece_zero_when_perfect_and_large_when_off():
    y = np.array([0] * 90 + [1] * 10)
    assert expected_calibration_error(y, np.where(y == 1, 1.0, 0.0), n_bins=10) == 0
    # Tüm skorlar eşit → tek dilim: |0,6 − 0,1| = 0,5 (satır sırasından bağımsız)
    assert expected_calibration_error(y, np.full(100, 0.6), n_bins=10) == pytest.approx(0.5)
    shuffled = np.random.default_rng(0).permutation(y)
    assert expected_calibration_error(shuffled, np.full(100, 0.6)) == pytest.approx(0.5)


def test_expected_cost_rule_depends_on_amount():
    p = np.array([0.02, 0.02, 0.5])
    amt = np.array([400.0, 100.0, 10.0])
    # 0,02 × 400 = 8 < 10; 0,02 × 100 = 2; 0,5 × 10 = 5 → hiçbiri
    assert expected_cost_alerts(p, amt, 10).tolist() == [False, False, False]
    assert expected_cost_alerts(p, amt, 5).tolist() == [True, False, True]


def test_forward_folds_never_look_ahead():
    t = pd.to_datetime(["2020-04-05", "2020-04-20", "2020-05-03", "2020-06-01", "2020-06-10"])
    folds = forward_folds(pd.DataFrame({"trans_date_trans_time": t}))
    assert [m for m, _, _ in folds] == ["2020-05", "2020-06"]
    for _, fit_idx, eval_idx in folds:
        assert t[fit_idx].max() < t[eval_idx].min()
    assert folds[0][1].tolist() == [0, 1] and folds[1][1].tolist() == [0, 1, 2]


def test_choose_ignores_oracle_and_sums_months():
    idx = pd.MultiIndex.from_tuples([
        ("sabit eşik", "izotonik", "05"), ("sabit eşik", "izotonik", "06"),
        ("beklenen maliyet", "izotonik", "05"), ("beklenen maliyet", "izotonik", "06"),
        (ORACLE, "—", "05"), (ORACLE, "—", "06"),
    ])
    table = pd.DataFrame({"maliyet": [50, 50, 30, 80, 1, 1]}, index=idx)
    assert choose(table) == ("sabit eşik", "izotonik")      # 100 < 110; tavan hariç
