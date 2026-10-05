"""Kart geçmişi deposu: servis, bir işlemin özelliklerini kartın geçmişinden hesaplar.

Özellikler eğitimdeki **aynı** `build_features` fonksiyonuyla, kartın geçmişi + yeni işlem
üzerinde hesaplanır; servis için ayrı bir özellik mantığı yazılmaz. Bedeli, her istekte kartın
tüm geçmişinin yeniden işlenmesidir (kart başına ~2.000 işlem, ~10 ms). Ölçeklenmesi gerekirse
yalnızca son 7 günü ve kümülatif özetleri tutan bir yapıya geçilebilir.
"""

from __future__ import annotations

import pandas as pd

from card_fraud_detection.config import CARD_COL, TIME_COL

HISTORY_COLUMNS = ["tx_id", TIME_COL, CARD_COL, "amt", "category", "merchant"]


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[HISTORY_COLUMNS].copy()
    # Kategorik sütunlar dosyadan dosyaya farklı kategori listeleri taşıyabilir; birleştirmede
    # sorun çıkmasın diye metin olarak tutulur (özellik kodu zaten metne çevirerek çalışır)
    out["category"] = out["category"].astype(str)
    out["merchant"] = out["merchant"].astype(str)
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])
    return out


class CardHistoryStore:
    """Kart numarası → o kartın işlemleri (zaman ve tx_id sırasıyla)."""

    def __init__(self, frame: pd.DataFrame | None = None):
        self._cards: dict[int, pd.DataFrame] = {}
        self._next_id = 0
        if frame is not None and len(frame):
            frame = _normalize(frame).sort_values([TIME_COL, "tx_id"], kind="stable")
            self._cards = {int(card): g.reset_index(drop=True)
                           for card, g in frame.groupby(CARD_COL, sort=False)}
            self._next_id = int(frame["tx_id"].max()) + 1

    @classmethod
    def from_transactions(cls, transactions: pd.DataFrame,
                          until: str | pd.Timestamp | None = None) -> CardHistoryStore:
        """`until` verilirse yalnızca o andan önceki işlemler yüklenir."""
        if until is not None:
            transactions = transactions[transactions[TIME_COL] < pd.Timestamp(until)]
        return cls(transactions)

    def history(self, card: int) -> pd.DataFrame:
        hist = self._cards.get(int(card))
        return hist if hist is not None else pd.DataFrame(columns=HISTORY_COLUMNS)

    def with_new(self, tx: dict) -> tuple[pd.DataFrame, int]:
        """Kartın geçmişi + yeni işlem (yeni işleme sıradaki tx_id verilir; aynı saniyedeki
        önceki işlemlerin ardından gelir). Depo değişmez."""
        new = _normalize(pd.DataFrame([{**tx, "tx_id": self._next_id}]))
        hist = self.history(tx[CARD_COL])
        frame = new if hist.empty else pd.concat([hist, new], ignore_index=True)
        return frame, len(frame) - 1

    def add(self, tx: dict) -> int:
        """İşlemi kartın geçmişine ekler ve verdiği tx_id'yi döndürür."""
        frame, _ = self.with_new(tx)
        self._cards[int(tx[CARD_COL])] = frame
        tx_id = self._next_id
        self._next_id += 1
        return tx_id

    @property
    def n_cards(self) -> int:
        return len(self._cards)

    @property
    def n_transactions(self) -> int:
        return sum(len(g) for g in self._cards.values())
