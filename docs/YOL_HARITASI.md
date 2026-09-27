# Card Fraud Detection: Faz Planı

Her alt faz tek başına tamamlanabilir, küçük bir iştir. Alt faz bitince kutucuğu işaretle ve
ayrı bir commit at. **Çıktı** o alt fazda üretilecek somut şeydir, **Bitti sayılır** ise
geçmeden önce kontrol edilecek kriterdir.

Toplam süre tahmini: ~5-6 hafta (haftada 10-15 saat).

## Temel kurallar
- **Zamana göre bölme.** Eğitim: 2019-01 → 2020-03, doğrulama: 2020-04 → 2020-06-20,
  test: 2020-06-21 → 2020-12-31 (veri setinin `fraudTest` dosyası). Rastgele bölme kullanılmaz.
  Test kümesine yalnızca Faz 3.5'te, bir kez bakılır.
- **Özellikler yalnızca geçmişten hesaplanır.** Geçmiş etiketler ("kart daha önce dolandırıldı
  mı") kullanılmaz, çünkü gerçekte etiketler gecikmeli gelir.
- **Kişisel veri modele girmez:** ad, soyad, sokak, işlem numarası.
- **Ana metrik PR-AUC'dir.** ROC-AUC, dengesiz veride fazla iyimser kaldığı için ikincil metriktir.

---

## FAZ 0: İskelet · ~1 gün

- [x] **0.1 Repo ve araçlar**
  - Çıktı: `pyproject.toml`, `Makefile`, ruff, pytest, GitHub Actions CI, ilk commit
  - Bitti sayılır: `make lint` ve `make test` temiz, CI yeşil
  - Sonuç: [github.com/TolgaARSLANN/card-fraud-detection](https://github.com/TolgaARSLANN/card-fraud-detection), CI yeşil.
- [x] **0.2 Veri indirme**
  - Çıktı: `python -m card_fraud_detection.data.download` → `data/raw/{train,test}.parquet`
  - Bitti sayılır: satır sayıları (1.296.675 / 555.719) ve dolandırıcılık oranları doğrulandı
  - Sonuç: Eğitim dosyasında 1.296.675 satır (%0,58 dolandırıcılık), test dosyasında 555.719 satır
    (%0,39). Test dönemindeki oran daha düşük, bu yüzden eşik doğrulama kümesinde seçilmeli ve
    PR-AUC dönemler arasında doğrudan karşılaştırılmamalı. kagglehub belirteç olmadan indirdi.

## FAZ 1: Veri ve Keşif (EDA) · ~1 hafta

- [x] **1.1 Veri kalite raporu** (`reports/veri_kalite_raporu.md`)
  - Çıktı: boş değerler, tekrarlar, zaman aralığı, kart başına işlem sayısı, train/test kart örtüşmesi
  - Sonuç: [`reports/veri_kalite_raporu.md`](../reports/veri_kalite_raporu.md) (`make quality`)
  - Bulgular ve 1.2 ile sonraki fazlar için kararlar:
    - Boş değer, tekrar eden işlem, sıfır veya negatif tutar, geçersiz koordinat yok. Aynı kartta
      aynı saniyede 44 işlem var, ancak tutarları farklı olduğu için gerçek işlem sayılıp korunacak.
    - İki dosya kesintisiz: eğitimin sonu ile testin başı arasında 48 saniye var. Kart hızı
      özellikleri iki dosya **birleştirilerek** hesaplanacak. Böylece testin ilk işlemleri,
      kartın eğitim dönemindeki geçmişini görecek; bu gerçek ortamdaki durumla aynı.
    - `unix_time`, aynı anın tam 7 yıl geriye (2012-2013'e) kaydırılmış hâli. Saat ve dakika
      birebir aynı; fark Şubat 2019'da 2557 günden 2556 güne iniyor, çünkü arada 29 Şubat 2012
      artık günü var. Yeni bilgi taşımadığı için **kullanılmayacak**; zaman kaynağı
      `trans_date_trans_time` olacak.
    - Satıcı adlarının %100'ü `fraud_` önekiyle başlıyor. Bu bir simülatör kalıntısı, etiket
      bilgisi taşımıyor. Temizlikte önek silinecek; aksi hâlde grafiklerde ve arayüzde yanıltıcı görünür.
    - Müşteri alanlarının 12'si de her kartta sabit. `cc_num` güvenilir bir müşteri kimliği;
      yaş, cinsiyet ve konum kart düzeyinde kullanılabilir.
    - **Dolandırıcılık kart başına tek bir patlama hâlinde görülüyor.** 999 kartın 976'sında (%97,7)
      dolandırıcılık var. Her kartta medyan 10, en fazla 19 dolandırıcılık işlemi, ilk ve son
      dolandırıcılık arasında en fazla ~2 gün var. Kartların %91'i patlamadan sonra normal
      kullanılmaya devam ediyor. Bunun sonuçları:
      (a) Rastgele bölme aynı patlamayı eğitim ve teste dağıtıp sonuçları şişirirdi; zamana göre
      bölme şart.
      (b) "Kart daha önce dolandırıldı mı" özelliği simülatörde iki yönde de sızıntı yaratır
      (patlama sonrası kart bir daha dolandırılmıyor), bu yüzden kullanılmayacak.
      (c) Son 1 saat / 24 saat pencereli hız özellikleri patlamayı yakalamak için kritik.
      (d) Faz 2.2'de işlem bazlı metriklere ek olarak **patlama bazlı** metrik de raporlanacak:
      patlama yakalandı mı, kaçıncı işlemde yakalandı.
    - Test kartlarının %98,3'ü eğitimde de var; satıcı ve kategorilerin tamamı ortak. Soğuk
      başlangıç (yeni kart) durumu neredeyse yok, bu README'de sınırlama olarak belirtilecek.
    - Aralık aylarında işlem hacmi iki katına çıkıyor ve dolandırıcılık oranı düşüyor
      (Aralık 2020'de %0,18). Testin genel oranının (%0,39) düşük olmasının bir nedeni bu. Eşik,
      oran yerine maliyet ve alarm bütçesiyle seçilecek; test sonuçları aylık olarak da raporlanacak.
    - En genç kart sahibi 14 yaşında. Sentetik veri olduğu için dokunulmayacak.
- [ ] **1.2 Temizlik**
  - Çıktı: `data/processed/transactions.parquet` (kişisel veri sütunları atılmış, zamana göre sıralı,
    `split` sütunu: train/valid/test)
  - Bitti sayılır: kart başına zaman sıralı, bölmeler çakışmıyor (testli)
- [ ] **1.3 EDA notebook'u** (`notebooks/01_eda.ipynb`)
  - Çıktı: kategori, saat ve tutara göre dolandırıcılık oranı, kartta dolandırıcılık patlamaları,
    müşteri–satıcı mesafesi. Grafikler `reports/figures/` altında, bulgular README'de.

## FAZ 2: Özellikler ve Referans Modeller · ~1 hafta

- [ ] **2.1 Özellikler** (`features/build.py`)
  - İşlem: tutar, log tutar, kategori, saat, haftanın günü, gece bayrağı
  - Kart hızı: son 1 sa / 24 sa / 7 gündeki işlem sayısı ve tutar toplamı, önceki işlemden bu yana
    geçen süre, tutarın kart geçmişine göre z-skoru, kategoride/satıcıda ilk işlem mi
  - Konum: müşteri–satıcı mesafesi, önceki işleme göre hız (km/sa)
  - Demografi: yaş, cinsiyet, şehir nüfusu
  - Bitti sayılır: sızıntı testi, yani t anından sonraki satırlar değiştirildiğinde t'deki özellikler değişmiyor
- [ ] **2.2 Metrikler** (`evaluation/metrics.py`)
  - PR-AUC, ROC-AUC, sabit precision'da recall, alarm bütçesine göre (top-k) yakalama,
    yakalanan dolandırıcılık tutarı, maliyet (kaçırılan = tutar, yanlış alarm = sabit inceleme ücreti)
- [ ] **2.3 Referans modeller** (`models/baselines.py`)
  - Kural tabanlı model, yalnızca tutar kullanan model, lojistik regresyon, Isolation Forest (denetimsiz)
  - Çıktı: `reports/baseline_sonuclari.md`

## FAZ 3: Modelleme · ~1-1,5 hafta

- [ ] **3.1 Model × dengesizlik stratejisi** (`models/train.py`)
  - LightGBM ve XGBoost × {sınıf ağırlığı, alt örnekleme, SMOTE (yalnızca eğitim kısmında)}
- [ ] **3.2 Hiperparametre ayarı** (`models/tune.py`, Optuna, doğrulama kümesinde PR-AUC)
- [ ] **3.3 Kalibrasyon ve eşik** (`models/threshold.py`)
  - İzotonik kalibrasyon, güvenilirlik eğrisi, doğrulama kümesinde maliyeti en aza indiren eşik
- [ ] **3.4 Hata analizi** (`evaluation/error_analysis.py`)
  - Kaçırılan dolandırıcılıklar ve yanlış alarmlar: kategori, tutar, kartın geçmişi
- [ ] **3.5 Final model ve tek seferlik test**
  - Çıktı: `models/model.joblib`, `models/metadata.json` (eşik, özellikler, metrikler)
  - Bitti sayılır: test PR-AUC değeri en iyi referans modelinkini açıkça geçiyor
- [ ] **3.6 Açıklanabilirlik** (SHAP özet grafiği ve işlem bazlı waterfall grafiği, `notebooks/02_model.ipynb`)

## FAZ 4: Servis ve Arayüz · ~1 hafta

- [ ] **4.1 FastAPI** (`serving/`)
  - `POST /score`: olasılık, risk seviyesi, karar, ilk 3 neden (Türkçe)
  - `GET /health`, `GET /model`
  - Kart geçmişi `CardHistoryStore`'da tutulur ve eğitimle aynı özellik kodunu kullanır.
  - Bitti sayılır: eğitim ile servis aynı işlem için aynı özellikleri üretiyor (testli)
- [ ] **4.2 Streamlit paneli** (`ui/`)
  - Canlı akış ve alarm kuyruğu, işlem inceleme (SHAP), eşik–maliyet kaydırıcısı

## FAZ 5: Yayına Alma ve Belgeler · ~3-4 gün

- [ ] **5.1 Docker** (`Dockerfile`, `docker-compose.yml`: api + ui)
- [ ] **5.2 İsteğe bağlı yayın** (Streamlit Community Cloud / Hugging Face Spaces, örneklem veriyle)
- [ ] **5.3 README** (sonuç tablosu, grafikler, sınırlamalar: sentetik veri, kavram kayması, etiket gecikmesi)
