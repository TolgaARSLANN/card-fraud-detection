"""Ham iki dosyayı tek, temiz ve zamana göre bölünmüş bir tabloya çevirir.

Kullanım:
    python -m card_fraud_detection.data.clean      # -> data/processed/transactions.parquet

Adımlar (gerekçeler: reports/veri_kalite_raporu.md ve docs/YOL_HARITASI.md §1.1):
1. fraudTrain ve fraudTest birleştirilir. Aralarında boşluk olmadığı için kart hızı özellikleri
   birleşik tablo üzerinde hesaplanabilir.
2. Kişisel veri sütunları (ad, soyad, sokak, işlem no) ve `unix_time` atılır.
3. Satıcı adlarındaki simülatör kalıntısı `fraud_` öneki silinir.
4. Satırlar zamana göre (eşitlikte kart numarasına göre) kararlı biçimde sıralanır ve
   sıraya göre `tx_id` verilir.
5. `split` sütunu eklenir: train / valid / test (sınırlar config.py'de).
Sonuç `validate` ile doğrulanır; kurallardan biri bozulursa dosya yazılmaz.
"""

from __future__ import annotations

import pandas as pd

from card_fraud_detection.config import (
    CARD_COL,
    PII_COLUMNS,
    PROCESSED_DIR,
    RAW_DIR,
    RAW_FILES,
    REDUNDANT_COLUMNS,
    SPLITS,
    TARGET,
    TEST_START,
    TIME_COL,
    VALID_START,
)

OUT_PATH = PROCESSED_DIR / "transactions.parquet"
MERCHANT_PREFIX = "fraud_"
CATEGORICAL_COLUMNS = ["merchant", "category", "gender", "city", "state", "job"]


def assign_split(times: pd.Series) -> pd.Series:
    split = pd.Series("train", index=times.index)
    split[times >= pd.Timestamp(VALID_START)] = "valid"
    split[times >= pd.Timestamp(TEST_START)] = "test"
    return pd.Categorical(split, categories=SPLITS, ordered=True)


def clean(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat([frames[s].assign(_source=s) for s in RAW_FILES], ignore_index=True)
    df = df.drop(columns=[c for c in PII_COLUMNS + REDUNDANT_COLUMNS if c in df])
    df["merchant"] = df["merchant"].str.removeprefix(MERCHANT_PREFIX)
    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    df = df.sort_values([TIME_COL, CARD_COL], kind="stable", ignore_index=True)
    df.insert(0, "tx_id", pd.RangeIndex(len(df)))
    df["split"] = assign_split(df[TIME_COL])

    # Zaman sınırı dosya sınırıyla örtüşmeli: test = fraudTest'in tamamı ve yalnızca o
    mismatch = (df["split"] == "test") != (df["_source"] == "test")
    if mismatch.any():
        raise ValueError(f"TEST_START dosya sınırıyla örtüşmüyor: {int(mismatch.sum())} satır")
    return df.drop(columns="_source")


def validate(df: pd.DataFrame) -> None:
    """Temiz tablonun sağlaması gereken kurallar; biri bozulursa ValueError fırlatır."""
    problems = []
    leftover = [c for c in PII_COLUMNS + REDUNDANT_COLUMNS if c in df]
    if leftover:
        problems.append(f"atılması gereken sütunlar duruyor: {leftover}")
    if df["merchant"].astype(str).str.startswith(MERCHANT_PREFIX).any():
        problems.append(f"'{MERCHANT_PREFIX}' önekli satıcı kaldı")
    # Genel sıra, her kartın kendi içinde de zaman sıralı olmasını garanti eder
    if not df[TIME_COL].is_monotonic_increasing:
        problems.append("tablo zamana göre sıralı değil")
    if not df["tx_id"].is_unique:
        problems.append("tx_id tekrar ediyor")
    if df.isna().any().any():
        problems.append(f"boş değer var: {df.columns[df.isna().any()].tolist()}")

    # Bölmeler zamanda çakışmamalı ve sırayla gelmeli: train < valid < test
    bounds = df.groupby("split", observed=True)[TIME_COL].agg(["min", "max"])
    present = [s for s in SPLITS if s in bounds.index]
    if present != SPLITS:
        problems.append(f"eksik bölme: {sorted(set(SPLITS) - set(present))}")
    for a, b in zip(present, present[1:], strict=False):
        if bounds.loc[a, "max"] >= bounds.loc[b, "min"]:
            problems.append(f"{a} ve {b} zamanda çakışıyor")
    if problems:
        raise ValueError("Temiz veri doğrulanamadı:\n- " + "\n- ".join(problems))


def summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("split", observed=True)
    return pd.DataFrame({
        "başlangıç": g[TIME_COL].min(),
        "bitiş": g[TIME_COL].max(),
        "işlem": g.size(),
        "dolandırıcılık": g[TARGET].sum(),
        "oran (%)": (100 * g[TARGET].mean()).round(3),
        "kart": g[CARD_COL].nunique(),
    })


def main() -> None:
    frames = {s: pd.read_parquet(RAW_DIR / f"{s}.parquet") for s in RAW_FILES}
    df = clean(frames)
    validate(df)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(summary(df).to_string())
    print(f"[ok] {OUT_PATH} ({len(df):,} satır, {df.shape[1]} sütun)")


if __name__ == "__main__":
    main()
