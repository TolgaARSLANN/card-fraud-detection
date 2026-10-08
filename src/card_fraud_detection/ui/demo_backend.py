"""Demo modunda panelin arka ucu: oturumlar birbirinden yalıtılmış, bellek sınırlı.

Herkese açık demoda panel API'ye gitmez; skorlama aynı süreçte yapılır:
- Model, açıklayıcı ve yüklenmiş geçmiş TEK kopyadır (panel `st.cache_resource` ile paylaşır).
- Her oturumun yalnızca kendi eklediği işlemleri tutan bir katmanı vardır
  (`OverlayHistoryStore`); bir ziyaretçinin akışı ötekinin özelliklerini etkilemez.
- Katmanlar paylaşılan bir oturum kaydında durur: en fazla `max_sessions` oturum, işlem
  yapmayan oturum `ttl` saniye sonra silinir. Toplam bellek ≈ oturum sınırı × oturum başına
  kayıt sınırı; ziyaretçi sayısıyla sınırsız büyümez.

Bu modül Streamlit'e bağlı değildir (testlerde doğrudan kullanılır); servis kodunu (SHAP)
içe aktardığı için yalnızca demo modunda yüklenir.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from card_fraud_detection.config import (
    DEMO_ADDED_PER_CARD,
    DEMO_ADDED_TOTAL,
    DEMO_MAX_SESSIONS,
    DEMO_SESSION_TTL,
    DEMO_STREAM_LIMIT,
    TIME_COL,
)
from card_fraud_detection.serving.history import CardHistoryStore, OverlayHistoryStore
from card_fraud_detection.serving.service import ScoringService
from card_fraud_detection.ui.client import ApiError

# Demo'da serbest başlangıç anı yerine sabit başlangıçlar: her birinin geçmişi bir kez kurulur
# ve tüm oturumlarca paylaşılır (None: test dönemi başı, yani servisin yüklü geçmişi).
PRESETS: dict[str, str | None] = {
    "Test dönemi başı · 21 Haziran 2020": None,
    "1 Temmuz 2020 gecesi · 22:00": "2020-07-01 22:00",
    "15 Ağustos 2020 gecesi · 22:00": "2020-08-15 22:00",
}
# Ziyaretçi ayrılınca kaydı bu kadar süredir boştaysa yer açmak için silinebilir
MIN_IDLE_TO_EVICT = 120.0


class DemoBusy(ApiError):
    """Oturum kaydı dolu: tüm oturumlar etkin (yeni ziyaretçi biraz sonra denemeli)."""


class StreamLimitReached(ApiError):
    pass


@dataclass
class DemoSession:
    store: OverlayHistoryStore
    start: str
    cursor: int = 0
    results: list = field(default_factory=list)
    scored: int = 0                    # oturumun toplam skorladığı akış işlemi (sıfırlanmaz)
    last_seen: float = 0.0


class SharedBases:
    """Başlangıçların taban geçmişleri: tembel kurulur, tek kopya, iş parçacığı güvenli.

    Bir başlangıç, yüklenmiş geçmişin tam kopyası değil, onun üstünde sınırsız bir katmandır:
    yalnızca yüklenmiş geçmişte olmayan ve o andan önceki işlemleri tutar. Her başlangıç kendi
    kilidiyle yalnızca bir kez kurulur; katman tamamen kurulduktan sonra paylaşıma girer (aynı
    anda seçen ikinci oturum bekler, çift kurulum ya da yarım katman olmaz)."""

    def __init__(self, service: ScoringService, presets: dict[str, str | None] = PRESETS):
        self.service, self.presets = service, presets
        self._bases: dict[str, CardHistoryStore] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self.builds = 0                                 # kaç katman kuruldu (test ve ölçüm)

    @property
    def default(self) -> str:
        return next(iter(self.presets))

    def __call__(self, key: str) -> CardHistoryStore:
        until = self.presets[key]
        if until is None:
            return self.service.store
        if (ready := self._bases.get(key)) is not None:
            return ready
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            if key not in self._bases:
                self._bases[key] = self._build(until)
                self.builds += 1
            return self._bases[key]

    def build_all(self, release: bool = True) -> None:
        """Tüm başlangıçları şimdi kurar. `release`: ardından servisin ham işlem kopyasını
        (`service.transactions`, ~51 MB) bırakır; demo'da başka bir şey onu kullanmaz."""
        for key in self.presets:
            self(key)
        if release:
            self.service.transactions = None

    def _build(self, until: str) -> OverlayHistoryStore:
        base, tx = self.service.store, self.service.transactions
        loaded = np.concatenate([base.history(c)["tx_id"].to_numpy() for c in base.cards()])
        rows = tx[(tx[TIME_COL] < pd.Timestamp(until)) & ~tx["tx_id"].isin(loaded)]
        return OverlayHistoryStore.layered(base, rows)


