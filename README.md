# 💳 Sahtekarlık: Finansal Dolandırıcılık Tespit Sistemi

![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Kart işlemlerini, **işlem anında bilinen bilgilerle** puanlayıp şüpheli olanları inceleme
kuyruğuna gönderen, uçtan uca bir makine öğrenmesi projesi. İşlemlerin yalnızca ~%0,5'i
dolandırıcılık olduğu için projenin odağında sınıf dengesizliği, PR-AUC, maliyet tabanlı eşik
seçimi ve açıklanabilirlik var.

> 🚧 Geliştirme sürüyor. Ayrıntılı plan: [docs/YOL_HARITASI.md](docs/YOL_HARITASI.md)

## Veri
[Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
(Sparkov simülatörü): ABD'de 1.000 müşteri ve 800 satıcı arasında 2019-01 ile 2020-12 arasındaki
~1,85 milyon **sentetik** kart işlemi.

## Kurulum ve Çalıştırma
Linux, macOS veya WSL üzerinde:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make data    # veriyi indirir: data/raw/{train,test}.parquet
make test
```
