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
- [x] **2.3 Referans modeller** (`models/baselines.py`)
  - Kural tabanlı model, yalnızca tutar kullanan model, lojistik regresyon, Isolation Forest (denetimsiz)
  - Çıktı: `reports/baseline_sonuclari.md`
  - Sonuç: [`reports/baseline_sonuclari.md`](../reports/baseline_sonuclari.md) (`make baselines`,
    ~50 sn). Tüm modeller eğitim bölmesinde eğitildi, doğrulama bölmesinde ölçüldü.

    | model | PR-AUC | günde 25 alarmla recall | eşik*: kaçan tutar | eşik*: maliyet | eşik*: ilk işlemde yakalanan |
    |---|---|---|---|---|---|
    | Lojistik regresyon | **0,625** | **%72** | $30.796 | **$61.996** | %53 |
    | Isolation Forest | 0,415 | %51 | $77.819 | $131.639 | %49 |
    | Kural tabanlı | 0,212 | %48 | $16.656 | $94.146 | %78 |
    | Yalnızca tutar | 0,187 | %46 | $12.022 | $67.702 | %79 |

    \* Maliyet eşiği doğrulamanın kendisinde seçildi (iyimser). Hiç alarm vermemenin maliyeti $619.630.
  - Yorum ve Faz 3'e aktarılanlar:
    - **Çıta: lojistik regresyon, PR-AUC 0,625.** Faz 3'teki model bunu açıkça geçmeli (3.5'teki
      "bitti sayılır" ölçütü). Günde 25 alarmla dolandırıcılıkların %72'sini yakalıyor.
    - **Doğrusal model, patlamanın ilk ve pahalı işlemini ıskalıyor.** Maliyeti en düşük model
      olsa da "yalnızca tutar" kuralına çok yakın. Nedeni: daha az alarm verdiği için inceleme
      maliyeti düşük, ama 2,5 kat daha fazla dolandırıcılık tutarı kaçırıyor. Patlamaları ilk
      işlemde yakalama oranı %53, basit tutar kuralında %79. Model kart geçmişi özelliklerine
      ağırlık veriyor, ama o işlemde geçmiş henüz sakin (EDA §4). Tutar ile kategori ve saat
      arasındaki etkileşimi doğrusal bir model kuramıyor. → Faz 3'te ağaç tabanlı modelin somut
      hedefi: ilk işlemde yakalama oranını ve kaçan tutarı iyileştirmek. Hata analizi (3.4)
      bu ayrıma göre yapılacak.
    - **Isolation Forest zayıf.** Etiket kullanmayan anomali skoru PR-AUC 0,415'te kaldı ve
      maliyeti en yüksek model. Veride etiket varken denetimsiz yaklaşım rekabetçi değil;
      Faz 3'te kullanılmayacak.
    - **Kural tabanlı model, tutara çok az şey ekliyor** (PR-AUC 0,187 → 0,212). Üç işaretten
      oluşan kaba skor, sıralama gücü sağlamıyor.
  - Testler (`tests/test_baselines.py`, 5 test): ön işleme tüm özellikleri karşılıyor ve boş
    değer bırakmıyor; kural skoru doğru sayılıyor; denetimli ve denetimsiz modeller sentetik
    veride dolandırıcılığa daha yüksek skor veriyor; bir doğrulama satırının skoru diğer
    doğrulama satırlarına bağlı değil (ön işleme yalnızca eğitimden öğreniyor).

## FAZ 3: Modelleme · ~1-1,5 hafta

