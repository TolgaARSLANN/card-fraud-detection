"""Her işlem için yalnızca o ana kadar bilinen bilgilerden özellik üretir.

Kullanım:
    python -m card_fraud_detection.features.build
        -> data/processed/features.parquet, models/feature_stats.json

Özellik aileleri (gerekçeler: notebooks/01_eda.ipynb §7):
- İşlem: tutar, log tutar, kategori, saat, haftanın günü, gece bayrağı ve tutarın kategori
  medyanına oranı. Kategori medyanları yalnızca eğitim bölmesinden hesaplanır (`fit_stats`).
- Kart geçmişi: 1 sa / 24 sa / 7 g pencerede işlem sayısı ve toplam tutar, önceki işlemden bu
  yana geçen süre, kartın geçmiş işlem sayısı, tutarın kartın geçmiş ortalamasına oranı ve
  z-skoru, kategoride / satıcıda ilk işlem mi.
- Demografi (yaş, cinsiyet): hesaplanır ama ana listede (`FEATURES`) yoktur; yalnızca
  karşılaştırma modelinde (`DEMOGRAPHIC_FEATURES`) kullanılır.

Sızıntı kuralı: Bir işlemin özellikleri yalnızca kendisinden **önceki** işlemlerden hesaplanır.
Pencere özellikleri `[t - pencere, t)` aralığına bakar; aynı saniyedeki diğer işlemler dahil
edilmez. Sıra tabanlı özellikler (önceki işlem, geçmiş ortalama, ilk işlem mi) ise kart içinde
zaman ve `tx_id` sırasına göre öncekileri kullanır. Geçmiş etiketler hiç kullanılmaz.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from card_fraud_detection.config import CARD_COL, MODELS_DIR, PROCESSED_DIR, TARGET, TIME_COL
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH

FEATURES_PATH = PROCESSED_DIR / "features.parquet"
STATS_PATH = MODELS_DIR / "feature_stats.json"

WINDOWS = {"1h": "1h", "24h": "24h", "7d": "7D"}
NIGHT_HOURS = (22, 23, 0, 1, 2, 3)

TRANSACTION_FEATURES = [
    "amt", "log_amt", "category", "hour", "dow", "is_night", "amt_to_cat_median",
]
CARD_FEATURES = [
    *(f"n_{w}" for w in WINDOWS), *(f"amt_sum_{w}" for w in WINDOWS),
    "hrs_since_prev", "card_n_prev", "amt_to_card_mean", "amt_card_z",
    "first_in_category", "first_at_merchant",
]
FEATURES = TRANSACTION_FEATURES + CARD_FEATURES
DEMOGRAPHIC_FEATURES = ["age", "gender"]
# Modele girmeyen ama değerlendirme ve analiz için taşınan sütunlar
ID_COLUMNS = ["tx_id", TIME_COL, CARD_COL, "merchant", "split", TARGET]


@dataclass(frozen=True)
class FeatureStats:
    """Eğitim bölmesinden öğrenilen, servis sırasında da aynen kullanılacak değerler."""

    category_median_amt: dict[str, float]
    categories: list[str]
    genders: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> FeatureStats:
        return cls(**json.loads(text))


def fit_stats(train: pd.DataFrame) -> FeatureStats:
    if "split" in train and (train["split"] != "train").any():
        raise ValueError("fit_stats yalnızca eğitim bölmesiyle çağrılmalı")
    medians = train.groupby("category", observed=True)["amt"].median()
    return FeatureStats(
        category_median_amt={str(k): float(v) for k, v in medians.items()},
        categories=sorted(str(c) for c in train["category"].unique()),
        genders=sorted(str(g) for g in train["gender"].unique()),
    )


def transaction_features(df: pd.DataFrame, stats: FeatureStats) -> pd.DataFrame:
    """Yalnızca işlemin kendisinden (ve eğitimden öğrenilmiş sabitlerden) gelen özellikler."""
    t = df[TIME_COL]
    # Eğitimde görülmemiş kategori ve cinsiyet değerleri boş (NaN) olur
    cat = df["category"].astype(str).where(lambda c: c.isin(stats.categories))
    gender = df["gender"].astype(str).where(lambda c: c.isin(stats.genders))
    return pd.DataFrame({
        "amt": df["amt"],
        "log_amt": np.log1p(df["amt"]),
        "category": pd.Categorical(cat, categories=stats.categories),
        "hour": t.dt.hour.astype("int8"),
        "dow": t.dt.dayofweek.astype("int8"),
        "is_night": t.dt.hour.isin(NIGHT_HOURS).astype("int8"),
        "amt_to_cat_median": df["amt"] / cat.map(stats.category_median_amt).astype(float),
        "age": ((t - df["dob"]).dt.days / 365.25).astype("float32"),
        "gender": pd.Categorical(gender, categories=stats.genders),
    }, index=df.index)


def card_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Kartın geçmiş işlemlerinden hesaplanan özellikler. Girdi sırası korunur."""
    order = df.sort_values([CARD_COL, TIME_COL, "tx_id"], kind="stable").index
    s = df.loc[order, [CARD_COL, TIME_COL, "amt", "category", "merchant"]]
    g = s.groupby(CARD_COL, sort=False)
    out = pd.DataFrame(index=order)

    # Zaman pencereleri: [t - pencere, t); o anki ve aynı saniyedeki işlemler hariç
    timed = s.set_index(TIME_COL).groupby(CARD_COL, sort=False)["amt"]
    for name, window in WINDOWS.items():
        roll = timed.rolling(window, closed="left")
        out[f"n_{name}"] = roll.count().fillna(0).to_numpy().astype("int32")
        out[f"amt_sum_{name}"] = roll.sum().fillna(0).to_numpy()

    out["hrs_since_prev"] = g[TIME_COL].diff().dt.total_seconds().to_numpy() / 3600

    # Geçmiş ortalama ve standart sapma: kümülatif toplamlardan, o anki işlem çıkarılarak
    n_prev = g.cumcount()
    sum_prev = g["amt"].cumsum() - s["amt"]
    sq_prev = (s["amt"] ** 2).groupby(s[CARD_COL], sort=False).cumsum() - s["amt"] ** 2
    mean_prev = sum_prev / n_prev.replace(0, np.nan)
    var_prev = (sq_prev - n_prev * mean_prev**2) / (n_prev - 1).where(n_prev > 1)
    std_prev = np.sqrt(var_prev.clip(lower=0))
    out["card_n_prev"] = n_prev.to_numpy().astype("int32")
    out["amt_to_card_mean"] = (s["amt"] / mean_prev).to_numpy()
    out["amt_card_z"] = ((s["amt"] - mean_prev) / std_prev.replace(0, np.nan)).to_numpy()

    out["first_in_category"] = (
        s.groupby([CARD_COL, "category"], sort=False, observed=True).cumcount() == 0
    ).astype("int8").to_numpy()
    out["first_at_merchant"] = (
        s.groupby([CARD_COL, "merchant"], sort=False, observed=True).cumcount() == 0
    ).astype("int8").to_numpy()
    return out.reindex(df.index)


def build_features(df: pd.DataFrame, stats: FeatureStats) -> pd.DataFrame:
    """Kimlik sütunları + tüm özellikler. Girdinin satır sırası korunur."""
    ids = df[[c for c in ID_COLUMNS if c in df]]
    return pd.concat([ids, transaction_features(df, stats), card_history_features(df)], axis=1)


def main() -> None:
    df = pd.read_parquet(TRANSACTIONS_PATH)
    stats = fit_stats(df[df["split"] == "train"])
    feats = build_features(df, stats)
    missing = sorted(set(FEATURES + DEMOGRAPHIC_FEATURES) - set(feats.columns))
    if missing:
        raise ValueError(f"Eksik özellik: {missing}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(stats.to_json() + "\n", encoding="utf-8")
    feats.to_parquet(FEATURES_PATH, index=False)
    print(f"[ok] {FEATURES_PATH} ({len(feats):,} satır, {len(FEATURES)} ana özellik)")
    print(f"[ok] {STATS_PATH}")


if __name__ == "__main__":
    main()
