"""Skoru olasılığa çeviren kalibrasyon (yalnızca numpy ve scikit-learn'e bağlı).

Ayrı bir modülde durur: servis (API) kalibratörü yükler ama eğitim kodunu, grafik
kütüphanesini ve eğitim bağımlılıklarını (xgboost, imbalanced-learn) içe aktarmaz.
Yöntemlerin karşılaştırması ve seçimi: models/threshold.py (Faz 3.3).
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

EPS = 1e-6


def prior_correction(p, beta: float):
    """Normal işlemlerin yalnızca `beta` oranı tutularak eğitilmiş modelin skorunu gerçek
    dağılıma çevirir: p' = beta·p / (beta·p − p + 1). beta = 1 ise değişiklik yoktur."""
    p = np.asarray(p, dtype=float)
    return np.clip(beta * p / (beta * p - p + 1), 0.0, 1.0)   # yuvarlama 1'i aşmasın


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p)).reshape(-1, 1)


class Calibrator:
    """Skoru olasılığa çeviren tek arayüz: fit(skor, y) ve transform(skor)."""

    METHODS = ("ham", "önsel düzeltme", "Platt", "izotonik")

    def __init__(self, method: str, beta: float = 1.0):
        if method not in self.METHODS:
            raise ValueError(f"Bilinmeyen yöntem: {method}")
        self.method, self.beta, self.model = method, beta, None

    def fit(self, score, y) -> Calibrator:
        if self.method == "Platt":
            self.model = LogisticRegression(C=1e6).fit(_logit(score), y)
        elif self.method == "izotonik":
            self.model = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(score, y)
        return self

    def transform(self, score) -> np.ndarray:
        score = np.asarray(score, dtype=float)
        if self.method == "ham":
            return score
        if self.method == "önsel düzeltme":
            return prior_correction(score, self.beta)
        if self.method == "Platt":
            return self.model.predict_proba(_logit(score))[:, 1]
        return self.model.predict(score)

    # Kaydetme: dosyaya bu sınıf değil, yalnızca sade veriler (ve scikit-learn nesnesi) yazılır.
    # Sınıfın kendisi yazılsaydı, modül betik olarak çalıştırıldığında `__main__.Calibrator`
    # adıyla kaydedilir ve başka bir yerden (ör. API) yüklenemezdi.
    def state(self) -> dict:
        return {"method": self.method, "beta": self.beta, "model": self.model}

    @classmethod
    def from_state(cls, state: dict) -> Calibrator:
        cal = cls(state["method"], state["beta"])
        cal.model = state["model"]
        return cal
