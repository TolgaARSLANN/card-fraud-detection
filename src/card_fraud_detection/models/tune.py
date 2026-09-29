"""Faz 3.2: LightGBM · alt örnekleme için hiperparametre ayarı (Optuna, doğrulamada PR-AUC).

Kullanım:
    python -m card_fraud_detection.models.tune [--trials 60]
        -> models/best_params.json, reports/ayar_sonuclari.md

Ayar doğrulama verisinde yapıldığı için en iyi deneme o veriye kısmen uyar (iyimserdir).
Bu yüzden ayarlanmış parametreler ancak iki kontrolü geçerse benimsenir:
1. Tohum kontrolü: varsayılan ve ayarlanmış parametreler üçer tohumla eğitilir; ortalama
   kazanç, iki tarafın tohum standart sapmasının toplamından büyük olmalıdır.
2. Zaman kararlılığı: doğrulamanın her ayında (Nisan, Mayıs, Haziran) ayarlanmış model
   varsayılandan iyi olmalıdır.
Geçemezse varsayılan parametrelerde kalınır ve bu karar dosyaya yazılır.
"""

from __future__ import annotations

import argparse
import gc
import json
import time

import numpy as np
import optuna
import pandas as pd

from card_fraud_detection.config import (
    MODELS_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
    REPORTS_DIR,
    TARGET,
    TIME_COL,
)
from card_fraud_detection.evaluation.metrics import pr_auc
from card_fraud_detection.features.build import FEATURES
from card_fraud_detection.models.train import (
    LGBM_PARAMS,
    MINORITY_RATIO,
    SEEDS,
    fit_predict,
    load_splits,
)
from card_fraud_detection.reporting import to_markdown

KIND, STRATEGY = "LightGBM", "alt örnekleme"
PARAMS_PATH = MODELS_DIR / "best_params.json"
REPORT_MD = REPORTS_DIR / "ayar_sonuclari.md"
STUDY_DB = PROCESSED_DIR / "optuna.db"         # denemeler burada kalıcı (repoya girmez)
STUDY_NAME = "lgbm_alt_ornekleme"
DEFAULTS = {"ratio": MINORITY_RATIO, **{k: v for k, v in LGBM_PARAMS.items()
                                        if k not in ("verbose", "n_jobs")}}


