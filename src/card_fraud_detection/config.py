"""Proje genelinde kullanılan sabitler ve yollar."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

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
