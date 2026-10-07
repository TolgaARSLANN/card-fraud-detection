"""Demo verisi: kişisel görünümlü sütun yok, model ve panel için gereken her şey var."""

import pandas as pd
import pytest
from conftest import synthetic_transactions

from card_fraud_detection.config import PII_COLUMNS
from card_fraud_detection.data.demo import DEMO_COLUMNS, EXCLUDED_COLUMNS, demo_frame
from card_fraud_detection.features.build import FEATURES, build_features, fit_stats
from card_fraud_detection.serving.history import HISTORY_COLUMNS

RAW_KAGGLE = ["Unnamed: 0", "trans_date_trans_time", "cc_num", "merchant", "category", "amt",
              "first", "last", "gender", "street", "city", "state", "zip", "lat", "long",
              "city_pop", "job", "dob", "trans_num", "unix_time", "merch_lat", "merch_long",
              "is_fraud"]
PERSONAL = {"first", "last", "gender", "street", "city", "state", "zip", "lat", "long", "dob",
            "job", "trans_num"}


def raw_like(n=400):
    tx = synthetic_transactions(n=n)
    extra = {c: "x" for c in RAW_KAGGLE if c not in tx}
    return tx.assign(**extra)


def test_demo_columns_have_no_personal_data():
    assert PERSONAL.isdisjoint(DEMO_COLUMNS)
    assert set(PII_COLUMNS) <= set(EXCLUDED_COLUMNS)
    assert set(DEMO_COLUMNS).isdisjoint(EXCLUDED_COLUMNS)
    # Ham verideki her sütun ya demoya girer ya da açıkça dışarıda bırakılır
    assert set(RAW_KAGGLE) <= set(DEMO_COLUMNS) | set(EXCLUDED_COLUMNS)


def test_demo_frame_drops_everything_else():
    out = demo_frame(raw_like())
    assert list(out.columns) == DEMO_COLUMNS
    assert PERSONAL.isdisjoint(out.columns)
    with pytest.raises(ValueError, match="gerekli"):
        demo_frame(raw_like().drop(columns="merchant"))


def test_demo_columns_are_enough_for_model_and_panel():
    out = demo_frame(raw_like())
    assert set(HISTORY_COLUMNS) <= set(out.columns)                  # servis geçmişi
    feats = build_features(out, fit_stats(out))                      # modelin tüm özellikleri
    assert set(FEATURES) <= set(feats.columns) and len(feats) == len(out)
    assert {"is_fraud", "split", "tx_id"} <= set(out.columns)       # panel akışı
    assert pd.api.types.is_datetime64_any_dtype(out["trans_date_trans_time"])
