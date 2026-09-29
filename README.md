# 💳 Card Fraud Detection: Kart Dolandırıcılığı Tespit Sistemi

[![CI](https://github.com/TolgaARSLANN/card-fraud-detection/actions/workflows/ci.yml/badge.svg)](https://github.com/TolgaARSLANN/card-fraud-detection/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Kart işlemlerini, **işlem anında bilinen bilgilerle** puanlayıp şüpheli olanları inceleme
kuyruğuna gönderen, uçtan uca bir makine öğrenmesi projesi. İşlemlerin yalnızca ~%0,5'i
dolandırıcılık olduğu için projenin odağında sınıf dengesizliği, PR-AUC, maliyet tabanlı eşik
seçimi ve açıklanabilirlik var.

> 🚧 Geliştirme sürüyor: Veri, kalite kontrolü ve keşif analizi tamamlandı; özellikler ve
> modelleme sırada. Ayrıntılı plan: [docs/YOL_HARITASI.md](docs/YOL_HARITASI.md)

## Veri
[Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
(Sparkov simülatörü): ABD'de 999 kart ve 693 satıcı arasında, 2019-01-01 ile 2020-12-31
arasındaki 1.852.394 **sentetik** kart işlemi.

| bölme | dönem | işlem | dolandırıcılık oranı |
|---|---|---|---|
| Eğitim | 2019-01-01 → 2020-03-31 | 1.097.693 | %0,58 |
| Doğrulama | 2020-04-01 → 2020-06-21 | 198.982 | %0,58 |
| Test | 2020-06-21 → 2020-12-31 | 555.719 | %0,39 |

- **Bölme zamana göredir, rastgele değildir.** Dolandırıcılık her kartta ~2 günlük tek bir
  patlama hâlinde geliyor; rastgele bölme aynı patlamayı eğitim ve teste dağıtıp sonuçları
  şişirirdi. Test dönemi, veri setinin kendi `fraudTest` dosyasıyla birebir aynıdır.
- **Kalite:** Boş değer, tekrar eden işlem ve geçersiz değer yok. Kişisel veri sütunları (ad,
  soyad, adres, işlem no) modele girmeden önce atılır. Ayrıntılar:
  [veri kalite raporu](reports/veri_kalite_raporu.md)

## Veriden Öğrendiklerimiz
Tam analiz: [notebooks/01_eda.ipynb](notebooks/01_eda.ipynb). Analiz yalnızca eğitim
bölmesiyle yapıldı.

1. **Tutar en güçlü tekil sinyal.** Dolandırıcılığın medyan tutarı $395, normal işlemlerin $47.
   $500–1.000 aralığındaki işlemlerde dolandırıcılık oranı %22,9.
2. **Ama tutarın anlamı kategoriye göre tersine dönüyor.** Çevrim içi alışverişte dolandırıcılık
   normalin ~120 katı tutarında, akaryakıtta ise ~6 kat **küçük**. Bu yüzden tutar, kategorinin
   normuna göre de ölçülüyor.
3. **Dolandırıcılık gece yoğunlaşıyor.** 22:00–03:59 arası işlemlerin %23,5'i, dolandırıcılığın
   ise %84,7'si.
4. **Patlamayı işlem sayısı değil, tutar ele veriyor.** Son 24 saatteki işlem sayısının medyanı
   normal işlemlerde 3, dolandırıcılıkta 4; fark küçük. Buna karşılık tutarı kartın geçmiş ortalamasının 3 katını aşan işlemler,
   tüm işlemlerin %4'ü ama dolandırıcılığın %65'i.
5. **Bazı beklenen sinyaller bu veride yok.** Müşteri–satıcı mesafesi iki sınıfta aynı
   dağılıyor; simülatör satıcı konumunu rastgele üretiyor. Demografik sinyal zayıf ve yaş ile
   cinsiyet korunan özellikler olduğu için ana modelde kullanılmıyor.

<p align="center">
  <img src="reports/figures/01_tutar.png" alt="Tutar dağılımı ve tutar aralığına göre dolandırıcılık oranı" width="100%"><br>
  <em>Dolandırıcılık tutarları birkaç dar bantta toplanıyor; oran $200'ün üzerinde hızla artıyor.</em>
</p>

<p align="center">
  <img src="reports/figures/02_kategori.png" alt="Kategoriye göre dolandırıcılık oranı ve medyan tutar" width="100%"><br>
  <em>Solda: En riskli üç kategori, dolandırıcılığın %58'ini içeriyor. Sağda: Bazı kategorilerde dolandırıcılık normalden çok büyük, bazılarında küçük.</em>
</p>

<p align="center">
  <img src="reports/figures/05_hiz_oran.png" alt="Kartın geçmişine göre tutar oranı ve son 24 saatteki işlem sayısına göre dolandırıcılık oranı" width="100%"><br>
  <em>Tutarın kartın geçmiş ortalamasına oranı güçlü bir sinyal (solda); işlem sayısı ise neredeyse hiç ayırt etmiyor (sağda).</em>
</p>

## Kurulum ve Çalıştırma
Linux, macOS veya WSL üzerinde:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make data       # veriyi indirir: data/raw/{train,test}.parquet
make quality    # veri kalite raporu: reports/veri_kalite_raporu.md
make process    # temizlik ve bölme: data/processed/transactions.parquet
make eda        # keşif analizi notebook'unu çalıştırır, grafikleri üretir
make test
```

## Sınırlamalar
- **Sentetik veri.** Bulgular Sparkov simülatörünün davranışını yansıtır. Örneğin
  dolandırıcılıkta en yüksek tutar $1.372'dir; model "bu tutarın üzerinde dolandırıcılık yok"
  gibi gerçek dünyada karşılığı olmayan kurallar öğrenebilir.
- **Soğuk başlangıç yok.** Test kartlarının %98'i eğitimde de görülüyor; yeni açılmış kartlardaki
  performans bu veriyle ölçülemiyor.
