"""Kaggle'dan Sparkov kart işlemi veri setini indirir ve parquet'e çevirir.

Kullanım:
    python -m sahtekarlik.data.download           # dosyalar varsa atlar
    python -m sahtekarlik.data.download --force

Çıktı: data/raw/train.parquet ve data/raw/test.parquet. Veri seti herkese açık olduğu için
kagglehub çoğu zaman belirteç (token) olmadan indirir. İstenirse ~/.kaggle/kaggle.json
dosyası kullanıcı tarafından yerleştirilir.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sahtekarlik.config import CARD_COL, KAGGLE_DATASET, RAW_DIR, RAW_FILES, TARGET, TIME_COL


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Ham CSV'yi okur: baştaki isimsiz indeks sütununu atar, tipleri düzeltir."""
    df = pd.read_csv(path, dtype={CARD_COL: "int64", "zip": "string"})
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    df["dob"] = pd.to_datetime(df["dob"])
    df[TARGET] = df[TARGET].astype("int8")
    return df


def download(force: bool = False) -> dict[str, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = {split: RAW_DIR / f"{split}.parquet" for split in RAW_FILES}
    if not force and all(p.exists() for p in out.values()):
        print("Ham veri zaten var, atlanıyor (yeniden indirmek için --force).")
        return out

    import kagglehub  # yalnızca indirme sırasında gerekli

    src = Path(kagglehub.dataset_download(KAGGLE_DATASET))
    for split, name in RAW_FILES.items():
        df = read_raw_csv(src / name)
        df.to_parquet(out[split], index=False)
        print(f"{split}: {len(df):,} satır, dolandırıcılık oranı %{100 * df[TARGET].mean():.2f}"
              f" → {out[split]}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="dosyalar varsa da yeniden indir")
    download(force=parser.parse_args().force)


if __name__ == "__main__":
    main()