class SessionRegistry:
    def __init__(self, bases: SharedBases,
                 max_sessions: int = DEMO_MAX_SESSIONS, ttl: float = DEMO_SESSION_TTL,
                 max_per_card: int = DEMO_ADDED_PER_CARD, max_total: int = DEMO_ADDED_TOTAL,
                 clock: Callable[[], float] = time.monotonic):
        self.bases, self.max_sessions, self.ttl, self.clock = bases, max_sessions, ttl, clock
        self.max_per_card, self.max_total = max_per_card, max_total
        self._sessions: OrderedDict[str, DemoSession] = OrderedDict()
        self._lock = threading.Lock()

    def new_store(self, start: str) -> OverlayHistoryStore:
        return OverlayHistoryStore(self.bases(start), self.max_per_card, self.max_total)

    def _sweep(self, now: float) -> None:
        for sid in [s for s, v in self._sessions.items() if now - v.last_seen > self.ttl]:
            del self._sessions[sid]

    def session(self, sid: str) -> tuple[DemoSession, bool]:
        """Oturumun durumu ve yeni mi oluşturulduğu. Kayıt doluysa en uzun süredir boştaki oturum
        yeterince boşsa silinir; değilse DemoBusy."""
        now = self.clock()
        with self._lock:
            self._sweep(now)
            if sid in self._sessions:
                state = self._sessions.pop(sid)
                state.last_seen = now
                self._sessions[sid] = state           # en sona: en son etkin
                return state, False
            if len(self._sessions) >= self.max_sessions:
                oldest_sid, oldest = next(iter(self._sessions.items()))
                if now - oldest.last_seen < MIN_IDLE_TO_EVICT:
                    raise DemoBusy("Demo şu an yoğun; birkaç dakika sonra yeniden deneyin.")
                del self._sessions[oldest_sid]
            start = self.bases.default
            state = DemoSession(self.new_store(start), start, last_seen=now)
            self._sessions[sid] = state
            return state, True

    @property
    def n_sessions(self) -> int:
        return len(self._sessions)


class DemoBackend:
    """Panelin kullandığı `ApiClient` arayüzü (health / score / reset), tek oturum için."""

    base_url = "demo (yerel skorlama)"

    def __init__(self, service: ScoringService, registry: SessionRegistry, session: DemoSession,
                 stream_limit: int = DEMO_STREAM_LIMIT):
        self.service, self.registry, self.state = service, registry, session
        self.stream_limit = stream_limit

    def health(self) -> dict:
        store = self.state.store
        return {"durum": "hazır", "kart": store.n_cards, "islem": store.n_transactions}

    def model(self) -> dict:
        return {**self.service.metadata, "ozellikler": self.service.features}

    @property
    def remaining(self) -> int:
        return max(self.stream_limit - self.state.scored, 0)

    def start(self, key: str) -> dict:
        """Oturumun geçmişini seçilen başlangıca döndürür (yalnızca bu oturum etkilenir)."""
        self.state.store = self.registry.new_store(key)
        self.state.start, self.state.cursor, self.state.results = key, 0, []
        return self.health()

    def reset(self, until=None) -> dict:
        if until is not None:
            raise ApiError("Demo modunda yalnızca sabit başlangıçlar kullanılabilir.")
        return self.start(self.state.start)

    def score(self, tx: dict, save: bool = True) -> dict:
        if not self.state.store.has_card(tx["cc_num"]):
            raise ApiError("Bu demo yalnızca veri setindeki sentetik kartları kabul eder.")
        if tx["category"] not in self.service.stats.categories:
            raise ApiError("Bilinmeyen kategori.")
        if save and self.remaining == 0:
            raise StreamLimitReached(f"Bu oturumda en fazla {self.stream_limit:,} işlem "
                                     "skorlanabilir.")
        tx = {**tx, "trans_date_trans_time": pd.Timestamp(tx["trans_date_trans_time"])}
        res = self.service.score(tx, save=save, store=self.state.store)
        if save:
            self.state.scored += 1
        return res
