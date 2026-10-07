"""Herkese açık demo için veri sütunu sözleşmesi.

Demo verisi yalnızca modele giren ve panelin ihtiyaç duyduğu sütunları içerir. Kişisel
görünümlü sütunlar (ad, adres, doğum tarihi, ...) sentetik olsalar da demo verisine hiç girmez.
Kesit henüz üretilmez (öneri: README "Demo modu" ve docs/YOL_HARITASI.md); bu modül hangi
sütunların kullanılacağını tek yerde tanımlar ve testle denetlenir.
"""

from __future__ import annotations

import pandas as pd

from card_fraud_detection.config import CARD_COL, TARGET, TIME_COL

# Servisin kart geçmişi (serving/history.py) + panelin akışı (etiket ve bölme)
DEMO_COLUMNS = ["tx_id", TIME_COL, CARD_COL, "amt", "category", "merchant", TARGET, "split"]

# Ham Kaggle verisindeki, demoya hiç girmeyecek sütunlar: kişisel görünümlü ya da gereksiz
EXCLUDED_COLUMNS = [
    "first", "last", "gender", "street", "city", "state", "zip", "lat", "long", "city_pop",
    "job", "dob", "trans_num", "unix_time", "merch_lat", "merch_long", "Unnamed: 0",
]


def demo_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Yalnızca DEMO_COLUMNS (başka hiçbir sütun taşınmaz). Eksik sütun varsa hata."""
    missing = [c for c in DEMO_COLUMNS if c not in df]
    if missing:
        raise ValueError(f"Demo için gerekli sütunlar yok: {missing}")
    return df[DEMO_COLUMNS].copy()
