"""Ham veri için kalite raporu üretir.

Kullanım:
    python -m sahtekarlik.data.quality      # -> reports/veri_kalite_raporu.md

Kontroller: kapsam ve sınıf oranı, eksik değer, tekrarlar, değer aralıkları, zaman damgası
tutarlılığı (unix_time), kart bazında sabit kalması gereken alanlar, kart başına işlem sayısı,
dolandırıcılık patlamaları, aylık hacim ve oran, eğitim/test örtüşmesi.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from sahtekarlik.config import CARD_COL, RAW_DIR, RAW_FILES, REPORTS_DIR, TARGET, TIME_COL
from sahtekarlik.reporting import to_markdown as _md

REPORT_PATH = REPORTS_DIR / "veri_kalite_raporu.md"

# Aynı kartın her işleminde aynı olması beklenen müşteri alanları
CARD_ATTRIBUTES = ["first", "last", "gender", "street", "city", "state", "zip", "lat", "long",
                   "city_pop", "job", "dob"]


def load_raw() -> dict[str, pd.DataFrame]:
    paths = {split: RAW_DIR / f"{split}.parquet" for split in RAW_FILES}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Eksik dosya: {missing}. Önce `make data` çalıştırın.")
    return {split: pd.read_parquet(p) for split, p in paths.items()}


def coverage(df: pd.DataFrame) -> dict:
    return {
        "başlangıç": df[TIME_COL].min(),
        "bitiş": df[TIME_COL].max(),
        "işlem": len(df),
        "dolandırıcılık": int(df[TARGET].sum()),
        "oran (%)": 100 * df[TARGET].mean(),
        "kart": df[CARD_COL].nunique(),
        "satıcı": df["merchant"].nunique(),
        "kategori": df["category"].nunique(),
    }


def duplicates(df: pd.DataFrame) -> dict:
    return {
        "tam satır tekrarı": int(df.duplicated().sum()),
        "trans_num tekrarı": int(df["trans_num"].duplicated().sum()),
        "aynı kart + zaman + tutar": int(df.duplicated([CARD_COL, TIME_COL, "amt"]).sum()),
        "aynı kart + zaman": int(df.duplicated([CARD_COL, TIME_COL]).sum()),
    }


def value_ranges(df: pd.DataFrame) -> dict:
    age = (df[TIME_COL] - df["dob"]).dt.days / 365.25
    return {
        "tutar ≤ 0": int((df["amt"] <= 0).sum()),
        "tutar min": df["amt"].min(),
        "tutar medyan": df["amt"].median(),
        "tutar maks": df["amt"].max(),
        "yaş min": age.min(),
        "yaş maks": age.max(),
        "geçersiz koordinat": int(
            (~df["lat"].between(-90, 90) | ~df["long"].between(-180, 180)
             | ~df["merch_lat"].between(-90, 90) | ~df["merch_long"].between(-180, 180)).sum()
        ),
        "'fraud_' önekli satıcı (%)": 100 * df["merchant"].str.startswith("fraud_").mean(),
    }


def unix_time_offset(df: pd.DataFrame) -> pd.Series:
    """`unix_time` ile tarih sütunu arasındaki fark (gün). Sabit değilse biri güvenilmezdir."""
    as_dt = pd.to_datetime(df["unix_time"], unit="s")
    return ((df[TIME_COL] - as_dt).dt.total_seconds() / 86400).round(3)


def inconsistent_card_attributes(df: pd.DataFrame) -> pd.Series:
    """Her müşteri alanı için, birden fazla farklı değer taşıyan kart sayısı."""
    cols = [c for c in CARD_ATTRIBUTES if c in df]
    return (df.groupby(CARD_COL)[cols].nunique() > 1).sum()


def fraud_bursts(df: pd.DataFrame) -> pd.DataFrame:
    """Dolandırıcılık görülen her kart için: dolandırıcılık sayısı, ilk ve son dolandırıcılık
    arasındaki süre ve son dolandırıcılıktan sonra kartta normal işlem olup olmadığı."""
    fraud = df[df[TARGET] == 1]
    g = fraud.groupby(CARD_COL)[TIME_COL]
    out = pd.DataFrame({
        "n_fraud": g.size(),
        "sure_gun": (g.max() - g.min()).dt.total_seconds() / 86400,
        "son_fraud": g.max(),
    })
    last_any = df.groupby(CARD_COL)[TIME_COL].max().reindex(out.index)
    out["sonrasinda_islem_var"] = last_any > out["son_fraud"]
    return out.drop(columns="son_fraud")


def overlap(train: pd.DataFrame, test: pd.DataFrame, col: str) -> dict:
    a, b = set(train[col].unique()), set(test[col].unique())
    return {
        "eğitimde": len(a),
        "testte": len(b),
        "ortak": len(a & b),
        "yalnızca testte": len(b - a),
        "testin eğitimde görülen oranı (%)": 100 * len(a & b) / max(len(b), 1),
    }


def build_report(frames: dict[str, pd.DataFrame]) -> str:
    train, test = frames["train"], frames["test"]
    both = pd.concat(frames, names=["split"]).reset_index(level=0)
    out: list[str] = [
        "# Veri Kalite Raporu",
        "",
        f"_Oluşturulma: {date.today().isoformat()} · Kaynak: `data/raw/{{train,test}}.parquet` "
        "(Kaggle, Sparkov) · Üreten: `python -m sahtekarlik.data.quality`_",
        "",
    ]

    # 1. Kapsam
    # from_dict(orient="index") sütun tiplerini korur; .T tüm tabloyu object'e çevirirdi
    cov = pd.DataFrame.from_dict({s: coverage(df) for s, df in frames.items()}, orient="index")
    cov.index.name = "dosya"
    gap = test[TIME_COL].min() - train[TIME_COL].max()
    out += ["## 1. Kapsam ve sınıf oranı", "", _md(cov, ".2f"), "",
            f"Eğitim dosyasının sonu ile test dosyasının başı arasındaki boşluk: {gap}.", ""]

    # 2. Eksik değer
    miss = pd.DataFrame({s: df.isna().mean() * 100 for s, df in frames.items()})
    miss = miss[miss.sum(axis=1) > 0]
    miss.index.name = "sütun (% boş)"
    out += ["## 2. Eksik değer", ""]
    out += [_md(miss, ".3f") if len(miss) else "Hiçbir sütunda boş değer yok.", ""]

    # 3. Tekrarlar
    dup = pd.DataFrame({s: duplicates(df) for s, df in frames.items()})
    dup.index.name = "kontrol"
    dup_all = duplicates(both.drop(columns="split"))
    dup["iki dosya birlikte"] = pd.Series(dup_all)
    out += ["## 3. Tekrar eden kayıtlar", "", _md(dup), ""]

    # 4. Değer aralıkları
    rng = pd.DataFrame({s: value_ranges(df) for s, df in frames.items()})
    rng.index.name = "kontrol"
    out += ["## 4. Değer aralıkları", "", _md(rng, ".2f"), ""]

    # 5. Zaman damgası tutarlılığı
    off = unix_time_offset(both)
    uniq = off.round(0).value_counts().head(5)
    uniq.index = [f"{v:.0f} gün" for v in uniq.index]
    uniq.index.name = "tarih − unix_time"
    out += ["## 5. Zaman damgası tutarlılığı", "",
            "`trans_date_trans_time` ile `unix_time` arasındaki farkın dağılımı (en sık 5 değer):",
            "", _md(uniq.rename("işlem")), ""]

    # 6. Kart bazında tutarlılık
    inc = pd.DataFrame({s: inconsistent_card_attributes(df) for s, df in frames.items()})
    inc["iki dosya birlikte"] = inconsistent_card_attributes(both)
    inc.index.name = "alan (tutarsız kart sayısı)"
    out += ["## 6. Kart bazında müşteri alanlarının tutarlılığı", "",
            "Aynı kartın her işleminde aynı olması beklenen alanlarda birden fazla değer taşıyan "
            "kart sayısı.", "", _md(inc), ""]

    # 7. Kart başına işlem
    per_card = pd.DataFrame({
        s: df.groupby(CARD_COL).size().describe(percentiles=[0.05, 0.5, 0.95])
        for s, df in frames.items()
    }).T.drop(columns="count")
    per_card.index.name = "dosya (kart başına işlem)"
    out += ["## 7. Kart başına işlem sayısı", "", _md(per_card), ""]

    # 8. Dolandırıcılık patlamaları
    rows = {}
    for s, df in {**frames, "iki dosya birlikte": both}.items():
        b = fraud_bursts(df)
        rows[s] = {
            "dolandırıcılık görülen kart": len(b),
            "kart oranı (%)": 100 * len(b) / df[CARD_COL].nunique(),
            "kart başına dolandırıcılık (medyan)": b["n_fraud"].median(),
            "kart başına dolandırıcılık (maks)": b["n_fraud"].max(),
            "ilk→son süre, gün (medyan)": b["sure_gun"].median(),
            "ilk→son süre, gün (%95)": b["sure_gun"].quantile(0.95),
            "sonrasında normal işlem olan kart (%)": 100 * b["sonrasinda_islem_var"].mean(),
        }
    bursts = pd.DataFrame(rows)
    bursts.index.name = "ölçü"
    out += ["## 8. Dolandırıcılık patlamaları", "",
            "Bir kartta dolandırıcılığın kısa bir dönemde toplanıp toplanmadığı. Kartlar "
            "dolandırıcılıktan sonra kapanmıyorsa geçmiş etiketler sızıntı riski taşır.", "",
            _md(bursts, ".2f"), ""]

    # 9. Aylık hacim ve oran
    month = both[TIME_COL].dt.to_period("M")
    monthly = both.groupby(month).agg(işlem=(TARGET, "size"), oran=(TARGET, "mean"))
    monthly["oran"] *= 100
    monthly.index = monthly.index.astype(str)
    monthly.index.name = "ay"
    monthly = monthly.rename(columns={"oran": "dolandırıcılık (%)"})
    out += ["## 9. Aylık işlem hacmi ve dolandırıcılık oranı", "", _md(monthly, ".2f"), ""]

    # 10. Eğitim / test örtüşmesi
    ov = pd.DataFrame.from_dict(
        {c: overlap(train, test, c) for c in [CARD_COL, "merchant", "category"]}, orient="index"
    )
    ov.index.name = "alan"
    out += ["## 10. Eğitim / test örtüşmesi", "", _md(ov, ".1f"), ""]

    # 11. Sütun kardinalitesi
    card = both.drop(columns="split").nunique().rename("farklı değer")
    card.index.name = "sütun"
    out += ["## 11. Sütunların farklı değer sayısı", "", _md(card), ""]

    return "\n".join(out)


def main() -> None:
    report = build_report(load_raw())
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    print(f"[ok] {REPORT_PATH}")


if __name__ == "__main__":
    main()
