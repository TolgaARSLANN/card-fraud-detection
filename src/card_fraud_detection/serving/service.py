"""Skorlama servisi: işlem → olasılık, beklenen kayıp, karar, risk seviyesi, ilk 3 neden.

Model, kalibrasyon ve karar kuralı Faz 3.3'te kaydedildiği gibi kullanılır (`models/`).
Özellikler eğitimdeki aynı kodla (`build_features`) kart geçmişi üzerinde hesaplanır.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from card_fraud_detection.config import MODELS_DIR, REVIEW_COST, TEST_START
from card_fraud_detection.data.clean import OUT_PATH as TRANSACTIONS_PATH
from card_fraud_detection.features.build import FEATURES, FeatureStats, build_features
from card_fraud_detection.models.explain import (
    explainer,
    group_contributions,
    shap_values,
    top_reasons,
)
from card_fraud_detection.models.threshold import Calibrator
from card_fraud_detection.serving.history import CardHistoryStore

# Risk seviyesi (kalibre olasılığa göre). Not: önsel düzeltme kalibrasyonu %0,1-1 bölgesinde
# riski olduğundan düşük gösterir (Faz 3.3); karar olasılığa değil beklenen kayba dayanır.
RISK_LEVELS = [(0.20, "yüksek"), (0.01, "orta"), (0.0, "düşük")]


def risk_level(p: float) -> str:
    return next(name for limit, name in RISK_LEVELS if p >= limit)


@dataclass
class Decision:
    rule: str
    threshold: float | None
    review_cost: float

    def alert(self, p: float, amt: float) -> bool:
        if self.rule == "beklenen maliyet":
            return p * amt >= self.review_cost
        if self.rule == "sabit eşik":
            return p >= self.threshold
        raise ValueError(f"Kural tek tek işlemde uygulanamaz: {self.rule}")


class ScoringService:
    def __init__(self, model, calibrator: Calibrator, decision: Decision, stats: FeatureStats,
                 store: CardHistoryStore, features: list[str] = FEATURES,
                 metadata: dict | None = None):
        self.model, self.calibrator, self.decision = model, calibrator, decision
        self.stats, self.store, self.features = stats, store, features
        self.metadata = metadata or {}
        self._explainer = explainer(model)
        self._initial = store.snapshot()
        self.transactions: pd.DataFrame | None = None     # load() ile yüklenirse dolar
        # FastAPI eşzamanlı istekleri iş parçacıklarında işler. Skorlama + geçmişe ekleme ve
        # sıfırlama tek kilit altında: aksi hâlde aynı karta eşzamanlı gelen işlemler geçmişte
        # kaybolur ve işlem numaraları tekrarlanır. Bedeli: istekler sırayla işlenir (~50 ms).
        self._lock = threading.RLock()

    def reset(self, until: str | pd.Timestamp | None = None) -> None:
        """Kart geçmişini başlangıç durumuna döndürür. `until` verilirse geçmiş, o ana kadarki
        tüm işlemlerle yeniden kurulur (panelde akışı istenen andan başlatmak için; atlanan
        işlemler skorlanmaz ama geçmişe girer, özellikler tutarlı kalır)."""
        with self._lock:
            if until is None:
                self.store.restore(self._initial)
                return
            if self.transactions is None:
                raise ValueError("Bu servis işlem dosyasıyla yüklenmedi; `until` kullanılamaz")
            rebuilt = CardHistoryStore.from_transactions(self.transactions, until)
            self.store.restore(rebuilt.snapshot())

    @classmethod
    def load(cls, models_dir: Path = MODELS_DIR, transactions_path: Path = TRANSACTIONS_PATH,
             history_until: str | None = TEST_START) -> ScoringService:
        bundle = joblib.load(models_dir / "model.joblib")
        decision = json.loads((models_dir / "decision.json").read_text(encoding="utf-8"))
        stats = FeatureStats.from_json((models_dir / "feature_stats.json").read_text("utf-8"))
        meta_path = models_dir / "metadata.json"
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        tx = pd.read_parquet(transactions_path, columns=[
            "tx_id", "trans_date_trans_time", "cc_num", "amt", "category", "merchant"])
        service = cls(bundle["model"], Calibrator.from_state(bundle["calibrator"]),
                      Decision(decision["kural"], decision.get("esik"),
                               decision.get("inceleme_ucreti", REVIEW_COST)),
                      stats, CardHistoryStore.from_transactions(tx, history_until),
                      bundle["features"], {**metadata, "karar": decision})
        service.transactions = tx
        return service

    def features_for(self, tx: dict) -> pd.DataFrame:
        """Yeni işlemin özellik satırı (1 satırlık tablo), kart geçmişiyle birlikte hesaplanır."""
        with self._lock:
            frame, pos = self.store.with_new(tx)
        feats = build_features(frame, self.stats)
        return feats.iloc[[pos]]

    def score(self, tx: dict, save: bool = True) -> dict:
        # Özellik hesabı ile geçmişe ekleme arasında başka bir işlem araya girmemeli
        with self._lock:
            row = self.features_for(tx)
            tx_id = self.store.add(tx) if save else None
        x = row[self.features]
        raw = float(self.model.predict_proba(x)[:, 1][0])
        p = float(self.calibrator.transform(np.array([raw]))[0])
        alert = self.decision.alert(p, float(tx["amt"]))
        reasons = []
        if alert:
            contrib = group_contributions(shap_values(self._explainer, x)).iloc[0]
            reasons = top_reasons(contrib, row.iloc[0])
        return {"islem_no": tx_id, "olasilik": p, "beklenen_kayip": p * float(tx["amt"]),
                "karar": "alarm" if alert else "onay", "risk_seviyesi": risk_level(p),
                "nedenler": reasons}
