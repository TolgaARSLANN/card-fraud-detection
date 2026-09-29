"""Referans modeller: asıl modelin geçmesi gereken çıtalar.

Kullanım:
    python -m card_fraud_detection.models.baselines
        -> reports/baseline_sonuclari.md, reports/baseline_sonuclari.json

Her model yalnızca eğitim bölmesinde eğitilir, doğrulama bölmesinde ölçülür. Test bölmesine
dokunulmaz.
- Yalnızca tutar: skor = işlem tutarı.
- Kural tabanlı: EDA'dan (yalnızca eğitim) alınan üç uyarı işaretinden kaçının tuttuğu (0–3):
  gece, tutar >= $200, tutar >= kartın geçmiş ortalamasının 3 katı.
- Lojistik regresyon: ana özellikler; log dönüşüm, kategorik kodlama, doldurma, ölçekleme;
  sınıf ağırlığı dengeli.
- Isolation Forest: etiket kullanmayan anomali skoru, aynı ön işlemeyle.

Karşılaştırmanın ana ölçütleri eşikten bağımsızdır (PR-AUC, günlük alarm bütçesi). Maliyete
göre eşik doğrulamanın kendisinde seçildiği için o sütunlar iyimserdir ve öyle etiketlenir.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from card_fraud_detection.config import RANDOM_STATE, REPORTS_DIR, REVIEW_COST, TARGET, TIME_COL
from card_fraud_detection.evaluation.metrics import (
    alert_metrics,
    best_threshold_by_cost,
    daily_budget_alerts,
    evaluate,
)
from card_fraud_detection.features.build import FEATURES, FEATURES_PATH
from card_fraud_detection.reporting import to_markdown

REPORT_MD = REPORTS_DIR / "baseline_sonuclari.md"
REPORT_JSON = REPORTS_DIR / "baseline_sonuclari.json"
DAILY_BUDGET = 25          # günde incelenebilecek alarm sayısı (doğrulamada ~14 dolandırıcılık/gün)

# Kural tabanlı modelin eşikleri: EDA §1 ve §4 (yalnızca eğitim bölmesi)
RULE_MIN_AMT = 200.0
RULE_MIN_CARD_RATIO = 3.0

# Lojistik regresyon için ön işleme grupları
LOG_COLS = ["amt", "amt_to_cat_median", "amt_sum_1h", "amt_sum_24h", "amt_sum_7d",
            "amt_to_card_mean", "hrs_since_prev", "card_n_prev", "n_1h", "n_24h", "n_7d"]
CATEGORICAL_COLS = ["category", "hour", "dow"]
PASS_COLS = ["is_night", "first_in_category", "first_at_merchant"]
CLIP_COLS = ["amt_card_z"]


def _clip(x):
    return np.clip(x, -10, 10)


def _numeric(transform) -> Pipeline:
    """Dönüşüm → boş değerleri medyanla doldur (+ boş göstergesi) → ölçekle."""
    return Pipeline([
        ("f", FunctionTransformer(transform, feature_names_out="one-to-one")),
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])


def preprocessor() -> ColumnTransformer:
    """Eğitimde fit edilir; doldurma değerleri ve ölçek yalnızca eğitimden öğrenilir."""
    covered = set(LOG_COLS + CATEGORICAL_COLS + PASS_COLS + CLIP_COLS) | {"log_amt"}
    missing = set(FEATURES) - covered
    if missing:
        raise ValueError(f"Ön işlemede karşılığı olmayan özellik: {sorted(missing)}")
    return ColumnTransformer([
        ("log", _numeric(np.log1p), LOG_COLS),
        ("clip", _numeric(_clip), CLIP_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLS),
        ("pass", "passthrough", PASS_COLS),
    ])  # log_amt, amt'nin log'u olduğu için ayrıca eklenmez


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    x = df[FEATURES].copy()
    # Kategori boşsa (eğitimde görülmemiş) OneHotEncoder tüm sütunları 0 yapar
    x["category"] = x["category"].astype(str)
    return x


# Modeller: her biri (eğitim, doğrulama) -> doğrulama skoru ---------------------------------------

def amount_only(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    return valid["amt"].to_numpy(dtype=float)


def rule_based(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    flags = (valid["is_night"].eq(1).astype(int)
             + valid["amt"].ge(RULE_MIN_AMT).astype(int)
             + valid["amt_to_card_mean"].ge(RULE_MIN_CARD_RATIO).astype(int))
    return flags.to_numpy(dtype=float)


def logistic_regression(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    model = Pipeline([
        ("prep", preprocessor()),
        ("lr", LogisticRegression(class_weight="balanced", max_iter=2000,
                                  random_state=RANDOM_STATE)),
    ])
    model.fit(_prepare(train), train[TARGET])
    return model.predict_proba(_prepare(valid))[:, 1]


def isolation_forest(train: pd.DataFrame, valid: pd.DataFrame) -> np.ndarray:
    model = Pipeline([
        ("prep", preprocessor()),
        ("if", IsolationForest(n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1)),
    ])
    model.fit(_prepare(train))                 # etiket kullanılmaz
    return -model.score_samples(_prepare(valid))   # yüksek = daha anormal


MODELS: dict[str, Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]] = {
    "Yalnızca tutar": amount_only,
    "Kural tabanlı": rule_based,
    "Lojistik regresyon": logistic_regression,
    "Isolation Forest": isolation_forest,
}


def score_models(train: pd.DataFrame, valid: pd.DataFrame) -> tuple[dict, dict]:
    scores, seconds = {}, {}
    for name, fn in MODELS.items():
        t0 = time.perf_counter()
        scores[name] = fn(train, valid)
        seconds[name] = time.perf_counter() - t0
        print(f"  {name}: {seconds[name]:.1f} sn")
    return scores, seconds


def summarize(valid: pd.DataFrame, scores: dict, seconds: dict) -> pd.DataFrame:
    y, amt = valid[TARGET].to_numpy(), valid["amt"].to_numpy()
    day = valid[TIME_COL].dt.date.to_numpy()
    rows = {}
    for name, s in scores.items():
        budget = alert_metrics(y, daily_budget_alerts(s, day, DAILY_BUDGET), amt)
        thr = best_threshold_by_cost(y, s, amt)
        m = evaluate(valid, s, thr)
        rows[name] = {
            "PR-AUC": m["pr_auc"], "ROC-AUC": m["roc_auc"], "recall@p0.5": m["recall@p0.5"],
            "bütçe: recall": budget["recall"], "bütçe: tutar recall": budget["tutar_recall"],
            "bütçe: precision": budget["precision"],
            "eşik*: alarm": m["alarm"], "eşik*: precision": m["precision"],
            "eşik*: recall": m["recall"], "eşik*: tutar recall": m["tutar_recall"],
            "eşik*: kaçan tutar ($)": m["kacan_tutar"], "eşik*: maliyet ($)": m["maliyet"],
            "eşik*: patlama recall": m["patlama_recall"],
            "eşik*: ilk işlemde yakalanan": m["ilk_islemde_yakalanan"],
            "süre (sn)": seconds[name],
        }
    return pd.DataFrame(rows).T


def build_report(table: pd.DataFrame, valid: pd.DataFrame) -> str:
    n_days = valid[TIME_COL].dt.date.nunique()
    no_alert_cost = valid.loc[valid[TARGET] == 1, "amt"].sum()
    rank = table.sort_values("PR-AUC", ascending=False)
    main = rank[["PR-AUC", "ROC-AUC", "recall@p0.5", "bütçe: recall", "bütçe: tutar recall",
                 "bütçe: precision", "süre (sn)"]]
    thr = rank[[c for c in rank.columns if c.startswith("eşik*")]].copy()
    for col in ["eşik*: alarm", "eşik*: kaçan tutar ($)", "eşik*: maliyet ($)"]:
        thr[col] = thr[col].round().astype(int)
    main.index.name = thr.index.name = "model"
    return "\n".join([
        "# Referans Model Sonuçları",
        "",
        "_Üreten: `python -m card_fraud_detection.models.baselines` · Eğitim: eğitim bölmesi · "
        f"Ölçüm: doğrulama bölmesi ({len(valid):,} işlem, {int(valid[TARGET].sum()):,} "
        f"dolandırıcılık, {n_days} gün)_",
        "",
        "## 1. Eşikten bağımsız karşılaştırma (ana ölçüt)",
        "",
        f"Bütçe: Her gün en yüksek skorlu **{DAILY_BUDGET}** işlem incelenir "
        f"(doğrulamada günde ortalama {valid[TARGET].sum() / n_days:.1f} dolandırıcılık var).",
        "",
        to_markdown(main, ".3f"),
        "",
        "## 2. Maliyete göre seçilen eşikte (iyimser)",
        "",
        f"\\* Eşik, maliyeti (kaçan tutar + alarm başına ${REVIEW_COST:g}) en aza indirecek "
        "biçimde **doğrulamanın kendisinde** seçildi. Bu yüzden sonuçlar iyimserdir; asıl model "
        "için eşik Faz 3.3'te doğrulamada seçilip testte sabit tutulacak. "
        f"Hiç alarm vermemenin maliyeti: ${no_alert_cost:,.0f}.",
        "",
        to_markdown(thr, ".3f"),
        "",
    ])


def main() -> None:
    f = pd.read_parquet(FEATURES_PATH, columns=list(dict.fromkeys(
        ["tx_id", TIME_COL, "cc_num", "split", TARGET, *FEATURES])))
    train = f[f["split"] == "train"].reset_index(drop=True)
    valid = f[f["split"] == "valid"].reset_index(drop=True)
    print(f"Eğitim {len(train):,} · doğrulama {len(valid):,} işlem")
    scores, seconds = score_models(train, valid)
    table = summarize(valid, scores, seconds)

    REPORT_MD.write_text(build_report(table, valid) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(table.to_dict(orient="index"), ensure_ascii=False,
                                      indent=2) + "\n", encoding="utf-8")
    print(table[["PR-AUC", "bütçe: recall", "eşik*: maliyet ($)"]].round(3).to_string())
    print(f"[ok] {REPORT_MD}")


if __name__ == "__main__":
    main()
