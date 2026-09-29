"""Faz 3.1: model × sınıf dengesizliği stratejisi karşılaştırması.

Kullanım:
    python -m card_fraud_detection.models.train
        -> reports/model_karsilastirma.md, reports/model_karsilastirma.json,
           data/processed/valid_scores_3_1.parquet

Modeller: LightGBM ve XGBoost, sabit (ayarlanmamış) hiperparametrelerle. Ayar Faz 3.2'de yapılır.
Doğrulama verisi erken durdurma için kullanılmaz; yalnızca ölçüm içindir.

Dengesizlik stratejileri (yalnızca eğitim verisine uygulanır, doğrulamaya dokunulmaz):
- yok: veri olduğu gibi
- ağırlık: dolandırıcılık örneklerine normal/dolandırıcılık oranı kadar ağırlık
- alt örnekleme: tüm dolandırıcılıklar + normal işlemlerden rastgele seçim (1'e 10)
- SMOTE: sentetik dolandırıcılık örnekleri (SMOTENC), dolandırıcılık = normalin %10'u.
  SMOTE komşuları yalnızca dolandırıcılık örnekleri arasında aradığı için, sentetikler
  dolandırıcılıklar + küçük bir normal örneklemi üzerinde üretilip tüm eğitime eklenir
  (sonuç aynı, bellek çok daha az). SMOTE boş değer kabul etmediği için bu yolda boş
  değerler eğitim medyanıyla doldurulur.

Ek olarak: en iyi iki kombinasyon üç tohumla tekrarlanır (fark gerçek mi?) ve en iyi
kombinasyon yaş ve cinsiyetle bir kez daha eğitilir (demografi ne katıyor?).
"""

from __future__ import annotations

import gc
import json
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from imblearn.over_sampling import SMOTENC
from imblearn.under_sampling import RandomUnderSampler

from card_fraud_detection.config import PROCESSED_DIR, RANDOM_STATE, REPORTS_DIR, TARGET, TIME_COL
from card_fraud_detection.evaluation.compare import comparison_sections, comparison_table
from card_fraud_detection.evaluation.metrics import pr_auc
from card_fraud_detection.features.build import DEMOGRAPHIC_FEATURES, FEATURES, FEATURES_PATH
from card_fraud_detection.models.baselines import REPORT_JSON as BASELINE_JSON
from card_fraud_detection.reporting import to_markdown

REPORT_MD = REPORTS_DIR / "model_karsilastirma.md"
REPORT_JSON = REPORTS_DIR / "model_karsilastirma.json"
SCORES_PATH = PROCESSED_DIR / "valid_scores_3_1.parquet"

STRATEGIES = ["yok", "ağırlık", "alt örnekleme", "SMOTE"]
MINORITY_RATIO = 0.1          # alt örnekleme ve SMOTE sonrası dolandırıcılık / normal
SMOTE_MAJORITY_SAMPLE = 20_000
SEEDS = [RANDOM_STATE, 7, 2024]
# SMOTENC'de kategorik sayılan (ara değer üretilmeyen) sütunlar
DISCRETE = ["category", "gender", "hour", "dow", "is_night", "first_in_category",
            "first_at_merchant"]

LGBM_PARAMS = dict(n_estimators=500, learning_rate=0.05, num_leaves=63, min_child_samples=100,
                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=-1)
XGB_PARAMS = dict(n_estimators=500, learning_rate=0.05, max_depth=6, min_child_weight=5,
                  subsample=0.8, colsample_bytree=0.8, tree_method="hist",
                  enable_categorical=True, eval_metric="aucpr", n_jobs=-1)


# Dengesizlik stratejileri -------------------------------------------------------------------------