- [x] **3.1 Model × dengesizlik stratejisi** (`models/train.py`)
  - LightGBM ve XGBoost × {sınıf ağırlığı, alt örnekleme, SMOTE (yalnızca eğitim kısmında)}
  - Sonuç: [`reports/model_karsilastirma.md`](../reports/model_karsilastirma.md) (`make train`,
    ~10 dk, en yüksek bellek 1,8 GB). Sabit hiperparametreler; doğrulama verisi erken durdurma
    için kullanılmadı. "Yok" (dengeleme yapmamak) da stratejilere eklendi.

    | model | PR-AUC | günde 25 alarmla recall | eşik*: maliyet | eşik*: ilk işlemde yakalanan | süre |
    |---|---|---|---|---|---|
    | XGBoost · yok | **0,976** | %93 | $19.898 | %95 | 65 sn |
    | LightGBM · alt örnekleme | 0,975 | %93 | $18.472 | %94 | **7 sn** |
    | XGBoost · ağırlık | 0,975 | %93 | $21.131 | %93 | 65 sn |
    | LightGBM · yok | 0,974 | %93 | $21.022 | %94 | 40 sn |
    | XGBoost · alt örnekleme | 0,974 | %93 | $18.403 | %94 | 6 sn |
    | LightGBM · ağırlık | 0,970 | %93 | $23.291 | %92 | 36 sn |
    | XGBoost · SMOTE | 0,968 | %92 | $22.154 | %91 | 80 sn |
    | LightGBM · SMOTE | 0,968 | %92 | $24.633 | %91 | 55 sn |
    | *Referans: lojistik regresyon* | *0,625* | *%72* | *$61.996* | *%53* | 50 sn |

  - Yorum:
    - **Ağaç modelleri çıtayı çok açık geçiyor:** PR-AUC 0,625 → ~0,975. Patlamayı ilk işlemde
      yakalama %53 → %94-95; maliyet (iyimser eşikte) $62 bin → ~$18-20 bin. 2.3'te konan
      hedef (ilk işlemde yakalama ve kaçan tutar) karşılandı.
    - **Sızıntı kontrolü:** Bu sıçrama sızıntı işareti olabileceği için iki kontrol yapıldı.
      Özellik önemleri EDA ile uyumlu (tutar %51, 24 sa tutar %15, kategori, kategori oranı,
      gece); açıklanamayan baskın bir özellik yok. Özellik aileleri tek başına ~0,83'te kalıyor
      (yalnızca işlem 0,834, yalnızca kart geçmişi 0,831), birlikte 0,975. Kazanç, özelliklerin
      birleşiminden ve doğrusal modelin kuramadığı tutar × kategori × saat etkileşimlerinden geliyor.
    - **Dengesizlik stratejisi az fark ediyor; SMOTE en kötüsü.** Ağaç modelleri dengesiz veriyle
      zaten iyi başa çıkıyor. SMOTE her iki modelde de en düşük PR-AUC ve en yüksek maliyeti verdi;
      sentetik örnekler yarar sağlamıyor. Faz 3.2'de kullanılmayacak.
    - **En iyi iki kombinasyon istatistiksel olarak berabere.** Tohum kontrolü (3 tohum):
      XGBoost · yok 0,9766 ± 0,0008; LightGBM · alt örnekleme 0,9749 ± 0,0016. Fark ~1 standart
      sapma. LightGBM · alt örnekleme ise **9 kat daha hızlı** (7 sn / 65 sn) ve maliyeti biraz
      daha düşük.
    - **Demografi ölçülebilir bir katkı sağlıyor:** Yaş ve cinsiyet eklenince PR-AUC 0,976 →
      0,985 (+0,009, tohum sapmasının ~10 katı; gerçek bir fark). İyimser eşikte maliyet
      $19.898 → $16.589. EDA'daki "ana model demografisiz" kararının bir bedeli olduğu artık
      ölçüldü; kullanıp kullanmama kararı kullanıcıya bırakıldı.
  - **Kararlar (kullanıcı onaylı):**
    - Ana model **demografi kullanmayacak**. Yaş ve cinsiyet korunan özellikler; +0,009 PR-AUC'lik
      kazanım, adalet riskine değmiyor. Kazanımın bedeli README'de rakamla belirtilecek.
    - 3.2'de **LightGBM · alt örnekleme** ayarlanacak: XGBoost · yok ile istatistiksel olarak
      berabere, 9 kat daha hızlı; aynı sürede çok daha fazla ayar denemesi yapılabilir.
  - Testler (`tests/test_train.py`, 10 test): stratejiler girdiyi değiştirmiyor ve hedef oranı
    tutturuyor; SMOTE yalnızca dolandırıcılık ekliyor, özgün satırlara ve normal işlemlere
    dokunmuyor, kategorik sütunlarda ara değer üretmiyor; 8 model × strateji kombinasyonunun
    her biri öğreniyor; doğrulama satırları birbirinden bağımsız skorlanıyor.
