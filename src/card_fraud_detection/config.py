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

# Zamana göre bölme: eğitim < VALID_START <= doğrulama < TEST_START <= test.
# Test dönemi, veri setinin kendi fraudTest dosyasıdır.
VALID_START = "2020-04-01"
TEST_START = "2020-06-21"

RANDOM_STATE = 42
