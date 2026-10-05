# Test Sonuçları (Faz 3.5)

_Üreten: `python -m card_fraud_detection.models.final` · ilk değerlendirme 2026-09-29T22:30:26 (rapor 2026-09-29T22:33:01) · Test: 2020-06-21 → 2020-12-31, 555,719 işlem, 2,145 dolandırıcılık · Test bir kez değerlendirildi; protokol önceden yazıldı (docs/YOL_HARITASI.md §3.5)_

## Başarı ölçütü: GEÇTİ

Ölçüt: Test PR-AUC farkının (model − lojistik regresyon) %95 güven aralığı tamamen sıfırın üstünde. Kart düzeyinde bootstrap, 200 tekrar.

| PR-AUC farkı: model − lojistik regresyon | değer |
|---|---|
| fark | 0.4254 |
| alt_sinir_95 | 0.3862 |
| ust_sinir_95 | 0.4670 |
| tekrar | 200 |

## Modeller (eşikten bağımsız)

| model | PR-AUC | ROC-AUC | günde 25 alarm: recall | günde 25 alarm: tutar recall |
|---|---|---|---|---|
| LightGBM · alt örnekleme (final) | 0.9594 | 0.9991 | 0.9385 | 0.9693 |
| Referans: lojistik regresyon | 0.5340 | 0.9828 | 0.7058 | 0.8766 |
| Referans: yalnızca tutar | 0.1369 | 0.8332 | 0.4573 | 0.7909 |

## Karar kuralıyla sonuç

Hiç alarm vermemenin maliyeti: $1,133,325.

| karar kuralı: beklenen maliyet (önsel düzeltme) | değer |
|---|---|
| alarm | 2,522 |
| tp | 1,870 |
| fp | 652 |
| fn | 275 |
| precision | 0.7415 |
| recall | 0.8718 |
| tutar_recall | 0.9821 |
| kacan_tutar | $20,305 |
| maliyet | $45,525 |
| patlama | 218 |
| patlama_recall | 0.9954 |
| ilk_islemde_yakalanan | 0.7431 |
| kayip_tutar_orani | 0.0070 |

## Doğrulama ve test

| ölçü | doğrulama | test |
|---|---|---|
| PR-AUC | 0.9752 | 0.9594 |
| dolandırıcılık oranı | 0.0058 | 0.0039 |

## Aylara göre

| ay | işlem | dolandırıcılık | PR-AUC | precision | recall | tutar_recall | kacan_tutar | maliyet | patlama_recall |
|---|---|---|---|---|---|---|---|---|---|
| 2020-06 | 30,058 | 133 | 0.9697 | 0.7405 | 0.8797 | 0.9885 | $846 | $2,426 | 1.0000 |
| 2020-07 | 85,848 | 321 | 0.9370 | 0.7150 | 0.8598 | 0.9822 | $2,819 | $6,679 | 0.9714 |
| 2020-08 | 88,759 | 415 | 0.9692 | 0.7741 | 0.8916 | 0.9841 | $3,321 | $8,101 | 1.0000 |
| 2020-09 | 69,533 | 340 | 0.9711 | 0.7850 | 0.8912 | 0.9746 | $5,140 | $9,000 | 1.0000 |
| 2020-10 | 69,348 | 384 | 0.9703 | 0.8029 | 0.8594 | 0.9843 | $3,080 | $7,190 | 0.9744 |
| 2020-11 | 72,635 | 294 | 0.9652 | 0.7567 | 0.8673 | 0.9865 | $2,062 | $5,432 | 1.0000 |
| 2020-12 | 139,538 | 258 | 0.9285 | 0.5984 | 0.8488 | 0.9785 | $3,038 | $6,698 | 1.0000 |

## Cinsiyete göre hata oranları (izlenen ölçüt, Faz 3.4)

| cinsiyet | işlem | dolandırıcılık | recall | yanlış alarm oranı (‰) |
|---|---|---|---|---|
| F | 304886 | 1164 | 0.848 | 1.245 |
| M | 250833 | 981 | 0.900 | 1.097 |