- [x] **3.2 Hiperparametre ayarı** (`models/tune.py`, Optuna, doğrulama kümesinde PR-AUC)
  - Sonuç: [`reports/ayar_sonuclari.md`](../reports/ayar_sonuclari.md) (`make tune`, 60 deneme,
    ~15 dk). LightGBM · alt örnekleme; alt örnekleme oranı da aranan parametrelerden biri.
    İlk deneme varsayılan parametreler. Denemeler `data/processed/optuna.db`'de kalıcı; yarıda
    kalan çalışma kaldığı yerden sürer.
  - **Karar: varsayılan parametrelerde kalındı.** Benimseme kuralı ayardan **önce** yazıldı:
    tohum ortalamasındaki kazanç tohum oynaklığından büyük olmalı **ve** doğrulamanın her ayında
    ayarlanmış model daha iyi olmalı.

    | kontrol | varsayılan | ayarlanmış | sonuç |
    |---|---|---|---|
    | 3 tohum PR-AUC | 0,9749 ± 0,0016 | 0,9769 ± 0,0012 | kazanç +0,0021 < oynaklık 0,0028 → geçmedi |
    | Nisan / Mayıs / Haziran | 0,971 / 0,987 / 0,967 | 0,974 / 0,989 / 0,972 | her ay daha iyi → geçti |

  - Not: Ayarlanmış model üç tohumun ve üç ayın her birinde daha iyi; eşleştirilmiş bir
    karşılaştırma büyük olasılıkla kazancı anlamlı bulurdu. Kural (iki standart sapmanın toplamı)
    temkinli, ama sonucu gördükten sonra kuralı gevşetmek ölçütü sonuca göre ayarlamak olacağı
    için değiştirilmedi. Pratik etki küçük (~0,002 PR-AUC). Ayarlanmış parametreler
    `models/best_params.json`'da (`ayarlanmis_parametreler`) saklı.
  - Ayardan öğrenilen: Etkinin yarısı alt örnekleme oranından geliyor (fANOVA 0,50). En iyi
    denemeler oranı ~0,04'e (1'e 25; varsayılan 1'e 10) indiriyor ve daha küçük ağaçlar
    (15-30 yaprak; varsayılan 63) seçiyor: Modele daha çok normal işlem göstermek ve modeli
    sadeleştirmek biraz yarar sağlıyor.
  - Hata ve düzeltme: İlk çalıştırma, 10 dakikalık aramadan sonra sonucu JSON'a yazarken çöktü
    (karar değeri `numpy.bool_` idi). Düzeltildi; JSON'a yazılabilirliği sınayan test ve
    denemelerin kalıcı saklanması eklendi. Yeniden çalıştırma aynı sonuçları verdi (tekrarlanabilir).
