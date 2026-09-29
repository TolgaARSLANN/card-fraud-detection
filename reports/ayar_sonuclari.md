# Hiperparametre Ayarı (Faz 3.2)

_Üreten: `python -m card_fraud_detection.models.tune` · Model: LightGBM · alt örnekleme · 60 deneme, 14 dk · Hedef: doğrulamada PR-AUC · İlk deneme varsayılan parametrelerdir_

## Karar: varsayılanda kalındı

- Tohum ortalamasında kazanç +0.0021; tohum oynaklığı (iki std toplamı) 0.0028 → geçmedi.
- Her ayda ayarlanmış model daha iyi mi: evet → geçti.

## Tohum kontrolü

| parametreler | PR-AUC ortalama | std | tohum 42 | tohum 7 | tohum 2024 |
|---|---|---|---|---|---|
| varsayılan | 0.9749 | 0.0016 | 0.9752 | 0.9763 | 0.9731 |
| ayarlanmış | 0.9769 | 0.0012 | 0.9781 | 0.9768 | 0.9758 |

## Aylara göre PR-AUC (tohum ortalamalı skor)

| ay | varsayılan | ayarlanmış |
|---|---|---|
| 2020-04 | 0.9707 | 0.9738 |
| 2020-05 | 0.9868 | 0.9885 |
| 2020-06 | 0.9672 | 0.9718 |

## En iyi 10 deneme

Değerler doğrulama verisinde seçildiği için iyimserdir.

| deneme | value | colsample_bytree | learning_rate | min_child_samples | n_estimators | num_leaves | ratio | reg_alpha | reg_lambda | subsample | duration |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 52 | 0.9781 | 0.7278 | 0.0849 | 14 | 700 | 20 | 0.0405 | 0.0011 | 0.0012 | 0.8382 | 11.1000 |
| 36 | 0.9779 | 0.7851 | 0.0713 | 31 | 700 | 26 | 0.0376 | 0.0034 | 0.0016 | 0.8616 | 12.1000 |
| 37 | 0.9779 | 0.7646 | 0.0909 | 13 | 700 | 15 | 0.0389 | 0.0055 | 0.0014 | 0.8392 | 21.0000 |
| 39 | 0.9777 | 0.7522 | 0.0424 | 31 | 800 | 20 | 0.0399 | 0.0076 | 0.0077 | 0.9124 | 23.0000 |
| 30 | 0.9777 | 0.5745 | 0.0847 | 25 | 600 | 26 | 0.0406 | 0.0171 | 0.0045 | 0.8222 | 14.0000 |
| 28 | 0.9776 | 0.7044 | 0.0598 | 11 | 500 | 22 | 0.0304 | 0.0050 | 0.0635 | 0.7310 | 8.5000 |
| 27 | 0.9776 | 0.6815 | 0.0770 | 16 | 700 | 30 | 0.0358 | 0.0037 | 0.0015 | 0.7955 | 13.7000 |
| 32 | 0.9775 | 0.7508 | 0.0926 | 26 | 600 | 21 | 0.0301 | 0.0029 | 0.0043 | 0.8240 | 12.1000 |
| 35 | 0.9775 | 0.6427 | 0.0750 | 16 | 1000 | 25 | 0.0412 | 0.0060 | 0.0012 | 0.7666 | 18.9000 |
| 59 | 0.9774 | 0.7512 | 0.0655 | 17 | 900 | 22 | 0.0373 | 0.0016 | 0.0037 | 0.7720 | 22.6000 |

## Parametre önemi (fANOVA)

| parametre | önem |
|---|---|
| ratio | 0.500 |
| n_estimators | 0.106 |
| subsample | 0.102 |
| min_child_samples | 0.095 |
| num_leaves | 0.054 |
| reg_lambda | 0.049 |
| reg_alpha | 0.045 |
| colsample_bytree | 0.029 |
| learning_rate | 0.020 |

