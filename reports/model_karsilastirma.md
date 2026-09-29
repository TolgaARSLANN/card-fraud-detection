# Model × Dengesizlik Stratejisi Karşılaştırması (Faz 3.1)

_Üreten: `python -m card_fraud_detection.models.train` · Eğitim: eğitim bölmesi · Ölçüm: doğrulama bölmesi (198,982 işlem, 1,163 dolandırıcılık) · Hiperparametreler sabit, ayar Faz 3.2'de_

## Eşikten bağımsız karşılaştırma (ana ölçüt)

Bütçe: Her gün en yüksek skorlu **25** işlem incelenir (ölçüm döneminde günde ortalama 14.2 dolandırıcılık var).

| model | PR-AUC | ROC-AUC | recall@p0.5 | bütçe: recall | bütçe: tutar recall | bütçe: precision | süre (sn) |
|---|---|---|---|---|---|---|---|
| XGBoost · yok + yaş, cinsiyet | 0.985 | 1.000 | 0.992 | 0.935 | 0.960 | 0.530 | 68.590 |
| XGBoost · yok | 0.976 | 1.000 | 0.986 | 0.931 | 0.957 | 0.528 | 65.170 |
| LightGBM · alt örnekleme | 0.975 | 1.000 | 0.986 | 0.931 | 0.965 | 0.528 | 7.491 |
| XGBoost · ağırlık | 0.975 | 1.000 | 0.985 | 0.933 | 0.958 | 0.529 | 65.339 |
| LightGBM · yok | 0.974 | 1.000 | 0.988 | 0.929 | 0.955 | 0.527 | 40.092 |
| XGBoost · alt örnekleme | 0.974 | 1.000 | 0.987 | 0.928 | 0.961 | 0.526 | 5.711 |
| LightGBM · ağırlık | 0.970 | 0.999 | 0.982 | 0.927 | 0.956 | 0.526 | 36.474 |
| XGBoost · SMOTE | 0.968 | 0.999 | 0.982 | 0.922 | 0.958 | 0.523 | 80.146 |
| LightGBM · SMOTE | 0.968 | 0.999 | 0.979 | 0.924 | 0.956 | 0.524 | 54.521 |
| Referans: lojistik regresyon | 0.625 | 0.987 | 0.753 | 0.723 | 0.868 | 0.410 | 50.090 |

## Maliyete göre seçilen eşikte (iyimser)

\* Eşik, maliyeti (kaçan tutar + alarm başına $10) en aza indirecek biçimde **ölçüm verisinin kendisinde** seçildi; sonuçlar iyimserdir. Nihai eşik Faz 3.3'te doğrulamada seçilip testte sabit tutulacak. Hiç alarm vermemenin maliyeti: $619,630.

| model | eşik*: alarm | eşik*: precision | eşik*: recall | eşik*: tutar recall | eşik*: kaçan tutar ($) | eşik*: maliyet ($) | eşik*: patlama recall | eşik*: ilk işlemde yakalanan |
|---|---|---|---|---|---|---|---|---|
| XGBoost · yok + yaş, cinsiyet | 1267 | 0.891 | 0.971 | 0.994 | 3919 | 16589 | 1.000 | 0.960 |
| XGBoost · yok | 1678 | 0.679 | 0.980 | 0.995 | 3118 | 19898 | 1.000 | 0.952 |
| LightGBM · alt örnekleme | 1435 | 0.788 | 0.972 | 0.993 | 4122 | 18472 | 1.000 | 0.944 |
| XGBoost · ağırlık | 1484 | 0.761 | 0.972 | 0.990 | 6291 | 21131 | 1.000 | 0.927 |
| LightGBM · yok | 1722 | 0.660 | 0.978 | 0.994 | 3802 | 21022 | 1.000 | 0.944 |
| XGBoost · alt örnekleme | 1443 | 0.782 | 0.970 | 0.994 | 3973 | 18403 | 1.000 | 0.944 |
| LightGBM · ağırlık | 1615 | 0.698 | 0.969 | 0.988 | 7141 | 23291 | 1.000 | 0.919 |
| XGBoost · SMOTE | 1432 | 0.781 | 0.961 | 0.987 | 7834 | 22154 | 1.000 | 0.911 |
| LightGBM · SMOTE | 1574 | 0.712 | 0.964 | 0.986 | 8893 | 24633 | 1.000 | 0.911 |
| Referans: lojistik regresyon | 3120 | 0.320 | 0.859 | 0.950 | 30796 | 61996 | 0.992 | 0.532 |

## Tohum kontrolü

En iyi iki kombinasyon 3 farklı rastgele tohumla yeniden eğitildi.

| model (3 tohum) | PR-AUC ortalama | std | en düşük | en yüksek |
|---|---|---|---|---|
| XGBoost · yok | 0.9766 | 0.0008 | 0.9759 | 0.9774 |
| LightGBM · alt örnekleme | 0.9749 | 0.0016 | 0.9731 | 0.9763 |

## Demografi

`XGBoost · yok + yaş, cinsiyet` satırı, en iyi kombinasyonun yaş ve cinsiyet eklenerek eğitilmiş hâlidir.

