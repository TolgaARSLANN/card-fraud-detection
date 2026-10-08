"""Gece Nöbeti · Streamlit Community Cloud giriş dosyası.

Cloud'da ortam değişkeni süreç başlamadan verilemez; bu dosya demo modunu, proje kökünü,
oturum sınırını ve bellek havuzu sınırını paneli çalıştırmadan önce ayarlar. Değerler zorla
atanır (setdefault değil): Cloud'da kök seviyedeki secrets ortam değişkeni olarak gelir ve
demo modunu kapatmamalı. Paket kurulmaz, src/ yoldan okunur.
Kaynak: https://github.com/TolgaARSLANN/card-fraud-detection
"""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ["DEMO_MODE"] = "1"
os.environ["CARD_FRAUD_ROOT"] = str(ROOT)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["DEMO_MAX_SESSIONS"] = "20"        # Cloud'un kaynakları Docker'dakinden dar
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from card_fraud_detection.space.memory import limit_malloc_arenas  # noqa: E402

limit_malloc_arenas(2)
runpy.run_path(str(ROOT / "src" / "card_fraud_detection" / "ui" / "app.py"), run_name="__main__")