def suggest_params(trial: optuna.Trial) -> dict:
    return {
        "ratio": trial.suggest_float("ratio", 0.02, 0.5, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 200, 1500, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 500, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "subsample_freq": 1,
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
    }


def score(params: dict, train, valid, seed: int = RANDOM_STATE, **extra) -> np.ndarray:
    p = dict(params)
    ratio = p.pop("ratio")
    return fit_predict(KIND, STRATEGY, train, valid, FEATURES, seed, ratio, **p, **extra)


def run_study(train, valid, n_trials: int, storage: str | None = None, **extra) -> optuna.Study:
    """`storage` verilirse denemeler kalıcıdır: yarıda kalan çalışma kaldığı yerden sürer ve
    toplam `n_trials` tamamlanmış denemeye tamamlanır."""
    def objective(trial):
        s = score(suggest_params(trial), train, valid, **extra)
        gc.collect()
        return pr_auc(valid[TARGET], s)

    study = optuna.create_study(direction="maximize", storage=storage, study_name=STUDY_NAME,
                                load_if_exists=storage is not None,
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not study.trials:
        # İlk deneme varsayılanlardır; düzenlileştirme alt sınırda (pratikte yok)
        study.enqueue_trial({**{k: v for k, v in DEFAULTS.items() if k != "subsample_freq"},
                             "reg_lambda": 1e-3, "reg_alpha": 1e-3})
    remaining = n_trials - len(done)
    if remaining > 0:
        study.optimize(objective, n_trials=remaining, show_progress_bar=False)
    return study


def full_params(study: optuna.Study) -> dict:
    return {**study.best_params, "subsample_freq": 1}


def seed_comparison(candidates: dict, train, valid) -> tuple[pd.DataFrame, dict]:
    """Her aday için tohum başına PR-AUC ve tohum ortalamalı skorlar (ay bazlı kontrol için)."""
    rows, mean_scores = {}, {}
    for name, params in candidates.items():
        vals, acc = [], np.zeros(len(valid))
        for seed in SEEDS:
            s = score(params, train, valid, seed)
            vals.append(pr_auc(valid[TARGET], s))
            acc += s / len(SEEDS)
            gc.collect()
        rows[name] = {"PR-AUC ortalama": np.mean(vals), "std": np.std(vals, ddof=1),
                      **{f"tohum {sd}": v for sd, v in zip(SEEDS, vals, strict=True)}}
        mean_scores[name] = acc
        print(f"  {name}: {np.round(vals, 4)}", flush=True)
    table = pd.DataFrame(rows).T
    table.index.name = "parametreler"
    return table, mean_scores


def monthly_pr_auc(valid, scores: dict) -> pd.DataFrame:
    month = valid[TIME_COL].dt.to_period("M").astype(str)
    rows = {m: {name: pr_auc(valid.loc[idx, TARGET], s[idx])
                for name, s in scores.items()}
            for m, idx in valid.groupby(month).indices.items()}
    table = pd.DataFrame(rows).T
    table.index.name = "ay"
    return table


def decide(seeds: pd.DataFrame, monthly: pd.DataFrame) -> tuple[bool, list[str]]:
    d, t = seeds.loc["varsayılan"], seeds.loc["ayarlanmış"]
    gain = t["PR-AUC ortalama"] - d["PR-AUC ortalama"]
    noise = t["std"] + d["std"]
    every_month = bool((monthly["ayarlanmış"] > monthly["varsayılan"]).all())
    reasons = [
        f"Tohum ortalamasında kazanç {gain:+.4f}; tohum oynaklığı (iki std toplamı) {noise:.4f} "
        f"→ {'geçti' if gain > noise else 'geçmedi'}.",
        f"Her ayda ayarlanmış model daha iyi mi: {'evet' if every_month else 'hayır'} "
        f"→ {'geçti' if every_month else 'geçmedi'}.",
    ]
    return bool(gain > noise and every_month), reasons   # numpy.bool_ JSON'a yazılamaz


def build_report(study, seeds, monthly, adopted, reasons, minutes) -> str:
    trials = study.trials_dataframe(attrs=("number", "value", "params", "duration"))
    trials["duration"] = trials["duration"].dt.total_seconds().round(1)
    trials = trials.rename(columns=lambda c: c.replace("params_", ""))
    top = trials.sort_values("value", ascending=False).head(10).set_index("number")
    top.index.name = "deneme"
    try:
        imp = pd.Series(optuna.importance.get_param_importances(study)).rename("önem")
        imp.index.name = "parametre"
        imp_md = to_markdown(imp, ".3f")
    except (RuntimeError, ValueError) as exc:           # çok az deneme varsa hesaplanamaz
        imp_md = f"_Hesaplanamadı: {exc}_"
    return "\n".join([
        "# Hiperparametre Ayarı (Faz 3.2)",
        "",
        f"_Üreten: `python -m card_fraud_detection.models.tune` · Model: {KIND} · {STRATEGY} · "
        f"{len(study.trials)} deneme, {minutes:.0f} dk · Hedef: doğrulamada PR-AUC · "
        "İlk deneme varsayılan parametrelerdir_",
        "",
        f"## Karar: {'ayarlanmış parametreler benimsendi' if adopted else 'varsayılanda kalındı'}",
        "",
        *[f"- {r}" for r in reasons],
        "",
        "## Tohum kontrolü",
        "",
        to_markdown(seeds, ".4f"),
        "",
        "## Aylara göre PR-AUC (tohum ortalamalı skor)",
        "",
        to_markdown(monthly, ".4f"),
        "",
        "## En iyi 10 deneme",
        "",
        "Değerler doğrulama verisinde seçildiği için iyimserdir.",
        "",
        to_markdown(top, ".4f"),
        "",
        "## Parametre önemi (fANOVA)",
        "",
        imp_md,
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=60)
    args = parser.parse_args()

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    train, valid = load_splits(FEATURES)
    t0 = time.perf_counter()
    study = run_study(train, valid, args.trials, storage=f"sqlite:///{STUDY_DB}")
    minutes = (time.perf_counter() - t0) / 60
    print(f"En iyi deneme #{study.best_trial.number}: PR-AUC {study.best_value:.4f} "
          f"({minutes:.0f} dk)", flush=True)

    tuned = full_params(study)
    seeds, mean_scores = seed_comparison({"varsayılan": DEFAULTS, "ayarlanmış": tuned},
                                         train, valid)
    monthly = monthly_pr_auc(valid, mean_scores)
    adopted, reasons = decide(seeds, monthly)

    chosen = tuned if adopted else DEFAULTS
    PARAMS_PATH.write_text(json.dumps({
        "model": KIND, "strateji": STRATEGY, "benimsendi": adopted,
        "parametreler": chosen, "ayarlanmis_parametreler": tuned, "gerekce": reasons,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_report(study, seeds, monthly, adopted, reasons, minutes) + "\n",
                         encoding="utf-8")
    print("\n".join(reasons))
    print(f"[ok] {PARAMS_PATH} · {REPORT_MD}")


if __name__ == "__main__":
    main()
