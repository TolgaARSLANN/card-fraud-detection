# Veri Kalite Raporu

_Oluşturulma: 2026-09-27 · Kaynak: `data/raw/{train,test}.parquet` (Kaggle, Sparkov) · Üreten: `python -m card_fraud_detection.data.quality`_

## 1. Kapsam ve sınıf oranı

| dosya | başlangıç | bitiş | işlem | dolandırıcılık | oran (%) | kart | satıcı | kategori |
|---|---|---|---|---|---|---|---|---|
| train | 2019-01-01 00:00:18 | 2020-06-21 12:13:37 | 1296675 | 7506 | 0.58 | 983 | 693 | 14 |
| test | 2020-06-21 12:14:25 | 2020-12-31 23:59:34 | 555719 | 2145 | 0.39 | 924 | 693 | 14 |

Eğitim dosyasının sonu ile test dosyasının başı arasındaki boşluk: 0 days 00:00:48.

## 2. Eksik değer

Hiçbir sütunda boş değer yok.

## 3. Tekrar eden kayıtlar

| kontrol | train | test | iki dosya birlikte |
|---|---|---|---|
| tam satır tekrarı | 0 | 0 | 0 |
| trans_num tekrarı | 0 | 0 | 0 |
| aynı kart + zaman + tutar | 0 | 0 | 0 |
| aynı kart + zaman | 20 | 24 | 44 |

## 4. Değer aralıkları

| kontrol | train | test |
|---|---|---|
| tutar ≤ 0 | 0.00 | 0.00 |
| tutar min | 1.00 | 1.00 |
| tutar medyan | 47.52 | 47.29 |
| tutar maks | 28948.90 | 22768.11 |
| yaş min | 13.92 | 15.39 |
| yaş maks | 95.64 | 96.17 |
| geçersiz koordinat | 0.00 | 0.00 |
| 'fraud_' önekli satıcı (%) | 100.00 | 100.00 |

## 5. Zaman damgası tutarlılığı

`trans_date_trans_time` ile `unix_time` arasındaki farkın dağılımı (en sık 5 değer):

| tarih − unix_time | işlem |
|---|---|
| 2557 gün | 928083 |
| 2556 gün | 924311 |

## 6. Kart bazında müşteri alanlarının tutarlılığı

Aynı kartın her işleminde aynı olması beklenen alanlarda birden fazla değer taşıyan kart sayısı.

| alan (tutarsız kart sayısı) | train | test | iki dosya birlikte |
|---|---|---|---|
| first | 0 | 0 | 0 |
| last | 0 | 0 | 0 |
| gender | 0 | 0 | 0 |
| street | 0 | 0 | 0 |
| city | 0 | 0 | 0 |
| state | 0 | 0 | 0 |
| zip | 0 | 0 | 0 |
| lat | 0 | 0 | 0 |
| long | 0 | 0 | 0 |
| city_pop | 0 | 0 | 0 |
| job | 0 | 0 | 0 |
| dob | 0 | 0 | 0 |

## 7. Kart başına işlem sayısı

| dosya (kart başına işlem) | mean | std | min | 5% | 50% | 95% | max |
|---|---|---|---|---|---|---|---|
| train | 1319.1 | 812.2 | 7.0 | 10.1 | 1054.0 | 2921.6 | 3123.0 |
| test | 601.4 | 329.2 | 6.0 | 208.0 | 634.5 | 1267.8 | 1474.0 |

## 8. Dolandırıcılık patlamaları

Bir kartta dolandırıcılığın kısa bir dönemde toplanıp toplanmadığı. Kartlar dolandırıcılıktan sonra kapanmıyorsa geçmiş etiketler sızıntı riski taşır.

| ölçü | train | test | iki dosya birlikte |
|---|---|---|---|
| dolandırıcılık görülen kart | 762.00 | 218.00 | 976.00 |
| kart oranı (%) | 77.52 | 23.59 | 97.70 |
| kart başına dolandırıcılık (medyan) | 10.00 | 10.00 | 10.00 |
| kart başına dolandırıcılık (maks) | 19.00 | 19.00 | 19.00 |
| ilk→son süre, gün (medyan) | 1.88 | 1.89 | 1.89 |
| ilk→son süre, gün (%95) | 1.98 | 1.98 | 1.98 |
| sonrasında normal işlem olan kart (%) | 89.50 | 92.66 | 90.68 |

## 9. Aylık işlem hacmi ve dolandırıcılık oranı

| ay | işlem | dolandırıcılık (%) |
|---|---|---|
| 2019-01 | 52525 | 0.96 |
| 2019-02 | 49866 | 1.04 |
| 2019-03 | 70939 | 0.70 |
| 2019-04 | 68078 | 0.55 |
| 2019-05 | 72532 | 0.56 |
| 2019-06 | 86064 | 0.41 |
| 2019-07 | 86596 | 0.38 |
| 2019-08 | 87359 | 0.44 |
| 2019-09 | 70652 | 0.59 |
| 2019-10 | 68758 | 0.66 |
| 2019-11 | 70421 | 0.55 |
| 2019-12 | 141060 | 0.42 |
| 2020-01 | 52202 | 0.66 |
| 2020-02 | 47791 | 0.70 |
| 2020-03 | 72850 | 0.61 |
| 2020-04 | 66892 | 0.45 |
| 2020-05 | 74343 | 0.71 |
| 2020-06 | 87805 | 0.53 |
| 2020-07 | 85848 | 0.37 |
| 2020-08 | 88759 | 0.47 |
| 2020-09 | 69533 | 0.49 |
| 2020-10 | 69348 | 0.55 |
| 2020-11 | 72635 | 0.40 |
| 2020-12 | 139538 | 0.18 |

## 10. Eğitim / test örtüşmesi

| alan | eğitimde | testte | ortak | yalnızca testte | testin eğitimde görülen oranı (%) |
|---|---|---|---|---|---|
| cc_num | 983 | 924 | 908 | 16 | 98.3 |
| merchant | 693 | 693 | 693 | 0 | 100.0 |
| category | 14 | 14 | 14 | 0 | 100.0 |

## 11. Sütunların farklı değer sayısı

| sütun | farklı değer |
|---|---|
| trans_date_trans_time | 1819551 |
| cc_num | 999 |
| merchant | 693 |
| category | 14 |
| amt | 60616 |
| first | 355 |
| last | 486 |
| gender | 2 |
| street | 999 |
| city | 906 |
| state | 51 |
| zip | 985 |
| lat | 983 |
| long | 983 |
| city_pop | 891 |
| job | 497 |
| dob | 984 |
| trans_num | 1852394 |
| unix_time | 1819583 |
| merch_lat | 1754157 |
| merch_long | 1809753 |
| is_fraud | 2 |

