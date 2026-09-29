import numpy as np
import pandas as pd
import pytest

import card_fraud_detection.models.final as final
from card_fraud_detection.models.final import (
    card_bootstrap_diff,
    check_lock,
    formatted,
    monthly,
)


def _scores(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    cards = rng.integers(0, 100, n)
    y = (rng.random(n) < 0.05).astype(int)
    good = y + rng.normal(0, 0.3, n)           # iyi ayıran skor
    weak = y + rng.normal(0, 1.5, n)           # zayıf skor
    return y, good, weak, cards


def test_bootstrap_detects_real_difference():
    y, good, weak, cards = _scores()
    r = card_bootstrap_diff(y, good, weak, cards, n_boot=100)
    assert r["fark"] > 0 and r["alt_sinir_95"] > 0
    assert r["alt_sinir_95"] <= r["fark"] <= r["ust_sinir_95"]


def test_bootstrap_interval_covers_zero_for_equal_models():
    y, good, _, cards = _scores()
    r = card_bootstrap_diff(y, good, good.copy(), cards, n_boot=50)
    assert r["fark"] == 0 and r["alt_sinir_95"] <= 0 <= r["ust_sinir_95"]


def test_lock_blocks_second_run(tmp_path, monkeypatch):
    lock = tmp_path / "kilit.lock"
    monkeypatch.setattr(final, "LOCK_PATH", lock)
    check_lock(force=False)                                   # ilk çalıştırma serbest
    lock.write_text("2020-01-01T00:00:00\n")
    with pytest.raises(SystemExit, match="bir kez"):
        check_lock(force=False)
    check_lock(force=True)                                    # bilinçli yeniden üretim


def test_formatted_counts_money_and_rates():
    s = pd.Series({"alarm": 2522.0, "maliyet": 45524.94, "recall": 0.87184, "tekrar": 200.0},
                  name="değer")
    assert formatted(s)["değer"].tolist() == ["2,522", "$45,525", "0.8718", "200"]


def test_monthly_splits_by_month():
    t = pd.to_datetime(["2020-07-01", "2020-07-02", "2020-08-01", "2020-08-02"])
    frame = pd.DataFrame({"trans_date_trans_time": t, "cc_num": [1, 1, 2, 2],
                          "is_fraud": [0, 1, 1, 0], "amt": [5.0, 500.0, 300.0, 10.0]})
    out = monthly(frame, np.array([0.1, 0.9, 0.8, 0.2]), np.array([0, 1, 0, 0], dtype=bool))
    assert list(out.index) == ["2020-07", "2020-08"]
    assert out.loc["2020-07", "recall"] == 1.0 and out.loc["2020-08", "recall"] == 0.0
    assert out.loc["2020-08", "maliyet"] == 300.0