def resample(x: pd.DataFrame, y: pd.Series, strategy: str, seed: int = RANDOM_STATE):
    """(x, y, ek model parametreleri) döndürür. Girdiler değiştirilmez."""
    n_pos, n_neg = int(y.sum()), int((y == 0).sum())
    if strategy == "yok":
        return x, y, {}
    if strategy == "ağırlık":
        return x, y, {"scale_pos_weight": n_neg / n_pos}
    if strategy == "alt örnekleme":
        rus = RandomUnderSampler(sampling_strategy=MINORITY_RATIO, random_state=seed)
        rus.fit_resample(x.iloc[:, :1], y)            # yalnızca seçilen indeksler gerekli
        idx = np.sort(rus.sample_indices_)
        return x.iloc[idx], y.iloc[idx], {}
    if strategy == "SMOTE":
        return (*smote(x, y, seed), {})
    raise ValueError(f"Bilinmeyen strateji: {strategy}")


def smote(x: pd.DataFrame, y: pd.Series, seed: int = RANDOM_STATE):
    n_pos, n_neg = int(y.sum()), int((y == 0).sum())
    n_new = int(MINORITY_RATIO * n_neg) - n_pos
    if n_new <= 0:
        return x, y

    rng = np.random.default_rng(seed)
    neg_idx = np.flatnonzero(y.to_numpy() == 0)
    sub_idx = np.r_[np.flatnonzero(y.to_numpy() == 1),
                    rng.choice(neg_idx, min(SMOTE_MAJORITY_SAMPLE, len(neg_idx)), replace=False)]
    sub = x.iloc[sub_idx].copy()
    discrete = [c for c in DISCRETE if c in sub]
    cats = {c: sub[c].cat.categories for c in discrete if hasattr(sub[c], "cat")}
    for c in cats:
        sub[c] = sub[c].cat.codes                     # SMOTENC tam sayı kod ister (-1 = boş)
    medians = x.drop(columns=discrete).median()
    sub = sub.fillna(medians)

    sm = SMOTENC(categorical_features=[sub.columns.get_loc(c) for c in discrete],
                 sampling_strategy={1: n_pos + n_new}, random_state=seed)
    xr, _ = sm.fit_resample(sub, y.iloc[sub_idx])
    synthetic = xr.iloc[len(sub):].copy()             # SMOTE sentetikleri sona ekler
    for c, categories in cats.items():
        codes = synthetic[c].astype(int).to_numpy()
        synthetic[c] = pd.Categorical.from_codes(np.where(codes < 0, -1, codes), categories)
    synthetic = synthetic.astype({c: x[c].dtype for c in x.columns if c not in cats})
    x_out = pd.concat([x, synthetic[x.columns]], ignore_index=True)
    y_out = pd.concat([y, pd.Series(1, index=synthetic.index, dtype=y.dtype)], ignore_index=True)
    return x_out, y_out


# Modeller ---------------------------------------------------------------------------------------

def make_model(kind: str, seed: int = RANDOM_STATE, **overrides):
    if kind == "LightGBM":
        return lgb.LGBMClassifier(**{**LGBM_PARAMS, "random_state": seed, **overrides})
    if kind == "XGBoost":
        return xgb.XGBClassifier(**{**XGB_PARAMS, "random_state": seed, **overrides})
    raise ValueError(f"Bilinmeyen model: {kind}")


def fit_predict(kind: str, strategy: str, train: pd.DataFrame, valid: pd.DataFrame,
                features: list[str], seed: int = RANDOM_STATE, **overrides) -> np.ndarray:
    x, y, params = resample(train[features], train[TARGET], strategy, seed)
    model = make_model(kind, seed, **{**params, **overrides})
    model.fit(x, y)
    return model.predict_proba(valid[features])[:, 1]


# Deney ------------------------------------------------------------------------------------------

