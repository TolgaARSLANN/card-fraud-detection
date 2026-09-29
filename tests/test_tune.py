import json

import optuna
import pandas as pd

from card_fraud_detection.models.tune import (
    DEFAULTS,
    decide,
    full_params,
    monthly_pr_auc,
    run_study,
    suggest_params,
)


def test_suggested_params_within_bounds():
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=0))
    for _ in range(50):
        p = suggest_params(study.ask())
        assert 0.02 <= p["ratio"] <= 0.5
        assert 200 <= p["n_estimators"] <= 1500 and p["n_estimators"] % 100 == 0
        assert 15 <= p["num_leaves"] <= 255
        assert 0.4 <= p["colsample_bytree"] <= 1.0


def test_defaults_are_a_point_in_the_search_space():
    # İlk deneme varsayılanlardır; arama alanının içinde olmalılar
    assert 0.02 <= DEFAULTS["ratio"] <= 0.5
    assert 200 <= DEFAULTS["n_estimators"] <= 1500
    assert 15 <= DEFAULTS["num_leaves"] <= 255


def test_run_study_first_trial_is_defaults(monkeypatch):
    import card_fraud_detection.models.tune as tune

    seen = []
    monkeypatch.setattr(tune, "score", lambda params, *a, **k: seen.append(params) or [0.1, 0.9])
    monkeypatch.setattr(tune, "pr_auc", lambda y, s: 0.5)
    valid = pd.DataFrame({"is_fraud": [0, 1]})
    study = run_study(None, valid, n_trials=3)
    assert len(study.trials) == 3
    assert seen[0]["num_leaves"] == DEFAULTS["num_leaves"]
    assert seen[0]["ratio"] == DEFAULTS["ratio"]
    assert full_params(study)["subsample_freq"] == 1


def test_study_resumes_from_storage(monkeypatch, tmp_path):
    """Yarıda kalan çalışma kaldığı yerden sürer; varsayılan deneme yalnızca bir kez eklenir."""
    import card_fraud_detection.models.tune as tune

    monkeypatch.setattr(tune, "score", lambda params, *a, **k: [0.1, 0.9])
    monkeypatch.setattr(tune, "pr_auc", lambda y, s: 0.5)
    valid = pd.DataFrame({"is_fraud": [0, 1]})
    storage = f"sqlite:///{tmp_path / 'study.db'}"
    assert len(run_study(None, valid, n_trials=2, storage=storage).trials) == 2
    study = run_study(None, valid, n_trials=5, storage=storage)
    assert len(study.trials) == 5
    assert sum(t.params.get("num_leaves") == DEFAULTS["num_leaves"]
               and t.params.get("ratio") == DEFAULTS["ratio"] for t in study.trials) == 1


def _seeds(default_mean, tuned_mean, std=0.001):
    return pd.DataFrame({"PR-AUC ortalama": [default_mean, tuned_mean], "std": [std, std]},
                        index=["varsayılan", "ayarlanmış"])


def test_decide_requires_both_checks():
    better_months = pd.DataFrame({"varsayılan": [0.95, 0.96], "ayarlanmış": [0.96, 0.97]})
    mixed_months = pd.DataFrame({"varsayılan": [0.95, 0.96], "ayarlanmış": [0.96, 0.955]})
    adopted, reasons = decide(_seeds(0.970, 0.980), better_months)
    assert adopted is True
    json.dumps({"benimsendi": adopted, "gerekce": reasons})   # rapora yazılabilmeli
    assert not decide(_seeds(0.970, 0.971), better_months)[0]   # kazanç gürültü içinde
    assert not decide(_seeds(0.970, 0.980), mixed_months)[0]    # bir ayda daha kötü


def test_monthly_pr_auc_splits_by_month():
    valid = pd.DataFrame({
        "trans_date_trans_time": pd.to_datetime(["2020-04-01", "2020-04-02", "2020-05-01",
                                                 "2020-05-02"]),
        "is_fraud": [0, 1, 1, 0],
    })
    t = monthly_pr_auc(valid, {"a": pd.Series([0.1, 0.9, 0.9, 0.1]).to_numpy()})
    assert list(t.index) == ["2020-04", "2020-05"]
    assert (t["a"] == 1.0).all()
