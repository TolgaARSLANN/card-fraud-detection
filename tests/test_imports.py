"""Servis ve panel, eğitim kütüphaneleri kurulu olmadan da açılmalı.

API (`.[api]`) ve panel (`.[ui]`) kurulumlarında matplotlib, xgboost, imbalanced-learn ve optuna
yoktur. Test, bu kütüphaneleri "kurulu değil" gibi engeller (içe aktarma ImportError verir) ve
modülün yine de yüklendiğini doğrular. Her modül ayrı bir süreçte denenir ki diğer testlerin
yüklediği modüller sonucu etkilemesin. (SHAP, matplotlib kuruluysa onu kendiliğinden yükler;
kurulu değilse onsuz çalışır. Bu yüzden "yüklendi mi" değil "onsuz açılıyor mu" sınanır.)
"""

import subprocess
import sys

import pytest

TRAINING_ONLY = ["matplotlib", "xgboost", "imblearn", "optuna", "seaborn"]
CASES = {
    "card_fraud_detection.serving.app": TRAINING_ONLY,
    # Panel modelle konuşmaz (API'ye sorar); SHAP da gerekmez
    "card_fraud_detection.ui.client": [*TRAINING_ONLY, "shap"],
    "card_fraud_detection.ui.logic": [*TRAINING_ONLY, "shap"],
    "card_fraud_detection.ui.theme": [*TRAINING_ONLY, "shap"],
    "card_fraud_detection.ui.prepare": [*TRAINING_ONLY, "shap"],
}


@pytest.mark.parametrize("module", CASES)
def test_module_imports_without_training_libraries(module):
    # sys.modules[ad] = None → "import ad" ImportError verir (paket kurulu değilmiş gibi)
    code = (f"import importlib, sys\n"
            f"for name in {CASES[module]!r}: sys.modules[name] = None\n"
            f"importlib.import_module({module!r})\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]


def test_blocking_actually_breaks_a_training_module():
    """Engelleme yöntemi gerçekten işliyor mu: eğitim modülü matplotlib olmadan açılmamalı."""
    code = ("import importlib, sys\nsys.modules['matplotlib'] = None\n"
            "importlib.import_module('card_fraud_detection.models.threshold')\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode != 0 and "matplotlib" in out.stderr