def load_splits(features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = list(dict.fromkeys(["tx_id", TIME_COL, "cc_num", "split", TARGET, "amt", *features]))
    f = pd.read_parquet(FEATURES_PATH, columns=cols, filters=[("split", "in", ["train", "valid"])])
    floats = f.select_dtypes("float64").columns.difference(["amt"])
    f[floats] = f[floats].astype("float32")          # bellek: ~3 GB'lık WSL'de sığsın
    train = f[f["split"] == "train"].reset_index(drop=True)
    valid = f[f["split"] == "valid"].reset_index(drop=True)
    return train, valid


def run_grid(train, valid, features) -> tuple[dict, dict]:
    scores, seconds = {}, {}
    for kind in ["LightGBM", "XGBoost"]:
        for strategy in STRATEGIES:
            name = f"{kind} · {strategy}"
            t0 = time.perf_counter()
            scores[name] = fit_predict(kind, strategy, train, valid, features)
            seconds[name] = time.perf_counter() - t0
            gc.collect()
            print(f"  {name}: {seconds[name]:.0f} sn", flush=True)
    return scores, seconds


def seed_check(train, valid, features, names: list[str]) -> pd.DataFrame:
    rows = {}
    for name in names:
        kind, strategy = name.split(" · ")
        vals = []
        for seed in SEEDS:
            vals.append(pr_auc(valid[TARGET], fit_predict(kind, strategy, train, valid,
                                                          features, seed)))
            gc.collect()
        rows[name] = {"PR-AUC ortalama": np.mean(vals), "std": np.std(vals, ddof=1),
                      "en düşük": min(vals), "en yüksek": max(vals)}
        print(f"  tohum kontrolü {name}: {np.round(vals, 4)}", flush=True)
    out = pd.DataFrame(rows).T
    out.index.name = f"model ({len(SEEDS)} tohum)"
    return out


def baseline_row() -> pd.DataFrame:
    table = pd.DataFrame(json.loads(BASELINE_JSON.read_text(encoding="utf-8"))).T
    return table.loc[["Lojistik regresyon"]].rename(
        index={"Lojistik regresyon": "Referans: lojistik regresyon"})


def build_report(table, valid, seeds, demo_name) -> str:
    return "\n".join([
        "# Model × Dengesizlik Stratejisi Karşılaştırması (Faz 3.1)",
        "",
        "_Üreten: `python -m card_fraud_detection.models.train` · Eğitim: eğitim bölmesi · "
        f"Ölçüm: doğrulama bölmesi ({len(valid):,} işlem, {int(valid[TARGET].sum()):,} "
        "dolandırıcılık) · Hiperparametreler sabit, ayar Faz 3.2'de_",
        "",
        *comparison_sections(table, valid),
        "## Tohum kontrolü",
        "",
        f"En iyi iki kombinasyon {len(SEEDS)} farklı rastgele tohumla yeniden eğitildi.",
        "",
        to_markdown(seeds, ".4f"),
        "",
        "## Demografi",
        "",
        f"`{demo_name}` satırı, en iyi kombinasyonun yaş ve cinsiyet eklenerek eğitilmiş hâlidir.",
        "",
    ])


def main() -> None:
    train, valid = load_splits(FEATURES + DEMOGRAPHIC_FEATURES)
    print(f"Eğitim {len(train):,} · doğrulama {len(valid):,} işlem", flush=True)
    scores, seconds = run_grid(train, valid, FEATURES)

    table = comparison_table(valid, scores, seconds)
    top2 = table["PR-AUC"].sort_values(ascending=False).index[:2].tolist()
    seeds = seed_check(train, valid, FEATURES, top2)

    best = top2[0]
    kind, strategy = best.split(" · ")
    demo_name = f"{best} + yaş, cinsiyet"
    t0 = time.perf_counter()
    scores[demo_name] = fit_predict(kind, strategy, train, valid, FEATURES + DEMOGRAPHIC_FEATURES)
    seconds[demo_name] = time.perf_counter() - t0
    table = pd.concat([comparison_table(valid, scores, seconds), baseline_row()])
    table = table.astype(float)

    REPORT_MD.write_text(build_report(table, valid, seeds, demo_name) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"karsilastirma": table.to_dict(orient="index"),
                                       "tohum": seeds.to_dict(orient="index")},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame({"tx_id": valid["tx_id"], **{k: v.astype("float32") for k, v in scores.items()}}
                 ).to_parquet(SCORES_PATH, index=False)
    print(table[["PR-AUC", "bütçe: recall", "eşik*: maliyet ($)",
                 "eşik*: ilk işlemde yakalanan"]].round(3).to_string())
    print(f"[ok] {REPORT_MD}")


if __name__ == "__main__":
    main()
