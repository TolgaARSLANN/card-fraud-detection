"""Kart geçmişi deposu: servis, bir işlemin özelliklerini kartın geçmişinden hesaplar.

Özellikler eğitimdeki **aynı** `build_features` fonksiyonuyla, kartın geçmişi + yeni işlem
üzerinde hesaplanır; servis için ayrı bir özellik mantığı yazılmaz. Bedeli, her istekte kartın
tüm geçmişinin yeniden işlenmesidir (kart başına ~2.000 işlem, ~10 ms). Ölçeklenmesi gerekirse
yalnızca son 7 günü ve kümülatif özetleri tutan bir yapıya geçilebilir.
"""

from __future__ import annotations

from collections import deque

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

    def snapshot(self) -> tuple[dict, int]:
        """Anlık durum. `add` kart tablolarını yerinde değiştirmez, yenisiyle değiştirir; bu
        yüzden sözlüğün sığ kopyası yeterlidir (veri kopyalanmaz)."""
        return dict(self._cards), self._next_id

    def restore(self, state: tuple[dict, int]) -> None:
        cards, next_id = state
        self._cards, self._next_id = dict(cards), next_id

    def has_card(self, card: int) -> bool:
        return int(card) in self._cards

    def cards(self) -> list[int]:
        return sorted(self._cards)

    @property
    def n_cards(self) -> int:
        return len(self._cards)

    @property
    def n_transactions(self) -> int:
        return sum(len(g) for g in self._cards.values())


class OverlayHistoryStore(CardHistoryStore):
    """Paylaşılan, salt-okunur bir taban geçmiş + yalnızca bu katmanda eklenen işlemler.

    Demo modunda her panel oturumu bir katman kullanır: taban (yüklenmiş geçmiş) oturum başına
    kopyalanmaz, oturum yalnızca kendi eklediklerini tutar. Eklenen kayıtlar kart başına ve
    toplamda sınırlıdır; sınır aşılınca en eski *eklenen* kayıt düşer. (Tabana dokunulmaz:
    kırpılsaydı kartın geçmiş sayısı ve ortalaması gibi özellikler raporlanandan farklı
    hesaplanırdı. Düşme yalnızca bir güvenlik ağıdır; panelin akış sınırı bunun altındadır.)
    """

    def __init__(self, base: CardHistoryStore, max_per_card: int, max_total: int):
        self.base, self.max_per_card, self.max_total = base, max_per_card, max_total
        self._added: dict[int, pd.DataFrame] = {}
        self._order: deque[int] = deque()           # eklenme sırası (kart), en eskisi solda
        self._next_id = base._next_id

    def history(self, card: int) -> pd.DataFrame:
        hist, added = self.base.history(card), self._added.get(int(card))
        if added is None:
            return hist
        return added if hist.empty else pd.concat([hist, added], ignore_index=True)

    def _drop_oldest(self, card: int) -> None:
        rows = self._added[card].iloc[1:].reset_index(drop=True)
        if rows.empty:
            del self._added[card]
        else:
            self._added[card] = rows

    def add(self, tx: dict) -> int:
        card, tx_id = int(tx[CARD_COL]), self._next_id
        new = _normalize(pd.DataFrame([{**tx, "tx_id": tx_id}]))
        prev = self._added.get(card)
        self._added[card] = new if prev is None else pd.concat([prev, new], ignore_index=True)
        self._order.append(card)
        self._next_id += 1
        if len(self._added[card]) > self.max_per_card:
            self._order.remove(card)                    # o kartın en eski eklenen kaydı
            self._drop_oldest(card)
        while len(self._order) > self.max_total:
            self._drop_oldest(self._order.popleft())
        return tx_id

    def snapshot(self):
        raise NotImplementedError("Katman anlık görüntü desteklemez; yeni katman oluşturun")

    restore = snapshot

    def has_card(self, card: int) -> bool:
        return self.base.has_card(card) or int(card) in self._added

    def cards(self) -> list[int]:
        return sorted(set(self.base.cards()) | set(self._added))

    @property
    def n_added(self) -> int:
        return len(self._order)

    @property
    def n_cards(self) -> int:
        return self.base.n_cards + sum(not self.base.has_card(c) for c in self._added)

    @property
    def n_transactions(self) -> int:
        return self.base.n_transactions + self.n_added