- [x] **3.3 Kalibrasyon ve eşik** (`models/threshold.py`)
  - İzotonik kalibrasyon, güvenilirlik eğrisi, doğrulama kümesinde maliyeti en aza indiren eşik
  - Sonuç: [`reports/kalibrasyon_esik.md`](../reports/kalibrasyon_esik.md) (`make threshold`, ~15 sn).
    Çıktılar: `models/model.joblib` (model + kalibratör; repoya girmez, `make threshold` ile
    yeniden üretilir) ve `models/decision.json` (karar kuralı).
  - Tasarım:
    - Model yalnızca eğitim bölmesiyle eğitildi. Doğrulama kalibrasyon ve karar kuralına
      ayrıldı; eğitim + doğrulamayla yeniden eğitilen bir modelin skor dağılımı değişeceği
      için doğrulamada öğrenilen kalibratör ona uymazdı.
    - Dürüst ölçüm için genişleyen zaman penceresi: Nisan'da öğren → Mayıs'ta ölç; Nisan +
      Mayıs'ta öğren → Haziran'da ölç. Seçim ölçütü önceden konuldu: öğrenilmeyen aylardaki
      toplam maliyet.
    - Kalibrasyon: ham skor, önsel düzeltme (alt örnekleme oranından analitik; β = 0,058),
      Platt, izotonik. Kurallar: tek sabit eşik, **beklenen maliyet** (olasılık × tutar ≥ $10;
      parametresiz, tutara göre değişen eşik), günlük 25 alarm bütçesi.
  - **Karar: beklenen maliyet kuralı, önsel düzeltmeyle.** Öğrenilmeyen iki ayda:

    | kural · kalibrasyon | alarm | kaçan tutar | işlem bazlı maliyet | kart bloke varsayımıyla maliyet |
    |---|---|---|---|---|
    | **beklenen maliyet · önsel düzeltme** | 932 | $3.832 | **$13.152** | **$4.969** |
    | sabit eşik, ölçülen ayda seçilmiş (iyimser tavan) | 1.054 | $2.726 | $13.266 | – |
    | beklenen maliyet · izotonik | 1.052 | $3.304 | $13.824 | $5.641 |
    | sabit eşik · izotonik | 1.028 | $3.744 | $14.024 | $5.780 |
    | günlük bütçe (25) · izotonik | 1.300 | $19.963 | $32.963 | – |

  - Yorum:
    - **Parametresiz beklenen maliyet kuralı, ölçülen ayın kendisinde seçilmiş (iyimser) sabit
      eşiğe eşdeğer.** Tutara göre değişen eşik, ayarlanacak bir değer gerektirmeden en iyi
      sabit eşik kadar iyi; eşiğin aylar arasında kayması riski de yok.
    - **İlk dört aday arasındaki fark küçük** (iki ayda $13,2-14,0 bin). Seçim, önceden konan
      ölçüte göre yapıldı ama sıralama kesin değil.
    - **Ödünleşim:** Beklenen maliyet kuralı daha az dolandırıcılık yakalıyor (recall ~%89,
      sabit eşikte ~%97; ilk işlemde yakalama ~%84 / ~%93). Beklenen kaybı $10'dan az olan
      küçük işlemlere bilerek alarm vermiyor. İşlem bazlı maliyet, küçük ilk işlemi yakalamanın
      kartı bloke edip sonraki büyük işlemleri önleyeceğini görmediği için ayrıca "kart ilk
      alarmda bloke edilir" varsayımıyla maliyet hesaplandı (ek kontrol, rapora girmedi).
      **Seçilen kural o hesapta da en ucuz:** sabit eşiğin fazladan alarmlarının ücreti,
      önlediği kaybı aşıyor. Karar, maliyetin tanımına bağlı değil.
    - **Günlük bütçe en kötüsü** (maliyet 2,5 kat): Günlerin dolandırıcılık yükü eşit değil ve
      bütçe tutarı hiç dikkate almıyor.
    - **Kalibrasyon:** Ham skor alt örnekleme nedeniyle riski abartıyor (Haziran'da ortalama
      tahmin %0,68, gerçek oran %0,58; yüksek bölgede %10 denen işlemlerin ~%3'ü dolandırıcılık).
      İzotonik ve Platt köşegene en yakın. Önsel düzeltme ortalamada iyi (ECE düşük) ama
      %0,1-1 bölgesinde riski ~4 kat düşük gösteriyor. → Faz 4'te analiste gösterilecek
      olasılık için bu not dikkate alınacak.
  - Hata ve düzeltmeler: ECE, eşit skorlu işlemleri satır sırasına göre farklı dilimlere
    bölüyordu (izotonik çıktı çok sayıda eşit değer üretir); dilim sınırları skor değerlerinden
    çizilecek biçimde düzeltildi ve testlendi. Önsel düzeltme, yuvarlama nedeniyle 1'i
    aşabiliyordu; sınırlandı. Güvenilirlik grafiğinin ilk iki sürümü yanıltıcıydı (noktalar
    sıfıra yığılıyordu; ardından hiç dolandırıcılık içermeyen dilimler atılıp eğri yukarı
    itilmişti); dilimler üst kuyruğa yoğunlaştırıldı ve boş dilimler tabanda gösterildi.
  - Testler (`tests/test_threshold.py`, 11 test): önsel düzeltmenin gerçek oranı geri
    kazanması; dört yöntemin [0, 1] aralığında monoton olasılık üretmesi; izotonik düzeltmenin
    ECE'yi düşürmesi; ECE'nin satır sırasından bağımsızlığı; beklenen maliyet kuralının tutara
    bağlılığı; zaman katmanlarının geleceğe bakmaması; seçimin tavan satırını dışlaması.
- [x] **3.4 Hata analizi** (`evaluation/error_analysis.py`)
  - Kaçırılan dolandırıcılıklar ve yanlış alarmlar: kategori, tutar, kartın geçmişi
  - Sonuç: [`reports/hata_analizi.md`](../reports/hata_analizi.md) (`make errors`, ~10 sn).
    İncelenen alarmlar 3.3'te maliyeti raporlananların aynısı (Mayıs + Haziran, her ay önceki
    aylarla kalibre edilmiş); test bölmesine dokunulmadı. 132.090 işlemde: 768 yakalandı,
    93 kaçtı, 164 yanlış alarm.
  - Bulgular:
    - **Kaçanlar çoğunlukla bilinçli:** Kaçan 93 dolandırıcılığın %92'si $50'nin altında;
      kaçan tutar yalnızca $3.832 (dolandırıcılık tutarının %0,8'i). $10'un altındaki
      dolandırıcılıkların tamamı kaçıyor (57/57): beklenen kaybı inceleme ücretinden az.
      Akaryakıt, `misc_pos` ve `grocery_net` kategorilerinde dolandırıcılığın yarısı kaçıyor,
      çünkü bu kategorilerde dolandırıcılık küçük tutarlı (EDA §2).
    - **Gerçek kör nokta: pahalı ama "sakin" dolandırıcılık.** $200 ve üzeri 4 kaçak, kaçan
      tutarın ~%65'i. Üçünde tutar kategori medyanının 75-100, kart ortalamasının 8-14 katı,
      ama eşlik eden bir patlama yok (24 sa tutar düşük) ve olasılık ‰0-2. Model aşırı sapmayı
      tek başına yeterli saymıyor; simülatörün kalıbını (tutar bandı + gece + patlama) arıyor.
      Olası iyileştirme: aşırı sapmaya (ör. kategori medyanının 50 katı) kural tabanlı bir
      emniyet ağı. Yalnızca 3 vakaya dayanacağı için doğrulamada ayarlanmadı; gelecek iş.
    - **Patlamalar:** 90 patlamadan yalnızca 1'i tamamen kaçtı (2 işlem, $20). Patlamanın ilk
      işleminde kaçma oranı (%16) diğer sıralardan belirgin biçimde yüksek değil, ama ilk
      işlem kaçakları kaçan tutarın %40'ı.
    - **Yanlış alarmlar = büyük, gece, çevrim içi gerçek alışverişler.** 164 yanlış alarmın
      130'u $500 ve üzerinde (bu tutardaki gerçek işlemlerin %10-12'si alarm alıyor);
      çevrim içi alışveriş ve gece yoğun. Kartlarda yoğunlaşmıyor (149 kart, kart başına en
      fazla 2). Bunlar dolandırıcılık kalıbına benzeyen gerçek işlemler; özelliklerin doğal sınırı.
    - **Patlama sonrası:** Dolandırıcılıktan sonraki 72 saatte kart sahibinin gerçek
      işlemlerinde yanlış alarm oranı 10 kat yüksek (%1,25 / %0,12), ama sayıca küçük
      (7 alarm, %4). Gerçekte kart patlamada bloke edileceği için pratik etkisi daha da az.
    - **Adalet: model cinsiyeti kullanmadığı hâlde kadınlara ~1,7 kat fazla yanlış alarm
      veriyor** (işlem başına ‰1,53 / ‰0,91; en az bir yanlış alarm alan kart %21,7 / %10,9).
      Fark $500 üzeri gerçek alışverişlerde (‰140 / ‰71) ve büyük kısmı **kategori
      karışımından** geliyor: Kadınların büyük alışverişlerinin %69'u dolandırıcılığın yoğun
      olduğu mağaza/çevrim içi alışverişte, erkeklerinkinin %41'i yanlış alarmın çok düşük
      olduğu seyahatte. Kategori ve gece karışımı eşitlendiğinde fark 2 kattan ~1,3 kata
      iniyor. Kategori, cinsiyetin vekili gibi davranıyor: **Korunan özelliği modelden
      çıkarmak dolaylı farkı tek başına önlemiyor.** Veri sentetik; harcama kalıplarını
      simülatör üretiyor. README'de ve Faz 4'te izlenecek ölçüt olarak yer alacak. Yaşa göre
      recall benzer (%83-92); yanlış alarm oranı 65 yaş ve üzerinde daha yüksek (‰1,7 / ~‰1,1-1,3).
  - Yolda bulunan hata: `model.joblib`, 3.3'te `threshold.py` betik olarak çalıştırılırken
    kaydedildiği için kalibratör `__main__.Calibrator` adıyla yazılmıştı; başka bir yerden
    (ör. API) yüklenemezdi. Hata analizi dosyayı tesadüfen açabildi (sınıfı kendi ad alanına
    almıştı); ayrı bir betik açamayınca fark edildi. Kalibratör artık sade veri olarak
    kaydediliyor; proje sınıflarına atıf yapmadığını sınayan test eklendi, dosya başka bir
    dizinden yüklenerek doğrulandı.
  - Testler (`tests/test_error_analysis.py`, 7 test): sonuç etiketleri, patlama sırası ve satır
    sırasından bağımsızlığı, patlama sonrası pencere, kaçan dolandırıcılık dökümü, grup hata
    oranları, doğrudan standartlaştırmanın karışım etkisini gidermesi, yanlış alarmların
    kartlara dağılımı.
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
