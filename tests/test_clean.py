import pandas as pd
import pytest

from card_fraud_detection.config import PII_COLUMNS, TARGET, TIME_COL
from card_fraud_detection.data.clean import clean, validate


def _raw(rows):
    """(zaman, kart, tutar, etiket) satırlarından ham dosya biçiminde tablo üretir."""
    df = pd.DataFrame(rows, columns=[TIME_COL, "cc_num", "amt", TARGET])
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    n = len(df)
    df = df.assign(
        merchant=["fraud_Kutch"] * n, category="grocery_pos", first="Ad", last="Soyad",
        gender="F", street="Sokak", city="Sehir", state="NC", zip="00123", lat=36.0,
        long=-81.0, city_pop=1000, job="Ogretmen", dob=pd.Timestamp("1980-01-01"),
        trans_num=[f"t{i}" for i in range(n)], unix_time=0, merch_lat=36.1, merch_long=-81.1,
    )
    df[TARGET] = df[TARGET].astype("int8")
    return df


@pytest.fixture
def frames():
    # Dosya içinde sırasız satırlar ve aynı saniyede iki kart var
    train = _raw([
        ("2020-03-31 23:59:59", 2, 10.0, 0),
        ("2019-01-01 00:00:00", 2, 5.0, 0),
        ("2019-01-01 00:00:00", 1, 7.0, 1),
        ("2020-04-01 00:00:00", 1, 9.0, 0),
        ("2020-06-21 12:13:37", 1, 3.0, 0),
    ])
    test = _raw([("2020-12-31 23:59:34", 2, 4.0, 1), ("2020-06-21 12:14:25", 1, 8.0, 0)])
    return {"train": train, "test": test}


def test_clean_splits_and_order(frames):
    df = clean(frames)
    validate(df)

    assert len(df) == 7                                        # satır kaybı yok
    assert df[TIME_COL].is_monotonic_increasing
    assert df["tx_id"].tolist() == list(range(7))
    # Aynı saniyede eşitlik kart numarasıyla bozulur
    assert df["cc_num"].iloc[:2].tolist() == [1, 2]
    assert df["split"].astype(str).tolist() == [
        "train", "train", "train", "valid", "valid", "test", "test",
    ]
    for _, g in df.groupby("cc_num"):                          # kart içinde zaman sıralı
        assert g[TIME_COL].is_monotonic_increasing


def test_clean_drops_pii_and_prefix(frames):
    df = clean(frames)
    assert not set(PII_COLUMNS + ["unix_time"]) & set(df.columns)
    assert (df["merchant"].astype(str) == "Kutch").all()
    assert df[TARGET].sum() == 2                               # etiketler korunuyor


def test_clean_rejects_split_not_matching_files(frames):
    # Eğitim dosyasına test sınırından sonra bir işlem sızarsa bölme dosyayla örtüşmez
    frames["train"] = pd.concat([frames["train"], _raw([("2020-07-01", 3, 1.0, 0)])])
    with pytest.raises(ValueError, match="örtüşmüyor"):
        clean(frames)


def test_validate_catches_problems(frames):
    df = clean(frames)
    bad = df.iloc[::-1].reset_index(drop=True)                 # sıra bozuk
    with pytest.raises(ValueError, match="sıralı değil"):
        validate(bad)

    bad = df.copy()
    bad["split"] = bad["split"].cat.set_categories(["train", "valid", "test"])
    bad.loc[bad.index[-1], "split"] = "valid"                  # valid, testle çakışır
    with pytest.raises(ValueError, match="çakışıyor"):
        validate(bad)
