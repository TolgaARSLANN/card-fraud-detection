# Card Fraud Detection: Faz Planı

Her alt faz tek başına tamamlanabilir, küçük bir iştir. Alt faz bitince kutucuğu işaretle ve
ayrı bir commit at. **Çıktı** o alt fazda üretilecek somut şeydir, **Bitti sayılır** ise
geçmeden önce kontrol edilecek kriterdir.

Toplam süre tahmini: ~5-6 hafta (haftada 10-15 saat).

## Temel kurallar
- **Zamana göre bölme.** Eğitim: 2019-01-01 → 2020-03-31, doğrulama: 2020-04-01 →
  2020-06-21 12:13, test: 2020-06-21 12:14 → 2020-12-31 (veri setinin `fraudTest` dosyası;
  sınırlar `config.py`'de). Rastgele bölme kullanılmaz. Test kümesine yalnızca Faz 3.5'te,
  bir kez bakılır.
  - İstisna (kayıt için): Faz 0.2, 1.1 ve 1.2'de test dosyasının yalnızca **betimleyici**
    istatistikleri görüldü: satır sayısı, genel ve aylık dolandırıcılık oranı, kart örtüşmesi.
    Bunlardan çıkan tek karar, eşiğin genel orana değil maliyete göre seçilmesi ve test
    sonuçlarının aylık da raporlanmasıdır. Hiçbir özellik, model ya da eşik değeri test
    verisine göre ayarlanmadı. EDA (1.3) yalnızca eğitim bölmesini kullandı.
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
      *Düzeltme (1.3):* EDA'ya göre işlem **sayısı** neredeyse hiç ayırt etmiyor; kritik olan
      pencere içindeki **toplam tutar** ve tutarın kartın geçmişine oranı.
      (d) Faz 2.2'de işlem bazlı metriklere ek olarak **patlama bazlı** metrik de raporlanacak:
      patlama yakalandı mı, kaçıncı işlemde yakalandı.
    - Test kartlarının %98,3'ü eğitimde de var; satıcı ve kategorilerin tamamı ortak. Soğuk
      başlangıç (yeni kart) durumu neredeyse yok, bu README'de sınırlama olarak belirtilecek.
    - Aralık aylarında işlem hacmi iki katına çıkıyor ve dolandırıcılık oranı düşüyor
      (Aralık 2020'de %0,18). Testin genel oranının (%0,39) düşük olmasının bir nedeni bu. Eşik,
      oran yerine maliyet ve alarm bütçesiyle seçilecek; test sonuçları aylık olarak da raporlanacak.
    - En genç kart sahibi 14 yaşında. Sentetik veri olduğu için dokunulmayacak.
- [x] **1.2 Temizlik**
  - Çıktı: `data/processed/transactions.parquet` (kişisel veri sütunları atılmış, zamana göre sıralı,
    `split` sütunu: train/valid/test)
  - Bitti sayılır: kart başına zaman sıralı, bölmeler çakışmıyor (testli)
  - Sonuç: `make process` (~7 sn) → 1.852.394 satır, 19 sütun; satır kaybı yok.

    | bölme | dönem | işlem | dolandırıcılık | oran | kart |
    |---|---|---|---|---|---|
    | train | 2019-01-01 → 2020-03-31 | 1.097.693 | 6.343 | %0,58 | 968 |
    | valid | 2020-04-01 → 2020-06-21 12:13 | 198.982 | 1.163 | %0,58 | 923 |
    | test | 2020-06-21 12:14 → 2020-12-31 | 555.719 | 2.145 | %0,39 | 924 |

  - Düzeltme: `TEST_START` başta `2020-06-21` (gün başı) idi. Eğitim dosyası o gün 12:13'e
    kadar sürdüğü için sabahki işlemler teste kayacaktı. Sınır, iki dosyanın arasına düşen
    `2020-06-21 12:14:00` yapıldı. `clean` artık test bölmesinin `fraudTest` dosyasıyla birebir
    örtüştüğünü doğruluyor, örtüşmezse hata veriyor.
  - `validate`: atılan sütunlar gerçekten yok, `fraud_` öneki kalmadı, tablo zamana göre sıralı
    (bu, kart içi sırayı da garanti eder), `tx_id` benzersiz, boş değer yok, bölmeler zamanda
    çakışmıyor. Kurallardan biri bozulursa dosya yazılmıyor.
  - Not: 7 kartın dolandırıcılık patlaması bir bölme sınırına denk geliyor (ör. 9 işlem train,
    3 işlem valid). Geçmiş etiketler özellik olarak kullanılmadığı için sızıntı yaratmıyor;
    gerçekte de sınırda başlayan bir patlama böyle görünür. Dokunulmadı.
- [x] **1.3 EDA notebook'u** (`notebooks/01_eda.ipynb`)
  - Çıktı: kategori, saat ve tutara göre dolandırıcılık oranı, kartta dolandırıcılık patlamaları,
    müşteri–satıcı mesafesi. Grafikler `reports/figures/` altında, bulgular README'de.
  - Sonuç: 7 bölüm ve özet tablo; 7 grafik `reports/figures/0*.png`. Yeniden üretmek için
    `make eda` (~20 sn). Analiz **yalnızca eğitim bölmesiyle** yapıldı; doğrulama ve test
    dönemlerine bakılmadı.
  - Sonraki fazlara aktarılan kararlar (gerekçeler notebook'un 7. bölümünde):
    - Tutar en güçlü tekil sinyal, ama anlamı kategoriye göre tersine dönüyor (çevrim içi
      alışverişte dolandırıcılık ~120 kat büyük, akaryakıtta ~6 kat küçük). → "Tutar / kategori
      medyanı" özelliği eklendi; medyanlar yalnızca eğitimden hesaplanacak.
    - Gece saatleri işlemlerin %23,5'i, dolandırıcılığın %84,7'si. → Saat ve gece bayrağı.
    - Patlamayı işlem **sayısı** değil **tutar** ele veriyor: 24 saatlik işlem sayısının medyanı
      normalde 3, dolandırıcılıkta 4; 24 saatlik tutar ise $1.687'ye $172. Tutarı kartın geçmiş
      ortalamasının 3 katını aşan işlemler, işlemlerin %4'ü ama dolandırıcılığın %65'i.
    - *Düzeltme (2.1):* EDA'nın ilk sürümü, son 24 saatte hiç işlemi olmayan satırlarda işlem
      sayısını 0 yerine boş bıraktı. Bu satırlar (eğitimin %8,5'i) o analizden düştü ve
      "medyan iki sınıfta da 4" sonucu çıktı. Hata, 2.1'deki bağımsız uygulamayla
      karşılaştırmada yakalandı ve notebook düzeltildi. Ana sonuç (işlem sayısı zayıf bir
      sinyal) değişmedi.
    - Patlamanın ilk işleminde kart sakin (24 saatte $39), ama tutar oranı zaten 5,1. → 2.2'deki
      patlama bazlı metrik, erken yakalamayı ölçmek için gerekli.
    - Müşteri–satıcı mesafesi iki sınıfta aynı dağılımda: simülatör satıcı konumunu rastgele
      üretiyor. → Mesafe ve hız özellikleri **plandan çıkarıldı**.
    - Demografik sinyal zayıf (yaşa göre %0,43–0,89). Yaş ve cinsiyet korunan özellikler olduğu
      için ana model bunları **kullanmayacak**; Faz 3'te katkıları ayrı bir karşılaştırmayla ölçülecek.
    - Simülatör kalıntısı: dolandırıcılıkta en yüksek tutar $1.372, normal işlemlerde $28.948.
      README'de sınırlama olarak belirtilecek.

## FAZ 2: Özellikler ve Referans Modeller · ~1 hafta

- [x] **2.1 Özellikler** (`features/build.py`)
  - İşlem: tutar, log tutar, kategori, saat, haftanın günü, gece bayrağı, tutar / kategori
    medyanı (medyanlar yalnızca eğitim bölmesinden)
  - Kart geçmişi: son 1 sa / 24 sa / 7 gündeki işlem sayısı ve tutar toplamı, önceki işlemden
    bu yana geçen süre, tutarın kartın geçmiş ortalamasına oranı ve z-skoru, kategoride/satıcıda
    ilk işlem mi
  - ~~Konum: müşteri–satıcı mesafesi, önceki işleme göre hız~~: EDA §5'te sinyal çıkmadı.
  - Demografi (yaş, cinsiyet): ana modelde yok; Faz 3'te ayrı bir karşılaştırma modelinde
    denenecek. Şehir nüfusu sinyal taşımadığı için kullanılmayacak.
  - Bitti sayılır: sızıntı testi, yani t anından sonraki satırlar değiştirildiğinde t'deki özellikler değişmiyor
  - Sonuç: `make features` (~20 sn, ~1 GB bellek) → `data/processed/features.parquet`
    (1.852.394 satır, 19 ana özellik + 2 demografik) ve `models/feature_stats.json` (eğitimden
    öğrenilen kategori medyanları; servis de aynı dosyayı kullanacak).
  - Testler (`tests/test_features.py`, 7 test): elle hesaplanmış değerler, aynı saniyedeki
    işlemler, **sızıntı testi** (kesim anından sonraki tutar, kategori, satıcı ve etiketler
    değiştirilir; öncesindeki özellikler birebir aynı kalır), satır sırasından bağımsızlık,
    etiketlerin kullanılmadığı, `fit_stats`'ın yalnızca eğitimi kabul etmesi, bilinmeyen kategori.
  - Testlerin koruyuculuğu, kod kasıtlı bozularak sınandı. Üç hata denendi: geleceği gören
    ortalama, o anı içeren pencere, kart yerine tüm tablo sırasına göre "önceki işlem". İlk
    denemede üçüncüsü yakalanmadı: değer testi yalnızca tablonun başındaki kartı kontrol
    ediyordu. İkinci kartın ilk işlemi için doğrulama eklendi; artık üçü de yakalanıyor.
  - Bağımsız sağlama: Eğitim bölmesindeki medyanlar, EDA'daki ayrı uygulamayla birebir
    tuttu (24 sa tutar $172/$1.687, önceki işlemden süre 4,6/1,3 sa, kart ortalamasına oran
    0,66/5,19). Karşılaştırma, EDA'daki işlem sayısı hatasını ortaya çıkardı (bkz. 1.3).
  - Eğitimde en çok ayrışan özellikler (medyan normal / dolandırıcılık): tutar / kategori
    medyanı 1,0 / 7,9; tutar / kart ortalaması 0,66 / 5,19; kart z-skoru −0,19 / 2,52;
    24 sa tutar $172 / $1.687; saat 14 / 22; satıcıda ilk işlem 0 / 1.
  - Tasarım notu: Pencere özellikleri `[t − pencere, t)` aralığına bakar, aynı saniyedeki
    işlemleri saymaz. Sıra tabanlı özellikler ise aynı saniyede `tx_id` sırasında öncekini
    geçmiş sayar. Bu fark yalnızca aynı kartta aynı saniyedeki 44 işlemi etkiler.
  - Boş değerler: kartın ilk işleminde önceki işlem yok (%0,05), z-skoru ilk iki işlemde
    tanımsız (%0,11). LightGBM boş değerleri doğrudan işler; lojistik regresyon için 2.3'te
    doldurulacak.
- [x] **2.2 Metrikler** (`evaluation/metrics.py`)
  - PR-AUC, ROC-AUC, sabit precision'da recall, alarm bütçesine göre (top-k) yakalama,
    yakalanan dolandırıcılık tutarı, maliyet (kaçırılan = tutar, yanlış alarm = sabit inceleme ücreti)
  - Sonuç: Üç düzey metrik ve tek çağrıda özet (`evaluate`):
    - Sıralama: PR-AUC, ROC-AUC, sabit precision'da recall
    - Operasyon: alarm, TP/FP/FN, precision, recall, yakalanan ve kaçan tutar, maliyet;
      maliyet eğrisi ve maliyeti en aza indiren eşik; günlük alarm bütçesi (her gün en
      yüksek skorlu k işlem)
    - Patlama: yakalanan patlama oranı, ilk işlemde yakalanan oranı, ilk alarmın medyan sırası,
      ilk alarma kadar kaybedilen tutar oranı
  - Varsayımlar (`config.py`, değiştirilebilir): Her alarmın inceleme ücreti $10; doğru
    alarmlar da incelendiği için ücret hepsine uygulanır. Bir kartta aralarında 3 günden az
    olan dolandırıcılıklar tek patlamadır. Patlama metriği ilk alarmda kartın bloke edildiğini
    varsayar; bu yüzden işlem bazlı kaçan tutardan iyimserdir ve ikisi birlikte raporlanacak.
  - Testler (`tests/test_metrics.py`, 10 test): elle hesaplanmış örnekler; maliyet eğrisi,
    eşit skorlu işlemler de olan rastgele veride her eşiği tek tek deneyen kaba kuvvet hesapla
    karşılaştırıldı. Beş kasıtlı hata denendi (eşitlik grubunu bölmek, ücreti yalnızca yanlış
    alarma yazmak, patlamaları kart ayırmadan bölmek, kaybı ilk alarm dahil saymak, bütçeyi
    gün ayırmadan uygulamak); beşi de yakalandı.
  - İşlerlik denemesi (doğrulama bölmesi, skor = yalnızca tutar): 199 bin işlem 0,5 sn'de
    değerlendirildi. **Tek başına tutar bile güçlü:** PR-AUC 0,19, ROC-AUC 0,84; maliyete göre
    seçilen $257 eşiğiyle recall 0,75, precision 0,16, patlamaların %98'i yakalanıyor. Hiç
    alarm vermemenin maliyeti $619.630, bu kuralla $67.702. → 2.3'te "yalnızca tutar" referans
    modeli ciddi bir çıta; asıl model bunu açıkça geçmeli.
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
