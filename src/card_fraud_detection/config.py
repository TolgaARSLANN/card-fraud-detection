"""Proje genelinde kullanılan sabitler ve yollar."""

import os
from pathlib import Path


def _project_root() -> Path:
    """Veri, model ve raporların bulunduğu proje kökü.

    Sıra: CARD_FRAUD_ROOT ortam değişkeni → kaynak ağacı (düzenlenebilir kurulum, `src/`
    düzeni) → çalışma dizini. Paket `pip install .` ile site-packages'a kurulduğunda kaynak
    ağacı yoktur; o zaman komut proje kökünden çalıştırılmalı ya da değişken verilmelidir.
    """
    if env := os.environ.get("CARD_FRAUD_ROOT"):
        return Path(env).resolve()
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "pyproject.toml").is_file():
        return source_root
    return Path.cwd().resolve()


ROOT = _project_root()
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
MODEL_PATH = MODELS_DIR / "model.joblib"          # model + kalibratör (make threshold)
DECISION_PATH = MODELS_DIR / "decision.json"      # karar kuralı

# Kaggle: "Credit Card Transactions Fraud Detection" (Sparkov simülatörü)
KAGGLE_DATASET = "kartik2112/fraud-detection"
RAW_FILES = {"train": "fraudTrain.csv", "test": "fraudTest.csv"}

TIME_COL = "trans_date_trans_time"
CARD_COL = "cc_num"
TARGET = "is_fraud"

# Kişisel veri ya da yalnızca kimlik taşıyan sütunlar; modele girmez, temizlikte atılır
PII_COLUMNS = ["first", "last", "street", "trans_num"]
# Tarih sütununun 7 yıl kaydırılmış kopyası; yeni bilgi taşımaz (bkz. veri kalite raporu §5)
REDUNDANT_COLUMNS = ["unix_time"]

# Zamana göre bölme: eğitim < VALID_START <= doğrulama < TEST_START <= test.
# TEST_START, iki dosyanın arasına düşer (fraudTrain son işlem 12:13:37, fraudTest ilk işlem
# 12:14:25); böylece test dönemi veri setinin kendi fraudTest dosyasıyla birebir aynıdır.
VALID_START = "2020-04-01"
TEST_START = "2020-06-21 12:14:00"
SPLITS = ["train", "valid", "test"]

# Değerlendirme varsayımları (evaluation/metrics.py)
# Her alarmın (doğru ya da yanlış) incelenme maliyeti; kaçırılan dolandırıcılığın maliyeti tutarıdır
REVIEW_COST = 10.0
# Bir kartta aralarında bu süreden az olan dolandırıcılıklar aynı patlama sayılır.
# Kalite raporu §8: patlamalar en fazla ~2 gün sürüyor.
BURST_GAP = "3D"
# Günde incelenebilecek alarm sayısı (doğrulamada günde ~14 dolandırıcılık var)
DAILY_BUDGET = 25

RANDOM_STATE = 42

# --- Demo modu (herkese açık yayın, ör. Hugging Face Spaces) ---------------------------------
# Kapalıyken (varsayılan) servis ve panel yerel, tek kullanıcılı davranışını aynen korur.


def demo_mode() -> bool:
    """DEMO_MODE ortam değişkeni (1/true/yes/on). Her çağrıda okunur (testler için)."""
    return os.environ.get("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


DEMO_RATE_LIMIT = 60              # IP başına istek sayısı ...
DEMO_RATE_WINDOW = 60.0           # ... bu kadar saniyelik kayan pencerede (aşımda 429)
DEMO_RATE_MAX_CLIENTS = 10_000    # izlenen IP sayısı sınırı (sınırlayıcı bellek sızdırmasın)
DEMO_MAX_BODY_BYTES = 10 * 1024   # istek gövdesi sınırı (aşımda 413)
# X-Forwarded-For'da güvenilen vekil sayısı: istemci IP'si sağdan bu kadar içerideki değerdir
# (en soldaki değeri istemci kendisi yazabilir). Spaces'ta yayında doğrulanmalı.
DEMO_TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "1"))
DEMO_STREAM_LIMIT = 2_000         # oturum başına canlı akışta skorlanabilecek işlem
DEMO_ADDED_PER_CARD = 200         # oturum katmanında kart başına eklenen kayıt sınırı
DEMO_ADDED_TOTAL = 5_000          # oturum katmanında toplam eklenen kayıt sınırı
DEMO_MAX_SESSIONS = 50            # aynı anda bellekte tutulan panel oturumu
DEMO_SESSION_TTL = 15 * 60.0      # bu kadar saniye işlem yapmayan oturumun katmanı silinir
